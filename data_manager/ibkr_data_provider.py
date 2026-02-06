"""
IBKR Data Provider

Fetches historical market data from Interactive Brokers TWS/Gateway.
"""

import os
import time
import threading
import collections
import pandas as pd
from typing import Optional, Callable, Dict, Any

from data_manager.data_provider import BaseDataProvider, Asset

# IBKR-specific imports
from ib_api_client.ib_api_client import IBApiClient
from ibapi.contract import Contract
import request_historical_data.request_historical_data as rhd
import request_historical_data.callback as rhd_callback


class IBKRDataProvider(BaseDataProvider):
    """
    Data provider for Interactive Brokers.

    Requires TWS or IB Gateway to be running with API enabled.
    """

    # IBKR-specific interval limits
    BAR_SIZE_INTERVAL_LIMITS = {
        "1 min": "1 M",
        "5 mins": "1 Y",
        "15 mins": "1 Y",
        "1 hour": "1 Y",
        "4 hours": "1 Y",
        "1 day": "10 Y",
        "1 week": "10 Y",
    }

    def __init__(
        self,
        data_base_dir: str = "data",
        host: str = "127.0.0.1",
        port: int = 7497,  # 7497 for TWS paper, 7496 for TWS live, 4001/4002 for Gateway
        client_id: int = None
    ):
        super().__init__(data_base_dir)
        self.host = host
        self.port = port
        self._client_id_counter = client_id or 1000

        self.client: Optional[IBApiClient] = None
        self.callbackFnMap: Dict = None
        self.contextMap: Dict = None
        self._api_thread: Optional[threading.Thread] = None

        # Download tracking
        self._pending_downloads = set()
        self._download_lock = threading.Lock()
        self._all_downloads_complete = threading.Event()
        self._all_downloads_complete.set()  # Start as complete (no pending)

    def connect(self) -> bool:
        """Connect to IBKR TWS/Gateway."""
        if self.connected and self.client:
            return True

        try:
            self.callbackFnMap = collections.defaultdict(lambda: collections.defaultdict(lambda: None))
            self.contextMap = collections.defaultdict(lambda: collections.defaultdict(lambda: None))
            self.client = IBApiClient(self.callbackFnMap, self.contextMap)

            # Generate unique client ID
            client_id = self._client_id_counter
            self._client_id_counter += 1
            if self._client_id_counter > 9999:
                self._client_id_counter = 1000

            self.client.connect(self.host, self.port, client_id)

            def run_loop():
                try:
                    self.client.run()
                except Exception:
                    pass

            self._api_thread = threading.Thread(target=run_loop, daemon=True)
            self._api_thread.start()

            # Wait for connection
            for _ in range(60):
                if isinstance(getattr(self.client, 'nextorderId', None), int):
                    self.connected = True
                    print(f"✓ Connected to IBKR (client_id: {client_id})")
                    return True
                time.sleep(1)

            print("✗ Could not connect to IBKR within 60s")
            return False

        except Exception as e:
            print(f"✗ Failed to connect to IBKR: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR."""
        if self.client:
            try:
                self.client.disconnect()
                time.sleep(0.1)
            except Exception:
                pass
            self.client = None
        self.connected = False

    def _asset_to_contract(self, asset: Asset) -> Contract:
        """Convert Asset to IBKR Contract."""
        contract = Contract()
        contract.symbol = asset.symbol
        contract.currency = asset.currency
        contract.secType = asset.sec_type
        contract.exchange = asset.exchange or "IDEALPRO"
        return contract

    def fetch_historical_data(
        self,
        asset: Asset,
        bar_size: str,
        interval: str,
        callback: Optional[Callable[[pd.DataFrame, Asset, str], None]] = None
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data from IBKR.

        Args:
            asset: Asset to fetch data for
            bar_size: Bar size (e.g., "1 hour", "5 mins")
            interval: Time interval (e.g., "6 M", "1 Y")
            callback: Optional callback for async operation

        Returns:
            DataFrame with OHLCV data (sync mode) or None (async mode with callback)
        """
        if not self.connected:
            raise RuntimeError("Not connected to IBKR. Call connect() first.")

        contract = self._asset_to_contract(asset)
        csv_path = self.get_csv_path(asset, bar_size, interval)

        # Create folder
        folder = self.get_asset_folder(asset)
        os.makedirs(folder, exist_ok=True)

        # Get request ID
        req_id = self.client.nextorderId
        self.client.nextorderId += 1

        candlestick_data = []
        download_complete = threading.Event()
        result_df = [None]  # Use list to store result from callback

        rhd_object = rhd.RequestHistoricalData(
            self.client, self.callbackFnMap, self.contextMap
        )
        rhd_cb = rhd_callback.Callback(candlestick_data)

        # Store context
        self.contextMap[req_id]["contract"] = contract
        self.contextMap[req_id]["csv_path"] = csv_path
        self.contextMap[req_id]["bar_size"] = bar_size
        self.contextMap[req_id]["req_id"] = req_id

        # Track download
        with self._download_lock:
            self._pending_downloads.add(req_id)
            self._all_downloads_complete.clear()

        def save_callback(df, ti, file_to_save, c):
            """Callback when data is received."""
            try:
                if df is not None and len(df) > 0:
                    df.to_csv(file_to_save, index=False)
                    print(f"  ✓ Saved {len(df)} bars to {file_to_save}")
                    result_df[0] = df

                    if callback:
                        callback(df, asset, file_to_save)
                else:
                    print(f"  ⚠ No data received for {asset.pair} ({bar_size})")
            finally:
                with self._download_lock:
                    self._pending_downloads.discard(req_id)
                    if len(self._pending_downloads) == 0:
                        self._all_downloads_complete.set()
                download_complete.set()

        # Request data
        rhd_object.requestHistoricalData(
            reqId=req_id,
            contract=contract,
            duration=interval,
            barSizeSetting=bar_size,
            callback=save_callback,
            fileToSave=csv_path,
        )

        # If no callback provided, wait for completion
        if callback is None:
            download_complete.wait(timeout=120)  # 2 minute timeout
            return result_df[0]

        return None

    def wait_for_all_downloads(self, timeout: float = None):
        """Wait for all pending downloads to complete."""
        self._all_downloads_complete.wait(timeout=timeout)

    @property
    def pending_download_count(self) -> int:
        """Get number of pending downloads."""
        with self._download_lock:
            return len(self._pending_downloads)
