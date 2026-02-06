"""
Pepperstone Broker Adapter using MetaTrader5 API.
"""
import asyncio
import logging
import threading
from typing import Callable, Optional, Dict, Any
from datetime import datetime
import time

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None

from live_trading.brokers.base_broker import BaseBroker
from live_trading.config import config

logger = logging.getLogger(__name__)


class PepperstoneBroker(BaseBroker):
    """Pepperstone Broker Adapter using MetaTrader5 API"""

    def __init__(self):
        if not MT5_AVAILABLE:
            logger.warning(
                "MetaTrader5 module not found. Please install it: pip install MetaTrader5"
            )
        self.connected = False
        self.account_info: Optional[Dict[str, Any]] = None
        self._data_subscriptions: Dict[str, bool] = {}  # asset -> subscribed
        self._data_callbacks: Dict[str, Callable] = {}  # asset -> callback
        self._tick_threads: Dict[str, threading.Thread] = {}  # asset -> thread
        self._stop_tick_threads: Dict[str, bool] = {}  # asset -> stop flag

    def _convert_asset_to_symbol(self, asset: str) -> str:
        """
        Convert asset format (USD-CAD) to MT5 symbol format.
        Pepperstone typically uses formats like 'USDCAD' or 'EURUSD'.
        """
        # Remove hyphen and convert to uppercase
        symbol = asset.replace("-", "").upper()
        return symbol

    def _convert_symbol_to_asset(self, symbol: str) -> str:
        """Convert MT5 symbol (USDCAD) to asset format (USD-CAD)"""
        # For major pairs, insert hyphen after 3 characters
        if len(symbol) == 6:
            return f"{symbol[:3]}-{symbol[3:]}"
        return symbol

    async def connect(self) -> bool:
        """Connect to Pepperstone via MetaTrader5"""
        if not MT5_AVAILABLE:
            logger.error(
                "MetaTrader5 module not available. Please install: pip install MetaTrader5"
            )
            return False

        try:
            # Initialize MT5 connection
            # Note: MT5 terminal must be installed and running
            # Login credentials should be set in MT5 terminal or passed here
            login = config.PEPPERSTONE_LOGIN
            password = config.PEPPERSTONE_PASSWORD
            server = config.PEPPERSTONE_SERVER

            if not login or not password or not server:
                logger.error(
                    "Pepperstone credentials not set. Please set PEPPERSTONE_LOGIN, "
                    "PEPPERSTONE_PASSWORD, and PEPPERSTONE_SERVER in environment variables"
                )
                return False

            # Initialize MT5
            if not mt5.initialize():
                error_code = mt5.last_error()
                logger.error(f"MT5 initialization failed. Error code: {error_code}")
                logger.error(f"Error description: {mt5.last_error()}")
                logger.error(
                    "Make sure MetaTrader5 terminal is installed and running. "
                    "You can download it from: https://www.metatrader5.com/"
                )
                return False

            # Login to account
            authorized = mt5.login(login=int(login), password=password, server=server)

            if not authorized:
                error_code = mt5.last_error()
                logger.error(f"MT5 login failed. Error code: {error_code}")
                logger.error(f"Error description: {mt5.last_error()}")
                logger.error(
                    "Please check your login credentials and ensure the account is active."
                )
                mt5.shutdown()
                return False

            # Get account info
            account_info = mt5.account_info()
            if account_info is None:
                logger.error("Failed to retrieve account information")
                mt5.shutdown()
                return False

            self.account_info = {
                "login": account_info.login,
                "balance": account_info.balance,
                "equity": account_info.equity,
                "margin": account_info.margin,
                "free_margin": account_info.margin_free,
                "margin_level": account_info.margin_level,
                "currency": account_info.currency,
                "server": account_info.server,
                "company": account_info.company,
            }

            self.connected = True
            logger.info("Successfully connected to Pepperstone via MT5")
            logger.info(f"Account: {account_info.login}")
            logger.info(f"Server: {account_info.server}")
            logger.info(f"Balance: {account_info.balance} {account_info.currency}")
            logger.info(f"Equity: {account_info.equity} {account_info.currency}")
            return True

        except Exception as e:
            logger.error(f"Error connecting to Pepperstone: {e}", exc_info=True)
            if MT5_AVAILABLE:
                mt5.shutdown()
            return False

    async def disconnect(self):
        """Disconnect from Pepperstone"""
        # Stop all tick threads
        for asset in list(self._stop_tick_threads.keys()):
            self._stop_tick_threads[asset] = True

        # Wait for threads to finish
        for asset, thread in list(self._tick_threads.items()):
            if thread.is_alive():
                thread.join(timeout=2.0)

        # Unsubscribe from all market data
        for asset in list(self._data_subscriptions.keys()):
            await self.unsubscribe_market_data(asset)

        if MT5_AVAILABLE and self.connected:
            mt5.shutdown()

        self.connected = False
        self.account_info = None
        logger.info("Disconnected from Pepperstone")

    def _tick_loop(self, asset: str, symbol: str):
        """Background thread to poll for tick data"""
        while not self._stop_tick_threads.get(asset, False):
            try:
                # Get latest tick
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    logger.warning(f"No tick data available for {symbol}")
                    time.sleep(1)
                    continue

                # Calculate mid price
                bid = tick.bid
                ask = tick.ask
                mid_price = (bid + ask) / 2.0

                # Call callback if registered
                if asset in self._data_callbacks:
                    callback = self._data_callbacks[asset]
                    # MT5 tick.time is a datetime object
                    tick_time = tick.time if hasattr(tick.time, 'year') else datetime.utcnow()
                    callback({
                        "type": "tick",
                        "tick_type": 0,  # MID
                        "tick_name": "MID",
                        "price": mid_price,
                        "bid": bid,
                        "ask": ask,
                        "timestamp": tick_time
                    })

                # Sleep briefly before next poll
                time.sleep(0.1)  # 10 ticks per second

            except Exception as e:
                logger.error(f"Error in tick loop for {asset}: {e}", exc_info=True)
                time.sleep(1)

    async def subscribe_market_data(
        self,
        asset: str,
        callback: Callable[[Dict[str, Any]], None],
        callback_id: str = None
    ) -> bool:
        """Subscribe to real-time market data (callback_id not yet supported)"""
        if not self.connected or not MT5_AVAILABLE:
            logger.error("Not connected to Pepperstone")
            return False

        # Unsubscribe if already subscribed
        if asset in self._data_subscriptions:
            await self.unsubscribe_market_data(asset)

        symbol = self._convert_asset_to_symbol(asset)

        # Check if symbol is available
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.error(f"Symbol {symbol} not found. Available symbols may differ.")
            logger.error("Please check the symbol name in MT5 terminal.")
            return False

        # Enable symbol in market watch if not already enabled
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                logger.error(f"Failed to enable symbol {symbol} in market watch")
                return False

        # Store callback
        self._data_callbacks[asset] = callback

        # Start tick polling thread
        self._stop_tick_threads[asset] = False
        tick_thread = threading.Thread(
            target=self._tick_loop,
            args=(asset, symbol),
            daemon=True
        )
        tick_thread.start()
        self._tick_threads[asset] = tick_thread
        self._data_subscriptions[asset] = True

        logger.info(f"Subscribed to market data for {asset} (symbol: {symbol})")
        return True

    async def unsubscribe_market_data(self, asset: str, callback_id: str = None):
        """Unsubscribe from market data (callback_id not yet supported)"""
        if asset in self._data_subscriptions:
            # Stop tick thread
            self._stop_tick_threads[asset] = True

            # Wait for thread to finish
            if asset in self._tick_threads:
                thread = self._tick_threads[asset]
                if thread.is_alive():
                    thread.join(timeout=2.0)
                del self._tick_threads[asset]

            # Cleanup
            del self._data_subscriptions[asset]
            if asset in self._data_callbacks:
                del self._data_callbacks[asset]
            if asset in self._stop_tick_threads:
                del self._stop_tick_threads[asset]

            logger.info(f"Unsubscribed from market data for {asset}")

    async def place_order(
        self,
        asset: str,
        action: str,  # 'BUY' or 'SELL'
        quantity: float,
        order_type: str = "MARKET",  # 'MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT'
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_status_callback: Optional[Callable] = None
    ) -> str:
        """Place an order"""
        if not self.connected or not MT5_AVAILABLE:
            logger.error("Not connected to Pepperstone")
            return ""

        symbol = self._convert_asset_to_symbol(asset)

        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.error(f"Symbol {symbol} not found")
            return ""

        # Calculate lot size (MT5 uses lots, typically 0.01 = 1 micro lot)
        # For forex, 1 lot = 100,000 units
        # quantity is in units, so we need to convert to lots
        lot_size = symbol_info.trade_contract_size  # Usually 100000 for forex
        lots = quantity / lot_size

        # Round to symbol's lot step
        lot_step = symbol_info.volume_step
        lots = round(lots / lot_step) * lot_step

        # Ensure minimum lot size
        if lots < symbol_info.volume_min:
            logger.error(f"Quantity too small. Minimum: {symbol_info.volume_min} lots")
            return ""

        # Determine order type
        if order_type == "MARKET":
            order_type_mt5 = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
        elif order_type == "LIMIT":
            order_type_mt5 = mt5.ORDER_TYPE_BUY_LIMIT if action == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
        elif order_type == "STOP":
            order_type_mt5 = mt5.ORDER_TYPE_BUY_STOP if action == "BUY" else mt5.ORDER_TYPE_SELL_STOP
        elif order_type == "STOP_LIMIT":
            # MT5 doesn't have direct STOP_LIMIT, use STOP with price
            order_type_mt5 = mt5.ORDER_TYPE_BUY_STOP if action == "BUY" else mt5.ORDER_TYPE_SELL_STOP
        else:
            logger.error(f"Unsupported order type: {order_type}")
            return ""

        # Get current price for market orders
        if order_type == "MARKET":
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logger.error(f"Failed to get current price for {symbol}")
                return ""
            price = tick.ask if action == "BUY" else tick.bid

        # Prepare order request
        request = {
            "action": mt5.TRADE_ACTION_DEAL if order_type == "MARKET" else mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": lots,
            "type": order_type_mt5,
            "price": price,
            "deviation": 20,  # Slippage in points
            "magic": 234000,  # Magic number for order identification
            "comment": f"Trading Bot {action}",
            "type_time": mt5.ORDER_TIME_GTC,  # Good till cancelled
            "type_filling": mt5.ORDER_FILLING_IOC,  # Immediate or Cancel
        }

        # Add stop loss and take profit
        if stop_loss:
            request["sl"] = stop_loss
        if take_profit:
            request["tp"] = take_profit

        # Send order
        result = mt5.order_send(request)
        if result is None:
            logger.error(f"Order send failed. Error: {mt5.last_error()}")
            return ""

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed. Retcode: {result.retcode}, Comment: {result.comment}")
            return ""

        order_id = str(result.order)
        logger.info(
            f"Order placed: {order_id} ({order_type} {action} {lots} lots of {symbol} @ {price})"
        )

        # Call order status callback if provided
        if order_status_callback:
            order_status_callback({
                "order_id": order_id,
                "status": "FILLED" if order_type == "MARKET" else "PENDING",
                "filled": lots if order_type == "MARKET" else 0.0,
                "remaining": 0.0 if order_type == "MARKET" else lots,
                "avg_fill_price": result.price if order_type == "MARKET" else None,
                "last_fill_price": result.price if order_type == "MARKET" else None
            })

        return order_id

    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an order"""
        if not self.connected or not MT5_AVAILABLE:
            return False

        try:
            # Get order info
            order_id = int(broker_order_id)
            order = mt5.orders_get(ticket=order_id)
            if order is None or len(order) == 0:
                logger.warning(f"Order {order_id} not found")
                return False

            order_info = order[0]

            # Delete pending order
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": order_id,
            }

            result = mt5.order_send(request)
            if result is None:
                logger.error(f"Order cancellation failed. Error: {mt5.last_error()}")
                return False

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Order cancellation failed. Retcode: {result.retcode}")
                return False

            logger.info(f"Cancelled order: {order_id}")
            return True

        except Exception as e:
            logger.error(f"Error cancelling order: {e}", exc_info=True)
            return False

    async def get_positions(self) -> list[Dict[str, Any]]:
        """Get current positions"""
        if not self.connected or not MT5_AVAILABLE:
            return []

        try:
            positions = mt5.positions_get()
            if positions is None:
                return []

            positions_list = []
            for pos in positions:
                symbol = pos.symbol
                asset = self._convert_symbol_to_asset(symbol)

                # Determine position type
                if pos.type == mt5.POSITION_TYPE_BUY:
                    position_type = "LONG"
                    quantity = pos.volume * pos.symbol_info().trade_contract_size
                else:
                    position_type = "SHORT"
                    quantity = -pos.volume * pos.symbol_info().trade_contract_size

                positions_list.append({
                    "asset": asset,
                    "symbol": symbol,
                    "quantity": quantity,
                    "position_type": position_type,
                    "avg_price": pos.price_open,
                    "current_price": pos.price_current,
                    "unrealized_pnl": pos.profit,
                    "unrealized_pnl_pct": (pos.profit / (pos.price_open * abs(quantity))) * 100 if quantity != 0 else 0
                })

            return positions_list

        except Exception as e:
            logger.error(f"Error getting positions: {e}", exc_info=True)
            return []

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        if not self.connected or not MT5_AVAILABLE:
            return {}

        try:
            account_info = mt5.account_info()
            if account_info is None:
                return {}

            return {
                "account_id": str(account_info.login),
                "currency": account_info.currency,
                "balance": account_info.balance,
                "equity": account_info.equity,
                "margin_used": account_info.margin,
                "margin_available": account_info.margin_free,
                "margin_level": account_info.margin_level,
                "unrealized_pnl": account_info.profit,
                "open_trade_count": len(mt5.positions_get() or []),
                "open_position_count": len(mt5.positions_get() or [])
            }

        except Exception as e:
            logger.error(f"Error getting account info: {e}", exc_info=True)
            return {}

    async def fetch_historical_data(
        self,
        asset: str,
        bar_size: str,
        interval: str,
        callback: Callable[[list, Dict], None],
        context: Optional[Dict] = None
    ) -> bool:
        """
        Fetch historical data for an asset.

        Args:
            asset: Asset symbol (e.g., "USD-CAD")
            bar_size: Bar size (e.g., "1 hour", "15 mins")
            interval: Time period (e.g., "1 Y", "6 M")
            callback: Callback function(bars: list, context: dict) called when data is complete
            context: Optional context dict passed to callback

        Returns:
            True if request was sent successfully
        """
        if not self.connected or not MT5_AVAILABLE:
            logger.error("Not connected to Pepperstone")
            return False

        symbol = self._convert_asset_to_symbol(asset)

        # Convert bar_size to MT5 timeframe
        timeframe_map = {
            "1 min": mt5.TIMEFRAME_M1,
            "5 mins": mt5.TIMEFRAME_M5,
            "15 mins": mt5.TIMEFRAME_M15,
            "30 mins": mt5.TIMEFRAME_M30,
            "1 hour": mt5.TIMEFRAME_H1,
            "4 hours": mt5.TIMEFRAME_H4,
            "1 day": mt5.TIMEFRAME_D1,
            "1 week": mt5.TIMEFRAME_W1,
            "1 month": mt5.TIMEFRAME_MN1,
        }

        timeframe = timeframe_map.get(bar_size)
        if timeframe is None:
            logger.error(f"Unsupported bar size: {bar_size}")
            return False

        # Parse interval (e.g., "1 Y" = 1 year, "6 M" = 6 months)
        # For simplicity, convert to number of bars
        # MT5 copy_rates_from requires datetime
        from datetime import timedelta
        import re

        interval_match = re.match(r"(\d+)\s*([YMD])", interval.upper())
        if interval_match:
            value = int(interval_match.group(1))
            unit = interval_match.group(2)

            if unit == "Y":
                days = value * 365
            elif unit == "M":
                days = value * 30
            else:  # D
                days = value

            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
        else:
            # Default to 1 year
            start_time = datetime.now() - timedelta(days=365)
            end_time = datetime.now()

        try:
            # Fetch historical data
            rates = mt5.copy_rates_range(symbol, timeframe, start_time, end_time)
            if rates is None:
                logger.error(f"Failed to fetch historical data for {symbol}")
                return False

            # Convert to list of dicts
            bars = []
            for rate in rates:
                bars.append({
                    "date": datetime.fromtimestamp(rate[0]),
                    "open": float(rate[1]),
                    "high": float(rate[2]),
                    "low": float(rate[3]),
                    "close": float(rate[4]),
                    "volume": float(rate[5])
                })

            # Call callback
            callback(bars, context or {})

            logger.info(f"Fetched {len(bars)} bars of historical data for {asset}")
            return True

        except Exception as e:
            logger.error(f"Error fetching historical data: {e}", exc_info=True)
            return False

