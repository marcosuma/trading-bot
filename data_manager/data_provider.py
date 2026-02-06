"""
Data Provider Abstraction Layer

Provides a unified interface for fetching historical market data from different sources.
This allows cli.py and data_downloader to work with multiple data providers:
- IBKR (Interactive Brokers)
- cTrader
- Local CSV files (for backtesting without live broker connection)
"""

import os
import pandas as pd
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum


class DataProviderType(Enum):
    """Supported data provider types."""
    IBKR = "ibkr"
    CTRADER = "ctrader"
    LOCAL = "local"  # Read from local CSV files only


@dataclass
class Asset:
    """Universal asset representation (broker-agnostic)."""
    symbol: str  # Base currency (e.g., "EUR")
    currency: str  # Quote currency (e.g., "USD")
    sec_type: str = "CASH"  # Security type (CASH for forex)
    exchange: str = ""  # Exchange (broker-specific)

    @property
    def pair(self) -> str:
        """Get forex pair string (e.g., 'EUR-USD')."""
        return f"{self.symbol}-{self.currency}"

    def __str__(self) -> str:
        return self.pair


@dataclass
class HistoricalBar:
    """Single OHLCV bar."""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class BaseDataProvider(ABC):
    """
    Abstract base class for data providers.

    All data providers must implement these methods to be compatible
    with cli.py and data_downloader.
    """

    # Default bar sizes supported by most providers
    DEFAULT_BAR_SIZES = ["1 week", "1 day", "4 hours", "1 hour", "15 mins", "5 mins"]
    DEFAULT_INTERVAL = "6 M"  # 6 months of historical data

    # Maximum interval per bar size (provider-specific, override in subclasses)
    BAR_SIZE_INTERVAL_LIMITS = {
        "1 min": "1 M",
        "5 mins": "1 Y",
        "15 mins": "1 Y",
        "1 hour": "1 Y",
        "4 hours": "1 Y",
        "1 day": "10 Y",
        "1 week": "10 Y",
    }

    def __init__(self, data_base_dir: str = "data"):
        self.data_base_dir = data_base_dir
        self.connected = False

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the data provider.

        Returns:
            True if connection successful, False otherwise.
        """
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from the data provider."""
        pass

    @abstractmethod
    def fetch_historical_data(
        self,
        asset: Asset,
        bar_size: str,
        interval: str,
        callback: Optional[Callable[[pd.DataFrame, Asset, str], None]] = None
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for an asset.

        Args:
            asset: Asset to fetch data for
            bar_size: Bar size (e.g., "1 hour", "5 mins")
            interval: Time interval (e.g., "6 M", "1 Y")
            callback: Optional callback for async operation

        Returns:
            DataFrame with OHLCV data, or None if async (data via callback)
        """
        pass

    def get_asset_folder(self, asset: Asset) -> str:
        """Get folder path for an asset's data."""
        return os.path.join(self.data_base_dir, asset.pair)

    def get_csv_path(self, asset: Asset, bar_size: str, interval: str) -> str:
        """Get CSV file path for an asset's data."""
        folder = self.get_asset_folder(asset)
        filename = f"data-{asset.symbol}-{asset.sec_type}-{asset.exchange or 'IDEALPRO'}-{asset.currency}-{interval}-{bar_size}.csv"
        return os.path.join(folder, filename)

    def get_interval_for_bar_size(self, bar_size: str, requested_interval: str = None) -> str:
        """Get appropriate interval for a bar size based on provider limitations."""
        if requested_interval:
            return requested_interval
        return self.BAR_SIZE_INTERVAL_LIMITS.get(bar_size, self.DEFAULT_INTERVAL)

    def data_exists(self, asset: Asset, bar_size: str, interval: str) -> bool:
        """Check if data file already exists."""
        csv_path = self.get_csv_path(asset, bar_size, interval)
        return os.path.exists(csv_path)

    def save_data(self, df: pd.DataFrame, asset: Asset, bar_size: str, interval: str) -> str:
        """
        Save DataFrame to CSV file.

        Returns:
            Path to saved file.
        """
        folder = self.get_asset_folder(asset)
        os.makedirs(folder, exist_ok=True)
        csv_path = self.get_csv_path(asset, bar_size, interval)
        df.to_csv(csv_path, index=False)
        return csv_path

    def load_data(self, asset: Asset, bar_size: str, interval: str) -> Optional[pd.DataFrame]:
        """Load data from CSV file if it exists."""
        csv_path = self.get_csv_path(asset, bar_size, interval)
        if os.path.exists(csv_path):
            return pd.read_csv(csv_path)
        return None


class LocalDataProvider(BaseDataProvider):
    """
    Data provider that reads from local CSV files only.

    Use this for backtesting when you already have downloaded data
    and don't need a live broker connection.
    """

    def __init__(self, data_base_dir: str = "data"):
        super().__init__(data_base_dir)

    def connect(self) -> bool:
        """Local provider is always 'connected'."""
        self.connected = True
        return True

    def disconnect(self):
        """No-op for local provider."""
        self.connected = False

    def fetch_historical_data(
        self,
        asset: Asset,
        bar_size: str,
        interval: str,
        callback: Optional[Callable[[pd.DataFrame, Asset, str], None]] = None
    ) -> Optional[pd.DataFrame]:
        """
        Fetch data from local CSV files.

        For local provider, this just loads existing CSV files.
        """
        df = self.load_data(asset, bar_size, interval)

        if df is None:
            print(f"⚠ No local data found for {asset.pair} ({bar_size}, {interval})")
            print(f"  Expected path: {self.get_csv_path(asset, bar_size, interval)}")
            return None

        if callback:
            callback(df, asset, self.get_csv_path(asset, bar_size, interval))

        return df

    def list_available_data(self) -> Dict[str, List[str]]:
        """
        List all available data files.

        Returns:
            Dictionary mapping asset pairs to list of available bar sizes.
        """
        available = {}

        if not os.path.exists(self.data_base_dir):
            return available

        for pair_folder in os.listdir(self.data_base_dir):
            pair_path = os.path.join(self.data_base_dir, pair_folder)
            if not os.path.isdir(pair_path):
                continue

            bar_sizes = []
            for filename in os.listdir(pair_path):
                if filename.endswith('.csv') and filename.startswith('data-'):
                    # Extract bar size from filename
                    # Format: data-{symbol}-{secType}-{exchange}-{currency}-{interval}-{bar_size}.csv
                    parts = filename[:-4].split('-')  # Remove .csv
                    if len(parts) >= 7:
                        bar_size = '-'.join(parts[6:])  # Bar size might have spaces replaced
                        bar_sizes.append(bar_size.replace('_', ' '))

            if bar_sizes:
                available[pair_folder] = list(set(bar_sizes))

        return available


def create_data_provider(
    provider_type: DataProviderType,
    data_base_dir: str = "data",
    **kwargs
) -> BaseDataProvider:
    """
    Factory function to create a data provider.

    Args:
        provider_type: Type of provider to create
        data_base_dir: Base directory for data storage
        **kwargs: Provider-specific arguments

    Returns:
        Configured data provider instance.
    """
    if provider_type == DataProviderType.LOCAL:
        return LocalDataProvider(data_base_dir)

    elif provider_type == DataProviderType.IBKR:
        from data_manager.ibkr_data_provider import IBKRDataProvider
        return IBKRDataProvider(data_base_dir, **kwargs)

    elif provider_type == DataProviderType.CTRADER:
        from data_manager.ctrader_data_provider import CTraderDataProvider
        return CTraderDataProvider(data_base_dir, **kwargs)

    else:
        raise ValueError(f"Unknown data provider type: {provider_type}")


def get_provider_type_from_string(provider_str: str) -> DataProviderType:
    """Convert string to DataProviderType enum."""
    provider_str = provider_str.lower().strip()

    if provider_str in ('ibkr', 'ib', 'interactive_brokers', 'interactivebrokers'):
        return DataProviderType.IBKR
    elif provider_str in ('ctrader', 'ct', 'spotware'):
        return DataProviderType.CTRADER
    elif provider_str in ('local', 'file', 'csv', 'offline'):
        return DataProviderType.LOCAL
    else:
        raise ValueError(f"Unknown data provider: {provider_str}. Valid options: ibkr, ctrader, local")
