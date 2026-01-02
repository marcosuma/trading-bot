# API Reference

Complete REST API reference for the Live Trading System.

## Base URL

```
http://localhost:8000/api
```

## Operations

### Create Operation

`POST /api/operations`

Create a new trading operation.

**Request Body**:
```json
{
  "asset": "USD-CAD",
  "bar_sizes": ["1 hour", "15 mins"],
  "primary_bar_size": "1 hour",
  "strategy_name": "MomentumStrategy",
  "strategy_config": {},
  "initial_capital": 10000,
  "stop_loss_type": "ATR",
  "stop_loss_value": 1.5,
  "take_profit_type": "RISK_REWARD",
  "take_profit_value": 2.0,
  "crash_recovery_mode": "CLOSE_ALL"
}
```

**Response**: `201 Created` with operation details

### List Operations

`GET /api/operations`

List all trading operations.

**Query Parameters**:
- `status`: Filter by status (active, paused, closed)

**Response**: Array of operations

### Get Operation

`GET /api/operations/{id}`

Get operation details.

**Response**: Operation object

### Stop Operation

`DELETE /api/operations/{id}`

Stop an operation (closes all positions).

**Response**: `200 OK`

### Pause Operation

`POST /api/operations/{id}/pause`

Pause an operation (stops trading, keeps positions).

**Response**: `200 OK`

### Resume Operation

`POST /api/operations/{id}/resume`

Resume a paused operation.

**Response**: `200 OK`

## Positions

### Get Positions

`GET /api/operations/{id}/positions`

Get all positions for an operation.

**Response**: Array of positions

## Transactions

### Get Transactions

`GET /api/operations/{id}/transactions`

Get all transactions for an operation.

**Response**: Array of transactions

## Trades

### Get Trades

`GET /api/operations/{id}/trades`

Get completed trades for an operation.

**Response**: Array of trades

## Orders

### Get Orders

`GET /api/operations/{id}/orders`

Get all orders for an operation.

**Response**: Array of orders

## Statistics

### Get Operation Statistics

`GET /api/operations/{id}/stats`

Get statistics for an operation.

**Response**: Statistics object

### Get Overall Statistics

`GET /api/stats/overall`

Get overall system statistics.

**Response**: Overall statistics object

## Error Responses

All endpoints return standard HTTP status codes:

- `200 OK`: Success
- `201 Created`: Resource created
- `400 Bad Request`: Invalid request
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

Error response format:
```json
{
  "detail": "Error message"
}
```

## Related Documentation

- [Live Trading System](README.md) - Overview
- [Frontend Guide](frontend.md) - Frontend usage
- [Configuration](../configuration.md) - Configuration options

