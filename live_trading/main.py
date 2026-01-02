"""
Main entry point for live trading system.
"""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from live_trading.api.main import app
from live_trading.config import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point"""
    logger.info("Starting Live Trading System...")
    logger.info(f"MongoDB: {config.MONGODB_URL}/{config.MONGODB_DB_NAME}")
    logger.info(f"Broker: {config.BROKER_TYPE}")
    logger.info(f"API Server: {config.API_HOST}:{config.API_PORT}")

    # Run FastAPI server
    uvicorn.run(
        "live_trading.api.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        log_level=config.LOG_LEVEL.lower(),
        reload=False  # Set to True for development
    )


if __name__ == "__main__":
    main()

