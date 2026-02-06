"""
OANDA Broker Adapter using v20 REST API.
"""
import asyncio
import logging
import threading
import json
from typing import Callable, Optional, Dict, Any
from datetime import datetime
import websocket  # websocket-client package
from oandapyV20 import API
from oandapyV20.endpoints import accounts, orders, positions, pricing, instruments
from oandapyV20.exceptions import V20Error

from live_trading.brokers.base_broker import BaseBroker
from live_trading.config import config

logger = logging.getLogger(__name__)


class OANDABroker(BaseBroker):
    """OANDA Broker Adapter using v20 REST API"""

    def __init__(self):
        self.api: Optional[API] = None
        self.account_id: Optional[str] = None
        self.connected = False
        self._data_subscriptions: Dict[str, websocket.WebSocketApp] = {}  # asset -> websocket
        self._data_callbacks: Dict[str, Callable] = {}  # asset -> callback
        self._ws_threads: Dict[str, threading.Thread] = {}  # asset -> thread

    def _convert_asset_to_instrument(self, asset: str) -> str:
        """Convert asset format (USD-CAD) to OANDA instrument (USD_CAD)"""
        return asset.replace("-", "_")

    def _convert_instrument_to_asset(self, instrument: str) -> str:
        """Convert OANDA instrument (USD_CAD) to asset format (USD-CAD)"""
        return instrument.replace("_", "-")

    async def connect(self) -> bool:
        """Connect to OANDA API"""
        try:
            if not config.OANDA_API_KEY:
                logger.error("OANDA_API_KEY not set in environment variables")
                return False

            if not config.OANDA_ACCOUNT_ID:
                logger.error("OANDA_ACCOUNT_ID not set in environment variables")
                return False

            # Determine environment (practice or live)
            environment = "practice" if config.OANDA_ENVIRONMENT.upper() == "PRACTICE" else "live"

            # Initialize OANDA API client
            self.api = API(
                access_token=config.OANDA_API_KEY,
                environment=environment
            )
            self.account_id = config.OANDA_ACCOUNT_ID

            # Test connection by fetching account info
            try:
                r = accounts.AccountDetails(accountID=self.account_id)
                response = self.api.request(r)

                if response.get("account"):
                    self.connected = True
                    account_info = response["account"]
                    logger.info(
                        f"Successfully connected to OANDA ({environment} environment)"
                    )
                    logger.info(f"Account ID: {self.account_id}")
                    logger.info(f"Account Currency: {account_info.get('currency', 'N/A')}")
                    logger.info(f"Account Balance: {account_info.get('balance', 'N/A')}")
                    return True
                else:
                    logger.error("Failed to connect to OANDA: Invalid account response")
                    return False
            except V20Error as e:
                logger.error(f"OANDA API error during connection: {e}")
                return False
            except Exception as e:
                logger.error(f"Error connecting to OANDA: {e}", exc_info=True)
                return False

        except Exception as e:
            logger.error(f"Error initializing OANDA API: {e}", exc_info=True)
            return False

    async def disconnect(self):
        """Disconnect from OANDA"""
        # Close all WebSocket connections
        for asset, ws in list(self._data_subscriptions.items()):
            await self.unsubscribe_market_data(asset)

        self.connected = False
        self.api = None
        logger.info("Disconnected from OANDA")

    async def subscribe_market_data(
        self,
        asset: str,
        callback: Callable[[Dict[str, Any]], None],
        callback_id: str = None
    ) -> bool:
        """Subscribe to real-time market data via WebSocket (callback_id not yet supported)"""
        if not self.connected or not self.api:
            logger.error("Not connected to OANDA")
            return False

        # Unsubscribe if already subscribed
        if asset in self._data_subscriptions:
            await self.unsubscribe_market_data(asset)

        instrument = self._convert_asset_to_instrument(asset)

        # Store callback
        self._data_callbacks[asset] = callback

        # OANDA WebSocket URL (v20 streaming API)
        environment = "practice" if config.OANDA_ENVIRONMENT.upper() == "PRACTICE" else "live"
        if environment == "live":
            ws_url = f"wss://stream-fxtrade.oanda.com/v3/accounts/{self.account_id}/pricing/stream"
        else:
            ws_url = f"wss://stream-fxpractice.oanda.com/v3/accounts/{self.account_id}/pricing/stream"

        def on_message(ws, message):
            """Handle incoming WebSocket messages"""
            try:
                data = json.loads(message)

                # Handle pricing updates
                if "type" in data and data["type"] == "PRICE":
                    price_data = data
                    instrument_name = price_data.get("instrument", "")
                    asset_name = self._convert_instrument_to_asset(instrument_name)

                    if asset_name in self._data_callbacks:
                        # Extract bid/ask prices
                        bids = price_data.get("bids", [])
                        asks = price_data.get("asks", [])

                        if bids and asks:
                            bid_price = float(bids[0].get("price", 0))
                            ask_price = float(asks[0].get("price", 0))
                            mid_price = (bid_price + ask_price) / 2.0

                            # Call callback with price data
                            callback({
                                "type": "tick",
                                "tick_type": 0,  # MID
                                "tick_name": "MID",
                                "price": mid_price,
                                "bid": bid_price,
                                "ask": ask_price,
                                "timestamp": datetime.utcnow()
                            })
                            logger.debug(f"Received price update for {asset}: mid={mid_price}, bid={bid_price}, ask={ask_price}")

                # Handle heartbeat
                elif "type" in data and data["type"] == "HEARTBEAT":
                    logger.debug(f"Heartbeat received for {asset}")

            except Exception as e:
                logger.error(f"Error processing WebSocket message for {asset}: {e}", exc_info=True)

        def on_error(ws, error):
            """Handle WebSocket errors"""
            logger.error(f"WebSocket error for {asset}: {error}")

        def on_close(ws, close_status_code, close_msg):
            """Handle WebSocket close"""
            logger.info(f"WebSocket closed for {asset} (code: {close_status_code})")
            if asset in self._data_subscriptions:
                del self._data_subscriptions[asset]
            if asset in self._data_callbacks:
                del self._data_callbacks[asset]

        def on_open(ws):
            """Handle WebSocket open"""
            logger.info(f"WebSocket opened for {asset}")
            # Subscribe to pricing stream for this instrument
            subscribe_msg = {
                "type": "subscribe",
                "instruments": [instrument]
            }
            ws.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to pricing stream for {instrument}")

        # Create WebSocket connection
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open,
            header=[f"Authorization: Bearer {config.OANDA_API_KEY}"]
        )

        # Store WebSocket connection
        self._data_subscriptions[asset] = ws

        # Start WebSocket in a separate thread
        def run_ws():
            ws.run_forever()

        ws_thread = threading.Thread(target=run_ws, daemon=True)
        ws_thread.start()
        self._ws_threads[asset] = ws_thread

        logger.info(f"Subscribed to market data for {asset} (instrument: {instrument})")
        return True

    async def unsubscribe_market_data(self, asset: str, callback_id: str = None):
        """Unsubscribe from market data (callback_id not yet supported)"""
        if asset in self._data_subscriptions:
            ws = self._data_subscriptions[asset]
            try:
                # Unsubscribe from pricing stream
                instrument = self._convert_asset_to_instrument(asset)
                unsubscribe_msg = {
                    "type": "unsubscribe",
                    "instruments": [instrument]
                }
                ws.send(json.dumps(unsubscribe_msg))
                ws.close()
            except Exception as e:
                logger.error(f"Error unsubscribing from {asset}: {e}")

            del self._data_subscriptions[asset]
            if asset in self._data_callbacks:
                del self._data_callbacks[asset]
            if asset in self._ws_threads:
                del self._ws_threads[asset]
            logger.info(f"Unsubscribed from market data for {asset}")

    async def place_order(
        self,
        asset: str,
        action: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> str:
        """Place an order"""
        if not self.connected or not self.api:
            logger.error("Not connected to OANDA")
            return ""

        instrument = self._convert_asset_to_instrument(asset)

        # Convert action to OANDA units
        # OANDA uses positive units for long, negative for short
        units = abs(quantity) if action == "BUY" else -abs(quantity)

        # Build order data
        order_data = {
            "order": {
                "instrument": instrument,
                "units": str(int(units)),
                "type": order_type.upper()
            }
        }

        # Add price for limit/stop orders
        if order_type.upper() in ["LIMIT", "STOP"] and price:
            order_data["order"]["price"] = f"{price:.5f}"

        # Add stop loss
        if stop_loss:
            order_data["order"]["stopLossOnFill"] = {
                "timeInForce": "GTC",
                "price": f"{stop_loss:.5f}"
            }

        # Add take profit
        if take_profit:
            order_data["order"]["takeProfitOnFill"] = {
                "timeInForce": "GTC",
                "price": f"{take_profit:.5f}"
            }

        try:
            r = orders.OrderCreate(accountID=self.account_id, data=order_data)
            response = self.api.request(r)

            if response.get("orderFillTransaction"):
                order_id = response["orderFillTransaction"].get("id", "")
                logger.info(f"Order filled immediately: {order_id}")
                return str(order_id)
            elif response.get("orderCreateTransaction"):
                order_id = response["orderCreateTransaction"].get("id", "")
                logger.info(f"Order placed: {order_id} ({order_type} {action} {quantity} {asset})")
                return str(order_id)
            else:
                logger.error(f"Unexpected order response: {response}")
                return ""
        except V20Error as e:
            logger.error(f"OANDA API error placing order: {e}")
            return ""
        except Exception as e:
            logger.error(f"Error placing order: {e}", exc_info=True)
            return ""

    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an order"""
        if not self.api:
            return False

        try:
            r = orders.OrderCancel(accountID=self.account_id, orderID=broker_order_id)
            response = self.api.request(r)

            if response.get("orderCancelTransaction"):
                logger.info(f"Cancelled order: {broker_order_id}")
                return True
            else:
                logger.warning(f"Order cancellation response: {response}")
                return False
        except V20Error as e:
            logger.error(f"OANDA API error cancelling order: {e}")
            return False
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    async def get_positions(self) -> list[Dict[str, Any]]:
        """Get current positions"""
        if not self.api:
            return []

        try:
            r = positions.OpenPositions(accountID=self.account_id)
            response = self.api.request(r)

            positions_list = []
            if response.get("positions"):
                for pos in response["positions"]:
                    instrument = pos.get("instrument", "")
                    asset = self._convert_instrument_to_asset(instrument)

                    long_units = float(pos.get("long", {}).get("units", 0))
                    short_units = float(pos.get("short", {}).get("units", 0))

                    # Determine position type and quantity
                    if long_units > 0:
                        quantity = long_units
                        position_type = "LONG"
                        avg_price = float(pos.get("long", {}).get("averagePrice", 0))
                    elif short_units < 0:
                        quantity = abs(short_units)
                        position_type = "SHORT"
                        avg_price = float(pos.get("short", {}).get("averagePrice", 0))
                    else:
                        continue  # Skip zero positions

                    positions_list.append({
                        "asset": asset,
                        "instrument": instrument,
                        "quantity": quantity,
                        "position_type": position_type,
                        "avg_price": avg_price,
                        "unrealized_pnl": float(pos.get("unrealizedPL", 0)),
                        "unrealized_pnl_pct": float(pos.get("unrealizedPL", 0)) / (avg_price * quantity) * 100 if avg_price * quantity > 0 else 0
                    })

            return positions_list
        except V20Error as e:
            logger.error(f"OANDA API error getting positions: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting positions: {e}", exc_info=True)
            return []

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        if not self.api:
            return {}

        try:
            r = accounts.AccountDetails(accountID=self.account_id)
            response = self.api.request(r)

            if response.get("account"):
                account = response["account"]
                return {
                    "account_id": account.get("id"),
                    "currency": account.get("currency"),
                    "balance": float(account.get("balance", 0)),
                    "unrealized_pnl": float(account.get("unrealizedPL", 0)),
                    "margin_used": float(account.get("marginUsed", 0)),
                    "margin_available": float(account.get("marginAvailable", 0)),
                    "open_trade_count": int(account.get("openTradeCount", 0)),
                    "open_position_count": int(account.get("openPositionCount", 0))
                }
            return {}
        except V20Error as e:
            logger.error(f"OANDA API error getting account info: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error getting account info: {e}", exc_info=True)
            return {}

