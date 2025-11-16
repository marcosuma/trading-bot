"""
Strategy tester for comparing multiple forex strategies.
"""
import pandas as pd
from typing import List, Dict, Any
from forex_strategies.base_strategy import BaseForexStrategy
from forex_strategies.backtesting_strategy import ForexBacktestingStrategy


class StrategyTester:
    """Test and compare multiple forex strategies."""

    def __init__(self, strategies: List[BaseForexStrategy]):
        """
        Initialize tester with list of strategies.

        Args:
            strategies: List of strategy instances to test
        """
        self.strategies = strategies

    def test_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Test all strategies and return comparison results.

        Args:
            df: DataFrame with OHLCV and technical indicators

        Returns:
            DataFrame with strategy comparison metrics
        """
        results = []

        for strategy in self.strategies:
            try:
                stats, _ = strategy.execute(df, ForexBacktestingStrategy)
                if stats is not None:
                    results.append(
                        {
                            "Strategy": strategy.__class__.__name__,
                            "Return [%]": stats["Return [%]"],
                            "Sharpe Ratio": stats.get("Sharpe Ratio", 0),
                            "Max. Drawdown [%]": stats["Max. Drawdown [%]"],
                            "# Trades": stats["# Trades"],
                            "Win Rate [%]": stats.get("Win Rate [%]", 0),
                            "Avg. Trade [%]": stats.get("Avg. Trade [%]", 0),
                        }
                    )
            except Exception as e:
                print(f"Error testing {strategy.__class__.__name__}: {e}")
                continue

        if not results:
            print("No strategies completed successfully")
            return pd.DataFrame()

        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values("Return [%]", ascending=False)
        return results_df

    def test_single(self, strategy: BaseForexStrategy, df: pd.DataFrame):
        """Test a single strategy."""
        return strategy.execute(df, ForexBacktestingStrategy)

