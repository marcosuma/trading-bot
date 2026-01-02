"""
Data Manager - Handles real-time data collection, bar aggregation, and indicator calculation.
"""
import logging
from typing import Dict, Callable, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import numpy as np

from live_trading.models.market_data import MarketData
from live_trading.models.trading_operation import TradingOperation
from live_trading.config import config

logger = logging.getLogger(__name__)


class BarAggregator:
    """Aggregates ticks into bars"""

    def __init__(self, bar_size: str):
        self.bar_size = bar_size
        self.current_bar: Optional[Dict] = None
        self.bar_start_time: Optional[datetime] = None
        self._parse_bar_size()

    def _parse_bar_size(self):
        """Parse bar size string to timedelta"""
        # Parse strings like "1 hour", "15 mins", "1 day"
        parts = self.bar_size.split()
        if len(parts) != 2:
            raise ValueError(f"Invalid bar size format: {self.bar_size}")

        value = int(parts[0])
        unit = parts[1].lower()

        if unit in ["min", "mins", "minute", "minutes"]:
            self.bar_duration = timedelta(minutes=value)
        elif unit in ["hour", "hours"]:
            self.bar_duration = timedelta(hours=value)
        elif unit in ["day", "days"]:
            self.bar_duration = timedelta(days=value)
        elif unit in ["week", "weeks"]:
            self.bar_duration = timedelta(weeks=value)
        else:
            raise ValueError(f"Unknown bar size unit: {unit}")

    def add_tick(self, price: float, size: float, timestamp: datetime) -> Optional[Dict]:
        """
        Add a tick and return completed bar if bar is complete.

        Returns:
            Completed bar dict or None if bar not yet complete
        """
        # Determine bar start time (round down to bar boundary)
        bar_start = self._get_bar_start_time(timestamp)

        # If new bar started, finalize previous bar
        if self.current_bar is not None and bar_start != self.bar_start_time:
            completed_bar = self.current_bar.copy()
            completed_bar["timestamp"] = self.bar_start_time
            completed_bar["close"] = self.current_bar["close"]  # Last price
            completed_bar["volume"] = self.current_bar["volume"]

            # Start new bar
            self._start_new_bar(bar_start, price, size)
            return completed_bar

        # Start first bar if needed
        if self.current_bar is None:
            self._start_new_bar(bar_start, price, size)
            return None

        # Update current bar
        self.current_bar["high"] = max(self.current_bar["high"], price)
        self.current_bar["low"] = min(self.current_bar["low"], price)
        self.current_bar["close"] = price
        self.current_bar["volume"] += size

        return None

    def _get_bar_start_time(self, timestamp: datetime) -> datetime:
        """Get the start time of the bar containing this timestamp"""
        if self.bar_duration >= timedelta(days=1):
            # For daily/weekly bars, use date boundaries
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # For intraday bars, round down to bar boundary
            total_seconds = int(self.bar_duration.total_seconds())
            timestamp_seconds = int(timestamp.timestamp())
            bar_start_seconds = (timestamp_seconds // total_seconds) * total_seconds
            return datetime.fromtimestamp(bar_start_seconds)

    def _start_new_bar(self, bar_start: datetime, first_price: float, first_size: float):
        """Start a new bar"""
        self.bar_start_time = bar_start
        self.current_bar = {
            "open": first_price,
            "high": first_price,
            "low": first_price,
            "close": first_price,
            "volume": first_size
        }


class DataManager:
    """Manages real-time data collection and bar aggregation"""

    def __init__(self, broker_adapter, indicator_calculator=None):
        self.broker = broker_adapter
        self.indicator_calculator = indicator_calculator

        # Per-operation data buffers: operation_id -> bar_size -> list of bars
        self.data_buffers: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))

        # Bar aggregators: operation_id -> bar_size -> BarAggregator
        self.aggregators: Dict[str, Dict[str, BarAggregator]] = defaultdict(dict)

        # Callbacks: operation_id -> bar_size -> callback
        self.bar_callbacks: Dict[str, Dict[str, Callable]] = defaultdict(dict)

    def register_operation(
        self,
        operation_id: str,
        bar_sizes: list[str],
        callback: Optional[Callable] = None
    ):
        """Register a trading operation for data collection"""
        for bar_size in bar_sizes:
            self.aggregators[operation_id][bar_size] = BarAggregator(bar_size)
            if callback:
                self.bar_callbacks[operation_id][bar_size] = callback

        logger.info(f"Registered operation {operation_id} for bar sizes: {bar_sizes}")

    def unregister_operation(self, operation_id: str):
        """Unregister a trading operation"""
        if operation_id in self.aggregators:
            del self.aggregators[operation_id]
        if operation_id in self.data_buffers:
            del self.data_buffers[operation_id]
        if operation_id in self.bar_callbacks:
            del self.bar_callbacks[operation_id]
        logger.info(f"Unregistered operation {operation_id}")

    async def handle_tick(
        self,
        operation_id: str,
        asset: str,
        price: float,
        size: float,
        timestamp: datetime
    ):
        """Handle incoming tick data"""
        # Process tick through all bar aggregators for this operation
        for bar_size, aggregator in self.aggregators[operation_id].items():
            completed_bar = aggregator.add_tick(price, size, timestamp)

            if completed_bar:
                # Bar is complete, process it
                await self._process_completed_bar(operation_id, asset, bar_size, completed_bar)

    async def _process_completed_bar(
        self,
        operation_id: str,
        asset: str,
        bar_size: str,
        bar_data: Dict
    ):
        """Process a completed bar"""
        # Add to buffer
        self.data_buffers[operation_id][bar_size].append(bar_data)

        # Apply data retention limit
        operation = await TradingOperation.get(operation_id)
        retention_bars = operation.data_retention_bars if operation else config.DEFAULT_DATA_RETENTION_BARS

        if len(self.data_buffers[operation_id][bar_size]) > retention_bars:
            # Remove oldest bars
            excess = len(self.data_buffers[operation_id][bar_size]) - retention_bars
            self.data_buffers[operation_id][bar_size] = self.data_buffers[operation_id][bar_size][excess:]

        # Calculate indicators if calculator available
        indicators = {}
        if self.indicator_calculator:
            df = self._buffer_to_dataframe(operation_id, bar_size)
            if len(df) > 0:
                try:
                    # TechnicalIndicators expects a DataFrame and returns it with indicators added
                    df_with_indicators = self.indicator_calculator.execute(df)
                    # Extract indicators as dict (or use the DataFrame columns)
                    # For now, store the indicator values from the last row
                    if len(df_with_indicators) > 0:
                        last_row = df_with_indicators.iloc[-1]
                        # Extract indicator columns (exclude OHLCV and timestamp)
                        indicator_cols = [col for col in df_with_indicators.columns
                                         if col not in ['open', 'high', 'low', 'close', 'volume', 'timestamp']]
                        indicators = {col: last_row[col] for col in indicator_cols if pd.notna(last_row.get(col))}
                except Exception as e:
                    logger.error(f"Error calculating indicators: {e}")

        # Store in database
        try:
            from bson import ObjectId
            market_data = MarketData(
                operation_id=ObjectId(operation_id),
                bar_size=bar_size,
                timestamp=bar_data["timestamp"],
                open=bar_data["open"],
                high=bar_data["high"],
                low=bar_data["low"],
                close=bar_data["close"],
                volume=bar_data.get("volume", 0.0),
                indicators=indicators
            )
            await market_data.insert()
            logger.debug(f"Stored bar for operation {operation_id}, bar_size {bar_size}")
        except Exception as e:
            logger.error(f"Error storing bar: {e}")

        # Notify callback
        if operation_id in self.bar_callbacks and bar_size in self.bar_callbacks[operation_id]:
            callback = self.bar_callbacks[operation_id][bar_size]
            callback(bar_data, indicators)

    def _buffer_to_dataframe(self, operation_id: str, bar_size: str) -> pd.DataFrame:
        """Convert buffer to DataFrame for indicator calculation"""
        bars = self.data_buffers[operation_id][bar_size]
        if not bars:
            return pd.DataFrame()

        df = pd.DataFrame(bars)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
        return df

    async def _store_bar(
        self,
        operation_id: str,
        bar_size: str,
        bar_data: Dict,
        indicators: Dict
    ):
        """Store bar in database"""
        market_data = MarketData(
            operation_id=operation_id,
            bar_size=bar_size,
            timestamp=bar_data["timestamp"],
            open=bar_data["open"],
            high=bar_data["high"],
            low=bar_data["low"],
            close=bar_data["close"],
            volume=bar_data.get("volume", 0.0),
            indicators=indicators
        )
        await market_data.insert()

    async def get_latest_bars(
        self,
        operation_id: str,
        bar_size: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, list]:
        """Get latest bars from buffer"""
        if bar_size:
            bars = self.data_buffers[operation_id].get(bar_size, [])
            return {bar_size: bars[-limit:]}
        else:
            return {
                size: bars[-limit:]
                for size, bars in self.data_buffers[operation_id].items()
            }

    async def get_dataframe(
        self,
        operation_id: str,
        bar_size: str
    ) -> pd.DataFrame:
        """Get DataFrame for a specific bar size"""
        return self._buffer_to_dataframe(operation_id, bar_size)

