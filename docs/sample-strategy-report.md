# Forex Multi-Timeframe Strategy Test Results

**Generated:** 2024-12-18 14:30:00
**Total Configurations:** 15
**Initial Capital:** $10,000.00
**Commission Rate:** 0.0002 (0.02%)

---

## Asset: USD-CAD

### Bar Size: 5 mins

**File:** `data-USD-CASH-IDEALPRO-CAD-1 Y-5 mins.csv`
**Data Points:** 52560 bars

**Testing against higher timeframes:** 15 mins, 1 hour, 4 hours, 1 day

| Higher TF | Return (%) | Sharpe | Max DD (%) | Win Rate (%) | # Trades |
|-----------|------------|--------|------------|--------------|----------|
| 15 mins | 12.45 | 1.23 | -8.50 | 55.20 | 245 |
| 1 hour | 15.30 | 1.45 | -7.20 | 58.10 | 189 |
| 4 hours | 18.75 | 1.67 | -6.80 | 61.30 | 142 |
| 1 day | 22.10 | 1.89 | -5.90 | 64.50 | 98 |

### Bar Size: 15 mins

**File:** `data-USD-CASH-IDEALPRO-CAD-1 Y-15 mins.csv`
**Data Points:** 17520 bars

**Testing against higher timeframes:** 1 hour, 4 hours, 1 day

| Higher TF | Return (%) | Sharpe | Max DD (%) | Win Rate (%) | # Trades |
|-----------|------------|--------|------------|--------------|----------|
| 1 hour | 14.20 | 1.35 | -7.80 | 56.40 | 156 |
| 4 hours | 17.60 | 1.58 | -6.50 | 59.70 | 118 |
| 1 day | 20.90 | 1.82 | -5.60 | 63.20 | 82 |

## Asset: EUR-CHF

### Bar Size: 1 hour

**File:** `data-EUR-CASH-IDEALPRO-CHF-1 Y-1 hour.csv`
**Data Points:** 6208 bars

**Testing against higher timeframes:** 4 hours, 1 day

| Higher TF | Return (%) | Sharpe | Max DD (%) | Win Rate (%) | # Trades |
|-----------|------------|--------|------------|--------------|----------|
| 4 hours | 16.80 | 1.52 | -7.10 | 58.90 | 95 |
| 1 day | 19.40 | 1.74 | -6.20 | 62.10 | 67 |

---

## 📊 Summary of All Results

**Total Successful Tests:** 9

### All Configurations (Sorted by Return)

| Rank | Configuration | Return (%) | Sharpe | Max DD (%) | Win Rate (%) | # Trades |
|------|---------------|------------|--------|------------|--------------|----------|
| 1 | USD-CAD (5 mins vs 1 day) | 22.10 | 1.89 | -5.90 | 64.50 | 98 |
| 2 | USD-CAD (15 mins vs 1 day) | 20.90 | 1.82 | -5.60 | 63.20 | 82 |
| 3 | EUR-CHF (1 hour vs 1 day) | 19.40 | 1.74 | -6.20 | 62.10 | 67 |
| 4 | USD-CAD (5 mins vs 4 hours) | 18.75 | 1.67 | -6.80 | 61.30 | 142 |
| 5 | USD-CAD (15 mins vs 4 hours) | 17.60 | 1.58 | -6.50 | 59.70 | 118 |
| 6 | EUR-CHF (1 hour vs 4 hours) | 16.80 | 1.52 | -7.10 | 58.90 | 95 |
| 7 | USD-CAD (5 mins vs 1 hour) | 15.30 | 1.45 | -7.20 | 58.10 | 189 |
| 8 | USD-CAD (15 mins vs 1 hour) | 14.20 | 1.35 | -7.80 | 56.40 | 156 |
| 9 | USD-CAD (5 mins vs 15 mins) | 12.45 | 1.23 | -8.50 | 55.20 | 245 |

## 🏆 Top 5 Configurations

### 1. USD-CAD (5 mins vs 1 day)

- **Return:** 22.10%
- **Sharpe Ratio:** 1.89
- **Max Drawdown:** -5.90%
- **Win Rate:** 64.50%
- **Number of Trades:** 98
- **Asset:** USD-CAD
- **Lower Timeframe:** 5 mins
- **Higher Timeframe:** 1 day

### 2. USD-CAD (15 mins vs 1 day)

- **Return:** 20.90%
- **Sharpe Ratio:** 1.82
- **Max Drawdown:** -5.60%
- **Win Rate:** 63.20%
- **Number of Trades:** 82
- **Asset:** USD-CAD
- **Lower Timeframe:** 15 mins
- **Higher Timeframe:** 1 day

### 3. EUR-CHF (1 hour vs 1 day)

- **Return:** 19.40%
- **Sharpe Ratio:** 1.74
- **Max Drawdown:** -6.20%
- **Win Rate:** 62.10%
- **Number of Trades:** 67
- **Asset:** EUR-CHF
- **Lower Timeframe:** 1 hour
- **Higher Timeframe:** 1 day

### 4. USD-CAD (5 mins vs 4 hours)

- **Return:** 18.75%
- **Sharpe Ratio:** 1.67
- **Max Drawdown:** -6.80%
- **Win Rate:** 61.30%
- **Number of Trades:** 142
- **Asset:** USD-CAD
- **Lower Timeframe:** 5 mins
- **Higher Timeframe:** 4 hours

### 5. USD-CAD (15 mins vs 4 hours)

- **Return:** 17.60%
- **Sharpe Ratio:** 1.58
- **Max Drawdown:** -6.50%
- **Win Rate:** 59.70%
- **Number of Trades:** 118
- **Asset:** USD-CAD
- **Lower Timeframe:** 15 mins
- **Higher Timeframe:** 4 hours

