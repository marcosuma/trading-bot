"""
Daemon Manager - Manages the trading system as a background process.
Handles starting, stopping, and monitoring the daemon.
"""
import os
import sys
import signal
import time
import subprocess
import psutil
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import json


class DaemonManager:
    """
    Manages the live trading daemon process.

    Features:
    - Start/stop/restart daemon
    - PID file management
    - Process monitoring
    - Graceful shutdown
    """

    def __init__(
        self,
        pid_file: str = "live_trading.pid",
        log_dir: str = "logs",
        working_dir: Optional[str] = None
    ):
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.pid_file = self.working_dir / pid_file
        self.log_dir = self.working_dir / log_dir
        self.status_file = self.working_dir / "daemon_status.json"

        # Ensure directories exist
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _get_pid(self) -> Optional[int]:
        """Read PID from file"""
        if not self.pid_file.exists():
            return None
        try:
            with open(self.pid_file, 'r') as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            return None

    def _write_pid(self, pid: int):
        """Write PID to file"""
        with open(self.pid_file, 'w') as f:
            f.write(str(pid))

    def _remove_pid(self):
        """Remove PID file"""
        if self.pid_file.exists():
            self.pid_file.unlink()

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with given PID is running"""
        try:
            process = psutil.Process(pid)
            return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def _update_status(self, status: str, **extra):
        """Update daemon status file"""
        data = {
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "pid": self._get_pid(),
            **extra
        }
        with open(self.status_file, 'w') as f:
            json.dump(data, f, indent=2)

    def get_status(self) -> Dict[str, Any]:
        """Get current daemon status"""
        pid = self._get_pid()

        status = {
            "running": False,
            "pid": None,
            "uptime_seconds": None,
            "memory_mb": None,
            "cpu_percent": None,
            "started_at": None,
            "status_file": str(self.status_file)
        }

        if pid and self._is_process_running(pid):
            try:
                process = psutil.Process(pid)
                status.update({
                    "running": True,
                    "pid": pid,
                    "uptime_seconds": time.time() - process.create_time(),
                    "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
                    "cpu_percent": process.cpu_percent(interval=0.1),
                    "started_at": datetime.fromtimestamp(process.create_time()).isoformat()
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Read status file for additional info
        if self.status_file.exists():
            try:
                with open(self.status_file, 'r') as f:
                    file_status = json.load(f)
                    status["last_status_update"] = file_status.get("timestamp")
                    status["last_status"] = file_status.get("status")
            except:
                pass

        return status

    def start(self, python_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Start the daemon process.

        Returns dict with status and any error message.
        """
        # Check if already running
        pid = self._get_pid()
        if pid and self._is_process_running(pid):
            return {
                "success": False,
                "message": f"Daemon already running with PID {pid}",
                "pid": pid
            }

        # Clean up stale PID file
        self._remove_pid()

        # Determine Python executable
        if python_path is None:
            python_path = sys.executable

        # Build command
        module_path = "live_trading.main"
        cmd = [
            python_path,
            "-m", module_path,
            "--daemon"  # Flag to indicate daemon mode
        ]

        # Output files for stdout/stderr (in addition to structured logs)
        stdout_file = self.log_dir / "daemon_stdout.log"
        stderr_file = self.log_dir / "daemon_stderr.log"

        try:
            # Start process
            with open(stdout_file, 'a') as stdout, open(stderr_file, 'a') as stderr:
                # Write separator
                separator = f"\n{'='*60}\nDaemon started at {datetime.now().isoformat()}\n{'='*60}\n"
                stdout.write(separator)
                stderr.write(separator)
                stdout.flush()
                stderr.flush()

                process = subprocess.Popen(
                    cmd,
                    cwd=str(self.working_dir),
                    stdout=stdout,
                    stderr=stderr,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True  # Detach from terminal
                )

            # Write PID
            self._write_pid(process.pid)
            self._update_status("starting", command=" ".join(cmd))

            # Wait briefly to check if process started successfully
            time.sleep(1)

            if self._is_process_running(process.pid):
                self._update_status("running")
                return {
                    "success": True,
                    "message": f"Daemon started successfully",
                    "pid": process.pid,
                    "stdout_log": str(stdout_file),
                    "stderr_log": str(stderr_file)
                }
            else:
                self._remove_pid()
                # Read stderr for error message
                error_msg = "Process exited immediately"
                if stderr_file.exists():
                    with open(stderr_file, 'r') as f:
                        lines = f.readlines()[-20:]  # Last 20 lines
                        if lines:
                            error_msg = ''.join(lines)

                return {
                    "success": False,
                    "message": f"Daemon failed to start: {error_msg}",
                    "pid": None
                }

        except Exception as e:
            self._remove_pid()
            return {
                "success": False,
                "message": f"Failed to start daemon: {str(e)}",
                "pid": None
            }

    def stop(self, timeout: int = 30) -> Dict[str, Any]:
        """
        Stop the daemon process gracefully.

        Args:
            timeout: Seconds to wait for graceful shutdown before force kill
        """
        pid = self._get_pid()

        if not pid:
            return {
                "success": True,
                "message": "Daemon not running (no PID file)"
            }

        if not self._is_process_running(pid):
            self._remove_pid()
            return {
                "success": True,
                "message": "Daemon not running (stale PID file removed)"
            }

        try:
            process = psutil.Process(pid)

            # Send SIGTERM for graceful shutdown
            self._update_status("stopping")
            process.terminate()

            # Wait for process to exit
            try:
                process.wait(timeout=timeout)
                self._remove_pid()
                self._update_status("stopped")
                return {
                    "success": True,
                    "message": f"Daemon stopped gracefully (PID {pid})"
                }
            except psutil.TimeoutExpired:
                # Force kill
                process.kill()
                process.wait(timeout=5)
                self._remove_pid()
                self._update_status("killed")
                return {
                    "success": True,
                    "message": f"Daemon force killed after {timeout}s timeout (PID {pid})"
                }

        except psutil.NoSuchProcess:
            self._remove_pid()
            return {
                "success": True,
                "message": "Daemon already stopped"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to stop daemon: {str(e)}"
            }

    def restart(self, python_path: Optional[str] = None) -> Dict[str, Any]:
        """Restart the daemon"""
        stop_result = self.stop()
        if not stop_result["success"]:
            return {
                "success": False,
                "message": f"Failed to stop: {stop_result['message']}"
            }

        # Brief pause
        time.sleep(2)

        start_result = self.start(python_path=python_path)
        return {
            "success": start_result["success"],
            "message": f"Restart: {start_result['message']}",
            "stop_result": stop_result,
            "start_result": start_result
        }

    def get_logs(self, lines: int = 100, log_type: str = "stdout") -> str:
        """Get recent daemon output logs"""
        if log_type == "stdout":
            log_file = self.log_dir / "daemon_stdout.log"
        else:
            log_file = self.log_dir / "daemon_stderr.log"

        if not log_file.exists():
            return f"No {log_type} log file found"

        try:
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        except Exception as e:
            return f"Error reading log: {e}"


# Global instance
_daemon_manager: Optional[DaemonManager] = None


def get_daemon_manager(working_dir: Optional[str] = None) -> DaemonManager:
    """Get or create the global DaemonManager instance"""
    global _daemon_manager
    if _daemon_manager is None:
        _daemon_manager = DaemonManager(working_dir=working_dir)
    return _daemon_manager
