"""
Daemon management for running the trading system in the background.
"""
from .daemon_manager import DaemonManager, get_daemon_manager

__all__ = ['DaemonManager', 'get_daemon_manager']
