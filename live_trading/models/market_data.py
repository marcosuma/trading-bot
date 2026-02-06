"""
Market Data model.
"""
from datetime import datetime
from typing import Optional
from beanie import Document
from pydantic import Field, ConfigDict
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING


class MarketData(Document):
    """Market data document (accumulated bars per bar_size)"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    operation_id: ObjectId = Field(..., description="Reference to trading_operations")
    bar_size: str = Field(..., description="Bar size (e.g., '1 hour', '15 mins')")

    timestamp: datetime = Field(..., description="Bar timestamp")

    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: float = Field(default=0.0, description="Volume")

    # Technical indicators (stored as dict for flexibility)
    indicators: dict = Field(default_factory=dict, description="Technical indicators")

    class Settings:
        name = "market_data"
        indexes = [
            "operation_id",
            [("operation_id", ASCENDING), ("bar_size", ASCENDING), ("timestamp", DESCENDING)],
            [("operation_id", ASCENDING), ("bar_size", ASCENDING), ("timestamp", ASCENDING)],
            # Note: Unique constraint is handled at application level in data_manager.py
            # to avoid startup failures when duplicates exist. See _process_completed_bar()
        ]

