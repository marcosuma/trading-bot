"""
Tests for data deduplication in the data manager.
"""
import pytest
from datetime import datetime, timedelta
from collections import defaultdict

from live_trading.data.data_manager import BarAggregator


class TestBarAggregator:
    """Tests for the BarAggregator class"""

    def test_bar_aggregator_creates_new_bar(self):
        """Test that the first tick creates a new bar"""
        aggregator = BarAggregator("1 hour")

        timestamp = datetime(2024, 1, 15, 14, 30, 0)
        result = aggregator.add_tick(price=1.1000, size=100, timestamp=timestamp)

        # First tick should not return a completed bar
        assert result is None
        # Current bar should be initialized
        assert aggregator.current_bar is not None
        assert aggregator.current_bar["open"] == 1.1000
        assert aggregator.current_bar["high"] == 1.1000
        assert aggregator.current_bar["low"] == 1.1000
        assert aggregator.current_bar["close"] == 1.1000
        assert aggregator.current_bar["volume"] == 100

    def test_bar_aggregator_updates_ohlc(self):
        """Test that subsequent ticks update OHLC correctly"""
        aggregator = BarAggregator("1 hour")

        base_time = datetime(2024, 1, 15, 14, 0, 0)

        # First tick
        aggregator.add_tick(price=1.1000, size=100, timestamp=base_time)

        # Higher price
        aggregator.add_tick(price=1.1050, size=50, timestamp=base_time + timedelta(minutes=10))
        assert aggregator.current_bar["high"] == 1.1050

        # Lower price
        aggregator.add_tick(price=1.0950, size=75, timestamp=base_time + timedelta(minutes=20))
        assert aggregator.current_bar["low"] == 1.0950

        # Close should be last price
        assert aggregator.current_bar["close"] == 1.0950

        # Volume should accumulate
        assert aggregator.current_bar["volume"] == 225

    def test_bar_aggregator_completes_bar_on_new_period(self):
        """Test that a new time period completes the previous bar"""
        aggregator = BarAggregator("1 hour")

        # First bar: 14:00-15:00
        base_time = datetime(2024, 1, 15, 14, 30, 0)
        aggregator.add_tick(price=1.1000, size=100, timestamp=base_time)
        aggregator.add_tick(price=1.1050, size=50, timestamp=base_time + timedelta(minutes=15))

        # Next bar: 15:00-16:00 (this should complete the previous bar)
        next_bar_time = datetime(2024, 1, 15, 15, 5, 0)
        completed_bar = aggregator.add_tick(price=1.1025, size=100, timestamp=next_bar_time)

        assert completed_bar is not None
        assert completed_bar["open"] == 1.1000
        assert completed_bar["high"] == 1.1050
        assert completed_bar["close"] == 1.1050
        assert completed_bar["volume"] == 150

        # Verify new bar started
        assert aggregator.current_bar["open"] == 1.1025

    def test_bar_start_time_calculation(self):
        """Test that bar start times are calculated correctly"""
        aggregator = BarAggregator("15 mins")

        # 14:22 should round down to 14:15
        timestamp = datetime(2024, 1, 15, 14, 22, 30)
        bar_start = aggregator._get_bar_start_time(timestamp)
        assert bar_start.hour == 14
        assert bar_start.minute == 15
        assert bar_start.second == 0

    def test_volume_zero_for_spot_data(self):
        """Test that bars created from spot data (no size) have zero volume"""
        aggregator = BarAggregator("1 hour")

        timestamp = datetime(2024, 1, 15, 14, 30, 0)
        # Simulating spot data with size=0 (like cTrader spot events)
        aggregator.add_tick(price=1.1000, size=0, timestamp=timestamp)

        assert aggregator.current_bar["volume"] == 0


class TestDataBufferDeduplication:
    """Tests for data buffer deduplication logic"""

    def test_duplicate_prevention(self):
        """Test that duplicate timestamps are handled correctly"""
        # Simulate the buffer behavior
        data_buffer = []

        # Add historical bar
        historical_bar = {
            "timestamp": datetime(2024, 1, 15, 14, 0, 0),
            "open": 1.1000,
            "high": 1.1050,
            "low": 1.0950,
            "close": 1.1025,
            "volume": 1000
        }
        data_buffer.append(historical_bar)

        # Simulate real-time bar with same timestamp
        realtime_bar = {
            "timestamp": datetime(2024, 1, 15, 14, 0, 0),
            "open": 1.1000,
            "high": 1.1060,  # Slightly higher
            "low": 1.0940,   # Slightly lower
            "close": 1.1030, # Different close
            "volume": 0      # No volume from spot data
        }

        # Apply deduplication logic (same as in data_manager._process_completed_bar)
        bar_timestamp = realtime_bar.get("timestamp")
        found_existing = False

        for existing_bar in data_buffer:
            if existing_bar.get("timestamp") == bar_timestamp:
                # Update existing bar - merge OHLC
                existing_bar["high"] = max(existing_bar.get("high", realtime_bar["high"]), realtime_bar["high"])
                existing_bar["low"] = min(existing_bar.get("low", realtime_bar["low"]), realtime_bar["low"])
                existing_bar["close"] = realtime_bar["close"]
                # Preserve volume if it was set (historical data has actual volume)
                if realtime_bar.get("volume", 0) > 0 or existing_bar.get("volume", 0) == 0:
                    existing_bar["volume"] = realtime_bar.get("volume", 0)
                found_existing = True
                break

        if not found_existing:
            data_buffer.append(realtime_bar)

        # Should only have one bar
        assert len(data_buffer) == 1

        # High should be updated to the max
        assert data_buffer[0]["high"] == 1.1060

        # Low should be updated to the min
        assert data_buffer[0]["low"] == 1.0940

        # Close should be the real-time close
        assert data_buffer[0]["close"] == 1.1030

        # Volume should be preserved from historical (since real-time is 0)
        assert data_buffer[0]["volume"] == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
