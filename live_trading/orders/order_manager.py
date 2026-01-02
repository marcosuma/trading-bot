"""
Order Manager - Handles order placement, position management, and P/L calculation.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from live_trading.models.order import Order
from live_trading.models.transaction import Transaction
from live_trading.models.position import Position
from live_trading.models.trade import Trade
from live_trading.models.trading_operation import TradingOperation
from live_trading.brokers.base_broker import BaseBroker
from live_trading.journal.journal_manager import JournalManager

logger = logging.getLogger(__name__)


class OrderManager:
    """Manages orders, positions, and trades"""

    def __init__(
        self,
        broker: BaseBroker,
        journal_manager: JournalManager
    ):
        self.broker = broker
        self.journal = journal_manager

    async def place_order(
        self,
        operation_id: ObjectId,
        asset: str,
        signal_type: str,  # 'BUY' or 'SELL'
        price: Optional[float] = None,
        quantity: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Order:
        """
        Place an order based on strategy signal.

        Args:
            operation_id: Trading operation ID
            asset: Asset symbol
            signal_type: 'BUY' or 'SELL'
            price: Entry price (for limit orders) or None (for market orders)
            quantity: Order quantity (if None, uses default from operation)
            stop_loss: Stop loss price (if None, calculated from operation config)
            take_profit: Take profit price (if None, calculated from operation config)

        Returns:
            Created Order document
        """
        # Get operation
        operation = await TradingOperation.get(operation_id)
        if not operation:
            raise ValueError(f"Operation {operation_id} not found")

        # Determine order type
        order_type = "LIMIT" if price else "MARKET"

        # Calculate stop loss and take profit if not provided
        if stop_loss is None or take_profit is None:
            # Get current market price if needed
            entry_price = price
            if entry_price is None:
                # TODO: Get current market price from broker
                entry_price = 0.0  # Placeholder

            # Determine position type
            position_type = "LONG" if signal_type == "BUY" else "SHORT"

            if stop_loss is None:
                stop_loss = await self.calculate_stop_loss(
                    operation_id,
                    entry_price,
                    position_type
                )

            if take_profit is None:
                take_profit = await self.calculate_take_profit(
                    operation_id,
                    entry_price,
                    stop_loss,
                    position_type
                )

        # Place order with broker
        broker_order_id = await self.broker.place_order(
            asset=asset,
            action=signal_type,
            quantity=quantity or 1.0,  # TODO: Get default quantity from operation
            order_type=order_type,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        # Create order record
        order = Order(
            operation_id=operation_id,
            broker_order_id=broker_order_id,
            order_type=order_type,
            action=signal_type,
            quantity=quantity or 1.0,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status="PENDING"
        )
        await order.insert()

        # Log to journal
        await self.journal.log_action(
            action_type="ORDER_PLACED",
            action_data={
                "order_id": str(order.id),
                "broker_order_id": broker_order_id,
                "asset": asset,
                "action": signal_type,
                "quantity": quantity,
                "price": price,
                "stop_loss": stop_loss,
                "take_profit": take_profit
            },
            operation_id=operation_id
        )

        logger.info(f"Order placed: {signal_type} {quantity} {asset} @ {price or 'MARKET'}")
        return order

    async def calculate_stop_loss(
        self,
        operation_id: ObjectId,
        entry_price: float,
        position_type: str
    ) -> float:
        """
        Calculate stop loss price based on operation configuration.

        Args:
            operation_id: Trading operation ID
            entry_price: Entry price
            position_type: 'LONG' or 'SHORT'

        Returns:
            Stop loss price
        """
        operation = await TradingOperation.get(operation_id)
        if not operation:
            raise ValueError(f"Operation {operation_id} not found")

        stop_loss_type = operation.stop_loss_type
        stop_loss_value = operation.stop_loss_value

        if stop_loss_type == "ATR":
            # TODO: Get ATR value from latest bar
            atr_value = 0.001  # Placeholder - should get from market data
            stop_distance = stop_loss_value * atr_value
        elif stop_loss_type == "PERCENTAGE":
            stop_distance = stop_loss_value * entry_price
        elif stop_loss_type == "FIXED":
            stop_distance = stop_loss_value
        else:
            raise ValueError(f"Unknown stop_loss_type: {stop_loss_type}")

        # Calculate stop loss price
        if position_type == "LONG":
            stop_loss = entry_price - stop_distance
        else:  # SHORT
            stop_loss = entry_price + stop_distance

        return stop_loss

    async def calculate_take_profit(
        self,
        operation_id: ObjectId,
        entry_price: float,
        stop_loss_price: float,
        position_type: str
    ) -> float:
        """
        Calculate take profit price based on operation configuration.

        Args:
            operation_id: Trading operation ID
            entry_price: Entry price
            stop_loss_price: Calculated stop loss price
            position_type: 'LONG' or 'SHORT'

        Returns:
            Take profit price
        """
        operation = await TradingOperation.get(operation_id)
        if not operation:
            raise ValueError(f"Operation {operation_id} not found")

        take_profit_type = operation.take_profit_type
        take_profit_value = operation.take_profit_value

        if take_profit_type == "RISK_REWARD":
            # Calculate risk distance
            if position_type == "LONG":
                risk_distance = entry_price - stop_loss_price
            else:  # SHORT
                risk_distance = stop_loss_price - entry_price

            # Take profit = entry ± (risk * reward_ratio)
            profit_distance = risk_distance * take_profit_value

            if position_type == "LONG":
                take_profit = entry_price + profit_distance
            else:  # SHORT
                take_profit = entry_price - profit_distance

        elif take_profit_type == "ATR":
            # TODO: Get ATR value from latest bar
            atr_value = 0.001  # Placeholder
            profit_distance = take_profit_value * atr_value

            if position_type == "LONG":
                take_profit = entry_price + profit_distance
            else:  # SHORT
                take_profit = entry_price - profit_distance

        elif take_profit_type == "PERCENTAGE":
            profit_distance = take_profit_value * entry_price

            if position_type == "LONG":
                take_profit = entry_price + profit_distance
            else:  # SHORT
                take_profit = entry_price - profit_distance

        elif take_profit_type == "FIXED":
            take_profit = take_profit_value

        else:
            raise ValueError(f"Unknown take_profit_type: {take_profit_type}")

        return take_profit

    async def on_order_filled(
        self,
        order_id: ObjectId,
        fill_data: Dict[str, Any]
    ):
        """
        Handle order fill callback.

        - Create transaction record (BUY or SELL, ENTRY or EXIT)
        - Calculate profit for EXIT transactions
        - Link EXIT to corresponding ENTRY transaction
        - Create trade record if position is closed
        """
        order = await Order.get(order_id)
        if not order:
            logger.error(f"Order {order_id} not found")
            return

        # Update order
        order.status = "FILLED"
        order.filled_quantity = fill_data.get("filled", order.quantity)
        order.avg_fill_price = fill_data.get("avg_fill_price", order.price)
        order.filled_at = datetime.utcnow()
        await order.save()

        # Determine if this is ENTRY or EXIT
        # Check if there's an open position for this operation
        open_position = await Position.find_one(
            Position.operation_id == order.operation_id,
            Position.closed_at == None
        )

        if open_position:
            # This is an EXIT transaction
            transaction_role = "EXIT"
            position_type = "LONG" if open_position.quantity > 0 else "SHORT"

            # Create EXIT transaction
            exit_transaction = await self.create_transaction(
                operation_id=order.operation_id,
                order_id=order_id,
                transaction_type=order.action,
                transaction_role=transaction_role,
                position_type=position_type,
                price=order.avg_fill_price,
                quantity=order.filled_quantity,
                commission=order.commission,
                related_entry_transaction_id=open_position.entry_transaction_id if hasattr(open_position, 'entry_transaction_id') else None
            )

            # Calculate profit
            entry_transaction = await Transaction.get(exit_transaction.related_entry_transaction_id)
            if entry_transaction:
                if position_type == "LONG":
                    profit = (exit_transaction.price - entry_transaction.price) * exit_transaction.quantity
                else:  # SHORT
                    profit = (entry_transaction.price - exit_transaction.price) * exit_transaction.quantity

                profit_pct = (profit / (entry_transaction.price * entry_transaction.quantity)) * 100

                exit_transaction.profit = profit
                exit_transaction.profit_pct = profit_pct
                await exit_transaction.save()

            # Close position
            open_position.closed_at = datetime.utcnow()
            await open_position.save()

            # Create trade record
            if entry_transaction:
                await self.create_trade(
                    operation_id=order.operation_id,
                    entry_transaction_id=entry_transaction.id,
                    exit_transaction_id=exit_transaction.id,
                    position_type=position_type
                )

        else:
            # This is an ENTRY transaction
            transaction_role = "ENTRY"
            position_type = "LONG" if order.action == "BUY" else "SHORT"

            # Create ENTRY transaction
            entry_transaction = await self.create_transaction(
                operation_id=order.operation_id,
                order_id=order_id,
                transaction_type=order.action,
                transaction_role=transaction_role,
                position_type=position_type,
                price=order.avg_fill_price,
                quantity=order.filled_quantity,
                commission=order.commission
            )

            # Create position
            position = Position(
                operation_id=order.operation_id,
                contract_symbol=order.operation_id,  # TODO: Get from operation
                quantity=order.filled_quantity if position_type == "LONG" else -order.filled_quantity,
                entry_price=order.avg_fill_price,
                current_price=order.avg_fill_price,
                stop_loss=order.stop_loss,
                take_profit=order.take_profit
            )
            await position.insert()

        # Log to journal
        await self.journal.log_action(
            action_type="ORDER_FILLED",
            action_data={
                "order_id": str(order_id),
                "filled_quantity": order.filled_quantity,
                "avg_fill_price": order.avg_fill_price
            },
            operation_id=order.operation_id
        )

    async def create_transaction(
        self,
        operation_id: ObjectId,
        order_id: ObjectId,
        transaction_type: str,
        transaction_role: str,
        position_type: str,
        price: float,
        quantity: float,
        commission: float,
        related_entry_transaction_id: Optional[ObjectId] = None
    ) -> Transaction:
        """Create a transaction record"""
        transaction = Transaction(
            operation_id=operation_id,
            order_id=order_id,
            transaction_type=transaction_type,
            transaction_role=transaction_role,
            position_type=position_type,
            price=price,
            quantity=quantity,
            commission=commission,
            related_entry_transaction_id=related_entry_transaction_id
        )
        await transaction.insert()
        return transaction

    async def create_trade(
        self,
        operation_id: ObjectId,
        entry_transaction_id: ObjectId,
        exit_transaction_id: ObjectId,
        position_type: str
    ) -> Trade:
        """Create a trade record (completed round-trip)"""
        entry_transaction = await Transaction.get(entry_transaction_id)
        exit_transaction = await Transaction.get(exit_transaction_id)

        if position_type == "LONG":
            pnl = (exit_transaction.price - entry_transaction.price) * entry_transaction.quantity
        else:  # SHORT
            pnl = (entry_transaction.price - exit_transaction.price) * entry_transaction.quantity

        pnl_pct = (pnl / (entry_transaction.price * entry_transaction.quantity)) * 100
        total_commission = entry_transaction.commission + exit_transaction.commission
        duration_seconds = (exit_transaction.executed_at - entry_transaction.executed_at).total_seconds()

        trade = Trade(
            operation_id=operation_id,
            position_type=position_type,
            entry_transaction_id=entry_transaction_id,
            exit_transaction_id=exit_transaction_id,
            entry_price=entry_transaction.price,
            exit_price=exit_transaction.price,
            quantity=abs(entry_transaction.quantity),
            pnl=pnl,
            pnl_pct=pnl_pct,
            total_commission=total_commission,
            entry_time=entry_transaction.executed_at,
            exit_time=exit_transaction.executed_at,
            duration_seconds=duration_seconds
        )
        await trade.insert()
        return trade

    async def update_positions(self, operation_id: ObjectId):
        """Update position P/L"""
        positions = await Position.find(
            Position.operation_id == operation_id,
            Position.closed_at == None
        ).to_list()

        for position in positions:
            # TODO: Get current market price from broker
            current_price = position.current_price  # Placeholder

            # Calculate unrealized P/L
            if position.quantity > 0:  # LONG
                unrealized_pnl = (current_price - position.entry_price) * position.quantity
            else:  # SHORT
                unrealized_pnl = (position.entry_price - current_price) * abs(position.quantity)

            unrealized_pnl_pct = (unrealized_pnl / (position.entry_price * abs(position.quantity))) * 100

            position.current_price = current_price
            position.unrealized_pnl = unrealized_pnl
            position.unrealized_pnl_pct = unrealized_pnl_pct
            await position.save()

    async def close_position(self, operation_id: ObjectId, position_id: ObjectId):
        """Manually close a position"""
        position = await Position.get(position_id)
        if not position or position.closed_at:
            raise ValueError(f"Position {position_id} not found or already closed")

        # Determine exit transaction type
        if position.quantity > 0:  # LONG
            exit_action = "SELL"
        else:  # SHORT
            exit_action = "BUY"

        # Place market order to close
        order = await self.place_order(
            operation_id=operation_id,
            asset=position.contract_symbol,  # TODO: Get from operation
            signal_type=exit_action,
            quantity=abs(position.quantity)
        )

        logger.info(f"Closing position {position_id} with order {order.id}")

    async def handle_crash_recovery(self, operation_id: ObjectId):
        """
        Handle crash recovery for an operation with open positions.

        Checks crash_recovery_mode and applies appropriate strategy:
        - CLOSE_ALL: Close all open positions immediately via market orders
        - RESUME: Resume normal operation, apply emergency stop loss if needed
        - EMERGENCY_EXIT: Close positions if unrealized loss > emergency_stop_loss_pct
        """
        operation = await TradingOperation.get(operation_id)
        if not operation:
            logger.error(f"Operation {operation_id} not found")
            return

        # Get open positions
        open_positions = await Position.find(
            Position.operation_id == operation_id,
            Position.closed_at == None
        ).to_list()

        if not open_positions:
            logger.info(f"No open positions for operation {operation_id}")
            return

        logger.info(f"Found {len(open_positions)} open positions for operation {operation_id}")

        # Update position P/L first
        await self.update_positions(operation_id)

        if operation.crash_recovery_mode == "CLOSE_ALL":
            # Close all positions immediately
            for position in open_positions:
                try:
                    await self.close_position(operation_id, position.id)
                    await self.journal.log_action(
                        action_type="CRASH_RECOVERY_CLOSE",
                        action_data={
                            "position_id": str(position.id),
                            "mode": "CLOSE_ALL"
                        },
                        operation_id=operation_id,
                        notes="Position closed during crash recovery"
                    )
                except Exception as e:
                    logger.error(f"Error closing position {position.id}: {e}")

        elif operation.crash_recovery_mode == "RESUME":
            # Resume normal operation, but check for emergency stop loss
            for position in open_positions:
                if abs(position.unrealized_pnl_pct) > operation.emergency_stop_loss_pct * 100:
                    # Emergency exit
                    try:
                        await self.close_position(operation_id, position.id)
                        await self.journal.log_action(
                            action_type="CRASH_RECOVERY_EMERGENCY_EXIT",
                            action_data={
                                "position_id": str(position.id),
                                "unrealized_pnl_pct": position.unrealized_pnl_pct
                            },
                            operation_id=operation_id,
                            notes=f"Emergency exit due to {position.unrealized_pnl_pct:.2f}% loss"
                        )
                    except Exception as e:
                        logger.error(f"Error in emergency exit for position {position.id}: {e}")

        elif operation.crash_recovery_mode == "EMERGENCY_EXIT":
            # Only close positions exceeding threshold
            for position in open_positions:
                if position.unrealized_pnl_pct < -operation.emergency_stop_loss_pct * 100:
                    try:
                        await self.close_position(operation_id, position.id)
                        await self.journal.log_action(
                            action_type="CRASH_RECOVERY_EMERGENCY_EXIT",
                            action_data={
                                "position_id": str(position.id),
                                "unrealized_pnl_pct": position.unrealized_pnl_pct
                            },
                            operation_id=operation_id,
                            notes=f"Emergency exit due to {position.unrealized_pnl_pct:.2f}% loss"
                        )
                    except Exception as e:
                        logger.error(f"Error in emergency exit for position {position.id}: {e}")

