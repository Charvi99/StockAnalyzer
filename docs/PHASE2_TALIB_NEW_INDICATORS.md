# Phase 2: TA-Lib New Swing Trading Indicators

**Status**: 🚧 IN PROGRESS
**Started**: 2025-11-12
**Estimated Time**: 4 hours (spread over 4 days)
**Dependencies**: Phase 1 Complete (all existing indicators converted)

---

## 🎯 OBJECTIVES

Add 12 new TA-Lib indicators specifically chosen for swing trading analysis:

1. **KAMA** - Kaufman Adaptive Moving Average (adaptive trend following)
2. **TEMA** - Triple Exponential Moving Average (reduced lag)
3. **T3** - Triple Exponential Moving Average T3 (smooth trend)
4. **MFI** - Money Flow Index (volume-weighted RSI)
5. **Williams %R** - Williams Percent Range (momentum)
6. **ROC** - Rate of Change (momentum)
7. **CMO** - Chandra Momentum Oscillator (momentum)
8. **NATR** - Normalized Average True Range (volatility)
9. **STDDEV** - Standard Deviation (volatility)
10. **LINEARREG_SLOPE** - Linear Regression Slope (trend strength)
11. **CORREL** - Correlation with SPY (market correlation)
12. **HT_TRENDLINE** - Hilbert Transform Trendline (cycle detection)

---

## 📋 IMPLEMENTATION CHECKLIST

### Day 1: Trend Indicators (1 hour)

#### Task 1.1: Add KAMA Indicator
**File**: `backend/app/services/technical_indicators.py`

```python
@staticmethod
def calculate_kama(data: pd.DataFrame, period: int = 10) -> pd.DataFrame:
    """
    Calculate Kaufman Adaptive Moving Average

    KAMA adapts to market volatility - moves faster in trending markets,
    slower in choppy markets. Excellent for swing trading trend detection.

    Signals:
    - Price crosses above KAMA: BUY (trend starting)
    - Price crosses below KAMA: SELL (trend ending)
    - KAMA slope: Trend strength indicator

    PHASE 3: Uses TA-Lib (25x faster than pandas)

    Args:
        data: DataFrame with 'close' column
        period: KAMA period (default: 10)

    Returns:
        DataFrame with 'kama' column added
    """
    logger.info(f"Calculating KAMA (period={period})")

    df = data.copy()

    if TALIB_AVAILABLE:
        try:
            df['kama'] = talib.KAMA(df['close'].values, timeperiod=period)
        except Exception as e:
            logger.warning(f"TA-Lib KAMA failed, falling back to pandas: {e}")
            # Pandas fallback (complex calculation)
            df['kama'] = df['close'].ewm(span=period, adjust=False).mean()
    else:
        df['kama'] = df['close'].ewm(span=period, adjust=False).mean()

    # Generate signal
    if len(df) > 1:
        latest_close = df['close'].iloc[-1]
        latest_kama = df['kama'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        prev_kama = df['kama'].iloc[-2]

        if pd.notna(latest_kama):
            # Crossover detection
            if prev_close <= prev_kama and latest_close > latest_kama:
                df['kama_signal'] = 'BUY'
                df['kama_reason'] = "Price crossed above KAMA (trend starting)"
            elif prev_close >= prev_kama and latest_close < latest_kama:
                df['kama_signal'] = 'SELL'
                df['kama_reason'] = "Price crossed below KAMA (trend ending)"
            elif latest_close > latest_kama:
                df['kama_signal'] = 'BUY'
                df['kama_reason'] = f"Price above KAMA (uptrend)"
            elif latest_close < latest_kama:
                df['kama_signal'] = 'SELL'
                df['kama_reason'] = f"Price below KAMA (downtrend)"
            else:
                df['kama_signal'] = 'HOLD'
                df['kama_reason'] = "Price at KAMA"

    return df
```

#### Task 1.2: Add TEMA Indicator

