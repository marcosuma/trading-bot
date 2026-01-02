"""
Trade model.
"""
from datetime import datetime
from beanie import Document
from pydantic import Field, ConfigDict
from bson import ObjectId


class Trade(Document):
    """Trade document (completed round-trip trades)"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    operation_id: ObjectId = Field(..., description="Reference to trading_operations")
    position_type: str = Field(..., description="Position type: 'LONG' or 'SHORT'")

    entry_transaction_id: ObjectId = Field(..., description="Reference to ENTRY transaction (BUY for LONG, SELL for SHORT)")
    exit_transaction_id: ObjectId = Field(..., description="Reference to EXIT transaction (SELL for LONG, BUY for SHORT)")

    entry_price: float = Field(..., description="Entry price")
    exit_price: float = Field(..., description="Exit price")
    quantity: float = Field(..., description="Absolute quantity")

    pnl: float = Field(..., description="Total profit/loss")
    pnl_pct: float = Field(..., description="Profit/loss percentage")

    total_commission: float = Field(default=0.0, description="Sum of entry + exit commissions")

    entry_time: datetime = Field(..., description="Entry time")
    exit_time: datetime = Field(..., description="Exit time")
    duration_seconds: float = Field(..., description="Trade duration in seconds")

    class Settings:
        name = "trades"
        indexes = [
            "operation_id",
            [("operation_id", 1), ("exit_time", -1)],
            [("operation_id", 1), ("position_type", 1)],
            "entry_transaction_id",
            "exit_transaction_id",
        ]

