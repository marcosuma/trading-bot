"""
Configuration module for the trading bot.
Handles debug mode and other configuration settings.
"""
import os

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, skip loading .env file
    # Environment variables can still be set directly
    pass


def is_debug_mode() -> bool:
    """
    Check if debug mode is enabled.

    Debug mode can be enabled by:
    1. Setting DEBUG=true in .env file
    2. Setting DEBUG environment variable

    Returns:
        bool: True if debug mode is enabled, False otherwise
    """
    debug_value = os.getenv("DEBUG", "false").lower()
    return debug_value in ("true", "1", "yes", "on")


# Export debug mode state for easy access
DEBUG = is_debug_mode()