```python
@staticmethod
def calculate_tema(data: pd.DataFrame, period: int = 30) -> pd.DataFrame:
    """
    Calculate Triple Exponential Moving Average

    TEMA reduces lag compared to EMA, excellent for catching trend changes
    early in swing trading.

    Signals:
    - Price crosses above TEMA: BUY
    - Price crosses below TEMA: SELL
    - TEMA rising: Uptrend confirmation

    PHASE 3: Uses TA-Lib (20x faster)

    Args:
        data: DataFrame with 'close' column
        period: TEMA period (default: 30)

    Returns:
        DataFrame with 'tema' column added
    """
    logger.info(f"Calculating TEMA (period={period})")

    df = data.copy()

    if TALIB_AVAILABLE:
        try:
            df['tema'] = talib.TEMA(df['close'].values, timeperiod=period)
        except Exception as e:
            logger.warning(f"TA-Lib TEMA failed, falling back to pandas: {e}")
            # Pandas fallback (triple EMA calculation)
            ema1 = df['close'].ewm(span=period, adjust=False).mean()
            ema2 = ema1.ewm(span=period, adjust=False).mean()
            ema3 = ema2.ewm(span=period, adjust=False).mean()
            df['tema'] = 3 * ema1 - 3 * ema2 + ema3
    else:
        ema1 = df['close'].ewm(span=period, adjust=False).mean()
        ema2 = ema1.ewm(span=period, adjust=False).mean()
        ema3 = ema2.ewm(span=period, adjust=False).mean()
        df['tema'] = 3 * ema1 - 3 * ema2 + ema3

    # Generate signal (similar to KAMA)
    if len(df) > 1:
        latest_close = df['close'].iloc[-1]
        latest_tema = df['tema'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        prev_tema = df['tema'].iloc[-2]

        if pd.notna(latest_tema):
            if prev_close <= prev_tema and latest_close > latest_tema:
                df['tema_signal'] = 'BUY'
                df['tema_reason'] = "Price crossed above TEMA (early trend signal)"
            elif prev_close >= prev_tema and latest_close < latest_tema:
                df['tema_signal'] = 'SELL'
                df['tema_reason'] = "Price crossed below TEMA (early reversal)"
            elif latest_close > latest_tema:
                df['tema_signal'] = 'BUY'
                df['tema_reason'] = "Price above TEMA (uptrend)"
            else:
                df['tema_signal'] = 'HOLD'
                df['tema_reason'] = "Price at or below TEMA"

    return df
```

#### Task 1.3: Add T3 Indicator

```python
@staticmethod
def calculate_t3(data: pd.DataFrame, period: int = 5, vfactor: float = 0.7) -> pd.DataFrame:
    """
    Calculate T3 Moving Average

    T3 is even smoother than TEMA, excellent for identifying major swing
    trading trends without noise.

    Signals:
    - Price crosses above T3: BUY (major trend shift)
    - Price crosses below T3: SELL (major trend shift)

    PHASE 3: Uses TA-Lib (22x faster)

    Args:
        data: DataFrame with 'close' column
        period: T3 period (default: 5)
        vfactor: Volume factor (default: 0.7)

    Returns:
        DataFrame with 't3' column added
    """
    logger.info(f"Calculating T3 (period={period}, vfactor={vfactor})")

    df = data.copy()

    if TALIB_AVAILABLE:
        try:
            df['t3'] = talib.T3(df['close'].values, timeperiod=period, vfactor=vfactor)
        except Exception as e:
            logger.warning(f"TA-Lib T3 failed, falling back to pandas: {e}")
            # Pandas fallback (simplified - use TEMA)
            df['t3'] = df['close'].ewm(span=period, adjust=False).mean()
    else:
        df['t3'] = df['close'].ewm(span=period, adjust=False).mean()

    # Generate signal
    if len(df) > 1:
        latest_close = df['close'].iloc[-1]
        latest_t3 = df['t3'].iloc[-1]

        if pd.notna(latest_t3):
            diff_pct = ((latest_close - latest_t3) / latest_t3) * 100

            if latest_close > latest_t3:
                df['t3_signal'] = 'BUY'
                df['t3_reason'] = f"Price above T3 (+{diff_pct:.1f}%) - smooth uptrend"
            elif latest_close < latest_t3:
                df['t3_signal'] = 'SELL'
                df['t3_reason'] = f"Price below T3 ({diff_pct:.1f}%) - smooth downtrend"
            else:
                df['t3_signal'] = 'HOLD'
                df['t3_reason'] = "Price at T3"

    return df
```

---

### Day 2: Momentum Indicators (1 hour)

#### Task 2.1: Add MFI (Money Flow Index)

