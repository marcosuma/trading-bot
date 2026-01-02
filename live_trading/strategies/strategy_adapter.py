"""
Strategy Adapter - Adapts backtesting strategies for live trading.
"""
import logging
from typing import Dict, Optional, List
import pandas as pd

from live_trading.data.data_manager import DataManager
from forex_strategies.base_strategy import BaseForexStrategy

logger = logging.getLogger(__name__)


class StrategyAdapter:
    """Adapts backtesting strategies for incremental live trading"""

    def __init__(
        self,
        strategy_class: type[BaseForexStrategy],
        strategy_config: Dict,
        data_manager: DataManager,
        operation_id: str,
        bar_sizes: List[str],
        primary_bar_size: str
    ):
        self.strategy_class = strategy_class
        self.strategy_config = strategy_config
        self.data_manager = data_manager
        self.operation_id = operation_id
        self.bar_sizes = bar_sizes
        self.primary_bar_size = primary_bar_size

        # Initialize strategy instance
        self.strategy = strategy_class(**strategy_config)

        # Signal callback
        self.signal_callback: Optional[callable] = None

    def set_signal_callback(self, callback: callable):
        """Set callback for when signals are generated"""
        self.signal_callback = callback

    async def on_new_bar(self, bar_size: str, bar_data: Dict, indicators: Dict):
        """Called when a new bar is completed"""
        # Only generate signals when primary bar_size completes
        if bar_size != self.primary_bar_size:
            return

        # Get aligned dataframes for all timeframes
        aligned_data = await self._align_timeframes()

        if aligned_data is None or aligned_data.empty:
            return

        # Generate signals using strategy
        try:
            signals_df = self.strategy.generate_signals(aligned_data)

            # Check for signals in the last row
            last_row = signals_df.iloc[-1]

            # Check for buy signal
            if pd.notna(last_row.get("execute_buy")):
                buy_price = last_row["execute_buy"]
                await self._handle_signal("BUY", buy_price)

            # Check for sell signal
            if pd.notna(last_row.get("execute_sell")):
                sell_price = last_row["execute_sell"]
                await self._handle_signal("SELL", sell_price)

        except Exception as e:
            logger.error(f"Error generating signals: {e}", exc_info=True)

    async def _align_timeframes(self) -> Optional[pd.DataFrame]:
        """Align data from multiple timeframes"""
        # Get latest bars for primary timeframe
        primary_df = await self.data_manager.get_dataframe(
            self.operation_id,
            self.primary_bar_size
        )

        if primary_df.empty:
            return None

        # For other timeframes, get most recent available bar
        for bar_size in self.bar_sizes:
            if bar_size == self.primary_bar_size:
                continue

            other_df = await self.data_manager.get_dataframe(
                self.operation_id,
                bar_size
            )

            if not other_df.empty:
                # Get most recent bar
                latest_bar = other_df.iloc[-1]

                # Add columns with bar_size prefix
                for col in ["open", "high", "low", "close", "volume"]:
                    if col in latest_bar:
                        primary_df[f"{bar_size}_{col}"] = latest_bar[col]

                # Add indicators with bar_size prefix
                if "indicators" in latest_bar and isinstance(latest_bar["indicators"], dict):
                    for indicator_name, indicator_value in latest_bar["indicators"].items():
                        primary_df[f"{bar_size}_{indicator_name}"] = indicator_value

        return primary_df

    async def _handle_signal(self, signal_type: str, price: float):
        """Handle a trading signal"""
        if self.signal_callback:
            await self.signal_callback(
                operation_id=self.operation_id,
                signal_type=signal_type,
                price=price
            )
        else:
            logger.warning(f"Signal generated but no callback set: {signal_type} @ {price}")

