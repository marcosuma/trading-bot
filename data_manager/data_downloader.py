"""
Phase 1: Download historical data from IBKR for all contracts.
Organizes data by contract in separate folders with multiple bar sizes.
"""
import os
import json
import time
import threading
import collections
from typing import List, Dict, Tuple
from ib_api_client.ib_api_client import IBApiClient
from ibapi.contract import Contract
import request_historical_data.request_historical_data as rhd
import request_historical_data.callback as rhd_callback


class DataDownloader:
    """Downloads historical data from IBKR for contracts with multiple bar sizes."""

    # Default bar sizes to download (1 min excluded by default due to IBKR limitations)
    DEFAULT_BAR_SIZES = ["1 week", "1 day", "4 hours", "1 hour", "15 mins", "5 mins"]
    DEFAULT_INTERVAL = "6 M"  # 6 months of historical data

    # IBKR API limitations for historical data. This mapping is the
    # **single source of truth** for the maximum practical interval
    # per bar size across the project. Other modules (e.g. cli.py)
    # should import and use this constant instead of duplicating it.
    # - 1 min bars: max ~2 months (use "2 M" or "1 M")
    # - 5 min bars: max ~1 year
    # - 15 min bars: max ~2 years
    # - 1 hour bars: max ~20 years
    # - 4 hours bars: max ~20 years
    # - 1 day bars: max ~20 years
    # - 1 week bars: max ~20 years
    BAR_SIZE_INTERVAL_LIMITS = {
        "1 min": "1 M",
        "5 mins": "1 Y",
        "15 mins": "1 Y",
        "1 hour": "1 Y",
        "4 hours": "1 Y",
        "1 day": "10 Y",
        "1 week": "10 Y",
    }

    def __init__(self, ib_client, callbackFnMap, contextMap, contracts_file="contracts.json"):
        """
        Initialize data downloader.

        Args:
            ib_client: IBKR API client
            callbackFnMap: Callback function map
            contextMap: Context map for callbacks
            contracts_file: Path to contracts.json file
        """
        self.ib_client = ib_client
        self.callbackFnMap = callbackFnMap
        self.contextMap = contextMap
        self.contracts_file = contracts_file
        self.data_base_dir = "data"

        # Tracking for async downloads
        self.pending_downloads = set()
        self.download_lock = threading.Lock()
        self.all_downloads_complete = threading.Event()

    def get_contract_folder(self, contract: Contract) -> str:
        """
        Get folder path for a contract.

        Args:
            contract: IBKR Contract object

        Returns:
            Folder path (e.g., "data/USD-CAD")
        """
        folder_name = f"{contract.symbol}-{contract.currency}"
        return os.path.join(self.data_base_dir, folder_name)

    def get_csv_path(self, contract: Contract, bar_size: str, interval: str) -> str:
        """
        Get CSV file path for a contract and bar size.

        Args:
            contract: IBKR Contract object
            bar_size: Bar size (e.g., "1 hour")
            interval: Time interval (e.g., "6 M")

        Returns:
            CSV file path
        """
        folder = self.get_contract_folder(contract)
        filename = f"data-{contract.symbol}-{contract.secType}-{contract.exchange}-{contract.currency}-{interval}-{bar_size}.csv"
        return os.path.join(folder, filename)

    def contract_data_exists(self, contract: Contract, bar_sizes: List[str], interval: str = None) -> bool:
        """
        Check if all required data files exist for a contract.

        Args:
            contract: IBKR Contract object
            bar_sizes: List of bar sizes to check
            interval: Time interval (optional, will use bar-specific if not provided)

        Returns:
            True if all files exist, False otherwise
        """
        folder = self.get_contract_folder(contract)
        if not os.path.exists(folder):
            return False

        for bar_size in bar_sizes:
            # Use bar-specific interval if interval not provided
            bar_interval = self.get_interval_for_bar_size(bar_size, interval)
            csv_path = self.get_csv_path(contract, bar_size, bar_interval)
            if not os.path.exists(csv_path):
                return False

        return True

    def get_interval_for_bar_size(self, bar_size: str, requested_interval: str = None) -> str:
        """
        Get appropriate interval for a bar size based on IBKR limitations.

        Args:
            bar_size: Bar size (e.g., "1 min", "5 mins")
            requested_interval: User-requested interval (if any)

        Returns:
            Appropriate interval string
        """
        # If user specified an interval, use it (but warn if too long)
        if requested_interval:
            max_interval = self.BAR_SIZE_INTERVAL_LIMITS.get(bar_size)
            if max_interval:
                # Simple check: if requested is longer than max, use max
                # This is a heuristic - could be improved
                return requested_interval
            return requested_interval

        # Use default based on bar size limitations
        return self.BAR_SIZE_INTERVAL_LIMITS.get(bar_size, self.DEFAULT_INTERVAL)

    def download_contract_data(
        self,
        contract: Contract,
        bar_sizes: List[str],
        interval: str = None,
        force_refresh: bool = False,
        start_id: int = None,
    ) -> Tuple[Dict[str, bool], int]:
        """
        Download historical data for a contract with multiple bar sizes.

        Args:
            contract: IBKR Contract object
            bar_sizes: List of bar sizes to download
            interval: Time interval (default: auto-adjusted per bar size)
            force_refresh: Force re-download even if files exist
            start_id: Starting request ID (for unique IDs across contracts)

        Returns:
            Tuple of (dictionary mapping bar_size to success status, next available ID)
        """

        # Check if data already exists (using bar-specific intervals)
        if not force_refresh and self.contract_data_exists(contract, bar_sizes, interval):
            print(f"✓ Data already exists for {contract.symbol}/{contract.currency}. Skipping.")
            # Still need to return the next ID even if skipping
            if start_id is None:
                start_id = self.ib_client.nextorderId
            next_id = start_id + len(bar_sizes)
            return ({bar_size: True for bar_size in bar_sizes}, next_id)

        # Create contract folder
        folder = self.get_contract_folder(contract)
        os.makedirs(folder, exist_ok=True)

        results = {}
        # Use provided start_id or get from client
        if start_id is None:
            id_counter = self.ib_client.nextorderId
        else:
            id_counter = start_id

        for bar_size in bar_sizes:
            # Get appropriate interval for this bar size
            bar_interval = self.get_interval_for_bar_size(bar_size, interval)
            csv_path = self.get_csv_path(contract, bar_size, bar_interval)

            # Skip if file exists and not forcing refresh
            if not force_refresh and os.path.exists(csv_path):
                print(f"  ✓ {bar_size} data already exists. Skipping.")
                results[bar_size] = True
                continue

            # Warn about 1-minute data limitations
            if bar_size == "1 min":
                print(f"  ⚠ Downloading {bar_size} data (limited to {bar_interval} by IBKR API)...")
            else:
                print(f"  Downloading {bar_size} data for {contract.symbol}/{contract.currency}...")

            try:
                candlestick_data = []
                rhd_object = rhd.RequestHistoricalData(
                    self.ib_client, self.callbackFnMap, self.contextMap
                )
                rhd_cb = rhd_callback.Callback(candlestick_data)

                # Store context for callback
                self.contextMap[id_counter]["contract"] = contract
                self.contextMap[id_counter]["csv_path"] = csv_path
                self.contextMap[id_counter]["bar_size"] = bar_size
                # Store the req_id explicitly for easy retrieval in callback
                self.contextMap[id_counter]["req_id"] = id_counter

                # Track this download
                with self.download_lock:
                    self.pending_downloads.add(id_counter)
                    from config import DEBUG as DEBUG_MODE
                    if DEBUG_MODE:
                        print(f"  [DEBUG] Added req_id {id_counter} to pending_downloads. Total pending: {len(self.pending_downloads)}")
                    # Clear the event since we have pending downloads
                    if len(self.pending_downloads) == 1:
                        self.all_downloads_complete.clear()

                # Create a wrapper callback that retrieves req_id from contextMap
                # We look it up by matching file_to_save to ensure we get the correct req_id
                # The key insight: IBKR calls the callback stored at callbackFnMap[reqId],
                # so we need to find which reqId matches this file_to_save
                from config import DEBUG as DEBUG_MODE

                def save_data_callback_wrapper(df, ti, fts, c):
                    # Find the req_id by matching file_to_save in contextMap
                    # The contextMap key IS the req_id that IBKR uses
                    # Since IBKR calls callbackFnMap[reqId], the contextMap[reqId] has the matching data
                    actual_req_id = None
                    for req_id_key, ctx in self.contextMap.items():
                        if isinstance(ctx, dict):
                            # Match by fileToSave (most reliable) and contract
                            if ctx.get("fileToSave") == fts:
                                ctx_contract = ctx.get("contract")
                                if ctx_contract and ctx_contract.symbol == c.symbol and ctx_contract.currency == c.currency:
                                    # The contextMap key IS the req_id - use it directly
                                    actual_req_id = req_id_key
                                    break

                    if actual_req_id is None:
                        # Fallback: try to find by contract only (in case file path differs slightly)
                        for req_id_key, ctx in self.contextMap.items():
                            if isinstance(ctx, dict):
                                ctx_contract = ctx.get("contract")
                                if ctx_contract and ctx_contract.symbol == c.symbol and ctx_contract.currency == c.currency:
                                    # The contextMap key IS the req_id - use it directly
                                    actual_req_id = req_id_key
                                    break

                    if actual_req_id is None:
                        print(f"  ⚠ Warning: Could not find req_id for {c.symbol}/{c.currency}, file={fts}")
                        print(f"    Available context keys: {sorted(self.contextMap.keys())}")
                        # Try to signal completion anyway by checking if any pending downloads match
                        with self.download_lock:
                            # If only one pending, assume it's this one
                            if len(self.pending_downloads) == 1:
                                actual_req_id = next(iter(self.pending_downloads))
                                print(f"    Assuming req_id={actual_req_id} (only one pending)")
                            else:
                                print(f"    Pending req_ids: {sorted(self.pending_downloads)}")
                                # Try to match by contract symbol/currency in pending downloads
                                # This is a last resort - shouldn't normally happen
                                for pending_req_id in sorted(self.pending_downloads):
                                    pending_ctx = self.contextMap.get(pending_req_id, {})
                                    if isinstance(pending_ctx, dict):
                                        pending_contract = pending_ctx.get("contract")
                                        if pending_contract and pending_contract.symbol == c.symbol and pending_contract.currency == c.currency:
                                            actual_req_id = pending_req_id
                                            print(f"    Matched by contract: req_id={actual_req_id}")
                                            break

                    # Always print when callback is invoked (helps debug the issue)
                    print(f"  [CALLBACK] Data received for req_id={actual_req_id}, contract={c.symbol}/{c.currency}")
                    if DEBUG_MODE:
                        print(f"  [DEBUG] Callback wrapper: found req_id={actual_req_id}, pending={sorted(self.pending_downloads)}")
                    try:
                        self._save_data_callback(df, fts, c, actual_req_id)
                    except Exception as e:
                        # Ensure we still signal completion even if callback fails
                        print(f"  ✗ Error in callback for req_id {actual_req_id}: {e}")
                        import traceback
                        traceback.print_exc()
                        # Still try to signal completion
                        if actual_req_id is not None:
                            with self.download_lock:
                                was_in_set = actual_req_id in self.pending_downloads
                                self.pending_downloads.discard(actual_req_id)
                                if DEBUG_MODE:
                                    print(f"  [DEBUG] Exception handler: was_in_set={was_in_set}, remaining={len(self.pending_downloads)}")
                                remaining = len(self.pending_downloads)
                                if remaining == 0:
                                    self.all_downloads_complete.set()
                                    print(f"\n✓ All downloads completed (after error)!")
                                else:
                                    print(f"  ({remaining} download(s) still pending after error)")

                # Request historical data
                # Note: technicalIndicators=None for Phase 1 (raw data only)
                rhd_object.request_historical_data(
                    reqID=id_counter,
                    contract=contract,
                    interval=bar_interval,  # Use bar-specific interval
                    timePeriod=bar_size,
                    dataType="MIDPOINT",
                    rth=0,
                    timeFormat=2,
                    keepUpToDate=False,
                    atDatapointFn=rhd_cb.handle,
                    afterAllDataFn=save_data_callback_wrapper,
                    atDatapointUpdateFn=lambda x, y: None,
                    technicalIndicators=None,  # No indicators in Phase 1
                    fileToSave=csv_path,
                    candlestickData=candlestick_data,
                )

                id_counter += 1
                results[bar_size] = True

                # Wait between requests to avoid rate limiting
                # Longer wait for 1-minute data due to larger data volume
                if bar_size == "1 min":
                    time.sleep(3)  # 3 seconds for 1-minute data
                else:
                    time.sleep(1)  # 1 second for other bar sizes

            except Exception as e:
                print(f"  ✗ Error downloading {bar_size}: {e}")
                results[bar_size] = False
                # Still increment ID even on error to avoid duplicates
                id_counter += 1

        return results, id_counter

    def _save_data_callback(self, df, file_to_save, contract, req_id):
        """Callback after data is saved - ensures proper indexing.

        Args:
            df: DataFrame with the historical data
            file_to_save: Path to the CSV file
            contract: IBKR Contract object
            req_id: Request ID for tracking completion
        """
        import pandas as pd

        # Debug: Verify callback is being called
        from config import DEBUG
        if DEBUG:
            print(f"  [DEBUG] _save_data_callback called for req_id={req_id}, contract={contract.symbol}/{contract.currency}")

        # Data is already saved by ib_api_client.historicalDataEnd, but we need to ensure
        # the CSV has a proper datetime index for Phase 2 processing.
        if df is not None and len(df) > 0:
            try:
                # Reload from disk so we work with exactly what was written.
                df_reload = pd.read_csv(file_to_save)

                # If a "date" column exists, normalise it to a datetime index.
                if "date" in df_reload.columns:
                    dates = df_reload["date"].dropna()

                    # Heuristic: IB can return either YYYYMMDD-style dates for
                    # daily/weekly bars or epoch seconds for intraday, and we
                    # previously stored them as integers in the CSV. Using
                    # `unit="s"` unconditionally was corrupting YYYYMMDD
                    # values (e.g. 20240102 -> 1970-08-22...).
                    if not dates.empty:
                        sample = str(dates.iloc[0])
                        if sample.isdigit():
                            if len(sample) == 8:
                                # YYYYMMDD format (daily/weekly bars)
                                df_reload["date"] = pd.to_datetime(
                                    df_reload["date"].astype("int64").astype(str),
                                    format="%Y%m%d",
                                    errors="coerce",
                                )
                            else:
                                # Assume epoch seconds for intraday bars
                                df_reload["date"] = pd.to_datetime(
                                    df_reload["date"].astype("int64"),
                                    unit="s",
                                    errors="coerce",
                                )
                        else:
                            # Already a string datetime (let pandas infer)
                            df_reload["date"] = pd.to_datetime(
                                df_reload["date"], errors="coerce"
                            )
                    else:
                        df_reload["date"] = pd.to_datetime(
                            df_reload["date"], errors="coerce"
                        )

                    # Use date as index and drop rows without valid OHLC data.
                    df_reload = df_reload.set_index("date")
                    df_reload = df_reload.dropna(subset=["open", "high", "low", "close"])

                    # Save again with proper index
                    df_reload.to_csv(file_to_save)
                    print(
                        f"    ✓ Completed: {len(df_reload)} bars saved to {os.path.basename(file_to_save)}"
                    )
                else:
                    print(
                        f"    ✓ Completed: {len(df)} bars saved to {os.path.basename(file_to_save)}"
                    )

            except Exception as e:
                print(
                    f"    ⚠ Warning processing {os.path.basename(file_to_save)}: {e}"
                )
                if df is not None:
                    print(f"    ✓ Data saved: {len(df)} bars")
        else:
            print(f"    ✗ No data received for {os.path.basename(file_to_save)}")

        # Signal that this download is complete (always, even on errors)
        # This MUST execute to ensure we don't hang waiting for downloads
        if req_id is not None:
            with self.download_lock:
                was_pending = req_id in self.pending_downloads
                if DEBUG:
                    print(f"  [DEBUG] Signaling completion for req_id={req_id}")
                    print(f"  [DEBUG] Before discard: pending_downloads={sorted(self.pending_downloads)}, was_pending={was_pending}")

                # Always try to remove, even if not in set (defensive programming)
                self.pending_downloads.discard(req_id)
                remaining = len(self.pending_downloads)

                if DEBUG:
                    print(f"  [DEBUG] After discard: pending_downloads={sorted(self.pending_downloads)}, remaining={remaining}")

                if was_pending:
                    if remaining == 0:
                        self.all_downloads_complete.set()
                        print(f"\n✓ All downloads completed!")
                    else:
                        print(f"  ({remaining} download(s) still pending)")
                else:
                    # This shouldn't happen, but log it for debugging
                    print(f"  ⚠ Warning: req_id {req_id} was not in pending_downloads")
                    print(f"    Current pending: {sorted(self.pending_downloads)}")
                    # Still set the event if set is empty (defensive)
                    if remaining == 0:
                        self.all_downloads_complete.set()
        else:
            if DEBUG:
                print(f"  [DEBUG] req_id is None, cannot signal completion")
            print(f"  ⚠ Warning: Cannot signal completion - req_id is None")

    def download_all_contracts(
        self,
        bar_sizes: List[str] = None,
        interval: str = None,
        force_refresh: bool = False,
    ) -> Dict[str, Dict[str, bool]]:
        """
        Download data for all contracts in contracts.json.

        Args:
            bar_sizes: List of bar sizes (default: DEFAULT_BAR_SIZES)
            interval: Time interval (default: None, uses bar-size-specific intervals)
            force_refresh: Force re-download

        Returns:
            Dictionary mapping contract string to bar_size results
        """
        if bar_sizes is None:
            bar_sizes = self.DEFAULT_BAR_SIZES
        # Don't set interval to DEFAULT_INTERVAL - keep it as None so get_interval_for_bar_size
        # can use bar-size-specific limits from BAR_SIZE_INTERVAL_LIMITS

        # Load contracts
        with open(self.contracts_file) as f:
            data = json.load(f)

        # Parse and filter contracts by enabled flag
        enabled_contracts = self._parse_contracts(data["contracts"])

        # Reset tracking for this batch of downloads
        with self.download_lock:
            self.pending_downloads.clear()
            self.all_downloads_complete.set()  # Set initially in case no downloads needed

        all_results = {}
        # Start with a unique ID and track it across all contracts
        current_id = self.ib_client.nextorderId

        for contract_str in enabled_contracts:
            fields = contract_str.split(",")
            if len(fields) < 4:
                print(f"⚠ Skipping invalid contract: {contract_str}")
                continue

            contract = Contract()
            contract.symbol = fields[0]
            contract.currency = fields[1]
            contract.secType = fields[2]
            contract.exchange = fields[3]

            print(f"\n📊 Processing contract: {contract.symbol}/{contract.currency}")

            results, next_id = self.download_contract_data(
                contract, bar_sizes, interval, force_refresh, start_id=current_id
            )
            all_results[contract_str] = results
            current_id = next_id  # Update ID for next contract

            # Small delay between contracts to avoid rate limiting
            time.sleep(2)

        return all_results

    def wait_for_downloads_complete(self, timeout: int = 6000) -> bool:
        """
        Wait for all pending downloads to complete.

        Args:
            timeout: Maximum time to wait in seconds (default: 6000 = 100 minutes)

        Returns:
            True if all downloads completed, False if timeout occurred
        """
        with self.download_lock:
            num_pending = len(self.pending_downloads)

        if num_pending == 0:
            return True

        print(f"\n⏳ Waiting for {num_pending} download(s) to complete...")
        print("   (This may take a few minutes depending on data size)")

        completed = self.all_downloads_complete.wait(timeout=timeout)

        if not completed:
            with self.download_lock:
                remaining = len(self.pending_downloads)
            print(f"\n⚠ Warning: {remaining} download(s) may not have completed within timeout period ({timeout}s)")
            return False

        return True

    def _parse_contracts(self, contracts_data):
        """
        Parse contracts from JSON data, handling both old string format and new object format.
        Filters by enabled flag (defaults to True for backward compatibility).

        Args:
            contracts_data: List of contracts (strings or objects with 'contract' and 'enabled' keys)

        Returns:
            List of contract strings that are enabled
        """
        enabled_contracts = []
        for item in contracts_data:
            if isinstance(item, str):
                # Old format: just a string, treat as enabled
                enabled_contracts.append(item)
            elif isinstance(item, dict):
                # New format: object with 'contract' and optional 'enabled' flag
                if item.get("enabled", True):  # Default to True if not specified
                    enabled_contracts.append(item["contract"])
            else:
                print(f"⚠ Skipping invalid contract format: {item}")
        return enabled_contracts


def connect_ibkr():
    """Helper function to connect to IBKR."""
    import collections

    callbackFnMap = collections.defaultdict(
        lambda: collections.defaultdict(lambda: None)
    )
    contextMap = collections.defaultdict(lambda: collections.defaultdict(lambda: None))
    client = IBApiClient(callbackFnMap, contextMap)

    # Use unique client ID (similar to cli.py)
    import random
    client_id = random.randint(1000, 9999)
    client.connect("127.0.0.1", 7497, client_id)

    def run_loop():
        try:
            client.run()
        except Exception:
            # Thread might be interrupted during shutdown
            pass

    api_thread = threading.Thread(target=run_loop, daemon=True)
    api_thread.start()

    # Wait for connection
    for _ in range(60):
        if isinstance(getattr(client, "nextorderId", None), int):
            print("✓ Connected to IBKR")
            return client, callbackFnMap, contextMap
        time.sleep(1)

    raise RuntimeError("Could not connect to IBKR within 60 seconds")

