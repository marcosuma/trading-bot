import { useState, useEffect, useCallback, useRef } from 'react'
import { API_BASE } from '../api/client'

const LOG_LEVELS = ['ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

const LEVEL_COLORS = {
  DEBUG: '#6b7280',
  INFO: '#3b82f6',
  WARNING: '#f59e0b',
  ERROR: '#ef4444',
  CRITICAL: '#dc2626'
}

const LEVEL_BG_COLORS = {
  DEBUG: 'rgba(107, 114, 128, 0.1)',
  INFO: 'rgba(59, 130, 246, 0.1)',
  WARNING: 'rgba(245, 158, 11, 0.1)',
  ERROR: 'rgba(239, 68, 68, 0.1)',
  CRITICAL: 'rgba(220, 38, 38, 0.2)'
}

export default function Logs() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(null)
  const [stats, setStats] = useState(null)
  const [logFiles, setLogFiles] = useState([])
  const [totalCount, setTotalCount] = useState(null)

  // Filters
  const [levelFilter, setLevelFilter] = useState('ALL')
  const [loggerFilter, setLoggerFilter] = useState('')
  const [searchFilter, setSearchFilter] = useState('')
  const [limit, setLimit] = useState(100)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(5)

  // Date range filters
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  // UI state
  const [showFiles, setShowFiles] = useState(false)
  const logsEndRef = useRef(null)
  const logsContainerRef = useRef(null)
  const [autoScroll, setAutoScroll] = useState(true)

  // Use ref to track current offset for "load more" functionality
  const offsetRef = useRef(0)
  // Track if we're loading older logs (to prevent scroll jump)
  const isLoadingOlderRef = useRef(false)
  const scrollPositionRef = useRef(0)

  const fetchLogs = useCallback(async (append = false) => {
    try {
      if (append) {
        setLoadingMore(true)
        isLoadingOlderRef.current = true
        // Save scroll position before loading more
        if (logsContainerRef.current) {
          scrollPositionRef.current = logsContainerRef.current.scrollTop
        }
      } else {
        setLoading(true)
        offsetRef.current = 0
        isLoadingOlderRef.current = false
      }

      const params = new URLSearchParams()
      if (levelFilter !== 'ALL') params.append('level', levelFilter)
      if (loggerFilter) params.append('logger_name', loggerFilter)
      if (searchFilter) params.append('search', searchFilter)
      if (startDate) params.append('start_time', new Date(startDate).toISOString())
      if (endDate) params.append('end_time', new Date(endDate).toISOString())
      params.append('limit', limit.toString())
      params.append('offset', append ? offsetRef.current.toString() : '0')

      const response = await fetch(`${API_BASE}/api/logs?${params}`)
      if (!response.ok) throw new Error('Failed to fetch logs')
      const data = await response.json()

      // Logs come in reverse order (newest first), reverse for display
      const newLogs = data.logs.reverse()

      if (append) {
        // Prepend older logs at the top
        const oldScrollHeight = logsContainerRef.current?.scrollHeight || 0
        const oldScrollTop = logsContainerRef.current?.scrollTop || 0

        setLogs(prev => [...newLogs, ...prev])
        offsetRef.current += limit

        // Restore scroll position after DOM updates (use setTimeout to ensure React has rendered)
        setTimeout(() => {
          if (logsContainerRef.current) {
            const newScrollHeight = logsContainerRef.current.scrollHeight
            const heightDiff = newScrollHeight - oldScrollHeight
            // Keep viewing the same content by adjusting scroll position
            logsContainerRef.current.scrollTop = oldScrollTop + heightDiff
          }
          isLoadingOlderRef.current = false
        }, 50)
      } else {
        setLogs(newLogs)
        offsetRef.current = limit
      }

      setError(null)
    } catch (err) {
      setError(err.message)
      isLoadingOlderRef.current = false
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [levelFilter, loggerFilter, searchFilter, startDate, endDate, limit])

  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/logs/stats`)
      if (!response.ok) throw new Error('Failed to fetch stats')
      const data = await response.json()
      setStats(data)
    } catch (err) {
      console.error('Error fetching stats:', err)
    }
  }, [])

  const fetchLogFiles = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/logs/files`)
      if (!response.ok) throw new Error('Failed to fetch log files')
      const data = await response.json()
      setLogFiles(data.files)
    } catch (err) {
      console.error('Error fetching log files:', err)
    }
  }, [])

  const fetchTotalCount = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      if (levelFilter !== 'ALL') params.append('level', levelFilter)
      if (loggerFilter) params.append('logger_name', loggerFilter)
      if (searchFilter) params.append('search', searchFilter)
      if (startDate) params.append('start_time', new Date(startDate).toISOString())
      if (endDate) params.append('end_time', new Date(endDate).toISOString())

      const response = await fetch(`${API_BASE}/api/logs/count?${params}`)
      if (!response.ok) throw new Error('Failed to fetch count')
      const data = await response.json()
      setTotalCount(data.count)
    } catch (err) {
      console.error('Error fetching count:', err)
    }
  }, [levelFilter, loggerFilter, searchFilter, startDate, endDate])

  // Initial load
  useEffect(() => {
    fetchStats()
    fetchLogFiles()
  }, [fetchStats, fetchLogFiles])

  // Refetch when filters change (including initial load)
  useEffect(() => {
    fetchLogs()
    fetchTotalCount()
  }, [fetchLogs, fetchTotalCount])

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(() => {
      fetchLogs()
    }, refreshInterval * 1000)

    return () => clearInterval(interval)
  }, [autoRefresh, refreshInterval, fetchLogs])

  // Auto-scroll to bottom when new logs arrive (but not when loading older logs)
  useEffect(() => {
    if (autoScroll && logsEndRef.current && !isLoadingOlderRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  const formatTimestamp = (timestamp) => {
    try {
      const date = new Date(timestamp)
      return date.toLocaleString()
    } catch {
      return timestamp
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      fetchLogs()
    }
  }

  const loadMore = () => {
    fetchLogs(true)
  }

  const clearDateFilters = () => {
    setStartDate('')
    setEndDate('')
  }

  const setQuickDateRange = (days) => {
    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - days)
    setStartDate(start.toISOString().split('T')[0])
    setEndDate(end.toISOString().split('T')[0])
  }

  return (
    <div style={{
      padding: '20px',
      backgroundColor: '#0f0f23',
      minHeight: '100vh',
      color: '#e0e0e0'
    }}>
      <h1 style={{
        color: '#fff',
        marginBottom: '20px',
        display: 'flex',
        alignItems: 'center',
        gap: '10px'
      }}>
        📋 Application Logs
        {autoRefresh && (
          <span style={{
            fontSize: '12px',
            backgroundColor: '#22c55e',
            color: '#fff',
            padding: '2px 8px',
            borderRadius: '4px',
            animation: 'pulse 2s infinite'
          }}>
            LIVE
          </span>
        )}
        {totalCount !== null && (
          <span style={{
            fontSize: '14px',
            color: '#888',
            fontWeight: 'normal'
          }}>
            ({totalCount.toLocaleString()} total logs)
          </span>
        )}
      </h1>

      {/* Stats Bar */}
      {stats && (
        <div style={{
          display: 'flex',
          gap: '20px',
          marginBottom: '20px',
          padding: '15px',
          backgroundColor: '#1a1a2e',
          borderRadius: '8px',
          flexWrap: 'wrap',
          alignItems: 'center'
        }}>
          <div>
            <span style={{ color: '#888' }}>Log Directory:</span>{' '}
            <code style={{ color: '#4ade80' }}>{stats.log_directory}</code>
          </div>
          <div>
            <span style={{ color: '#888' }}>Current File:</span>{' '}
            <span style={{ color: '#fff' }}>{stats.current_file_size_mb} MB</span>
          </div>
          <div>
            <span style={{ color: '#888' }}>Files:</span>{' '}
            <span style={{ color: '#fff' }}>{stats.file_count}</span>
            {stats.archive_count > 0 && (
              <span style={{ color: '#888' }}> (+{stats.archive_count} archived)</span>
            )}
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            {Object.entries(stats.level_counts || {}).map(([level, count]) => (
              <span key={level} style={{
                color: LEVEL_COLORS[level] || '#888',
                fontSize: '12px'
              }}>
                {level}: {count}
              </span>
            ))}
          </div>
          <button
            onClick={() => setShowFiles(!showFiles)}
            style={{
              marginLeft: 'auto',
              padding: '4px 12px',
              borderRadius: '4px',
              border: '1px solid #4b5563',
              backgroundColor: showFiles ? '#374151' : 'transparent',
              color: '#9ca3af',
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            📁 {showFiles ? 'Hide' : 'Show'} Files
          </button>
        </div>
      )}

      {/* Log Files Panel - Informational only */}
      {showFiles && logFiles.length > 0 && (
        <div style={{
          marginBottom: '20px',
          padding: '15px',
          backgroundColor: '#1a1a2e',
          borderRadius: '8px',
          border: '1px solid #333'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <h3 style={{ color: '#fff', margin: 0, fontSize: '14px' }}>
              📁 Log Files Storage
            </h3>
            <span style={{ color: '#666', fontSize: '11px' }}>
              ℹ️ All files are searched automatically
            </span>
          </div>
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '8px'
          }}>
            {logFiles.map((file, index) => (
              <div key={index} style={{
                padding: '6px 10px',
                backgroundColor: '#16162a',
                borderRadius: '4px',
                border: '1px solid #333',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <span style={{
                  fontFamily: 'monospace',
                  fontSize: '11px',
                  color: file.type === 'current' ? '#22c55e' : '#9ca3af'
                }}>
                  {file.name}
                </span>
                <span style={{ color: '#666', fontSize: '10px' }}>
                  {file.size_mb}MB
                </span>
                {file.type === 'current' && (
                  <span style={{
                    fontSize: '9px',
                    backgroundColor: '#22c55e',
                    color: '#000',
                    padding: '1px 4px',
                    borderRadius: '3px',
                    fontWeight: 'bold'
                  }}>
                    ACTIVE
                  </span>
                )}
                {file.compressed && (
                  <span style={{ fontSize: '10px' }}>📦</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{
        display: 'flex',
        gap: '15px',
        marginBottom: '20px',
        flexWrap: 'wrap',
        alignItems: 'flex-end'
      }}>
        <div>
          <label style={{ color: '#888', fontSize: '12px', display: 'block', marginBottom: '4px' }}>
            Level
          </label>
          <select
            value={levelFilter}
            onChange={(e) => setLevelFilter(e.target.value)}
            style={{
              padding: '8px 12px',
              borderRadius: '4px',
              border: '1px solid #333',
              backgroundColor: '#1a1a2e',
              color: '#fff',
              cursor: 'pointer'
            }}
          >
            {LOG_LEVELS.map(level => (
              <option key={level} value={level}>{level}</option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ color: '#888', fontSize: '12px', display: 'block', marginBottom: '4px' }}>
            Logger
          </label>
          <input
            type="text"
            value={loggerFilter}
            onChange={(e) => setLoggerFilter(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Filter by logger name..."
            style={{
              padding: '8px 12px',
              borderRadius: '4px',
              border: '1px solid #333',
              backgroundColor: '#1a1a2e',
              color: '#fff',
              width: '180px'
            }}
          />
        </div>

        <div>
          <label style={{ color: '#888', fontSize: '12px', display: 'block', marginBottom: '4px' }}>
            Search
          </label>
          <input
            type="text"
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search in messages..."
            style={{
              padding: '8px 12px',
              borderRadius: '4px',
              border: '1px solid #333',
              backgroundColor: '#1a1a2e',
              color: '#fff',
              width: '200px'
            }}
          />
        </div>

        <div>
          <label style={{ color: '#888', fontSize: '12px', display: 'block', marginBottom: '4px' }}>
            Per Page
          </label>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            style={{
              padding: '8px 12px',
              borderRadius: '4px',
              border: '1px solid #333',
              backgroundColor: '#1a1a2e',
              color: '#fff',
              cursor: 'pointer'
            }}
          >
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={250}>250</option>
            <option value={500}>500</option>
            <option value={1000}>1000</option>
            <option value={5000}>5000</option>
          </select>
        </div>
      </div>

      {/* Date Range Filters */}
      <div style={{
        display: 'flex',
        gap: '15px',
        marginBottom: '20px',
        flexWrap: 'wrap',
        alignItems: 'flex-end'
      }}>
        <div>
          <label style={{ color: '#888', fontSize: '12px', display: 'block', marginBottom: '4px' }}>
            Start Date
          </label>
          <input
            type="datetime-local"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            style={{
              padding: '8px 12px',
              borderRadius: '4px',
              border: '1px solid #333',
              backgroundColor: '#1a1a2e',
              color: '#fff'
            }}
          />
        </div>

        <div>
          <label style={{ color: '#888', fontSize: '12px', display: 'block', marginBottom: '4px' }}>
            End Date
          </label>
          <input
            type="datetime-local"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            style={{
              padding: '8px 12px',
              borderRadius: '4px',
              border: '1px solid #333',
              backgroundColor: '#1a1a2e',
              color: '#fff'
            }}
          />
        </div>

        <div style={{ display: 'flex', gap: '5px' }}>
          <button
            onClick={() => setQuickDateRange(1)}
            style={{
              padding: '8px 12px',
              borderRadius: '4px',
              border: '1px solid #333',
              backgroundColor: '#1a1a2e',
              color: '#9ca3af',
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            24h
          </button>
          <button
            onClick={() => setQuickDateRange(7)}
            style={{
              padding: '8px 12px',
              borderRadius: '4px',
              border: '1px solid #333',
              backgroundColor: '#1a1a2e',
              color: '#9ca3af',
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            7d
          </button>
          <button
            onClick={() => setQuickDateRange(30)}
            style={{
              padding: '8px 12px',
              borderRadius: '4px',
              border: '1px solid #333',
              backgroundColor: '#1a1a2e',
              color: '#9ca3af',
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            30d
          </button>
          {(startDate || endDate) && (
            <button
              onClick={clearDateFilters}
              style={{
                padding: '8px 12px',
                borderRadius: '4px',
                border: '1px solid #ef4444',
                backgroundColor: 'transparent',
                color: '#ef4444',
                cursor: 'pointer',
                fontSize: '12px'
              }}
            >
              Clear
            </button>
          )}
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: '10px' }}>
          <button
            onClick={() => fetchLogs()}
            disabled={loading}
            style={{
              padding: '8px 16px',
              borderRadius: '4px',
              border: 'none',
              backgroundColor: '#3b82f6',
              color: '#fff',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.5 : 1
            }}
          >
            {loading ? 'Loading...' : '🔄 Refresh'}
          </button>

          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            style={{
              padding: '8px 16px',
              borderRadius: '4px',
              border: 'none',
              backgroundColor: autoRefresh ? '#22c55e' : '#6b7280',
              color: '#fff',
              cursor: 'pointer'
            }}
          >
            {autoRefresh ? '⏸️ Pause' : '▶️ Auto'}
          </button>

          <button
            onClick={() => setAutoScroll(!autoScroll)}
            style={{
              padding: '8px 16px',
              borderRadius: '4px',
              border: 'none',
              backgroundColor: autoScroll ? '#8b5cf6' : '#6b7280',
              color: '#fff',
              cursor: 'pointer'
            }}
          >
            {autoScroll ? '📌 Pinned' : '📌 Pin'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: '15px',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid #ef4444',
          borderRadius: '8px',
          color: '#ef4444',
          marginBottom: '20px'
        }}>
          Error: {error}
        </div>
      )}

      {/* Load More (older) button at top */}
      {totalCount !== null && logs.length < totalCount && (
        <div style={{
          marginBottom: '10px',
          textAlign: 'center'
        }}>
          <button
            onClick={loadMore}
            disabled={loadingMore}
            style={{
              padding: '8px 24px',
              borderRadius: '4px',
              border: '1px solid #4b5563',
              backgroundColor: '#1a1a2e',
              color: '#9ca3af',
              cursor: loadingMore ? 'not-allowed' : 'pointer',
              opacity: loadingMore ? 0.5 : 1
            }}
          >
            {loadingMore ? 'Loading...' : `⬆️ Load ${limit} older logs (${logs.length.toLocaleString()} / ${totalCount.toLocaleString()})`}
          </button>
        </div>
      )}

      {/* Logs */}
      <div style={{
        backgroundColor: '#1a1a2e',
        borderRadius: '8px',
        overflow: 'hidden',
        border: '1px solid #333'
      }}>
        <div style={{
          padding: '10px 15px',
          backgroundColor: '#16162a',
          borderBottom: '1px solid #333',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span style={{ color: '#888', fontSize: '12px' }}>
            Showing {logs.length.toLocaleString()} log entries
            {totalCount !== null && totalCount > logs.length && (
              <span> of {totalCount.toLocaleString()} total</span>
            )}
          </span>
          <span style={{ color: '#888', fontSize: '12px' }}>
            {autoRefresh && `Refreshing every ${refreshInterval}s`}
          </span>
        </div>

        <div
          ref={logsContainerRef}
          style={{
            maxHeight: '600px',
            overflow: 'auto',
            fontFamily: 'Monaco, Consolas, monospace',
            fontSize: '12px'
          }}
        >
          {logs.length === 0 && !loading && (
            <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
              No logs found matching your filters
            </div>
          )}

          {logs.map((log, index) => (
            <div
              key={`${log.timestamp}-${index}`}
              style={{
                padding: '8px 15px',
                borderBottom: '1px solid #222',
                backgroundColor: LEVEL_BG_COLORS[log.level] || 'transparent',
                display: 'grid',
                gridTemplateColumns: '160px 80px 200px 1fr',
                gap: '15px',
                alignItems: 'start'
              }}
            >
              <span style={{ color: '#888' }}>
                {formatTimestamp(log.timestamp)}
              </span>
              <span style={{
                color: LEVEL_COLORS[log.level] || '#888',
                fontWeight: 'bold'
              }}>
                {log.level}
              </span>
              <span style={{
                color: '#8b5cf6',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {log.logger}
              </span>
              <span style={{
                color: '#e0e0e0',
                wordBreak: 'break-word'
              }}>
                {log.message}
                {log.extra && Object.keys(log.extra).length > 0 && (
                  <span style={{ color: '#666', marginLeft: '10px' }}>
                    {JSON.stringify(log.extra)}
                  </span>
                )}
              </span>
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
      </div>

      {/* Quick Actions */}
      <div style={{
        marginTop: '20px',
        display: 'flex',
        gap: '10px',
        flexWrap: 'wrap'
      }}>
        <button
          onClick={async () => {
            setLevelFilter('ERROR')
          }}
          style={{
            padding: '8px 16px',
            borderRadius: '4px',
            border: '1px solid #ef4444',
            backgroundColor: 'transparent',
            color: '#ef4444',
            cursor: 'pointer'
          }}
        >
          🔴 Show Errors Only
        </button>
        <button
          onClick={async () => {
            setLevelFilter('WARNING')
          }}
          style={{
            padding: '8px 16px',
            borderRadius: '4px',
            border: '1px solid #f59e0b',
            backgroundColor: 'transparent',
            color: '#f59e0b',
            cursor: 'pointer'
          }}
        >
          🟡 Show Warnings
        </button>
        <button
          onClick={() => {
            setLoggerFilter('live_trading.brokers')
          }}
          style={{
            padding: '8px 16px',
            borderRadius: '4px',
            border: '1px solid #3b82f6',
            backgroundColor: 'transparent',
            color: '#3b82f6',
            cursor: 'pointer'
          }}
        >
          🔌 Broker Logs
        </button>
        <button
          onClick={() => {
            setSearchFilter('[CONNECTION]')
          }}
          style={{
            padding: '8px 16px',
            borderRadius: '4px',
            border: '1px solid #22c55e',
            backgroundColor: 'transparent',
            color: '#22c55e',
            cursor: 'pointer'
          }}
        >
          📡 Connection Logs
        </button>
        <button
          onClick={() => {
            setSearchFilter('[ORDER]')
          }}
          style={{
            padding: '8px 16px',
            borderRadius: '4px',
            border: '1px solid #8b5cf6',
            backgroundColor: 'transparent',
            color: '#8b5cf6',
            cursor: 'pointer'
          }}
        >
          📋 Order Logs
        </button>
        <button
          onClick={() => {
            setLevelFilter('ALL')
            setLoggerFilter('')
            setSearchFilter('')
            clearDateFilters()
          }}
          style={{
            padding: '8px 16px',
            borderRadius: '4px',
            border: '1px solid #6b7280',
            backgroundColor: 'transparent',
            color: '#6b7280',
            cursor: 'pointer'
          }}
        >
          🔄 Clear All Filters
        </button>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  )
}
