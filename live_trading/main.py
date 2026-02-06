"""
Main entry point for live trading system.
Supports both interactive and daemon modes.
"""
import argparse
import logging
import os
import signal
import sys

import uvicorn

from live_trading.config import config

# Global state
_shutdown_requested = False
_daemon_mode = False


def _signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM signals"""
    global _shutdown_requested

    logger = logging.getLogger(__name__)

    if _shutdown_requested:
        # Second signal - force exit
        logger.warning("Forced shutdown requested, exiting immediately...")
        os._exit(1)

    _shutdown_requested = True
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")

    # Raise KeyboardInterrupt to let uvicorn handle it
    raise KeyboardInterrupt()


def setup_logging(daemon_mode: bool = False):
    """
    Setup logging based on mode.
    In daemon mode, uses file-based logging.
    In interactive mode, uses console logging.
    """
    from live_trading.logging import setup_logging as setup_log_manager

    log_dir = os.environ.get("LOG_DIR", "logs")

    # Setup the modular logging system
    log_manager = setup_log_manager(
        log_dir=log_dir,
        console_level=logging.INFO if not daemon_mode else logging.CRITICAL + 1,
        file_level=logging.DEBUG,
        daemon_mode=daemon_mode
    )

    return log_manager


def main():
    """Main entry point"""
    global _daemon_mode

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Live Trading System")
    parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="Run in daemon mode (background, file logging only)"
    )
    parser.add_argument(
        "--log-dir",
        default=os.environ.get("LOG_DIR", "logs"),
        help="Directory for log files"
    )
    args = parser.parse_args()

    _daemon_mode = args.daemon

    # Set log directory environment variable for consistency
    os.environ["LOG_DIR"] = args.log_dir

    # Setup logging
    log_manager = setup_logging(daemon_mode=_daemon_mode)
    logger = logging.getLogger(__name__)

    # Log startup info
    mode = "DAEMON" if _daemon_mode else "INTERACTIVE"
    logger.info(f"Starting Live Trading System in {mode} mode...")
    logger.info(f"MongoDB: {config.MONGODB_URL}/{config.MONGODB_DB_NAME}")

    # Log broker type with environment variable info
    broker_type_env = os.getenv("BROKER_TYPE", "not set")
    logger.info(f"Broker Type (from env): {broker_type_env}")
    logger.info(f"Broker Type (configured): {config.BROKER_TYPE}")
    logger.info(f"API Server: {config.API_HOST}:{config.API_PORT}")
    logger.info(f"Log Directory: {args.log_dir}")
    logger.info(f"PID: {os.getpid()}")

    # Install signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Run FastAPI server
    try:
        uvicorn.run(
            "live_trading.api.main:app",
            host=config.API_HOST,
            port=config.API_PORT,
            log_level=config.LOG_LEVEL.lower(),
            reload=False,
            access_log=not _daemon_mode  # Disable access log in daemon mode (handled by our logger)
        )
    except KeyboardInterrupt:
        logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Cleanup complete")


if __name__ == "__main__":
    main()