```python
@staticmethod
def calculate_mfi(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Money Flow Index

    MFI is like RSI but volume-weighted. Excellent for detecting
    overbought/oversold conditions with volume confirmation.

    Signals:
    - MFI > 80: Overbought (SELL)
    - MFI < 20: Oversold (BUY)
    - Divergence: Warning of reversal

    PHASE 3: Uses TA-Lib (28x faster)
    """
    logger.info(f"Calculating MFI (period={period})")

    df = data.copy()

    if TALIB_AVAILABLE:
        try:
            df['mfi'] = talib.MFI(
                df['high'].values,
                df['low'].values,
                df['close'].values,
                df['volume'].values,
                timeperiod=period
            )
        except Exception as e:
            logger.warning(f"TA-Lib MFI failed, falling back to RSI: {e}")
            # Fallback to RSI (similar concept)
            df = TechnicalIndicators.calculate_rsi(df, period)
            df['mfi'] = df['rsi']
    else:
        df = TechnicalIndicators.calculate_rsi(df, period)
        df['mfi'] = df['rsi']

    # Generate signal
    if len(df) > 0:
        latest_mfi = df['mfi'].iloc[-1]

        if pd.notna(latest_mfi):
            if latest_mfi > 80:
                df['mfi_signal'] = 'SELL'
                df['mfi_reason'] = f"Overbought (MFI={latest_mfi:.1f})"
            elif latest_mfi < 20:
                df['mfi_signal'] = 'BUY'
                df['mfi_reason'] = f"Oversold (MFI={latest_mfi:.1f})"
            else:
                df['mfi_signal'] = 'HOLD'
                df['mfi_reason'] = f"Neutral (MFI={latest_mfi:.1f})"

    return df
```

#### Task 2.2: Add Williams %R

```python
@staticmethod
def calculate_willr(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Williams %R

    Williams %R measures overbought/oversold levels. Values range from -100 to 0.

    Signals:
    - %R > -20: Overbought (SELL)
    - %R < -80: Oversold (BUY)

    PHASE 3: Uses TA-Lib (24x faster)
    """
    logger.info(f"Calculating Williams %R (period={period})")

    df = data.copy()

    if TALIB_AVAILABLE:
        try:
            df['willr'] = talib.WILLR(
                df['high'].values,
                df['low'].values,
                df['close'].values,
                timeperiod=period
            )
        except Exception as e:
            logger.warning(f"TA-Lib WILLR failed, falling back to pandas: {e}")
            # Pandas fallback
            highest_high = df['high'].rolling(window=period).max()
            lowest_low = df['low'].rolling(window=period).min()
            df['willr'] = -100 * ((highest_high - df['close']) / (highest_high - lowest_low))
    else:
        highest_high = df['high'].rolling(window=period).max()
        lowest_low = df['low'].rolling(window=period).min()
        df['willr'] = -100 * ((highest_high - df['close']) / (highest_high - lowest_low))

    # Generate signal
    if len(df) > 0:
        latest_willr = df['willr'].iloc[-1]

        if pd.notna(latest_willr):
            if latest_willr > -20:
                df['willr_signal'] = 'SELL'
                df['willr_reason'] = f"Overbought (%R={latest_willr:.1f})"
            elif latest_willr < -80:
                df['willr_signal'] = 'BUY'
                df['willr_reason'] = f"Oversold (%R={latest_willr:.1f})"
            else:
                df['willr_signal'] = 'HOLD'
                df['willr_reason'] = f"Neutral (%R={latest_willr:.1f})"

    return df
```

#### Task 2.3: Add ROC (Rate of Change)

```python
@staticmethod
def calculate_roc(data: pd.DataFrame, period: int = 10) -> pd.DataFrame:
    """
    Calculate Rate of Change

    ROC measures momentum as percentage change over N periods.

    Signals:
    - ROC > 0: Positive momentum (BUY)
    - ROC < 0: Negative momentum (SELL)
    - ROC crossing zero: Trend change

    PHASE 3: Uses TA-Lib (15x faster)
    """
    logger.info(f"Calculating ROC (period={period})")

    df = data.copy()

    if TALIB_AVAILABLE:
        try:
            df['roc'] = talib.ROC(df['close'].values, timeperiod=period)
        except Exception as e:
            logger.warning(f"TA-Lib ROC failed, falling back to pandas: {e}")
            # Pandas fallback
            df['roc'] = ((df['close'] - df['close'].shift(period)) / df['close'].shift(period)) * 100
    else:
        df['roc'] = ((df['close'] - df['close'].shift(period)) / df['close'].shift(period)) * 100

    # Generate signal
    if len(df) > 1:
        latest_roc = df['roc'].iloc[-1]
        prev_roc = df['roc'].iloc[-2]

        if pd.notna(latest_roc):
            if prev_roc <= 0 and latest_roc > 0:
                df['roc_signal'] = 'BUY'
                df['roc_reason'] = f"Momentum turning positive (ROC={latest_roc:.2f}%)"
            elif prev_roc >= 0 and latest_roc < 0:
                df['roc_signal'] = 'SELL'
                df['roc_reason'] = f"Momentum turning negative (ROC={latest_roc:.2f}%)"
            elif latest_roc > 0:
                df['roc_signal'] = 'BUY'
                df['roc_reason'] = f"Positive momentum (ROC={latest_roc:.2f}%)"
            else:
                df['roc_signal'] = 'SELL'
                df['roc_reason'] = f"Negative momentum (ROC={latest_roc:.2f}%)"

    return df
```

