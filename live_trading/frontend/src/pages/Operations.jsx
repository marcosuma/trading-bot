import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { operationsApi } from '../api/client'
import { formatCurrency, formatPercent } from '../utils/formatters'

function Operations() {
  const [operations, setOperations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')

  useEffect(() => {
    loadOperations()
    const interval = setInterval(loadOperations, 5000) // Refresh every 5 seconds
    return () => clearInterval(interval)
  }, [statusFilter])

  const loadOperations = async () => {
    try {
      setLoading(true)
      const res = await operationsApi.list(statusFilter || undefined)
      setOperations(res.data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handlePause = async (id) => {
    try {
      await operationsApi.pause(id)
      loadOperations()
    } catch (err) {
      alert(`Error pausing operation: ${err.message}`)
    }
  }

  const handleResume = async (id) => {
    try {
      await operationsApi.resume(id)
      loadOperations()
    } catch (err) {
      alert(`Error resuming operation: ${err.message}`)
    }
  }

  const handleStop = async (id) => {
    if (!window.confirm('Are you sure you want to stop this operation?')) {
      return
    }
    try {
      await operationsApi.delete(id)
      loadOperations()
    } catch (err) {
      alert(`Error stopping operation: ${err.message}`)
    }
  }

  if (loading && operations.length === 0) {
    return <div className="loading">Loading operations...</div>
  }

  return (
    <div className="container">
      <div className="page-header">
        <h1 className="page-title">Trading Operations</h1>
        <Link to="/operations/create" className="btn btn-primary">
          Create Operation
        </Link>
      </div>

      {error && <div className="error">Error: {error}</div>}

      <div className="card">
        <div style={{ marginBottom: '20px' }}>
          <label>
            Filter by Status:{' '}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="closed">Closed</option>
            </select>
          </label>
        </div>

        {operations.length === 0 ? (
          <p>No operations found</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Asset</th>
                <th>Strategy</th>
                <th>Bar Sizes</th>
                <th>Status</th>
                <th>Initial Capital</th>
                <th>Current Capital</th>
                <th>P/L</th>
                <th>P/L %</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {operations.map((op) => (
                <tr key={op.id}>
                  <td>{op.asset}</td>
                  <td>{op.strategy_name}</td>
                  <td>{op.bar_sizes.join(', ')}</td>
                  <td>
                    <span className={`status-badge status-${op.status}`}>
                      {op.status}
                    </span>
                  </td>
                  <td>{formatCurrency(op.initial_capital)}</td>
                  <td>{formatCurrency(op.current_capital)}</td>
                  <td className={op.total_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                    {formatCurrency(op.total_pnl)}
                  </td>
                  <td className={op.total_pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                    {formatPercent(op.total_pnl_pct)}
                  </td>
                  <td>{new Date(op.created_at).toLocaleDateString()}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <Link to={`/operations/${op.id}`} className="btn btn-secondary">
                        View
                      </Link>
                      {op.status === 'active' && (
                        <button
                          onClick={() => handlePause(op.id)}
                          className="btn btn-secondary"
                        >
                          Pause
                        </button>
                      )}
                      {op.status === 'paused' && (
                        <button
                          onClick={() => handleResume(op.id)}
                          className="btn btn-success"
                        >
                          Resume
                        </button>
                      )}
                      {(op.status === 'active' || op.status === 'paused') && (
                        <button
                          onClick={() => handleStop(op.id)}
                          className="btn btn-danger"
                        >
                          Stop
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export default Operations

