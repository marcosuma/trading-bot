"""
Transaction model.
"""
from datetime import datetime
from typing import Optional
from beanie import Document
from pydantic import Field, ConfigDict
from bson import ObjectId


class Transaction(Document):
    """Transaction document (individual buy/sell operations)"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    operation_id: ObjectId = Field(..., description="Reference to trading_operations")
    transaction_type: str = Field(..., description="Transaction type: 'BUY' or 'SELL'")
    transaction_role: str = Field(..., description="Transaction role: 'ENTRY' or 'EXIT'")
    position_type: str = Field(..., description="Position type: 'LONG' or 'SHORT'")

    order_id: Optional[ObjectId] = Field(None, description="Reference to orders")
    position_id: Optional[ObjectId] = Field(None, description="Reference to positions")

    price: float = Field(..., description="Execution price")
    quantity: float = Field(..., description="Quantity executed")
    commission: float = Field(default=0.0, description="Commission paid")

    executed_at: datetime = Field(default_factory=datetime.utcnow, description="When transaction was executed")

    profit: float = Field(default=0.0, description="Profit for this transaction (0 for ENTRY, calculated for EXIT)")
    profit_pct: float = Field(default=0.0, description="Profit percentage (0 for ENTRY, calculated for EXIT)")

    # For EXIT transactions, link to corresponding ENTRY transaction
    related_entry_transaction_id: Optional[ObjectId] = Field(None, description="Reference to ENTRY transaction (for EXIT only)")

    notes: Optional[str] = Field(None, description="Optional notes")

    class Settings:
        name = "transactions"
        indexes = [
            "operation_id",
            [("operation_id", 1), ("executed_at", -1)],
            [("operation_id", 1), ("transaction_type", 1)],
            [("operation_id", 1), ("transaction_role", 1)],
            [("operation_id", 1), ("position_type", 1)],
            "related_entry_transaction_id",
        ]

