import React, { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  operationsApi,
  positionsApi,
  transactionsApi,
  tradesApi,
  ordersApi,
  statsApi,
} from '../api/client'
import { formatCurrency, formatPercent, formatDate } from '../utils/formatters'

function OperationDetail() {
  const { id } = useParams()
  const [operation, setOperation] = useState(null)
  const [positions, setPositions] = useState([])
  const [transactions, setTransactions] = useState([])
  const [trades, setTrades] = useState([])
  const [orders, setOrders] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 5000) // Refresh every 5 seconds
    return () => clearInterval(interval)
  }, [id])

  const loadData = async () => {
    try {
      setLoading(true)
      const [
        opRes,
        posRes,
        txnRes,
        tradesRes,
        ordersRes,
        statsRes,
      ] = await Promise.all([
        operationsApi.get(id),
        positionsApi.list(id),
        transactionsApi.list(id),
        tradesApi.list(id),
        ordersApi.list(id),
        statsApi.operation(id),
      ])
      setOperation(opRes.data)
      setPositions(posRes.data)
      setTransactions(txnRes.data)
      setTrades(tradesRes.data)
      setOrders(ordersRes.data)
      setStats(statsRes.data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading && !operation) {
    return <div className="loading">Loading operation details...</div>
  }

  if (error || !operation) {
    return <div className="error">Error: {error || 'Operation not found'}</div>
  }

  const openPositions = positions.filter((p) => !p.closed_at)
  const closedPositions = positions.filter((p) => p.closed_at)

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <Link to="/operations" style={{ color: '#6c757d', textDecoration: 'none' }}>
            ← Back to Operations
          </Link>
          <h1 className="page-title" style={{ marginTop: '10px' }}>
            {operation.asset} - {operation.strategy_name}
          </h1>
        </div>
        <div>
          <span className={`status-badge status-${operation.status}`}>
            {operation.status}
          </span>
        </div>
      </div>

      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Total P/L</div>
            <div className={`stat-value ${stats.total_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}`}>
              {formatCurrency(stats.total_pnl)}
            </div>
            <div className="stat-label">{formatPercent(stats.total_pnl_pct)}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Trades</div>
            <div className="stat-value">{stats.total_trades}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Winning Trades</div>
            <div className="stat-value">{stats.winning_trades}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Losing Trades</div>
            <div className="stat-value">{stats.losing_trades}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Open Positions</div>
            <div className="stat-value">{stats.open_positions}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Current Capital</div>
            <div className="stat-value">{formatCurrency(stats.current_capital)}</div>
          </div>
        </div>
      )}

      <div className="card">
        <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', borderBottom: '1px solid #ddd', paddingBottom: '10px' }}>
          <button
            className={`btn ${activeTab === 'overview' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('overview')}
          >
            Overview
          </button>
          <button
            className={`btn ${activeTab === 'positions' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('positions')}
          >
            Positions ({positions.length})
          </button>
          <button
            className={`btn ${activeTab === 'transactions' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('transactions')}
          >
            Transactions ({transactions.length})
          </button>
          <button
            className={`btn ${activeTab === 'trades' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('trades')}
          >
            Trades ({trades.length})
          </button>
          <button
            className={`btn ${activeTab === 'orders' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('orders')}
          >
            Orders ({orders.length})
          </button>
        </div>

        {activeTab === 'overview' && (
          <div>
            <h3>Operation Details</h3>
            <table>
              <tbody>
                <tr>
                  <td><strong>Asset</strong></td>
                  <td>{operation.asset}</td>
                </tr>
                <tr>
                  <td><strong>Strategy</strong></td>
                  <td>{operation.strategy_name}</td>
                </tr>
                <tr>
                  <td><strong>Bar Sizes</strong></td>
                  <td>{operation.bar_sizes.join(', ')}</td>
                </tr>
                <tr>
                  <td><strong>Primary Bar Size</strong></td>
                  <td>{operation.primary_bar_size}</td>
                </tr>
                <tr>
                  <td><strong>Status</strong></td>
                  <td>
                    <span className={`status-badge status-${operation.status}`}>
                      {operation.status}
                    </span>
                  </td>
                </tr>
                <tr>
                  <td><strong>Initial Capital</strong></td>
                  <td>{formatCurrency(operation.initial_capital)}</td>
                </tr>
                <tr>
                  <td><strong>Current Capital</strong></td>
                  <td>{formatCurrency(operation.current_capital)}</td>
                </tr>
                <tr>
                  <td><strong>Total P/L</strong></td>
                  <td className={operation.total_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                    {formatCurrency(operation.total_pnl)} ({formatPercent(operation.total_pnl_pct)})
                  </td>
                </tr>
                <tr>
                  <td><strong>Created</strong></td>
                  <td>{formatDate(operation.created_at)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'positions' && (
          <div>
            <h3>Open Positions</h3>
            {openPositions.length === 0 ? (
              <p>No open positions</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Quantity</th>
                    <th>Entry Price</th>
                    <th>Current Price</th>
                    <th>Unrealized P/L</th>
                    <th>Unrealized P/L %</th>
                    <th>Stop Loss</th>
                    <th>Take Profit</th>
                  </tr>
                </thead>
                <tbody>
                  {openPositions.map((pos) => (
                    <tr key={pos.id}>
                      <td>{pos.contract_symbol}</td>
                      <td>{pos.quantity}</td>
                      <td>{formatCurrency(pos.entry_price)}</td>
                      <td>{formatCurrency(pos.current_price)}</td>
                      <td className={pos.unrealized_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                        {formatCurrency(pos.unrealized_pnl)}
                      </td>
                      <td className={pos.unrealized_pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                        {formatPercent(pos.unrealized_pnl_pct)}
                      </td>
                      <td>{pos.stop_loss ? formatCurrency(pos.stop_loss) : '-'}</td>
                      <td>{pos.take_profit ? formatCurrency(pos.take_profit) : '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {closedPositions.length > 0 && (
              <>
                <h3 style={{ marginTop: '30px' }}>Closed Positions</h3>
                <table>
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Quantity</th>
                      <th>Entry Price</th>
                      <th>Exit Price</th>
                      <th>Opened</th>
                      <th>Closed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {closedPositions.map((pos) => (
                      <tr key={pos.id}>
                        <td>{pos.contract_symbol}</td>
                        <td>{pos.quantity}</td>
                        <td>{formatCurrency(pos.entry_price)}</td>
                        <td>{formatCurrency(pos.current_price)}</td>
                        <td>{formatDate(pos.opened_at)}</td>
                        <td>{formatDate(pos.closed_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        )}

        {activeTab === 'transactions' && (
          <div>
            <h3>Transactions</h3>
            {transactions.length === 0 ? (
              <p>No transactions</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Role</th>
                    <th>Position Type</th>
                    <th>Price</th>
                    <th>Quantity</th>
                    <th>Commission</th>
                    <th>Profit</th>
                    <th>Profit %</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((txn) => (
                    <tr key={txn.id}>
                      <td>{txn.transaction_type}</td>
                      <td>{txn.transaction_role}</td>
                      <td>{txn.position_type}</td>
                      <td>{formatCurrency(txn.price)}</td>
                      <td>{txn.quantity}</td>
                      <td>{formatCurrency(txn.commission)}</td>
                      <td className={txn.profit >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                        {formatCurrency(txn.profit)}
                      </td>
                      <td className={txn.profit_pct >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                        {formatPercent(txn.profit_pct)}
                      </td>
                      <td>{formatDate(txn.executed_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {activeTab === 'trades' && (
          <div>
            <h3>Completed Trades</h3>
            {trades.length === 0 ? (
              <p>No completed trades</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Position Type</th>
                    <th>Entry Price</th>
                    <th>Exit Price</th>
                    <th>Quantity</th>
                    <th>P/L</th>
                    <th>P/L %</th>
                    <th>Commission</th>
                    <th>Duration</th>
                    <th>Entry Time</th>
                    <th>Exit Time</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((trade) => (
                    <tr key={trade.id}>
                      <td>{trade.position_type}</td>
                      <td>{formatCurrency(trade.entry_price)}</td>
                      <td>{formatCurrency(trade.exit_price)}</td>
                      <td>{trade.quantity}</td>
                      <td className={trade.pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                        {formatCurrency(trade.pnl)}
                      </td>
                      <td className={trade.pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                        {formatPercent(trade.pnl_pct)}
                      </td>
                      <td>{formatCurrency(trade.total_commission)}</td>
                      <td>{(trade.duration_seconds / 3600).toFixed(2)} hours</td>
                      <td>{formatDate(trade.entry_time)}</td>
                      <td>{formatDate(trade.exit_time)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {activeTab === 'orders' && (
          <div>
            <h3>Orders</h3>
            {orders.length === 0 ? (
              <p>No orders</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Action</th>
                    <th>Quantity</th>
                    <th>Price</th>
                    <th>Status</th>
                    <th>Filled</th>
                    <th>Avg Fill Price</th>
                    <th>Placed</th>
                    <th>Filled</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((order) => (
                    <tr key={order.id}>
                      <td>{order.order_type}</td>
                      <td>{order.action}</td>
                      <td>{order.quantity}</td>
                      <td>{order.price ? formatCurrency(order.price) : 'MARKET'}</td>
                      <td>
                        <span className={`status-badge status-${order.status.toLowerCase()}`}>
                          {order.status}
                        </span>
                      </td>
                      <td>{order.filled_quantity}</td>
                      <td>{order.avg_fill_price ? formatCurrency(order.avg_fill_price) : '-'}</td>
                      <td>{formatDate(order.placed_at)}</td>
                      <td>{order.filled_at ? formatDate(order.filled_at) : '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default OperationDetail