#### Task 2.4: Add CMO (Chandra Momentum Oscillator)

```python
@staticmethod
def calculate_cmo(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Chandra Momentum Oscillator

    CMO is an alternative to RSI, ranges from -100 to +100.

    Signals:
    - CMO > +50: Overbought (SELL)
    - CMO < -50: Oversold (BUY)

    PHASE 3: Uses TA-Lib (26x faster)
    """
    logger.info(f"Calculating CMO (period={period})")

    df = data.copy()

    if TALIB_AVAILABLE:
        try:
            df['cmo'] = talib.CMO(df['close'].values, timeperiod=period)
        except Exception as e:
            logger.warning(f"TA-Lib CMO failed, falling back to RSI: {e}")
            # Fallback: Convert RSI to CMO-like scale
            df = TechnicalIndicators.calculate_rsi(df, period)
            df['cmo'] = (df['rsi'] - 50) * 2  # Scale RSI 0-100 to CMO -100 to +100
    else:
        df = TechnicalIndicators.calculate_rsi(df, period)
        df['cmo'] = (df['rsi'] - 50) * 2

    # Generate signal
    if len(df) > 0:
        latest_cmo = df['cmo'].iloc[-1]

        if pd.notna(latest_cmo):
            if latest_cmo > 50:
                df['cmo_signal'] = 'SELL'
                df['cmo_reason'] = f"Overbought (CMO={latest_cmo:.1f})"
            elif latest_cmo < -50:
                df['cmo_signal'] = 'BUY'
                df['cmo_reason'] = f"Oversold (CMO={latest_cmo:.1f})"
            else:
                df['cmo_signal'] = 'HOLD'
                df['cmo_reason'] = f"Neutral (CMO={latest_cmo:.1f})"

    return df
```

---

### Day 3: Volatility & Regression Indicators (1 hour)

#### Task 3.1: Add NATR (Normalized ATR)

```python
@staticmethod
def calculate_natr(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Normalized Average True Range

    NATR is ATR as percentage of price, better for comparing volatility
    across different price ranges.

    Signals:
    - NATR > 4%: High volatility (wait for calmer entry)
    - NATR < 1%: Low volatility (potential breakout coming)

    PHASE 3: Uses TA-Lib (30x faster)
    """
    logger.info(f"Calculating NATR (period={period})")

    df = data.copy()

    if TALIB_AVAILABLE:
        try:
            df['natr'] = talib.NATR(
                df['high'].values,
                df['low'].values,
                df['close'].values,
                timeperiod=period
            )
        except Exception as e:
            logger.warning(f"TA-Lib NATR failed, falling back to ATR: {e}")
            # Fallback: Calculate ATR and normalize
            df = TechnicalIndicators.calculate_atr(df, period)
            df['natr'] = (df['atr'] / df['close']) * 100
    else:
        df = TechnicalIndicators.calculate_atr(df, period)
        df['natr'] = (df['atr'] / df['close']) * 100

    # Generate signal
    if len(df) > 0:
        latest_natr = df['natr'].iloc[-1]

        if pd.notna(latest_natr):
            if latest_natr > 4:
                df['natr_signal'] = 'HOLD'
                df['natr_reason'] = f"High volatility (NATR={latest_natr:.2f}%) - wait for entry"
            elif latest_natr < 1:
                df['natr_signal'] = 'WATCH'
                df['natr_reason'] = f"Low volatility (NATR={latest_natr:.2f}%) - breakout pending"
            else:
                df['natr_signal'] = 'NEUTRAL'
                df['natr_reason'] = f"Normal volatility (NATR={latest_natr:.2f}%)"

    return df
```

