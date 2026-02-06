"""
Order model.
"""
from datetime import datetime
from typing import Optional
from beanie import Document
from pydantic import Field, ConfigDict, field_validator, model_validator
from bson import ObjectId
from bson.decimal128 import Decimal128


class Order(Document):
    """Order document (all orders placed)"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    operation_id: ObjectId = Field(..., description="Reference to trading_operations")
    broker_order_id: Optional[str] = Field(None, description="IBKR/OANDA order ID")

    order_type: str = Field(..., description="Order type: 'MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT'")
    action: str = Field(..., description="Action: 'BUY' or 'SELL'")

    quantity: float = Field(..., description="Order quantity")
    price: Optional[float] = Field(None, description="Limit price (for limit orders)")

    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")

    status: str = Field(default="PENDING", description="Order status: 'PENDING', 'FILLED', 'CANCELLED', 'REJECTED'")

    filled_quantity: float = Field(default=0.0, description="Filled quantity")
    avg_fill_price: Optional[float] = Field(None, description="Average fill price")
    commission: float = Field(default=0.0, description="Commission paid")

    placed_at: datetime = Field(default_factory=datetime.utcnow, description="When order was placed")
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    @model_validator(mode='before')
    @classmethod
    def convert_decimal128(cls, data):
        """Convert Decimal128 values to float for Pydantic validation"""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, Decimal128):
                    # Convert Decimal128 -> Decimal -> float
                    data[key] = float(value.to_decimal())
        return data

    class Settings:
        name = "orders"
        indexes = [
            "operation_id",
            [("operation_id", 1), ("placed_at", -1)],
            [("operation_id", 1), ("status", 1)],
            "broker_order_id",
        ]

