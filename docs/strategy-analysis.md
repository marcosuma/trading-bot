# Technical Indicators Analysis & Strategy Design

## CSV Columns Available

### Price Data (OHLCV)
- **open**: Opening price of the candlestick
- **close**: Closing price of the candlestick
- **high**: Highest price during the period
- **low**: Lowest price during the period
- **volume**: Trading volume (often -1 for forex, not reliable)
- **shifted_open**: Next period's opening price (for forward-looking analysis)

### Moving Averages
- **SMA_50**: Simple Moving Average over 50 periods - medium-term trend
- **SMA_100**: Simple Moving Average over 100 periods - long-term trend
- **SMA_200**: Simple Moving Average over 200 periods - very long-term trend
- **EMA_10**: Exponential Moving Average over 10 periods - short-term trend

**Trading Signals:**
- Price above SMA = uptrend, below = downtrend
- SMA crossovers: 50 crossing above 100/200 = bullish, below = bearish
- Price distance from SMA indicates trend strength

### Momentum Indicators

#### RSI_14 (Relative Strength Index)
- **Range**: 0-100
- **Oversold**: <30 (potential buy)
- **Overbought**: >70 (potential sell)
- **Neutral**: 40-60
- **Divergence**: Price makes new high but RSI doesn't = weakening momentum

**Trading Signals:**
- RSI <30 + price bounce = buy opportunity
- RSI >70 + price rejection = sell opportunity
- RSI divergence = trend reversal signal

#### MACD (Moving Average Convergence Divergence)
- **macd**: 12-period EMA - 26-period EMA (momentum)
- **macd_s**: 9-period EMA of MACD (signal line)
- **macd_h**: MACD - Signal (histogram, shows momentum strength)

**Trading Signals:**
- MACD crosses above signal = bullish momentum (buy)
- MACD crosses below signal = bearish momentum (sell)
- MACD histogram increasing = momentum strengthening
- MACD histogram decreasing = momentum weakening
- MACD divergence = potential reversal

### Trend Strength Indicators

#### ADX (Average Directional Index)
- **adx**: Trend strength (0-100)
  - <20: Weak/no trend (ranging market)
  - 20-40: Moderate trend
  - >40: Strong trend
- **plus_di**: +DI (bullish directional indicator)
- **minus_di**: -DI (bearish directional indicator)

**Trading Signals:**
- ADX >25: Strong trend, use trend-following strategies
- ADX <20: Weak trend, use mean reversion strategies
- +DI > -DI: Bullish trend
- -DI > +DI: Bearish trend
- +DI crosses above -DI with ADX >20 = strong buy signal
- -DI crosses above +DI with ADX >20 = strong sell signal

### Volatility Indicators

#### ATR (Average True Range)
- **atr**: 14-period average of true range (volatility measure)
- Measures price volatility, not direction

**Trading Signals:**
- High ATR = high volatility = wider stops needed
- Low ATR = low volatility = tighter stops possible
- ATR increasing = volatility expanding (breakout potential)
- ATR decreasing = volatility contracting (consolidation)

#### STDEV_30
- 30-period standard deviation of close prices
- Used for volatility-based entry/exit buffers

#### Bollinger Bands
- **bollinger_up**: Upper band (SMA_20 + 2*std)
- **bollinger_down**: Lower band (SMA_20 - 2*std)
- Middle band = SMA_20 (not explicitly stored)

**Trading Signals:**
- Price touches lower band + RSI oversold = buy (mean reversion)
- Price touches upper band + RSI overbought = sell (mean reversion)
- Price breaks above upper band = potential breakout (trend continuation)
- Price breaks below lower band = potential breakdown
- Bands narrowing = low volatility (squeeze, often precedes big move)
- Bands widening = high volatility (trending market)

### Pattern Indicators

#### local_extrema
- **LOCAL_MAX**: Swing high (local maximum)
- **LOCAL_MIN**: Swing low (local minimum)
- Identifies support/resistance levels

**Trading Signals:**
- LOCAL_MAX = potential resistance level
- LOCAL_MIN = potential support level
- Price breaking above LOCAL_MAX = bullish breakout
- Price breaking below LOCAL_MIN = bearish breakdown
- Multiple LOCAL_MAX at similar levels = strong resistance
- Multiple LOCAL_MIN at similar levels = strong support

