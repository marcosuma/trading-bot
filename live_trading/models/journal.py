"""
Journal Entry model.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from beanie import Document
from pydantic import Field, ConfigDict
from bson import ObjectId


class JournalEntry(Document):
    """Journal entry document (action log for recovery)"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    operation_id: Optional[ObjectId] = Field(None, description="Reference to trading_operations (optional)")
    sequence_number: int = Field(..., description="Sequential number for ordering")

    action_type: str = Field(..., description="Action type (e.g., 'ORDER_PLACED', 'POSITION_OPENED', 'SIGNAL_GENERATED')")
    action_data: Dict[str, Any] = Field(default_factory=dict, description="Action-specific data")

    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When action occurred")

    notes: Optional[str] = Field(None, description="Optional notes")

    class Settings:
        name = "journal"
        indexes = [
            "operation_id",
            [("operation_id", 1), ("sequence_number", 1)],
            [("timestamp", -1)],
        ]

