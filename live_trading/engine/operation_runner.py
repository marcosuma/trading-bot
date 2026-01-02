"""
Operation Runner - Manages a single trading operation.
"""
import logging
import asyncio
from typing import Dict, Optional
from datetime import datetime
from bson import ObjectId

from live_trading.data.data_manager import DataManager
from live_trading.strategies.strategy_adapter import StrategyAdapter
from live_trading.orders.order_manager import OrderManager
from live_trading.models.trading_operation import TradingOperation
from forex_strategies.strategy_registry import get_strategy

logger = logging.getLogger(__name__)


class OperationRunner:
    """Manages a single trading operation"""

    def __init__(
        self,
        operation_id: ObjectId,
        data_manager: DataManager,
        order_manager: OrderManager
    ):
        self.operation_id = operation_id
        self.data_manager = data_manager
        self.order_manager = order_manager
        self.strategy_adapter: Optional[StrategyAdapter] = None
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self):
        """Start the operation"""
        operation = await TradingOperation.get(self.operation_id)
        if not operation:
            raise ValueError(f"Operation {self.operation_id} not found")

        if operation.status != "active":
            raise ValueError(f"Operation {self.operation_id} is not active")

        # Get strategy class
        strategy_class = get_strategy(operation.strategy_name)

        if strategy_class is None:
            raise ValueError(f"Strategy {operation.strategy_name} not found")

        # Create strategy adapter
        self.strategy_adapter = StrategyAdapter(
            strategy_class=strategy_class,
            strategy_config=operation.strategy_config,
            data_manager=self.data_manager,
            operation_id=str(self.operation_id),
            bar_sizes=operation.bar_sizes,
            primary_bar_size=operation.primary_bar_size
        )

        # Set signal callback
        self.strategy_adapter.set_signal_callback(self._handle_signal)

        # Register with data manager
        self.data_manager.register_operation(
            operation_id=str(self.operation_id),
            bar_sizes=operation.bar_sizes,
            callback=self._on_new_bar
        )

        # Store the event loop for use in the callback
        # This is the event loop from the async context where start() is called
        try:
            self.event_loop = asyncio.get_running_loop()
        except RuntimeError:
            # If we're not in an async context, try to get the current loop
            try:
                self.event_loop = asyncio.get_event_loop()
            except RuntimeError:
                logger.warning("No event loop available - tick processing may not work")
                self.event_loop = None

        # Subscribe to market data from broker
        # Create a callback that routes broker ticks to data manager
        # Note: Broker callbacks are synchronous and run in the IBKR API thread,
        # so we need to use run_coroutine_threadsafe to schedule async work
        def broker_tick_callback(tick_data: Dict):
            """Callback to route broker ticks to data manager"""
            if tick_data.get("type") == "tick":
                # Extract price from tick data
                # IBKR sends different tick types (bid, ask, last, etc.)
                price = tick_data.get("price")
                size = tick_data.get("size", 0.0)
                timestamp = tick_data.get("timestamp", datetime.utcnow())

                if price is not None and self.event_loop is not None:
                    # Schedule async work from the IBKR thread to the main event loop
                    # This is the correct way to call async functions from a different thread
                    try:
                        coro = self.data_manager.handle_tick(
                            operation_id=str(self.operation_id),
                            asset=operation.asset,
                            price=price,
                            size=size,
                            timestamp=timestamp
                        )
                        # Schedule the coroutine in the main event loop
                        future = asyncio.run_coroutine_threadsafe(coro, self.event_loop)
                        # Don't wait for the result - fire and forget
                        # The future will be executed in the main event loop
                    except Exception as e:
                        logger.error(f"Error scheduling tick processing: {e}", exc_info=True)
                elif price is not None:
                    logger.warning(f"Received tick but no event loop available (price: {price})")

        # Get broker from data manager and subscribe
        if self.data_manager.broker:
            subscribed = await self.data_manager.broker.subscribe_market_data(
                asset=operation.asset,
                callback=broker_tick_callback
            )
            if subscribed:
                logger.info(f"Subscribed to market data for {operation.asset}")
            else:
                logger.warning(f"Failed to subscribe to market data for {operation.asset}")
        else:
            logger.warning("Broker not available - cannot subscribe to market data")

        self.running = True
        logger.info(f"Operation {self.operation_id} started")

    async def stop(self):
        """Stop the operation"""
        self.running = False

        # Unregister from data manager
        self.data_manager.unregister_operation(str(self.operation_id))

        # Cancel task if running
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info(f"Operation {self.operation_id} stopped")

    async def pause(self):
        """Pause the operation"""
        operation = await TradingOperation.get(self.operation_id)
        if operation:
            operation.status = "paused"
            await operation.save()
            logger.info(f"Operation {self.operation_id} paused")

    async def resume(self):
        """Resume the operation"""
        operation = await TradingOperation.get(self.operation_id)
        if operation:
            operation.status = "active"
            await operation.save()
            logger.info(f"Operation {self.operation_id} resumed")

    async def _on_new_bar(self, bar_data: Dict, indicators: Dict):
        """Callback when a new bar is completed"""
        if not self.running:
            return

        # Get bar size from bar_data (need to pass this through)
        # For now, use primary bar size
        operation = await TradingOperation.get(self.operation_id)
        if operation and self.strategy_adapter:
            await self.strategy_adapter.on_new_bar(
                operation.primary_bar_size,
                bar_data,
                indicators
            )

    async def _handle_signal(
        self,
        operation_id: str,
        signal_type: str,
        price: float
    ):
        """Handle trading signal from strategy"""
        operation = await TradingOperation.get(self.operation_id)
        if not operation or operation.status != "active":
            return

        # Place order
        try:
            await self.order_manager.place_order(
                operation_id=self.operation_id,
                asset=operation.asset,
                signal_type=signal_type,
                price=price
            )
        except Exception as e:
            logger.error(f"Error placing order for signal {signal_type}: {e}")