## Strategy Design Principles

### 1. Multi-Timeframe Confirmation
- Use multiple indicators to confirm signals
- Reduce false signals by requiring multiple conditions

### 2. Market Regime Detection
- **Trending Market** (ADX >25): Use trend-following strategies
- **Ranging Market** (ADX <20): Use mean reversion strategies

### 3. Entry Conditions (BUY)
- **Trend Following:**
  - ADX >25 (strong trend)
  - +DI > -DI (bullish direction)
  - Price above SMA_50 (uptrend)
  - MACD above signal (bullish momentum)
  - RSI 40-70 (not overbought, room to run)

- **Mean Reversion:**
  - ADX <20 (weak trend, ranging)
  - Price at or below Bollinger lower band
  - RSI <30 (oversold)
  - Price near LOCAL_MIN (support level)

### 4. Exit Conditions (SELL)
- **Trend Following:**
  - ADX >25 (strong trend)
  - -DI > +DI (bearish direction)
  - Price below SMA_50 (downtrend)
  - MACD below signal (bearish momentum)
  - RSI 30-60 (not oversold, room to fall)

- **Mean Reversion:**
  - ADX <20 (weak trend, ranging)
  - Price at or above Bollinger upper band
  - RSI >70 (overbought)
  - Price near LOCAL_MAX (resistance level)

### 5. Risk Management
- Use ATR for stop-loss placement (2-3x ATR)
- Use ATR for take-profit targets (2-3x ATR)
- Don't trade when volatility is extreme (ATR >3x average)

### 6. Signal Quality Filters
- Require minimum 2-3 confirming indicators
- Avoid trading during low ADX periods unless mean reversion setup
- Wait for clear breakouts above/below key levels (LOCAL_MAX/MIN)

## Proposed Multi-Indicator Strategy

### Strategy Name: **Adaptive Multi-Indicator Strategy (AMIS)**

**Core Concept:**
- Adapts to market conditions (trending vs ranging)
- Uses multiple indicators for confirmation
- Combines trend-following and mean reversion approaches
- Uses local extrema for support/resistance levels

**Entry Logic:**

1. **Market Regime Detection:**
   - If ADX >25: Use trend-following mode
   - If ADX <20: Use mean reversion mode
   - If 20 <= ADX <= 25: Wait for clearer signal

2. **Trend-Following BUY:**
   - ADX >25 (strong trend)
   - +DI > -DI (bullish direction)
   - Price > SMA_50 (uptrend)
   - MACD > macd_s (bullish momentum)
   - RSI between 40-65 (not overbought)
   - Price breaks above recent LOCAL_MAX (breakout confirmation)
   - ATR not extreme (filter out high volatility periods)

3. **Mean Reversion BUY:**
   - ADX <20 (ranging market)
   - Price <= bollinger_down (at lower band)
   - RSI <35 (oversold but not extreme)
   - Price near LOCAL_MIN (support level)
   - MACD histogram turning positive (momentum shift)

4. **Trend-Following SELL:**
   - ADX >25 (strong trend)
   - -DI > +DI (bearish direction)
   - Price < SMA_50 (downtrend)
   - MACD < macd_s (bearish momentum)
   - RSI between 35-60 (not oversold)
   - Price breaks below recent LOCAL_MIN (breakdown confirmation)
   - ATR not extreme

5. **Mean Reversion SELL:**
   - ADX <20 (ranging market)
   - Price >= bollinger_up (at upper band)
   - RSI >65 (overbought but not extreme)
   - Price near LOCAL_MAX (resistance level)
   - MACD histogram turning negative (momentum shift)

**Exit Logic:**
- Take profit: 2.5x ATR from entry
- Stop loss: 2x ATR from entry
- Trailing stop: If profit >1.5x ATR, move stop to breakeven + 0.5x ATR
- Exit on opposite signal (if buy signal, exit on sell signal)

**Risk Management:**
- Maximum position size: 2% of capital per trade
- Don't enter if ATR >3x rolling average ATR (extreme volatility)
- Don't trade if insufficient data (missing key indicators)