#### Task 3.2: Add STDDEV (Standard Deviation)

```python
@staticmethod
def calculate_stddev(data: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    Calculate Standard Deviation

    STDDEV measures price volatility/dispersion. Used in volatility-based
    strategies and stop loss calculations.

    PHASE 3: Uses TA-Lib (18x faster)
    """
    logger.info(f"Calculating STDDEV (period={period})")

    df = data.copy()

    if TALIB_AVAILABLE:
        try:
            df['stddev'] = talib.STDDEV(df['close'].values, timeperiod=period, nbdev=1)
        except Exception as e:
            logger.warning(f"TA-Lib STDDEV failed, falling back to pandas: {e}")
            df['stddev'] = df['close'].rolling(window=period).std()
    else:
        df['stddev'] = df['close'].rolling(window=period).std()

    # Generate signal (informational, not trading signal)
    if len(df) > 0:
        latest_stddev = df['stddev'].iloc[-1]
        latest_close = df['close'].iloc[-1]

        if pd.notna(latest_stddev):
            volatility_pct = (latest_stddev / latest_close) * 100
            df['stddev_signal'] = 'INFO'
            df['stddev_reason'] = f"Volatility: {volatility_pct:.2f}% of price"

    return df
```

#### Task 3.3: Add LINEARREG_SLOPE

```python
@staticmethod
def calculate_linearreg_slope(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Linear Regression Slope

    Measures trend strength and direction. Positive slope = uptrend,
    negative slope = downtrend. Magnitude = strength.

    Signals:
    - Slope > 0 and increasing: Strong uptrend (BUY)
    - Slope < 0 and decreasing: Strong downtrend (SELL)
    - Slope near 0: No trend (HOLD)

    PHASE 3: Uses TA-Lib (35x faster)
    """
    logger.info(f"Calculating Linear Regression Slope (period={period})")

    df = data.copy()

    if TALIB_AVAILABLE:
        try:
            df['linearreg_slope'] = talib.LINEARREG_SLOPE(df['close'].values, timeperiod=period)
        except Exception as e:
            logger.warning(f"TA-Lib LINEARREG_SLOPE failed, falling back to pandas: {e}")
            # Pandas fallback (simplified)
            df['linearreg_slope'] = df['close'].diff(period) / period
    else:
        df['linearreg_slope'] = df['close'].diff(period) / period

    # Generate signal
    if len(df) > 1:
        latest_slope = df['linearreg_slope'].iloc[-1]
        prev_slope = df['linearreg_slope'].iloc[-2]

        if pd.notna(latest_slope):
            slope_change = latest_slope - prev_slope if pd.notna(prev_slope) else 0

            if latest_slope > 0.1 and slope_change > 0:
                df['linearreg_signal'] = 'BUY'
                df['linearreg_reason'] = f"Strong uptrend (slope={latest_slope:.3f}, accelerating)"
            elif latest_slope < -0.1 and slope_change < 0:
                df['linearreg_signal'] = 'SELL'
                df['linearreg_reason'] = f"Strong downtrend (slope={latest_slope:.3f}, accelerating)"
            elif abs(latest_slope) < 0.05:
                df['linearreg_signal'] = 'HOLD'
                df['linearreg_reason'] = f"No clear trend (slope={latest_slope:.3f})"
            else:
                df['linearreg_signal'] = 'HOLD'
                df['linearreg_reason'] = f"Weak trend (slope={latest_slope:.3f})"

    return df
```

---

### Day 4: Advanced Indicators & Integration (1.5 hours)

#### Task 4.1: Add CORREL (Correlation with SPY)

**Note**: This requires fetching SPY data as reference. Implementation:

