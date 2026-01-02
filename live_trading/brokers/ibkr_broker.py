"""
IBKR Broker Adapter.
"""
import asyncio
import logging
import threading
import random
from typing import Callable, Optional, Dict, Any
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
        self.connected = False
        self.next_valid_id = None
        # Store latest prices per reqId for BID/ASK/LAST
        self._latest_prices: Dict[int, Dict[int, float]] = {}  # reqId -> {tickType: price}

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
            logger.info(f"[TICK_PRICE] reqId={reqId}, tickType={tickType}({tick_name}), price={price}, attrib={attrib}")

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
            logger.info(f"[TICK_SIZE] reqId={reqId}, tickType={tickType}({tick_name}), size={size}")

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
        logger.info(f"[TICK_STRING] reqId={reqId}, tickType={tickType}({tick_name}), value={value}")

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


class IBKRBroker(BaseBroker):
    """IBKR Broker Adapter"""

    def __init__(self):
        self.wrapper = IBKRWrapper()
        self.client: Optional[EClient] = None
        self.connected = False
        self._req_id_counter = 0
        self._order_id_counter = 0
        self._data_subscriptions: Dict[str, int] = {}  # asset -> req_id
        self._api_thread: Optional[threading.Thread] = None

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

    async def connect(self) -> bool:
        """Connect to IBKR TWS/Gateway"""
        try:
            # Generate unique client ID to avoid conflicts
            client_id = random.randint(1000, 9999)

            self.client = EClient(self.wrapper)
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
        callback: Callable[[Dict[str, Any]], None]
    ) -> bool:
        """Subscribe to real-time market data"""
        if not self.connected or not self.client:
            logger.error("Not connected to IBKR")
            return False

        # Unsubscribe if already subscribed
        if asset in self._data_subscriptions:
            await self.unsubscribe_market_data(asset)

        # Parse asset (e.g., "USD-CAD" -> base="USD", quote="CAD")
        parts = asset.split("-")
        if len(parts) != 2:
            logger.error(f"Invalid asset format: {asset}")
            return False

        base, quote = parts

        # Create contract
        contract = Contract()
        contract.symbol = base
        contract.currency = quote
        contract.secType = "CASH"
        contract.exchange = "IDEALPRO"

        req_id = self._get_next_req_id()
        self._data_subscriptions[asset] = req_id
        self.wrapper.data_callbacks[req_id] = callback

        # Request market data
        # Parameters: reqId, contract, genericTickList, snapshot, regulatorySnapshots, mktDataOptions
        # genericTickList: "" = all available ticks
        # snapshot: False = streaming data, True = single snapshot
        # regulatorySnapshots: False = no regulatory snapshots
        # mktDataOptions: [] = no additional options
        logger.info(f"Requesting DELAYED market data for {asset}: symbol={base}, currency={quote}, secType={contract.secType}, exchange={contract.exchange}, req_id={req_id}")
        try:
            self.client.reqMktData(req_id, contract, "", False, False, [])
            logger.info(f"Market data request sent for {asset} (req_id: {req_id}, using DELAYED data - free)")
        except Exception as e:
            logger.error(f"Error requesting market data for {asset}: {e}", exc_info=True)
            return False

        return True

    async def unsubscribe_market_data(self, asset: str):
        """Unsubscribe from market data"""
        if asset in self._data_subscriptions:
            req_id = self._data_subscriptions[asset]
            if self.client:
                self.client.cancelMktData(req_id)
            del self._data_subscriptions[asset]
            if req_id in self.wrapper.data_callbacks:
                del self.wrapper.data_callbacks[req_id]
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
        if not self.connected or not self.client:
            logger.error("Not connected to IBKR")
            return ""

        # Parse asset
        parts = asset.split("-")
        if len(parts) != 2:
            logger.error(f"Invalid asset format: {asset}")
            return ""

        base, quote = parts

        # Create contract
        contract = Contract()
        contract.symbol = base
        contract.currency = quote
        contract.secType = "CASH"
        contract.exchange = "IDEALPRO"

        # Create order
        order = IBOrder()
        order.action = action  # "BUY" or "SELL"
        order.totalQuantity = abs(quantity)
        order.orderType = order_type

        if order_type == "LIMIT" and price:
            order.lmtPrice = price
        elif order_type == "STOP" and stop_loss:
            order.auxPrice = stop_loss

        # TODO: Handle stop loss and take profit as separate orders or OCA groups

        order_id = self._get_next_order_id()
        order.orderId = order_id

        # Place order
        self.client.placeOrder(order_id, contract, order)

        logger.info(f"Placed {order_type} {action} order for {asset}: {quantity} (order_id: {order_id})")
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
        # TODO: Implement position query
        # This requires implementing reqPositions() and position() callback
        logger.warning("get_positions() not yet implemented")
        return []

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        # TODO: Implement account info query
        logger.warning("get_account_info() not yet implemented")
        return {}

