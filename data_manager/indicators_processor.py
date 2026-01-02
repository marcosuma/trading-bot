"""
Phase 2: Process all downloaded CSV files and add technical indicators.
"""
import os
import pandas as pd
from typing import List, Dict
from technical_indicators.technical_indicators import TechnicalIndicators


class IndicatorsProcessor:
    """Processes CSV files to add technical indicators."""

    def __init__(self, data_base_dir="data"):
        """
        Initialize indicators processor.

        Args:
            data_base_dir: Base directory containing contract folders
        """
        self.data_base_dir = data_base_dir

    def get_contract_folders(self) -> List[str]:
        """
        Get all contract folders.

        Returns:
            List of contract folder paths
        """
        if not os.path.exists(self.data_base_dir):
            return []

        folders = []
        for item in os.listdir(self.data_base_dir):
            folder_path = os.path.join(self.data_base_dir, item)
            if os.path.isdir(folder_path):
                folders.append(folder_path)

        return folders

    def get_csv_files(self, folder_path: str) -> List[str]:
        """
        Get all CSV files in a folder.

        Args:
            folder_path: Path to contract folder

        Returns:
            List of CSV file paths
        """
        csv_files = []
        if os.path.exists(folder_path):
            for file in os.listdir(folder_path):
                if file.endswith(".csv"):
                    csv_files.append(os.path.join(folder_path, file))
        return csv_files

    def has_indicators(self, df: pd.DataFrame) -> bool:
        """
        Check if DataFrame already has technical indicators computed.

        Args:
            df: DataFrame to check

        Returns:
            True if indicators exist, False otherwise
        """
        # Check for common indicator columns
        indicator_columns = [
            "RSI_14",
            "macd",
            "macd_s",
            "macd_h",
            "EMA_10",
            "SMA_50",
            "SMA_100",
            "SMA_200",
            "ATR_14",
            "atr",
            "adx",
            "plus_di",
            "minus_di",
            "bollinger_up",
            "bollinger_down",
            "local_extrema",
        ]
        # If at least 3 indicator columns exist, assume indicators are computed
        existing_indicators = sum(1 for col in indicator_columns if col in df.columns)
        return existing_indicators >= 3

    def process_csv(self, csv_path: str, skip_if_exists: bool = True) -> bool:
        """
        Process a single CSV file to add technical indicators.

        Args:
            csv_path: Path to CSV file
            skip_if_exists: Skip processing if indicators already exist

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if file exists
            if not os.path.exists(csv_path):
                return False

            # Load CSV
            df = pd.read_csv(csv_path, index_col=[0])

            # Convert index to datetime if needed
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index, errors="coerce")
                # Drop rows where date parsing failed (NaN in index)
                df = df[df.index.notna()]
                if len(df) == 0:
                    print(f"  ✗ No valid data in {os.path.basename(csv_path)}")
                    return False

            # Ensure required OHLC columns exist
            required_cols = ["open", "high", "low", "close"]
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                print(f"  ✗ Missing columns in {os.path.basename(csv_path)}: {missing}")
                return False

            # Check if indicators already exist
            if skip_if_exists and self.has_indicators(df):
                print(f"  ✓ Indicators already exist in {os.path.basename(csv_path)}. Skipping.")
                return True

            # Initialize technical indicators processor
            # Use None for candlestickData since we're loading from file
            technical_indicators = TechnicalIndicators(candlestickData=None, fileToSave=csv_path)

            # Compute indicators
            df = technical_indicators.execute(df)

            # Save back to CSV
            df.to_csv(csv_path)
            print(f"  ✓ Processed {len(df)} bars in {os.path.basename(csv_path)}")

            return True

        except Exception as e:
            print(f"  ✗ Error processing {os.path.basename(csv_path)}: {e}")
            return False

    def process_contract_folder(self, folder_path: str) -> Dict[str, bool]:
        """
        Process all CSV files in a contract folder.

        Args:
            folder_path: Path to contract folder

        Returns:
            Dictionary mapping CSV filename to success status
        """
        contract_name = os.path.basename(folder_path)
        print(f"\n📈 Processing indicators for: {contract_name}")

        csv_files = self.get_csv_files(folder_path)
        if not csv_files:
            print(f"  ⚠ No CSV files found in {contract_name}")
            return {}

        results = {}
        for csv_path in csv_files:
            filename = os.path.basename(csv_path)
            # Local extrema is now calculated as part of technical indicators
            processed = self.process_csv(csv_path)
            results[filename] = processed

        return results

    def process_all_contracts(self) -> Dict[str, Dict[str, bool]]:
        """
        Process all contract folders.

        Returns:
            Dictionary mapping contract folder to CSV processing results
        """
        contract_folders = self.get_contract_folders()
        if not contract_folders:
            print(f"⚠ No contract folders found in {self.data_base_dir}")
            return {}

        print(f"\n🔧 Processing technical indicators for {len(contract_folders)} contracts...")

        all_results = {}
        for folder_path in contract_folders:
            results = self.process_contract_folder(folder_path)
            all_results[os.path.basename(folder_path)] = results

        return all_results