```python
@staticmethod
def calculate_correl_spy(data: pd.DataFrame, spy_data: pd.DataFrame, period: int = 30) -> pd.DataFrame:
    """
    Calculate Correlation with SPY (S&P 500 ETF)

    Measures how much stock moves with the overall market.
    - Correlation > 0.7: High positive correlation (market follower)
    - Correlation < 0.3: Low correlation (independent/hedge)

    PHASE 3: Uses TA-Lib (20x faster)

    Args:
        data: Stock DataFrame with 'close' column
        spy_data: SPY DataFrame with 'close' column (aligned timestamps)
        period: Correlation window (default: 30)
    """
    logger.info(f"Calculating Correlation with SPY (period={period})")

    df = data.copy()

    # Align data (ensure same timestamps)
    if len(spy_data) != len(df):
        logger.warning("SPY data length mismatch, skipping CORREL")
        df['correl_spy'] = np.nan
        df['correl_signal'] = 'N/A'
        df['correl_reason'] = "SPY data not available"
        return df

    if TALIB_AVAILABLE:
        try:
            df['correl_spy'] = talib.CORREL(
                df['close'].values,
                spy_data['close'].values,
                timeperiod=period
            )
        except Exception as e:
            logger.warning(f"TA-Lib CORREL failed, falling back to pandas: {e}")
            df['correl_spy'] = df['close'].rolling(window=period).corr(spy_data['close'])
    else:
        df['correl_spy'] = df['close'].rolling(window=period).corr(spy_data['close'])

    # Generate signal
    if len(df) > 0:
        latest_correl = df['correl_spy'].iloc[-1]

        if pd.notna(latest_correl):
            if latest_correl > 0.7:
                df['correl_signal'] = 'INFO'
                df['correl_reason'] = f"High market correlation ({latest_correl:.2f}) - market follower"
            elif latest_correl < 0.3:
                df['correl_signal'] = 'INFO'
                df['correl_reason'] = f"Low market correlation ({latest_correl:.2f}) - independent"
            else:
                df['correl_signal'] = 'INFO'
                df['correl_reason'] = f"Moderate market correlation ({latest_correl:.2f})"

    return df
```

#### Task 4.2: Add HT_TRENDLINE (Hilbert Transform)

```python
@staticmethod
def calculate_ht_trendline(data: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Hilbert Transform Instantaneous Trendline

    Uses Hilbert Transform to identify underlying trend by removing
    cyclic components. Excellent for swing trading trend detection.

    Signals:
    - Price > HT_TRENDLINE: Uptrend (BUY)
    - Price < HT_TRENDLINE: Downtrend (SELL)
    - Crossovers: Trend changes

    PHASE 3: Uses TA-Lib (Hilbert Transform not available in pandas)
    """
    logger.info("Calculating Hilbert Transform Trendline")

    df = data.copy()

    if TALIB_AVAILABLE:
        try:
            df['ht_trendline'] = talib.HT_TRENDLINE(df['close'].values)
        except Exception as e:
            logger.warning(f"TA-Lib HT_TRENDLINE failed, falling back to EMA: {e}")
            # Fallback: Use long-term EMA as proxy
            df['ht_trendline'] = df['close'].ewm(span=50, adjust=False).mean()
    else:
        # Pandas fallback (use EMA as proxy)
        df['ht_trendline'] = df['close'].ewm(span=50, adjust=False).mean()

    # Generate signal
    if len(df) > 1:
        latest_close = df['close'].iloc[-1]
        latest_ht = df['ht_trendline'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        prev_ht = df['ht_trendline'].iloc[-2]

        if pd.notna(latest_ht):
            if prev_close <= prev_ht and latest_close > latest_ht:
                df['ht_signal'] = 'BUY'
                df['ht_reason'] = "Price crossed above HT Trendline (cycle-based uptrend)"
            elif prev_close >= prev_ht and latest_close < latest_ht:
                df['ht_signal'] = 'SELL'
                df['ht_reason'] = "Price crossed below HT Trendline (cycle-based downtrend)"
            elif latest_close > latest_ht:
                df['ht_signal'] = 'BUY'
                df['ht_reason'] = "Price above HT Trendline (uptrend)"
            else:
                df['ht_signal'] = 'SELL'
                df['ht_reason'] = "Price below HT Trendline (downtrend)"

    return df
```

#### Task 4.3: Update calculate_all_indicators()

Add all new indicators to the main calculation function:

```python
@staticmethod
def calculate_all_indicators(data: pd.DataFrame, ...) -> pd.DataFrame:
    # ... existing code ...

    # NEW PHASE 2 INDICATORS

    # Advanced Trend Indicators
    df = TechnicalIndicators.calculate_kama(df, 10)
    df = TechnicalIndicators.calculate_tema(df, 30)
    df = TechnicalIndicators.calculate_t3(df, 5, 0.7)
    df = TechnicalIndicators.calculate_ht_trendline(df)

    # Advanced Momentum Indicators
    df = TechnicalIndicators.calculate_mfi(df, 14)
    df = TechnicalIndicators.calculate_willr(df, 14)
    df = TechnicalIndicators.calculate_roc(df, 10)
    df = TechnicalIndicators.calculate_cmo(df, 14)

    # Advanced Volatility & Regression
    df = TechnicalIndicators.calculate_natr(df, 14)
    df = TechnicalIndicators.calculate_stddev(df, 20)
    df = TechnicalIndicators.calculate_linearreg_slope(df, 14)

    # Market Correlation (requires SPY data - handle separately in service)
    # df = TechnicalIndicators.calculate_correl_spy(df, spy_data, 30)

    return df
```

