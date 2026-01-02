"""
Journal Manager - Logs all actions for recovery and audit trail.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from live_trading.models.journal import JournalEntry
from live_trading.config import config


logger = logging.getLogger(__name__)


class JournalManager:
    """Manages journal entries for action logging and recovery"""

    def __init__(self):
        self._sequence_counter = 0

    async def log_action(
        self,
        action_type: str,
        action_data: Dict[str, Any],
        operation_id: Optional[ObjectId] = None,
        notes: Optional[str] = None
    ) -> JournalEntry:
        """
        Log an action to the journal.

        Args:
            action_type: Type of action (e.g., 'ORDER_PLACED', 'POSITION_OPENED')
            action_data: Action-specific data dictionary
            operation_id: Optional operation ID
            notes: Optional notes

        Returns:
            Created JournalEntry
        """
        # Get next sequence number
        self._sequence_counter += 1

        entry = JournalEntry(
            operation_id=operation_id,
            sequence_number=self._sequence_counter,
            action_type=action_type,
            action_data=action_data,
            notes=notes,
            timestamp=datetime.utcnow()
        )

        await entry.insert()
        logger.debug(f"Journal entry logged: {action_type} (seq: {self._sequence_counter})")

        return entry

    async def get_entries(
        self,
        operation_id: Optional[ObjectId] = None,
        limit: int = 100,
        start_time: Optional[datetime] = None
    ) -> list[JournalEntry]:
        """
        Get journal entries.

        Args:
            operation_id: Optional operation ID to filter by
            limit: Maximum number of entries to return
            start_time: Optional start time to filter from

        Returns:
            List of JournalEntry documents
        """
        query = {}
        if operation_id:
            query["operation_id"] = operation_id
        if start_time:
            query["timestamp"] = {"$gte": start_time}

        entries = await JournalEntry.find(query).sort(-JournalEntry.timestamp).limit(limit).to_list()
        return entries

    async def get_last_entry(self, operation_id: Optional[ObjectId] = None) -> Optional[JournalEntry]:
        """Get the most recent journal entry"""
        query = {}
        if operation_id:
            query["operation_id"] = operation_id

        entry = await JournalEntry.find(query).sort(-JournalEntry.timestamp).first()
        return entry

    async def initialize_sequence_counter(self):
        """Initialize sequence counter from last entry in database"""
        last_entries = await JournalEntry.find_all().sort(-JournalEntry.sequence_number).limit(1).to_list()
        if last_entries and len(last_entries) > 0:
            self._sequence_counter = last_entries[0].sequence_number
        else:
            self._sequence_counter = 0
        logger.info(f"Journal sequence counter initialized to: {self._sequence_counter}")

