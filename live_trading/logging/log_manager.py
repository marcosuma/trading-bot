"""
Log Manager - Central logging configuration and management.
Integrates with Python's logging module and provides storage backends.
"""
import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import json
import threading

from .log_storage import LogStorage, FileLogStorage, LogEntry


class StorageHandler(logging.Handler):
    """
    Custom logging handler that writes to a LogStorage backend.
    """

    def __init__(self, storage: LogStorage, level: int = logging.DEBUG):
        super().__init__(level)
        self.storage = storage

    def emit(self, record: logging.LogRecord):
        try:
            # Build extra data from record
            extra = {}

            # Include exception info if present
            if record.exc_info:
                extra['exception'] = self.formatException(record.exc_info)

            # Include any custom fields
            for key in ['operation_id', 'asset', 'broker', 'strategy']:
                if hasattr(record, key):
                    extra[key] = getattr(record, key)

            entry = LogEntry(
                timestamp=datetime.utcnow().isoformat() + 'Z',
                level=record.levelname,
                logger=record.name,
                message=record.getMessage(),
                extra=extra if extra else None
            )

            self.storage.write(entry)
        except Exception:
            self.handleError(record)


class LogManager:
    """
    Singleton log manager for the live trading application.
    Configures logging, manages storage, and provides query interface.
    """

    _instance: Optional['LogManager'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        log_dir: str = "logs",
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
        max_file_size_mb: int = 10,
        max_files: int = 30  # Increased from 5 to keep ~30 days of logs
    ):
        if self._initialized:
            return

        self.log_dir = Path(log_dir)
        self.console_level = console_level
        self.file_level = file_level

        # Allow override via environment variable
        import os
        max_files = int(os.environ.get('LOG_MAX_FILES', max_files))
        max_file_size_mb = int(os.environ.get('LOG_MAX_FILE_SIZE_MB', max_file_size_mb))

        # Create storage backend
        self.storage = FileLogStorage(
            log_dir=str(self.log_dir),
            max_file_size_mb=max_file_size_mb,
            max_files=max_files
        )

        # Track configured loggers
        self._configured_loggers: set = set()

        self._initialized = True

    def setup_logging(self, app_name: str = "live_trading"):
        """
        Configure the root logger and application loggers.
        """
        # Create formatters
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        root_logger.handlers.clear()

        # Console handler (for when running interactively)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.console_level)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # Storage handler (writes to files)
        storage_handler = StorageHandler(self.storage, level=self.file_level)
        root_logger.addHandler(storage_handler)

        # Configure specific loggers
        self._configure_app_loggers(app_name)

        # Log startup
        logger = logging.getLogger(app_name)
        logger.info(f"Logging initialized - logs stored in {self.log_dir}")

    def _configure_app_loggers(self, app_name: str):
        """Configure application-specific loggers"""
        loggers_to_configure = [
            app_name,
            f"{app_name}.brokers",
            f"{app_name}.engine",
            f"{app_name}.strategies",
            f"{app_name}.api",
            f"{app_name}.data",
            "uvicorn",
            "uvicorn.access",
            "uvicorn.error",
        ]

        for logger_name in loggers_to_configure:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.DEBUG)
            self._configured_loggers.add(logger_name)

        # Quieten noisy loggers
        noisy_loggers = [
            "urllib3",
            "asyncio",
            "websockets",
            "httpx",
            "httpcore",
        ]
        for logger_name in noisy_loggers:
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        logger: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve logs with optional filters.
        Returns list of log entry dictionaries.
        """
        entries = self.storage.read(
            start_time=start_time,
            end_time=end_time,
            level=level,
            logger=logger,
            search=search,
            limit=limit,
            offset=offset
        )
        return [entry.to_dict() for entry in entries]

    def get_stats(self) -> Dict[str, Any]:
        """Get logging statistics"""
        stats = self.storage.get_stats()
        stats['configured_loggers'] = list(self._configured_loggers)
        return stats

    def cleanup_old_logs(self, older_than_days: int = 30) -> Dict[str, Any]:
        """Clean up old log files"""
        return self.storage.cleanup(older_than_days)

    def get_recent_errors(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Shortcut to get recent errors"""
        return self.get_logs(level="ERROR", limit=limit)

    def get_recent_warnings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Shortcut to get recent warnings"""
        return self.get_logs(level="WARNING", limit=limit)


# Global instance access
_log_manager: Optional[LogManager] = None


def get_log_manager() -> LogManager:
    """Get the global LogManager instance"""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
    return _log_manager


def setup_logging(
    log_dir: str = "logs",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    daemon_mode: bool = False
):
    """
    Convenience function to setup logging.

    Args:
        log_dir: Directory for log files
        console_level: Console output log level
        file_level: File storage log level
        daemon_mode: If True, disable console output
    """
    global _log_manager

    # In daemon mode, don't log to console
    if daemon_mode:
        console_level = logging.CRITICAL + 1  # Effectively disable console

    _log_manager = LogManager(
        log_dir=log_dir,
        console_level=console_level,
        file_level=file_level
    )
    _log_manager.setup_logging()

    return _log_manager