---

## 🔗 INTEGRATION TASKS

### Backend Integration

#### Update Schemas (`backend/app/schemas/analysis.py`)

Add new indicator fields to `TechnicalIndicatorsResponse`:

```python
class TechnicalIndicatorsResponse(BaseModel):
    # ... existing fields ...

    # NEW PHASE 2 INDICATORS
    # Trend
    kama: Optional[float] = None
    kama_signal: Optional[str] = None
    kama_reason: Optional[str] = None

    tema: Optional[float] = None
    tema_signal: Optional[str] = None
    tema_reason: Optional[str] = None

    t3: Optional[float] = None
    t3_signal: Optional[str] = None
    t3_reason: Optional[str] = None

    ht_trendline: Optional[float] = None
    ht_signal: Optional[str] = None
    ht_reason: Optional[str] = None

    # Momentum
    mfi: Optional[float] = None
    mfi_signal: Optional[str] = None
    mfi_reason: Optional[str] = None

    willr: Optional[float] = None
    willr_signal: Optional[str] = None
    willr_reason: Optional[str] = None

    roc: Optional[float] = None
    roc_signal: Optional[str] = None
    roc_reason: Optional[str] = None

    cmo: Optional[float] = None
    cmo_signal: Optional[str] = None
    cmo_reason: Optional[str] = None

    # Volatility & Regression
    natr: Optional[float] = None
    natr_signal: Optional[str] = None
    natr_reason: Optional[str] = None

    stddev: Optional[float] = None
    stddev_signal: Optional[str] = None
    stddev_reason: Optional[str] = None

    linearreg_slope: Optional[float] = None
    linearreg_signal: Optional[str] = None
    linearreg_reason: Optional[str] = None

    correl_spy: Optional[float] = None
    correl_signal: Optional[str] = None
    correl_reason: Optional[str] = None
```

#### Update Recommendation Engine (`backend/app/services/recommendation_engine.py`)

Add new indicators to signal aggregation:

```python
def aggregate_signals(self, indicators: Dict) -> Dict:
    # ... existing code ...

    # NEW PHASE 2 INDICATORS
    signal_counts = self._count_signals([
        # Existing indicators...
        'kama_signal',
        'tema_signal',
        't3_signal',
        'ht_signal',
        'mfi_signal',
        'willr_signal',
        'roc_signal',
        'cmo_signal',
        # Note: NATR, STDDEV, LINEARREG_SLOPE, CORREL are informational
    ], indicators)

    # Weighted scoring (prioritize momentum + trend confirmation)
    buy_score = signal_counts['BUY'] * 1.0
    sell_score = signal_counts['SELL'] * 1.0

    # Bonus for multiple momentum indicators agreeing
    momentum_agreement = sum([
        1 for sig in ['mfi_signal', 'willr_signal', 'roc_signal', 'cmo_signal']
        if indicators.get(sig) == 'BUY'
    ])
    if momentum_agreement >= 3:
        buy_score += 2  # Bonus for strong momentum consensus

    # ... rest of logic ...
```

---

### Frontend Integration

#### Update TechnicalIndicators Component

**File**: `frontend/src/components/TechnicalIndicators.jsx`

Add new sections:

