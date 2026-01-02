"""
FastAPI main application.
"""
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from live_trading.engine.trading_engine import TradingEngine

logger = logging.getLogger(__name__)
from live_trading.models.trading_operation import TradingOperation
from live_trading.models.transaction import Transaction
from live_trading.models.position import Position
from live_trading.models.order import Order
from live_trading.models.trade import Trade
from live_trading.config import config

app = FastAPI(title="Live Trading System API", version="0.1.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global trading engine (will be initialized in startup)
trading_engine: Optional[TradingEngine] = None


def get_trading_engine() -> TradingEngine:
    """Dependency to get trading engine"""
    if trading_engine is None:
        raise HTTPException(status_code=500, detail="Trading engine not initialized")
    return trading_engine


# Pydantic models for request/response
class CreateOperationRequest(BaseModel):
    asset: str
    bar_sizes: List[str]
    primary_bar_size: str
    strategy_name: str
    strategy_config: Dict[str, Any] = {}
    initial_capital: float = 10000.0
    stop_loss_type: Optional[str] = None
    stop_loss_value: Optional[float] = None
    take_profit_type: Optional[str] = None
    take_profit_value: Optional[float] = None
    crash_recovery_mode: Optional[str] = None
    emergency_stop_loss_pct: Optional[float] = None
    data_retention_bars: Optional[int] = None


class OperationResponse(BaseModel):
    id: str
    asset: str
    bar_sizes: List[str]
    primary_bar_size: str
    strategy_name: str
    status: str
    initial_capital: float
    current_capital: float
    total_pnl: float
    total_pnl_pct: float
    created_at: datetime
    updated_at: datetime


# Operations endpoints
@app.post("/api/operations", response_model=OperationResponse)
async def create_operation(
    request: CreateOperationRequest,
    engine: TradingEngine = Depends(get_trading_engine)
):
    """Create a new trading operation"""
    try:
        operation = await engine.start_operation(
            asset=request.asset,
            bar_sizes=request.bar_sizes,
            primary_bar_size=request.primary_bar_size,
            strategy_name=request.strategy_name,
            strategy_config=request.strategy_config,
            initial_capital=request.initial_capital,
            stop_loss_type=request.stop_loss_type,
            stop_loss_value=request.stop_loss_value,
            take_profit_type=request.take_profit_type,
            take_profit_value=request.take_profit_value,
            crash_recovery_mode=request.crash_recovery_mode,
            emergency_stop_loss_pct=request.emergency_stop_loss_pct,
            data_retention_bars=request.data_retention_bars
        )

        return OperationResponse(
            id=str(operation.id),
            asset=operation.asset,
            bar_sizes=operation.bar_sizes,
            primary_bar_size=operation.primary_bar_size,
            strategy_name=operation.strategy_name,
            status=operation.status,
            initial_capital=operation.initial_capital,
            current_capital=operation.current_capital,
            total_pnl=operation.total_pnl,
            total_pnl_pct=operation.total_pnl_pct,
            created_at=operation.created_at,
            updated_at=operation.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/operations", response_model=List[OperationResponse])
async def list_operations(
    status: Optional[str] = None,
    engine: TradingEngine = Depends(get_trading_engine)
):
    """List all trading operations"""
    query = {}
    if status:
        query["status"] = status

    operations = await TradingOperation.find(query).sort(-TradingOperation.created_at).to_list()

    return [
        OperationResponse(
            id=str(op.id),
            asset=op.asset,
            bar_sizes=op.bar_sizes,
            primary_bar_size=op.primary_bar_size,
            strategy_name=op.strategy_name,
            status=op.status,
            initial_capital=op.initial_capital,
            current_capital=op.current_capital,
            total_pnl=op.total_pnl,
            total_pnl_pct=op.total_pnl_pct,
            created_at=op.created_at,
            updated_at=op.updated_at
        )
        for op in operations
    ]


@app.get("/api/operations/{operation_id}", response_model=OperationResponse)
async def get_operation(
    operation_id: str,
    engine: TradingEngine = Depends(get_trading_engine)
):
    """Get operation details"""
    try:
        op_id = ObjectId(operation_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid operation ID")

    operation = await TradingOperation.get(op_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")

    return OperationResponse(
        id=str(operation.id),
        asset=operation.asset,
        bar_sizes=operation.bar_sizes,
        primary_bar_size=operation.primary_bar_size,
        strategy_name=operation.strategy_name,
        status=operation.status,
        initial_capital=operation.initial_capital,
        current_capital=operation.current_capital,
        total_pnl=operation.total_pnl,
        total_pnl_pct=operation.total_pnl_pct,
        created_at=operation.created_at,
        updated_at=operation.updated_at
    )


@app.delete("/api/operations/{operation_id}")
async def delete_operation(
    operation_id: str,
    engine: TradingEngine = Depends(get_trading_engine)
):
    """Stop and close an operation"""
    try:
        op_id = ObjectId(operation_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid operation ID")

    try:
        await engine.stop_operation(op_id)
        return {"message": "Operation stopped"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/operations/{operation_id}/pause")
async def pause_operation(
    operation_id: str,
    engine: TradingEngine = Depends(get_trading_engine)
):
    """Pause an operation"""
    try:
        op_id = ObjectId(operation_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid operation ID")

    try:
        await engine.pause_operation(op_id)
        return {"message": "Operation paused"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/operations/{operation_id}/resume")
async def resume_operation(
    operation_id: str,
    engine: TradingEngine = Depends(get_trading_engine)
):
    """Resume a paused operation"""
    try:
        op_id = ObjectId(operation_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid operation ID")

    try:
        await engine.resume_operation(op_id)
        return {"message": "Operation resumed"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Positions endpoints
@app.get("/api/operations/{operation_id}/positions")
async def get_positions(operation_id: str):
    """Get positions for an operation"""
    try:
        op_id = ObjectId(operation_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid operation ID")

    positions = await Position.find(
        Position.operation_id == op_id
    ).sort(-Position.opened_at).to_list()

    return [
        {
            "id": str(pos.id),
            "contract_symbol": pos.contract_symbol,
            "quantity": pos.quantity,
            "entry_price": pos.entry_price,
            "current_price": pos.current_price,
            "unrealized_pnl": pos.unrealized_pnl,
            "unrealized_pnl_pct": pos.unrealized_pnl_pct,
            "stop_loss": pos.stop_loss,
            "take_profit": pos.take_profit,
            "opened_at": pos.opened_at,
            "closed_at": pos.closed_at
        }
        for pos in positions
    ]


# Transactions endpoints
@app.get("/api/operations/{operation_id}/transactions")
async def get_transactions(operation_id: str):
    """Get transactions for an operation"""
    try:
        op_id = ObjectId(operation_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid operation ID")

    transactions = await Transaction.find(
        Transaction.operation_id == op_id
    ).sort(-Transaction.executed_at).to_list()

    return [
        {
            "id": str(txn.id),
            "transaction_type": txn.transaction_type,
            "transaction_role": txn.transaction_role,
            "position_type": txn.position_type,
            "price": txn.price,
            "quantity": txn.quantity,
            "commission": txn.commission,
            "profit": txn.profit,
            "profit_pct": txn.profit_pct,
            "executed_at": txn.executed_at
        }
        for txn in transactions
    ]


# Trades endpoints
@app.get("/api/operations/{operation_id}/trades")
async def get_trades(operation_id: str):
    """Get completed trades for an operation"""
    try:
        op_id = ObjectId(operation_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid operation ID")

    trades = await Trade.find(
        Trade.operation_id == op_id
    ).sort(-Trade.exit_time).to_list()

    return [
        {
            "id": str(trade.id),
            "position_type": trade.position_type,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "quantity": trade.quantity,
            "pnl": trade.pnl,
            "pnl_pct": trade.pnl_pct,
            "total_commission": trade.total_commission,
            "entry_time": trade.entry_time,
            "exit_time": trade.exit_time,
            "duration_seconds": trade.duration_seconds
        }
        for trade in trades
    ]


# Orders endpoints
@app.get("/api/operations/{operation_id}/orders")
async def get_orders(operation_id: str):
    """Get orders for an operation"""
    try:
        op_id = ObjectId(operation_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid operation ID")

    orders = await Order.find(
        Order.operation_id == op_id
    ).sort(-Order.placed_at).to_list()

    return [
        {
            "id": str(order.id),
            "broker_order_id": order.broker_order_id,
            "order_type": order.order_type,
            "action": order.action,
            "quantity": order.quantity,
            "price": order.price,
            "status": order.status,
            "filled_quantity": order.filled_quantity,
            "avg_fill_price": order.avg_fill_price,
            "placed_at": order.placed_at,
            "filled_at": order.filled_at
        }
        for order in orders
    ]


# Statistics endpoints
@app.get("/api/operations/{operation_id}/stats")
async def get_operation_stats(operation_id: str):
    """Get operation statistics"""
    try:
        op_id = ObjectId(operation_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid operation ID")

    operation = await TradingOperation.get(op_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")

    # Get additional stats
    trades = await Trade.find(Trade.operation_id == op_id).to_list()
    positions = await Position.find(
        Position.operation_id == op_id,
        Position.closed_at == None
    ).to_list()

    return {
        "operation_id": str(operation.id),
        "total_trades": len(trades),
        "winning_trades": len([t for t in trades if t.pnl > 0]),
        "losing_trades": len([t for t in trades if t.pnl < 0]),
        "total_pnl": operation.total_pnl,
        "total_pnl_pct": operation.total_pnl_pct,
        "open_positions": len(positions),
        "current_capital": operation.current_capital
    }


@app.get("/api/stats/overall")
async def get_overall_stats(engine: TradingEngine = Depends(get_trading_engine)):
    """Get overall statistics across all operations"""
    operations = await TradingOperation.find_all().to_list()
    all_trades = await Trade.find_all().to_list()

    total_pnl = sum(op.total_pnl for op in operations)
    total_capital = sum(op.current_capital for op in operations)
    initial_capital = sum(op.initial_capital for op in operations)

    return {
        "total_operations": len(operations),
        "active_operations": len([op for op in operations if op.status == "active"]),
        "total_trades": len(all_trades),
        "total_pnl": total_pnl,
        "total_pnl_pct": (total_pnl / initial_capital * 100) if initial_capital > 0 else 0,
        "total_capital": total_capital,
        "initial_capital": initial_capital
    }


@app.on_event("startup")
async def startup_event():
    """Initialize trading engine on startup"""
    global trading_engine

    # Import here to avoid circular imports
    from live_trading.brokers import IBKRBroker
    from live_trading.journal.journal_manager import JournalManager

    # Initialize broker based on config
    if config.BROKER_TYPE == "IBKR":
        if IBKRBroker is None:
            raise ImportError(
                "IBKR broker requested but 'ibapi' module not found. "
                "Please install IBKR API: pip install -e ./IBJts/source/pythonclient"
            )
        broker = IBKRBroker()
        connected = await broker.connect()
        if not connected:
            logger.warning(
                "Failed to connect to IBKR. Make sure TWS/Gateway is running and API is enabled. "
                "The system will continue but trading operations will not work until IBKR is connected."
            )
    else:
        raise ValueError(f"Unsupported broker type: {config.BROKER_TYPE}")

    # Initialize journal manager
    journal_manager = JournalManager()

    # Initialize trading engine
    trading_engine = TradingEngine(broker, journal_manager)
    await trading_engine.initialize()

    # Recover from journal (crash recovery)
    await trading_engine.recover_from_journal()

    print(f"Trading engine started on {config.API_HOST}:{config.API_PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown trading engine"""
    global trading_engine
    if trading_engine:
        await trading_engine.shutdown()

