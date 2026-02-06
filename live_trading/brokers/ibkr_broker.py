"""
IBKR Broker Adapter.
"""
import asyncio
import json
import logging
import os
import threading
import random
from typing import Callable, Optional, Dict, Any, Tuple
from datetime import datetime

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order as IBOrder
from ibapi.common import TickerId, BarData, MarketDataTypeEnum
from ibapi.ticktype import TickTypeEnum

from live_trading.brokers.base_broker import BaseBroker
from live_trading.config import config

logger = logging.getLogger(__name__)


class IBKRWrapper(EWrapper):
    """IBKR API Wrapper for handling callbacks"""

    def __init__(self):
        EWrapper.__init__(self)
        self.data_callbacks: Dict[str, Callable] = {}
        self.order_callbacks: Dict[str, Callable] = {}
        self.historical_data_callbacks: Dict[int, Callable] = {}  # reqId -> callback
        self.historical_data_context: Dict[int, Dict] = {}  # reqId -> context
        self.connected = False
        self.next_valid_id = None
        # Store latest prices per reqId for BID/ASK/LAST
        self._latest_prices: Dict[int, Dict[int, float]] = {}  # reqId -> {tickType: price}
        # Store historical data bars as they arrive
        self._historical_bars: Dict[int, list] = {}  # reqId -> list of bars
        # Store positions
        self._positions: list = []  # List of position dictionaries
        self._positions_event: Optional[threading.Event] = None  # Event to signal positions received
        # Store account info
        self._account_values: Dict[str, str] = {}  # Key -> Value mapping for account info
        self._account_portfolio: Dict[str, Dict] = {}  # Contract key -> portfolio info
        self._account_info_event: Optional[threading.Event] = None  # Event to signal account info received

    def nextValidId(self, orderId: int):
        """Callback when connection is established"""
        self.next_valid_id = orderId
        self.connected = True
        logger.info(f"IBKR connected. Next valid ID: {orderId}")

    def error(self, reqId: TickerId, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """Error callback - comprehensive logging"""
        # Error code categories:
        # 200-299: System/Connection errors (critical)
        # 300-399: Order errors
        # 400-499: Market data errors
        # 500+: Informational messages

        # Log all errors with full context
        logger.info(f"[IBKR_ERROR] reqId={reqId}, errorCode={errorCode}, errorString={errorString}, advancedOrderRejectJson={advancedOrderRejectJson}")

        if errorCode == 200:
            # "No security definition has been found" - contract not found
            logger.error(f"IBKR error {errorCode} (reqId: {reqId}): {errorString}")
            logger.error(f"  This usually means the contract specification is incorrect or the pair is not available")
        elif errorCode in [2104, 2106]:  # Market data farm connection warnings (non-critical)
            logger.debug(f"IBKR warning {errorCode}: {errorString}")
        elif errorCode == 2108:  # Market data farm inactive (warning, not critical)
            logger.warning(f"IBKR warning {errorCode}: {errorString}")
        elif errorCode == 2158:  # Sec-def data farm OK (informational)
            logger.info(f"IBKR info {errorCode}: {errorString}")
        elif errorCode >= 500:  # Informational messages
            logger.info(f"IBKR info {errorCode}: {errorString}")
        else:
            logger.error(f"IBKR error {errorCode} (reqId: {reqId}): {errorString}")

    def tickPrice(self, reqId: TickerId, tickType: int, price: float, attrib):
        """Real-time/delayed price update"""
        try:
            # Comprehensive tick type mapping for all price ticks
            tick_type_names = {
                1: "BID", 2: "ASK", 4: "LAST", 6: "HIGH", 7: "LOW", 9: "CLOSE", 14: "OPEN",
                66: "DELAYED_BID", 67: "DELAYED_ASK", 68: "DELAYED_LAST", 72: "DELAYED_HIGH",
                73: "DELAYED_LOW", 75: "DELAYED_CLOSE", 76: "DELAYED_OPEN"
            }
            tick_name = tick_type_names.get(tickType, f"UNKNOWN({tickType})")
            # Log LAST ticks at INFO level, all others at DEBUG
            if tickType == 4:  # LAST
                logger.info(f"[TICK_PRICE] reqId={reqId}, tickType={tickType}({tick_name}), price={price}, attrib={attrib}")
            else:
                logger.debug(f"[TICK_PRICE] reqId={reqId}, tickType={tickType}({tick_name}), price={price}, attrib={attrib}")

            if reqId in self.data_callbacks:
                # Store latest prices for this reqId
                if reqId not in self._latest_prices:
                    self._latest_prices[reqId] = {}
                self._latest_prices[reqId][tickType] = price

                callback = self.data_callbacks[reqId]

                # Priority: LAST (4) > Mid of BID/ASK > BID (1) > ASK (2)
                # For forex, LAST ticks may be rare, so use BID/ASK as fallback
                use_price = None
                use_tick_type = None

                if tickType == 4:  # LAST - highest priority
                    use_price = price
                    use_tick_type = 4
                elif tickType in [1, 2]:  # BID or ASK
                    # Check if we have both BID and ASK, use mid price
                    latest = self._latest_prices[reqId]
                    if 1 in latest and 2 in latest:
                        use_price = (latest[1] + latest[2]) / 2.0  # Mid price
                        use_tick_type = 0  # MID
                        logger.debug(f"Using mid price {(latest[1] + latest[2]) / 2.0} for reqId {reqId}")
                    elif tickType == 1:  # BID only
                        use_price = price
                        use_tick_type = 1
                    elif tickType == 2:  # ASK only
                        use_price = price
                        use_tick_type = 2

                if use_price is not None:
                    callback({
                        "type": "tick",
                        "tick_type": use_tick_type,
                        "tick_name": tick_type_names.get(use_tick_type, "MID") if use_tick_type != 0 else "MID",
                        "price": use_price,
                        "timestamp": datetime.utcnow()
                    })
                    logger.debug(f"Sent tick to callback: reqId={reqId}, price={use_price}, type={use_tick_type}")
        except Exception as e:
            logger.error(f"Error in tickPrice callback (reqId: {reqId}): {e}", exc_info=True)

    def tickSize(self, reqId: TickerId, tickType: int, size: int):
        """Real-time/delayed size update"""
        try:
            # Comprehensive size tick type mapping
            tick_type_names = {
                0: "BID_SIZE", 3: "ASK_SIZE", 5: "LAST_SIZE", 8: "VOLUME",
                69: "DELAYED_BID_SIZE", 70: "DELAYED_ASK_SIZE", 71: "DELAYED_LAST_SIZE",
                74: "DELAYED_VOLUME"
            }
            tick_name = tick_type_names.get(tickType, f"UNKNOWN({tickType})")
            logger.debug(f"[TICK_SIZE] reqId={reqId}, tickType={tickType}({tick_name}), size={size}")

            if reqId in self.data_callbacks:
                callback = self.data_callbacks[reqId]
                # Size updates are informational, we mainly care about price
                # But we can log them for debugging
                if tickType == 5:  # LAST_SIZE
                    logger.debug(f"Received LAST_SIZE {size} for reqId {reqId}")
        except Exception as e:
            logger.error(f"Error in tickSize callback (reqId: {reqId}): {e}", exc_info=True)

    def tickGeneric(self, reqId: TickerId, tickType: int, value: float):
        """Generic tick update (for non-price data)"""
        # Comprehensive tick type mapping
        tick_type_names = {
            48: "RT_VOLUME", 49: "HALTED", 50: "BID_YIELD", 51: "ASK_YIELD", 52: "LAST_YIELD",
            54: "TRADE_COUNT", 55: "TRADE_RATE", 56: "VOLUME_RATE", 58: "RT_HISTORICAL_VOL",
            59: "IB_DIVIDENDS", 60: "BOND_FACTOR_MULTIPLIER", 61: "REGULATORY_IMBALANCE",
            62: "NEWS_TICK", 63: "SHORT_TERM_VOLUME_3_MIN", 64: "SHORT_TERM_VOLUME_5_MIN",
            65: "SHORT_TERM_VOLUME_10_MIN", 77: "RT_TRD_VOLUME", 78: "CREDITMAN_MARK_PRICE",
            79: "CREDITMAN_SLOW_MARK_PRICE"
        }
        tick_name = tick_type_names.get(tickType, f"UNKNOWN({tickType})")
        logger.info(f"[TICK_GENERIC] reqId={reqId}, tickType={tickType}({tick_name}), value={value}")
        # Don't process generic ticks as price data, but log them for debugging

    def tickString(self, reqId: TickerId, tickType: int, value: str):
        """String tick update (for text-based data)"""
        tick_type_names = {
            32: "BID_EXCH", 33: "ASK_EXCH", 45: "LAST_TIMESTAMP", 46: "SHORTABLE",
            47: "FUNDAMENTAL_RATIOS", 84: "LAST_EXCH", 85: "LAST_REG_TIME"
        }
        tick_name = tick_type_names.get(tickType, f"UNKNOWN({tickType})")
        logger.debug(f"[TICK_STRING] reqId={reqId}, tickType={tickType}({tick_name}), value={value}")

    def tickEFP(self, reqId: TickerId, tickType: int, basisPoints: float, formattedBasisPoints: str, totalDividends: float, holdDays: int, futureLastTradeDate: str, dividendImpact: float, dividendsToLastTradeDate: float):
        """EFP (Exchange for Physical) tick update"""
        logger.info(f"[TICK_EFP] reqId={reqId}, tickType={tickType}, basisPoints={basisPoints}, formattedBasisPoints={formattedBasisPoints}, totalDividends={totalDividends}, holdDays={holdDays}, futureLastTradeDate={futureLastTradeDate}, dividendImpact={dividendImpact}, dividendsToLastTradeDate={dividendsToLastTradeDate}")

    def tickOptionComputation(self, reqId: TickerId, tickType: int, tickAttrib: int, impliedVol: float, delta: float, optPrice: float, pvDividend: float, gamma: float, vega: float, theta: float, undPrice: float):
        """Option computation tick update"""
        logger.info(f"[TICK_OPTION] reqId={reqId}, tickType={tickType}, impliedVol={impliedVol}, delta={delta}, optPrice={optPrice}, gamma={gamma}, vega={vega}, theta={theta}, undPrice={undPrice}")

    def tickByTickAllLast(self, reqId: int, tickType: int, time: int, price: float, size: int, tickAttribLast: dict, exchange: str, specialConditions: str):
        """Tick-by-tick all last trade data"""
        logger.info(f"[TICK_BY_TICK_ALL_LAST] reqId={reqId}, tickType={tickType}, time={time}, price={price}, size={size}, exchange={exchange}, specialConditions={specialConditions}")

    def tickByTickBidAsk(self, reqId: int, time: int, bidPrice: float, askPrice: float, bidSize: int, askSize: int, tickAttribBidAsk: dict):
        """Tick-by-tick bid/ask data"""
        logger.info(f"[TICK_BY_TICK_BID_ASK] reqId={reqId}, time={time}, bidPrice={bidPrice}, askPrice={askPrice}, bidSize={bidSize}, askSize={askSize}")

    def tickByTickMidPoint(self, reqId: int, time: int, midPoint: float):
        """Tick-by-tick midpoint data"""
        logger.info(f"[TICK_BY_TICK_MIDPOINT] reqId={reqId}, time={time}, midPoint={midPoint}")

    def marketDataType(self, reqId: TickerId, marketDataType: int):
        """Callback when market data type is set"""
        market_data_types = {1: "REALTIME", 2: "FROZEN", 3: "DELAYED", 4: "DELAYED_FROZEN"}
        data_type_name = market_data_types.get(marketDataType, f"UNKNOWN({marketDataType})")

        # Log warning if we requested DELAYED but got REALTIME
        if marketDataType == 1:
            logger.warning(f"[MARKET_DATA_TYPE] Received REALTIME (reqId={reqId}) - this may incur costs!")
            logger.warning("  If you requested DELAYED, TWS/Gateway may be overriding it based on your subscriptions.")
            logger.warning("  To use DELAYED data:")
            logger.warning("  1. TWS: Configure > Global Configuration > API > Settings")
            logger.warning("     Uncheck 'Enable ActiveX and Socket Clients' market data subscriptions")
            logger.warning("  2. Or ensure you don't have real-time data subscriptions enabled")
            logger.warning("  3. Gateway: Check market data subscriptions in settings")
        elif marketDataType == 3:
            logger.info(f"[MARKET_DATA_TYPE] ✓ Using DELAYED data (reqId={reqId}) - free, 15-20 min delay")
        else:
            logger.info(f"[MARKET_DATA_TYPE] reqId={reqId}, marketDataType={marketDataType}({data_type_name})")

    def historicalData(self, reqId: int, bar: BarData):
        """Historical data bar received"""
        try:
            # Store bar data
            if reqId not in self._historical_bars:
                self._historical_bars[reqId] = []

            # Convert bar to dict
            bar_dict = {
                "date": bar.date,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume)
            }
            self._historical_bars[reqId].append(bar_dict)

            logger.debug(f"[HISTORICAL_DATA] reqId={reqId}, bar={bar.date}, close={bar.close}")
        except Exception as e:
            logger.error(f"Error in historicalData callback (reqId: {reqId}): {e}", exc_info=True)

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Historical data request completed"""
        try:
            logger.info(f"[HISTORICAL_DATA_END] reqId={reqId}, start={start}, end={end}")

            # Get bars for this request
            bars = self._historical_bars.get(reqId, [])

            # Get callback if registered
            if reqId in self.historical_data_callbacks:
                callback = self.historical_data_callbacks[reqId]
                context = self.historical_data_context.get(reqId, {})

                # Call callback with all bars
                callback(bars, context)

                # Cleanup
                del self.historical_data_callbacks[reqId]
                if reqId in self.historical_data_context:
                    del self.historical_data_context[reqId]

            # Cleanup bars
            if reqId in self._historical_bars:
                del self._historical_bars[reqId]

        except Exception as e:
            logger.error(f"Error in historicalDataEnd callback (reqId: {reqId}): {e}", exc_info=True)

    def orderStatus(
        self,
        orderId: int,
        status: str,
        filled: float,
        remaining: float,
        avgFillPrice: float,
        permId: int,
        parentId: int,
        lastFillPrice: float,
        clientId: int,
        whyHeld: str,
        mktCapPrice: float
    ):
        """Order status update"""
        if str(orderId) in self.order_callbacks:
            callback = self.order_callbacks[str(orderId)]
            callback({
                "order_id": orderId,
                "status": status,
                "filled": filled,
                "remaining": remaining,
                "avg_fill_price": avgFillPrice,
                "last_fill_price": lastFillPrice
            })

        # Handle stop loss and take profit orders after main order is filled
        if status == "Filled" and hasattr(self, '_pending_sl_tp') and str(orderId) in self._pending_sl_tp:
            sl_tp_info = self._pending_sl_tp[str(orderId)]
            # Place stop loss and take profit as separate orders
            # This runs in the IBKR thread, so we place orders directly (synchronously)
            try:
                self._place_sl_tp_orders(sl_tp_info, avgFillPrice, filled)
                # Remove from pending
                del self._pending_sl_tp[str(orderId)]
            except Exception as e:
                logger.error(f"Error placing stop loss/take profit orders: {e}", exc_info=True)

    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        """Position update callback"""
        try:
            # Convert contract to asset format
            if contract.secType == "CASH":
                # Forex: symbol is base currency, currency is quote currency
                asset = f"{contract.symbol}-{contract.currency}"
            else:
                # For other types, use symbol
                asset = contract.symbol

            # Skip zero positions
            if abs(position) < 0.0001:
                return

            # Determine position type
            if position > 0:
                position_type = "LONG"
                quantity = position
            else:
                position_type = "SHORT"
                quantity = abs(position)

            # Get current market price (we'll need to request it or use avgCost as fallback)
            # For now, use avgCost as current_price (will be updated if we have market data)
            current_price = avgCost

            # Calculate unrealized P/L (approximate, will need current price for accurate calculation)
            unrealized_pnl = 0.0  # Will be calculated if we have current price
            unrealized_pnl_pct = 0.0

            position_data = {
                "account": account,
                "asset": asset,
                "symbol": contract.symbol,
                "currency": contract.currency,
                "secType": contract.secType,
                "exchange": contract.exchange,
                "quantity": quantity,
                "position_type": position_type,
                "avg_price": avgCost,
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl,
                "unrealized_pnl_pct": unrealized_pnl_pct
            }

            # Add to positions list
            self._positions.append(position_data)
            logger.debug(f"Position received: {asset}, quantity: {quantity}, avgCost: {avgCost}")

        except Exception as e:
            logger.error(f"Error processing position callback: {e}", exc_info=True)

    def positionEnd(self):
        """Called when all positions have been received"""
        logger.info(f"Position list complete. Received {len(self._positions)} positions")
        if self._positions_event:
            self._positions_event.set()

    def _place_sl_tp_orders(self, sl_tp_info: Dict, fill_price: float, filled_quantity: float):
        """Place stop loss and take profit orders (called from orderStatus callback)"""
        try:
            from ibapi.order import Order as IBOrder
            contract = sl_tp_info["contract"]
            action = sl_tp_info["action"]
            quantity = sl_tp_info["quantity"]
            stop_loss = sl_tp_info.get("stop_loss")
            take_profit = sl_tp_info.get("take_profit")

            # Get the broker instance (stored in wrapper for this purpose)
            # We'll need to pass the client through
            if not hasattr(self, '_broker_client'):
                logger.warning("Cannot place SL/TP orders - broker client not available")
                return

            client = self._broker_client

            # Determine opposite action for stop loss and take profit
            # If we bought, SL/TP are sell orders. If we sold, SL/TP are buy orders.
            opposite_action = "SELL" if action == "BUY" else "BUY"

            # Place stop loss order
            if stop_loss:
                sl_order = IBOrder()
                sl_order.action = opposite_action
                sl_order.totalQuantity = quantity
                sl_order.orderType = "STOP"
                sl_order.auxPrice = stop_loss
                sl_order.parentId = sl_tp_info["parent_order_id"]

                sl_order_id = self._get_next_order_id_for_sl_tp()
                sl_order.orderId = sl_order_id

                try:
                    client.placeOrder(sl_order_id, contract, sl_order)
                    logger.info(f"Placed stop loss order: {sl_order_id} for {sl_tp_info['asset']} @ {stop_loss}")
                except Exception as e:
                    logger.error(f"Error placing stop loss order: {e}", exc_info=True)

            # Place take profit order
            if take_profit:
                tp_order = IBOrder()
                tp_order.action = opposite_action
                tp_order.totalQuantity = quantity
                tp_order.orderType = "LIMIT"
                tp_order.lmtPrice = take_profit
                tp_order.parentId = sl_tp_info["parent_order_id"]

                tp_order_id = self._get_next_order_id_for_sl_tp()
                tp_order.orderId = tp_order_id

                try:
                    client.placeOrder(tp_order_id, contract, tp_order)
                    logger.info(f"Placed take profit order: {tp_order_id} for {sl_tp_info['asset']} @ {take_profit}")
                except Exception as e:
                    logger.error(f"Error placing take profit order: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in _place_sl_tp_orders: {e}", exc_info=True)

    def _get_next_order_id_for_sl_tp(self) -> int:
        """Get next order ID for SL/TP orders"""
        # Use a simple counter, will be initialized by broker
        if not hasattr(self, '_sl_tp_order_counter'):
            # Start from a high number to avoid conflicts with regular orders
            # Regular orders use next_valid_id which is typically lower
            self._sl_tp_order_counter = 100000
        self._sl_tp_order_counter += 1
        return self._sl_tp_order_counter

    def updateAccountValue(self, key: str, val: str, currency: str, accountName: str):
        """Account value update callback"""
        try:
            # Store account value
            self._account_values[key] = val
            logger.debug(f"Account value update: {key} = {val} ({currency})")
        except Exception as e:
            logger.error(f"Error processing account value update: {e}", exc_info=True)

    def updatePortfolio(self, contract: Contract, position: float, marketPrice: float, marketValue: float,
                       averageCost: float, unrealizedPNL: float, realizedPNL: float, accountName: str):
        """Portfolio update callback"""
        try:
            # Create contract key
            if contract.secType == "CASH":
                contract_key = f"{contract.symbol}-{contract.currency}"
            else:
                contract_key = contract.symbol

            self._account_portfolio[contract_key] = {
                "position": position,
                "market_price": marketPrice,
                "market_value": marketValue,
                "average_cost": averageCost,
                "unrealized_pnl": unrealizedPNL,
                "realized_pnl": realizedPNL
            }
            logger.debug(f"Portfolio update: {contract_key}, position: {position}, marketPrice: {marketPrice}")
        except Exception as e:
            logger.error(f"Error processing portfolio update: {e}", exc_info=True)

    def updateAccountTime(self, timeStamp: str):
        """Called when account updates are complete"""
        logger.info(f"Account update complete at {timeStamp}")
        if self._account_info_event:
            self._account_info_event.set()


class IBKRBroker(BaseBroker):
    """IBKR Broker Adapter"""

    def __init__(self):
        self.wrapper = IBKRWrapper()
        self.wrapper._broker_client = None  # Will be set after client is created
        self.client: Optional[EClient] = None
        self.connected = False
        self._req_id_counter = 0
        self._order_id_counter = 0
        self._data_subscriptions: Dict[str, int] = {}  # asset -> req_id
        self._api_thread: Optional[threading.Thread] = None
        self._contracts_cache: Optional[Dict[str, Dict[str, str]]] = None

    def _get_next_req_id(self) -> int:
        """Get next request ID"""
        self._req_id_counter += 1
        return self._req_id_counter

    def _get_next_order_id(self) -> int:
        """Get next order ID"""
        if self.wrapper.next_valid_id:
            self._order_id_counter = max(self._order_id_counter, self.wrapper.next_valid_id)
        self._order_id_counter += 1
        return self._order_id_counter

    def _load_contracts(self) -> Dict[str, Dict[str, str]]:
        """Load contracts from contracts.json and cache them"""
        if self._contracts_cache is not None:
            return self._contracts_cache

        contracts_map = {}
        # Try multiple possible paths for contracts.json
        possible_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "contracts.json"),  # From live_trading/brokers/ to root
            "contracts.json",  # Current working directory
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "contracts.json"),  # Relative path
        ]

        contracts_file = None
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                contracts_file = abs_path
                break

        try:
            if contracts_file and os.path.exists(contracts_file):
                with open(contracts_file, 'r') as f:
                    data = json.load(f)
                    for contract_entry in data.get("contracts", []):
                        contract_str = contract_entry.get("contract", "")
                        if contract_str:
                            # Parse format: "BASE,QUOTE,SECTYPE,EXCHANGE"
                            parts = contract_str.split(",")
                            if len(parts) == 4:
                                base, quote, sec_type, exchange = parts
                                asset_key = f"{base}-{quote}"
                                contracts_map[asset_key] = {
                                    "base": base,
                                    "quote": quote,
                                    "secType": sec_type,
                                    "exchange": exchange
                                }
                logger.info(f"Loaded {len(contracts_map)} contracts from {contracts_file}")
            else:
                logger.warning(f"contracts.json not found in any of the expected locations, using defaults for all assets")
        except Exception as e:
            logger.error(f"Error loading contracts.json: {e}", exc_info=True)

        self._contracts_cache = contracts_map
        return contracts_map

    def _get_contract_details(self, asset: str) -> Tuple[str, str, str, str]:
        """
        Get contract details (base, quote, secType, exchange) for an asset.

        Args:
            asset: Asset symbol (e.g., "ETH-USD", "EUR-USD")

        Returns:
            Tuple of (base, quote, secType, exchange)
        """
        contracts = self._load_contracts()

        if asset in contracts:
            contract = contracts[asset]
            return (
                contract["base"],
                contract["quote"],
                contract["secType"],
                contract["exchange"]
            )

        # Fallback: assume forex (CASH/IDEALPRO) for unknown assets
        parts = asset.split("-")
        if len(parts) == 2:
            base, quote = parts
            logger.debug(f"Contract not found in contracts.json for {asset}, using default CASH/IDEALPRO")
            return (base, quote, "CASH", "IDEALPRO")

        raise ValueError(f"Invalid asset format: {asset}")

    async def connect(self) -> bool:
        """Connect to IBKR TWS/Gateway"""
        try:
            # Generate unique client ID to avoid conflicts
            client_id = random.randint(1000, 9999)

            self.client = EClient(self.wrapper)
            self.wrapper._broker_client = self.client  # Store client reference for SL/TP orders
            self.client.connect(
                config.IBKR_HOST,
                config.IBKR_PORT,
                clientId=client_id
            )

            # Start the API thread to process callbacks
            # This is REQUIRED - without it, callbacks like nextValidId never fire
            def run_loop():
                try:
                    self.client.run()
                except Exception as e:
                    logger.error(f"IBKR API thread error: {e}")
                    self.wrapper.connected = False

            self._api_thread = threading.Thread(target=run_loop, daemon=True)
            self._api_thread.start()
            logger.debug(f"Started IBKR API thread (client_id: {client_id})")

            # Wait for nextValidId callback (this confirms connection)
            max_wait = 30  # Increased timeout
            waited = 0
            while not self.wrapper.connected and waited < max_wait:
                await asyncio.sleep(0.5)
                waited += 0.5

                # Check if thread is still alive
                if not self._api_thread.is_alive():
                    logger.error("IBKR API thread died unexpectedly")
                    break

            if self.wrapper.connected:
                self.connected = True
                # Set market data type to DELAYED (3) to avoid real-time data costs
                # MarketDataTypeEnum: 1=REALTIME, 2=FROZEN, 3=DELAYED, 4=DELAYED_FROZEN
                if self.client:
                    self.client.reqMarketDataType(MarketDataTypeEnum.DELAYED)
                    logger.info("Requested market data type: DELAYED (free, 15-20 min delay)")
                    logger.info("  Note: Check [MARKET_DATA_TYPE] log to confirm actual data type")
                    logger.info("  TWS/Gateway may override if real-time subscriptions are enabled")
                logger.info(f"Successfully connected to IBKR (client_id: {client_id}, next_valid_id: {self.wrapper.next_valid_id})")
                return True
            else:
                logger.error(f"Failed to connect to IBKR - timeout waiting for connection (client_id: {client_id})")
                logger.error("Check that TWS/Gateway is running and API is enabled in settings")
                return False

        except Exception as e:
            logger.error(f"Error connecting to IBKR: {e}", exc_info=True)
            return False

    async def disconnect(self):
        """Disconnect from IBKR"""
        if self.client:
            try:
                self.client.disconnect()
                self.connected = False
                logger.info("Disconnected from IBKR")
            except Exception as e:
                logger.error(f"Error disconnecting from IBKR: {e}")

        # The API thread will stop when client.disconnect() is called
        # No need to explicitly stop it as it's a daemon thread

    async def subscribe_market_data(
        self,
        asset: str,
        callback: Callable[[Dict[str, Any]], None],
        callback_id: str = None
    ) -> bool:
        """Subscribe to real-time market data (callback_id not yet supported for IBKR)"""
        if not self.connected or not self.client:
            logger.error("Not connected to IBKR")
            return False

        # Unsubscribe if already subscribed
        if asset in self._data_subscriptions:
            await self.unsubscribe_market_data(asset)

        # Get contract details from contracts.json
        try:
            base, quote, sec_type, exchange = self._get_contract_details(asset)
        except ValueError as e:
            logger.error(f"Error getting contract details: {e}")
            return False

        # Create contract
        contract = Contract()
        contract.symbol = base
        contract.currency = quote
        contract.secType = sec_type
        contract.exchange = exchange

        req_id = self._get_next_req_id()
        self._data_subscriptions[asset] = req_id
        self.wrapper.data_callbacks[req_id] = callback

        # Request market data
        # Parameters: reqId, contract, genericTickList, snapshot, regulatorySnapshots, mktDataOptions
        # genericTickList: "" = all available ticks
        # snapshot: False = streaming data, True = single snapshot
        # regulatorySnapshots: False = no regulatory snapshots
        # mktDataOptions: [] = no additional options
        logger.info(f"Requesting DELAYED market data for {asset}: symbol={base}, currency={quote}, secType={sec_type}, exchange={exchange}, req_id={req_id}")
        try:
            self.client.reqMktData(req_id, contract, "", False, False, [])
            logger.info(f"Market data request sent for {asset} (req_id: {req_id}, using DELAYED data - free)")
        except Exception as e:
            logger.error(f"Error requesting market data for {asset}: {e}", exc_info=True)
            return False

        return True

    async def unsubscribe_market_data(self, asset: str, callback_id: str = None):
        """Unsubscribe from market data (callback_id not yet supported for IBKR)"""
        if asset in self._data_subscriptions:
            req_id = self._data_subscriptions[asset]
            if self.client:
                self.client.cancelMktData(req_id)
            del self._data_subscriptions[asset]
            if req_id in self.wrapper.data_callbacks:
                del self.wrapper.data_callbacks[req_id]
            logger.info(f"Unsubscribed from market data for {asset}")

    def register_order_callback(self, broker_order_id: str, callback: Callable):
        """Register a callback for order status updates"""
        self.wrapper.order_callbacks[broker_order_id] = callback

    async def place_order(
        self,
        asset: str,
        action: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_status_callback: Optional[Callable] = None
    ) -> str:
        """Place an order"""
        if not self.connected or not self.client:
            logger.error("Not connected to IBKR")
            return ""

        # Get contract details from contracts.json
        try:
            base, quote, sec_type, exchange = self._get_contract_details(asset)
        except ValueError as e:
            logger.error(f"Error getting contract details: {e}")
            return ""

        # Create contract
        contract = Contract()
        contract.symbol = base
        contract.currency = quote
        contract.secType = sec_type
        contract.exchange = exchange

        # Create order
        order = IBOrder()
        order.action = action  # "BUY" or "SELL"
        order.totalQuantity = abs(quantity)
        order.orderType = order_type

        # Round prices to 5 decimal places (0.00001 tick size for forex pairs)
        # IBKR requires prices to conform to minimum price variation
        if order_type == "LIMIT" and price:
            order.lmtPrice = round(price, 5)
            logger.debug(f"Rounded limit price from {price} to {order.lmtPrice}")
        elif order_type == "STOP" and stop_loss:
            order.auxPrice = round(stop_loss, 5)
            logger.debug(f"Rounded stop price from {stop_loss} to {order.auxPrice}")

        # Also round stop loss and take profit if provided
        if stop_loss:
            stop_loss = round(stop_loss, 5)
        if take_profit:
            take_profit = round(take_profit, 5)

        # Store stop loss and take profit for later use (will be placed as separate orders after fill)
        # IBKR doesn't support stop loss/take profit directly on orders like OANDA
        # We'll place them as separate orders after the main order is filled
        order_id = self._get_next_order_id()
        order.orderId = order_id

        # Store stop loss/take profit info for callback to use
        if stop_loss or take_profit:
            # Store in a way that the order status callback can access
            # We'll use a closure or store in wrapper
            if not hasattr(self.wrapper, '_pending_sl_tp'):
                self.wrapper._pending_sl_tp = {}
            self.wrapper._pending_sl_tp[str(order_id)] = {
                "asset": asset,
                "contract": contract,
                "action": action,
                "quantity": abs(quantity),
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "parent_order_id": order_id
            }

        # Register order status callback if provided
        if order_status_callback:
            self.register_order_callback(str(order_id), order_status_callback)

        # Place order
        self.client.placeOrder(order_id, contract, order)

        price_str = f" @ {order.lmtPrice}" if order_type == "LIMIT" and hasattr(order, 'lmtPrice') and order.lmtPrice else ""
        logger.info(f"Placed {order_type} {action} order for {asset}: {quantity}{price_str} (order_id: {order_id})")
        if stop_loss or take_profit:
            logger.info(f"  Stop loss/take profit will be placed as separate orders after fill")

        return str(order_id)

    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an order"""
        if not self.client:
            return False

        try:
            order_id = int(broker_order_id)
            self.client.cancelOrder(order_id)
            logger.info(f"Cancelled order: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    async def get_positions(self) -> list[Dict[str, Any]]:
        """Get current positions"""
        if not self.connected or not self.client:
            logger.error("Not connected to IBKR")
            return []

        try:
            # Clear previous positions
            self.wrapper._positions = []

            # Create event to wait for positions
            self.wrapper._positions_event = threading.Event()

            # Request positions
            logger.info("Requesting positions from IBKR...")
            self.client.reqPositions()

            # Wait for positions with timeout (10 seconds)
            # Use run_in_executor to wait for the threading event in a non-blocking way
            timeout = 10.0
            try:
                # Wait for the event in a thread pool executor
                loop = asyncio.get_event_loop()
                received = await loop.run_in_executor(
                    None,
                    self.wrapper._positions_event.wait,
                    timeout
                )
            except Exception as e:
                logger.error(f"Error waiting for positions: {e}")
                received = False

            if not received:
                logger.warning("Timeout waiting for positions from IBKR")
                # Cancel position request
                try:
                    self.client.cancelPositions()
                except:
                    pass
                return []

            # Cancel position request (we only want a snapshot)
            try:
                self.client.cancelPositions()
            except:
                pass

            positions = self.wrapper._positions

            # Convert to expected format
            positions_list = []
            for pos in positions:
                asset = pos.get("asset", "")

                # Use avg_price as current_price (IBKR doesn't provide current price in position callback)
                # In a production system, you might want to maintain a price cache or request current prices
                current_price = pos.get("current_price", pos.get("avg_price", 0.0))

                # Calculate unrealized P/L if we have current price
                avg_price = pos.get("avg_price", 0.0)
                quantity = pos.get("quantity", 0.0)
                position_type = pos.get("position_type", "LONG")

                unrealized_pnl = 0.0
                unrealized_pnl_pct = 0.0

                if avg_price > 0 and quantity > 0 and current_price > 0:
                    if position_type == "LONG":
                        unrealized_pnl = (current_price - avg_price) * quantity
                    else:  # SHORT
                        unrealized_pnl = (avg_price - current_price) * quantity

                    if avg_price * quantity > 0:
                        unrealized_pnl_pct = (unrealized_pnl / (avg_price * quantity)) * 100

                positions_list.append({
                    "asset": asset,
                    "quantity": quantity if position_type == "LONG" else -quantity,
                    "position_type": position_type,
                    "avg_price": avg_price,
                    "current_price": current_price,
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_pnl_pct": unrealized_pnl_pct
                })

            logger.info(f"Retrieved {len(positions_list)} positions from IBKR")
            return positions_list

        except Exception as e:
            logger.error(f"Error getting positions from IBKR: {e}", exc_info=True)
            # Cancel position request on error
            if self.client:
                try:
                    self.client.cancelPositions()
                except:
                    pass
            return []

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        if not self.connected or not self.client:
            logger.error("Not connected to IBKR")
            return {}

        try:
            # Clear previous account info
            self.wrapper._account_values = {}
            self.wrapper._account_portfolio = {}

            # Create event to wait for account info
            self.wrapper._account_info_event = threading.Event()

            # Request account updates
            # Use subscribe=True to get updates, then cancel after we get the snapshot
            logger.info("Requesting account information from IBKR...")
            self.client.reqAccountUpdates(True, "")  # True = subscribe, "" = all accounts

            # Wait for account info with timeout (5 seconds)
            timeout = 5.0
            try:
                loop = asyncio.get_event_loop()
                received = await loop.run_in_executor(
                    None,
                    self.wrapper._account_info_event.wait,
                    timeout
                )
            except Exception as e:
                logger.error(f"Error waiting for account info: {e}")
                received = False

            if not received:
                logger.warning("Timeout waiting for account information from IBKR")
                # Cancel account updates
                try:
                    self.client.reqAccountUpdates(False, "")  # False = unsubscribe
                except:
                    pass
                return {}

            # Cancel account updates (we only want a snapshot)
            try:
                self.client.reqAccountUpdates(False, "")
            except:
                pass

            # Extract account information from stored values
            account_info = {}

            # Common account value keys in IBKR
            account_info["account_id"] = self.wrapper._account_values.get("AccountCode", "")
            account_info["currency"] = self.wrapper._account_values.get("BaseCurrency", "USD")
            account_info["balance"] = float(self.wrapper._account_values.get("NetLiquidation", "0"))
            account_info["equity"] = float(self.wrapper._account_values.get("NetLiquidation", "0"))
            account_info["margin_used"] = float(self.wrapper._account_values.get("FullInitMarginReq", "0"))
            account_info["margin_available"] = float(self.wrapper._account_values.get("AvailableFunds", "0"))

            # Calculate margin level
            margin_used = account_info["margin_used"]
            equity = account_info["equity"]
            if margin_used > 0:
                account_info["margin_level"] = (equity / margin_used) * 100
            else:
                account_info["margin_level"] = 0.0

            # Calculate unrealized P/L from portfolio
            unrealized_pnl = 0.0
            for contract_key, portfolio in self.wrapper._account_portfolio.items():
                unrealized_pnl += portfolio.get("unrealized_pnl", 0.0)
            account_info["unrealized_pnl"] = unrealized_pnl

            # Count open positions
            open_positions = len([p for p in self.wrapper._account_portfolio.values() if abs(p.get("position", 0)) > 0.0001])
            account_info["open_trade_count"] = open_positions
            account_info["open_position_count"] = open_positions

            logger.info(f"Retrieved account information from IBKR: Balance={account_info.get('balance')}, Equity={account_info.get('equity')}")
            return account_info

        except Exception as e:
            logger.error(f"Error getting account info from IBKR: {e}", exc_info=True)
            # Cancel account updates on error
            if self.client:
                try:
                    self.client.reqAccountUpdates(False, "")
                except:
                    pass
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
        if not self.connected or not self.client:
            logger.error("Not connected to IBKR")
            return False

        # Get contract details from contracts.json
        try:
            base, quote, sec_type, exchange = self._get_contract_details(asset)
        except ValueError as e:
            logger.error(f"Error getting contract details: {e}")
            return False

        # Create contract
        contract = Contract()
        contract.symbol = base
        contract.currency = quote
        contract.secType = sec_type
        contract.exchange = exchange

        req_id = self._get_next_req_id()

        # Register callback and context
        self.wrapper.historical_data_callbacks[req_id] = callback
        self.wrapper.historical_data_context[req_id] = context or {}

        # Convert bar_size to IBKR format
        # IBKR uses format like "1 min", "5 mins", "1 hour", "1 day", "1 W"
        ibkr_bar_size = bar_size
        if bar_size == "1 week":
            ibkr_bar_size = "1 W"
        elif bar_size.endswith("mins"):
            # Keep as is (e.g., "15 mins")
            pass
        elif bar_size.endswith("hours"):
            # Convert "4 hours" to "4 H"
            ibkr_bar_size = bar_size.replace("hours", "H").replace("hour", "H")
        elif bar_size.endswith("days"):
            # Convert "1 days" to "1 D"
            ibkr_bar_size = bar_size.replace("days", "D").replace("day", "D")

        # Request historical data
        # Parameters: reqId, contract, endDateTime, durationStr, barSizeSetting, whatToShow, useRTH, formatDate, keepUpToDate, chartOptions
        # - endDateTime: "" = current time
        # - durationStr: interval (e.g., "1 Y", "6 M")
        # - barSizeSetting: bar size (e.g., "1 hour", "15 mins")
        # - whatToShow: "MIDPOINT" for forex (mid price)
        # - useRTH: 0 = all data, 1 = regular trading hours only
        # - formatDate: 1 = string, 2 = unix timestamp
        # - keepUpToDate: False = one-time request
        try:
            logger.info(f"Requesting historical data for {asset}: bar_size={bar_size}, interval={interval}, req_id={req_id}")
            self.client.reqHistoricalData(
                req_id,
                contract,
                "",  # endDateTime: "" = current time
                interval,  # durationStr: e.g., "1 Y", "6 M"
                ibkr_bar_size,  # barSizeSetting
                "MIDPOINT",  # whatToShow: mid price for forex
                0,  # useRTH: 0 = all data
                2,  # formatDate: 2 = unix timestamp
                False,  # keepUpToDate: False = one-time request
                []  # chartOptions: empty
            )
            logger.info(f"Historical data request sent for {asset} (req_id: {req_id})")
            return True
        except Exception as e:
            logger.error(f"Error requesting historical data for {asset}: {e}", exc_info=True)
            # Cleanup on error
            if req_id in self.wrapper.historical_data_callbacks:
                del self.wrapper.historical_data_callbacks[req_id]
            if req_id in self.wrapper.historical_data_context:
                del self.wrapper.historical_data_context[req_id]
            return False