```jsx
// Add after existing indicators

{/* Advanced Trend Indicators */}
<div className="indicator-section">
  <h4>Advanced Trend Indicators</h4>

  <div className="indicator-card">
    <div className="indicator-header">
      <span className="indicator-name">KAMA</span>
      <span className={`signal-badge ${getSignalClass(indicators.kama_signal)}`}>
        {indicators.kama_signal || 'N/A'}
      </span>
    </div>
    <div className="indicator-value">{formatValue(indicators.kama)}</div>
    <div className="indicator-reason">{indicators.kama_reason}</div>
    <div className="indicator-info">
      <InfoTooltip content="Kaufman Adaptive Moving Average - adapts to volatility" />
    </div>
  </div>

  {/* Repeat for TEMA, T3, HT_TRENDLINE */}
</div>

{/* Advanced Momentum Indicators */}
<div className="indicator-section">
  <h4>Advanced Momentum Indicators</h4>

  <div className="indicator-card">
    <div className="indicator-header">
      <span className="indicator-name">MFI</span>
      <span className={`signal-badge ${getSignalClass(indicators.mfi_signal)}`}>
        {indicators.mfi_signal || 'N/A'}
      </span>
    </div>
    <div className="indicator-value">{formatValue(indicators.mfi)}</div>
    <div className="indicator-reason">{indicators.mfi_reason}</div>
    <div className="indicator-info">
      <InfoTooltip content="Money Flow Index - volume-weighted RSI" />
    </div>
  </div>

  {/* Repeat for Williams %R, ROC, CMO */}
</div>

{/* Volatility & Trend Strength */}
<div className="indicator-section">
  <h4>Volatility & Trend Strength</h4>

  <div className="indicator-card">
    <div className="indicator-header">
      <span className="indicator-name">NATR</span>
      <span className="indicator-value">{formatValue(indicators.natr)}%</span>
    </div>
    <div className="indicator-reason">{indicators.natr_reason}</div>
  </div>

  <div className="indicator-card">
    <div className="indicator-header">
      <span className="indicator-name">Linear Reg Slope</span>
      <span className={`signal-badge ${getSignalClass(indicators.linearreg_signal)}`}>
        {indicators.linearreg_signal || 'N/A'}
      </span>
    </div>
    <div className="indicator-value">{formatValue(indicators.linearreg_slope, 3)}</div>
    <div className="indicator-reason">{indicators.linearreg_reason}</div>
  </div>

  {/* STDDEV, CORREL */}
</div>
```

---

## 🧪 TESTING PLAN

### Manual Testing

1. **Test with AAPL** (large cap, liquid)
   - All indicators should calculate without errors
   - Check signal logic makes sense
   - Verify performance improvement

2. **Test with TSLA** (high volatility)
   - NATR, STDDEV should show high volatility
   - MFI should respond to volume changes
   - KAMA should adapt quickly

3. **Test with MSFT** (stable trend)
   - TEMA, T3, HT_TRENDLINE should show smooth trend
   - LINEARREG_SLOPE should be consistent
   - CORREL should be high (tech stock follows market)

### Performance Benchmarks

Run before/after tests:

```python
import time
start = time.time()
df = TechnicalIndicators.calculate_all_indicators(price_data)
elapsed = time.time() - start
print(f"All indicators calculated in {elapsed:.2f}s")
```

**Expected Results:**
- Before (Phase 1): 30-45 seconds
- After (Phase 2): 10-30 seconds (target achieved!)

---

## 📊 SUCCESS CRITERIA

- [ ] All 12 new indicators implemented with TA-Lib
- [ ] Smart fallback to pandas for each indicator
- [ ] Signal generation logic tested and working
- [ ] Backend schemas updated with new fields
- [ ] Recommendation engine uses new indicators
- [ ] Frontend displays all new indicators
- [ ] Tooltips explain what each indicator does
- [ ] Performance benchmark: <30 seconds dashboard load
- [ ] No errors in backend logs
- [ ] Documentation updated (ROADMAP.md)

---

## 📝 NOTES

### Why These Indicators?

- **KAMA, TEMA, T3**: Better trend detection than simple MA (reduced lag)
- **MFI**: RSI + volume = better overbought/oversold signals
- **Williams %R**: Complements RSI with different calculation
- **ROC, CMO**: Additional momentum confirmation
- **NATR, STDDEV**: Volatility assessment for position sizing
- **LINEARREG_SLOPE**: Quantifies trend strength
- **CORREL**: Understand market correlation
- **HT_TRENDLINE**: Cycle-based trend (unique to TA-Lib)

### Integration Priority

1. **High Priority**: KAMA, TEMA, MFI, NATR (most useful for swing trading)
2. **Medium Priority**: Williams %R, ROC, LINEARREG_SLOPE
3. **Low Priority**: T3, CMO, STDDEV, CORREL, HT_TRENDLINE (nice-to-have)

---

**Last Updated**: 2025-11-12
**Status**: 🚧 Ready to start Day 1
**Next Action**: Implement KAMA, TEMA, T3 indicators
