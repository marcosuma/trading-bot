#!/usr/bin/env python3
"""
CLI for managing the Live Trading System daemon.

Usage:
    python -m live_trading.cli start      Start the daemon
    python -m live_trading.cli stop       Stop the daemon
    python -m live_trading.cli restart    Restart the daemon
    python -m live_trading.cli status     Check daemon status
    python -m live_trading.cli logs       View recent logs
"""
import argparse
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_status(status: dict):
    """Print daemon status in a formatted way"""
    running = status.get("running", False)

    print(f"\n{Colors.BOLD}{'='*50}{Colors.ENDC}")
    print(f"{Colors.BOLD}Live Trading Daemon Status{Colors.ENDC}")
    print(f"{'='*50}")

    if running:
        print(f"  Status:   {Colors.GREEN}● Running{Colors.ENDC}")
        print(f"  PID:      {status.get('pid', 'N/A')}")

        uptime = status.get("uptime_seconds")
        if uptime:
            hours = int(uptime // 3600)
            minutes = int((uptime % 3600) // 60)
            seconds = int(uptime % 60)
            print(f"  Uptime:   {hours}h {minutes}m {seconds}s")

        if status.get("started_at"):
            print(f"  Started:  {status['started_at']}")

        memory = status.get("memory_mb")
        if memory:
            print(f"  Memory:   {memory} MB")

        cpu = status.get("cpu_percent")
        if cpu is not None:
            print(f"  CPU:      {cpu}%")
    else:
        print(f"  Status:   {Colors.FAIL}○ Stopped{Colors.ENDC}")

    print(f"{'='*50}\n")


def print_logs(logs: list, limit: int):
    """Print logs in a formatted way"""
    level_colors = {
        "DEBUG": Colors.CYAN,
        "INFO": Colors.BLUE,
        "WARNING": Colors.WARNING,
        "ERROR": Colors.FAIL,
        "CRITICAL": Colors.FAIL + Colors.BOLD
    }

    print(f"\n{Colors.BOLD}Recent Logs (last {limit}){Colors.ENDC}")
    print("-" * 80)

    if not logs:
        print("  No logs found")
        return

    for log in logs:
        timestamp = log.get("timestamp", "")[:19]  # Trim to readable format
        level = log.get("level", "INFO")
        logger = log.get("logger", "")
        message = log.get("message", "")

        color = level_colors.get(level, "")

        # Truncate logger name if too long
        if len(logger) > 30:
            logger = "..." + logger[-27:]

        print(f"{Colors.CYAN}{timestamp}{Colors.ENDC} "
              f"{color}{level:8}{Colors.ENDC} "
              f"{Colors.HEADER}{logger:30}{Colors.ENDC} "
              f"{message[:100]}")

    print("-" * 80)


def cmd_start(args):
    """Start the daemon"""
    from live_trading.daemon import get_daemon_manager

    print(f"{Colors.BLUE}Starting Live Trading daemon...{Colors.ENDC}")

    manager = get_daemon_manager(working_dir=args.working_dir)
    result = manager.start(python_path=args.python)

    if result["success"]:
        print(f"{Colors.GREEN}✓ {result['message']}{Colors.ENDC}")
        print(f"  PID: {result.get('pid')}")
        print(f"  Logs: {result.get('stdout_log')}")
        print(f"\nView logs at: http://localhost:3000/logs (if frontend is running)")
        return 0
    else:
        print(f"{Colors.FAIL}✗ {result['message']}{Colors.ENDC}")
        return 1


def cmd_stop(args):
    """Stop the daemon"""
    from live_trading.daemon import get_daemon_manager

    print(f"{Colors.BLUE}Stopping Live Trading daemon...{Colors.ENDC}")

    manager = get_daemon_manager(working_dir=args.working_dir)
    result = manager.stop(timeout=args.timeout)

    if result["success"]:
        print(f"{Colors.GREEN}✓ {result['message']}{Colors.ENDC}")
        return 0
    else:
        print(f"{Colors.FAIL}✗ {result['message']}{Colors.ENDC}")
        return 1


def cmd_restart(args):
    """Restart the daemon"""
    from live_trading.daemon import get_daemon_manager

    print(f"{Colors.BLUE}Restarting Live Trading daemon...{Colors.ENDC}")

    manager = get_daemon_manager(working_dir=args.working_dir)
    result = manager.restart(python_path=args.python)

    if result["success"]:
        print(f"{Colors.GREEN}✓ {result['message']}{Colors.ENDC}")
        return 0
    else:
        print(f"{Colors.FAIL}✗ {result['message']}{Colors.ENDC}")
        return 1


def cmd_status(args):
    """Check daemon status"""
    from live_trading.daemon import get_daemon_manager

    manager = get_daemon_manager(working_dir=args.working_dir)
    status = manager.get_status()

    if args.json:
        print(json.dumps(status, indent=2, default=str))
    else:
        print_status(status)

    return 0 if status.get("running") else 1


def cmd_logs(args):
    """View logs"""
    # Try to fetch from API first (if daemon is running)
    import requests

    api_url = f"http://localhost:{args.port}/api/logs"

    params = {
        "limit": args.limit
    }
    if args.level and args.level != 'ALL':
        params["level"] = args.level
    if args.search:
        params["search"] = args.search
    if args.logger:
        params["logger_name"] = args.logger

    try:
        response = requests.get(api_url, params=params, timeout=5)
        if response.ok:
            data = response.json()
            logs = data.get("logs", [])
            # Reverse to show oldest first (for terminal reading)
            logs = list(reversed(logs))

            if args.json:
                print(json.dumps(logs, indent=2))
            else:
                print_logs(logs, args.limit)
            return 0
    except requests.exceptions.ConnectionError:
        print(f"{Colors.WARNING}Daemon not running or API not accessible.{Colors.ENDC}")
        print("Reading from log files directly...")
    except Exception as e:
        print(f"{Colors.WARNING}API error: {e}{Colors.ENDC}")
        print("Reading from log files directly...")

    # Fall back to reading log files directly
    try:
        from live_trading.logging import get_log_manager

        log_manager = get_log_manager()
        logs = log_manager.get_logs(
            level=args.level if args.level != 'ALL' else None,
            search=args.search,
            logger=args.logger,
            limit=args.limit
        )

        # Reverse to show oldest first
        logs = list(reversed(logs))

        if args.json:
            print(json.dumps(logs, indent=2))
        else:
            print_logs(logs, args.limit)
        return 0
    except Exception as e:
        print(f"{Colors.FAIL}Error reading logs: {e}{Colors.ENDC}")
        return 1


def cmd_tail(args):
    """Tail logs (follow mode)"""
    import time
    import requests

    api_url = f"http://localhost:{args.port}/api/logs"
    last_timestamp = None

    print(f"{Colors.BLUE}Tailing logs (Ctrl+C to stop)...{Colors.ENDC}")
    print("-" * 80)

    try:
        while True:
            params = {"limit": 20}
            if args.level and args.level != 'ALL':
                params["level"] = args.level

            try:
                response = requests.get(api_url, params=params, timeout=5)
                if response.ok:
                    data = response.json()
                    logs = data.get("logs", [])

                    # Filter new logs
                    for log in reversed(logs):
                        ts = log.get("timestamp")
                        if last_timestamp is None or ts > last_timestamp:
                            level = log.get("level", "INFO")
                            color = {
                                "DEBUG": Colors.CYAN,
                                "INFO": Colors.BLUE,
                                "WARNING": Colors.WARNING,
                                "ERROR": Colors.FAIL,
                                "CRITICAL": Colors.FAIL
                            }.get(level, "")

                            print(f"{Colors.CYAN}{ts[:19]}{Colors.ENDC} "
                                  f"{color}{level:8}{Colors.ENDC} "
                                  f"{log.get('message', '')}")
                            last_timestamp = ts

            except requests.exceptions.ConnectionError:
                print(f"{Colors.WARNING}Connection lost, retrying...{Colors.ENDC}")
            except Exception as e:
                print(f"{Colors.WARNING}Error: {e}{Colors.ENDC}")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n{Colors.BLUE}Stopped tailing.{Colors.ENDC}")
        return 0


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Live Trading System Daemon Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m live_trading.cli start           Start the daemon
  python -m live_trading.cli stop            Stop the daemon
  python -m live_trading.cli status          Check if running
  python -m live_trading.cli logs            View recent logs
  python -m live_trading.cli logs -f         Follow logs (tail -f)
  python -m live_trading.cli logs -l ERROR   Show only errors
        """
    )

    parser.add_argument(
        "--working-dir", "-w",
        default=None,
        help="Working directory (default: current directory)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start the daemon")
    start_parser.add_argument(
        "--python",
        default=None,
        help="Python executable path (default: current Python)"
    )

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop the daemon")
    stop_parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=30,
        help="Timeout in seconds for graceful shutdown (default: 30)"
    )

    # Restart command
    restart_parser = subparsers.add_parser("restart", help="Restart the daemon")
    restart_parser.add_argument(
        "--python",
        default=None,
        help="Python executable path"
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Check daemon status")
    status_parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON"
    )

    # Logs command
    logs_parser = subparsers.add_parser("logs", help="View logs")
    logs_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=50,
        help="Number of log entries (default: 50)"
    )
    logs_parser.add_argument(
        "--level", "-l",
        choices=["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="ALL",
        help="Filter by log level"
    )
    logs_parser.add_argument(
        "--search", "-s",
        default=None,
        help="Search in log messages"
    )
    logs_parser.add_argument(
        "--logger",
        default=None,
        help="Filter by logger name"
    )
    logs_parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON"
    )
    logs_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="API port (default: 8000)"
    )
    logs_parser.add_argument(
        "-f", "--follow",
        action="store_true",
        help="Follow logs (like tail -f)"
    )
    logs_parser.add_argument(
        "--interval", "-i",
        type=float,
        default=2.0,
        help="Refresh interval in seconds for follow mode (default: 2)"
    )

    # Tail command (alias for logs -f)
    tail_parser = subparsers.add_parser("tail", help="Tail logs (follow mode)")
    tail_parser.add_argument(
        "--level", "-l",
        choices=["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="ALL",
        help="Filter by log level"
    )
    tail_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="API port (default: 8000)"
    )
    tail_parser.add_argument(
        "--interval", "-i",
        type=float,
        default=2.0,
        help="Refresh interval in seconds (default: 2)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Handle follow flag for logs command
    if args.command == "logs" and args.follow:
        return cmd_tail(args)

    # Route to appropriate command
    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "status": cmd_status,
        "logs": cmd_logs,
        "tail": cmd_tail
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        return cmd_func(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
