"""
Modular log storage backends.
Designed to be extensible - can add database storage, cloud storage, etc.
"""
import os
import json
import gzip
import shutil
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass, asdict
import threading
import re


@dataclass
class LogEntry:
    """Represents a single log entry"""
    timestamp: str
    level: str
    logger: str
    message: str
    extra: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogEntry':
        return cls(**data)

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json_line(cls, line: str) -> 'LogEntry':
        return cls.from_dict(json.loads(line))


class LogStorage(ABC):
    """Abstract base class for log storage backends"""

    @abstractmethod
    def write(self, entry: LogEntry):
        """Write a single log entry"""
        pass

    @abstractmethod
    def read(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        logger: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[LogEntry]:
        """Read log entries with optional filters"""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        pass

    @abstractmethod
    def cleanup(self, older_than_days: int = 30):
        """Clean up old logs"""
        pass


class FileLogStorage(LogStorage):
    """
    File-based log storage with rotation and compression.

    Directory structure:
    logs/
        live_trading.log          # Current log file
        live_trading.log.1        # Rotated file
        live_trading.log.2.gz     # Compressed older file
        archive/
            2026-01-20.log.gz     # Daily archives
    """

    def __init__(
        self,
        log_dir: str = "logs",
        max_file_size_mb: int = 10,
        max_files: int = 5,
        compress_after: int = 2,
        archive_daily: bool = True
    ):
        self.log_dir = Path(log_dir)
        self.max_file_size = max_file_size_mb * 1024 * 1024  # Convert to bytes
        self.max_files = max_files
        self.compress_after = compress_after
        self.archive_daily = archive_daily

        self.current_file = self.log_dir / "live_trading.log"
        self.archive_dir = self.log_dir / "archive"

        self._write_lock = threading.Lock()

        # Create directories
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def write(self, entry: LogEntry):
        """Write a log entry to file with rotation"""
        with self._write_lock:
            # Check if rotation is needed
            if self.current_file.exists() and self.current_file.stat().st_size >= self.max_file_size:
                self._rotate()

            # Write entry
            with open(self.current_file, 'a', encoding='utf-8') as f:
                f.write(entry.to_json_line() + '\n')

    def _rotate(self):
        """Rotate log files"""
        # Remove oldest file if at limit
        oldest = self.log_dir / f"live_trading.log.{self.max_files}"
        if oldest.exists():
            oldest.unlink()
        oldest_gz = self.log_dir / f"live_trading.log.{self.max_files}.gz"
        if oldest_gz.exists():
            oldest_gz.unlink()

        # Shift existing files
        for i in range(self.max_files - 1, 0, -1):
            old_name = self.log_dir / f"live_trading.log.{i}"
            old_name_gz = self.log_dir / f"live_trading.log.{i}.gz"
            new_name = self.log_dir / f"live_trading.log.{i + 1}"
            new_name_gz = self.log_dir / f"live_trading.log.{i + 1}.gz"

            if old_name_gz.exists():
                old_name_gz.rename(new_name_gz)
            elif old_name.exists():
                # Compress if past threshold
                if i >= self.compress_after:
                    with open(old_name, 'rb') as f_in:
                        with gzip.open(new_name_gz, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    old_name.unlink()
                else:
                    old_name.rename(new_name)

        # Rename current to .1
        if self.current_file.exists():
            self.current_file.rename(self.log_dir / "live_trading.log.1")

    def read(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        logger: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[LogEntry]:
        """Read log entries with filters"""
        entries = []
        skipped = 0

        # Read from all log files (newest first)
        for entry in self._read_all_files():
            # Apply filters
            if not self._matches_filters(entry, start_time, end_time, level, logger, search):
                continue

            # Handle offset
            if skipped < offset:
                skipped += 1
                continue

            entries.append(entry)

            if len(entries) >= limit:
                break

        return entries

    def _read_all_files(self) -> Generator[LogEntry, None, None]:
        """Read entries from all log files, newest first"""
        files_to_read = []

        # Current file (newest)
        if self.current_file.exists():
            files_to_read.append(self.current_file)

        # Rotated files (in order: .1 is newest rotated, .5 is oldest)
        for i in range(1, self.max_files + 1):
            path = self.log_dir / f"live_trading.log.{i}"
            path_gz = self.log_dir / f"live_trading.log.{i}.gz"
            if path.exists():
                files_to_read.append(path)
            elif path_gz.exists():
                files_to_read.append(path_gz)

        # Archive files (sorted by date, newest first)
        archive_files = sorted(
            self.archive_dir.glob("*.log.gz"),
            key=lambda p: p.name,
            reverse=True  # Newest archives first (2026-01-23 before 2026-01-22)
        )
        files_to_read.extend(archive_files)

        # Read files
        for file_path in files_to_read:
            try:
                # Read file (handle gzip)
                if str(file_path).endswith('.gz'):
                    with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                        lines = f.readlines()
                else:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()

                # Yield entries in reverse order (newest first within each file)
                for line in reversed(lines):
                    line = line.strip()
                    if line:
                        try:
                            yield LogEntry.from_json_line(line)
                        except json.JSONDecodeError:
                            # Skip malformed entries
                            continue
            except Exception as e:
                # Log error but continue with other files
                import logging
                logging.getLogger(__name__).debug(f"Error reading log file {file_path}: {e}")
                continue

    def _matches_filters(
        self,
        entry: LogEntry,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        level: Optional[str],
        logger: Optional[str],
        search: Optional[str]
    ) -> bool:
        """Check if entry matches all filters"""
        # Time filter
        if start_time or end_time:
            try:
                entry_time = datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00'))
                if start_time and entry_time < start_time:
                    return False
                if end_time and entry_time > end_time:
                    return False
            except ValueError:
                pass

        # Level filter
        if level and entry.level.upper() != level.upper():
            return False

        # Logger filter
        if logger and logger.lower() not in entry.logger.lower():
            return False

        # Search filter
        if search:
            search_lower = search.lower()
            if search_lower not in entry.message.lower():
                if not entry.extra or search_lower not in json.dumps(entry.extra).lower():
                    return False

        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        total_size = 0
        file_count = 0

        # Count files and size
        for file_path in self.log_dir.glob("live_trading.log*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1

        # Count archives
        archive_count = 0
        archive_size = 0
        for file_path in self.archive_dir.glob("*.log.gz"):
            archive_count += 1
            archive_size += file_path.stat().st_size

        # Get log level counts from current file
        level_counts = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
        if self.current_file.exists():
            try:
                with open(self.current_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entry = LogEntry.from_json_line(line.strip())
                            level_counts[entry.level.upper()] = level_counts.get(entry.level.upper(), 0) + 1
                        except:
                            pass
            except:
                pass

        return {
            "log_directory": str(self.log_dir),
            "current_file_size_mb": round(self.current_file.stat().st_size / 1024 / 1024, 2) if self.current_file.exists() else 0,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "file_count": file_count,
            "archive_count": archive_count,
            "archive_size_mb": round(archive_size / 1024 / 1024, 2),
            "level_counts": level_counts,
            "max_file_size_mb": self.max_file_size / 1024 / 1024,
            "max_files": self.max_files
        }

    def cleanup(self, older_than_days: int = 30):
        """Clean up old archives"""
        cutoff = datetime.now() - timedelta(days=older_than_days)
        removed = 0

        for file_path in self.archive_dir.glob("*.log.gz"):
            # Extract date from filename
            match = re.match(r'(\d{4}-\d{2}-\d{2})\.log\.gz', file_path.name)
            if match:
                file_date = datetime.strptime(match.group(1), '%Y-%m-%d')
                if file_date < cutoff:
                    file_path.unlink()
                    removed += 1

        return {"removed_files": removed}

    def archive_current_day(self):
        """Archive today's logs (called at midnight)"""
        if not self.archive_daily:
            return

        today = datetime.now().strftime('%Y-%m-%d')
        archive_path = self.archive_dir / f"{today}.log.gz"

        # Compress current file to archive
        if self.current_file.exists():
            with open(self.current_file, 'rb') as f_in:
                with gzip.open(archive_path, 'ab') as f_out:
                    shutil.copyfileobj(f_in, f_out)
