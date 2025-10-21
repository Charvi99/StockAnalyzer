import React, { useState } from 'react';

const IndicatorInfo = ({ onClose }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeSection, setActiveSection] = useState('');

  const scrollToSection = (sectionId) => {
    const element = document.getElementById(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setActiveSection(sectionId);
    }
  };

  const indicators = [
    // Trend Indicators
    { id: 'ma', name: 'Moving Averages (SMA & EMA)', category: 'Trend Indicators' },
    { id: 'macd', name: 'MACD', category: 'Trend Indicators' },
    { id: 'adx', name: 'Average Directional Index (ADX)', category: 'Trend Indicators' },
    { id: 'psar', name: 'Parabolic SAR', category: 'Trend Indicators' },
    { id: 'ichimoku', name: 'Ichimoku Cloud', category: 'Trend Indicators' },
    // Momentum Indicators
    { id: 'rsi', name: 'Relative Strength Index (RSI)', category: 'Momentum Indicators' },
    { id: 'stochastic', name: 'Stochastic Oscillator', category: 'Momentum Indicators' },
    { id: 'cci', name: 'Commodity Channel Index (CCI)', category: 'Momentum Indicators' },
    // Volume Indicators
    { id: 'obv', name: 'On-Balance Volume (OBV)', category: 'Volume Indicators' },
    { id: 'vwap', name: 'VWAP', category: 'Volume Indicators' },
    { id: 'ad', name: 'Accumulation/Distribution Line', category: 'Volume Indicators' },
    // Volatility & Other Tools
    { id: 'bb', name: 'Bollinger Bands', category: 'Volatility & Other Tools' },
    { id: 'atr', name: 'Average True Range (ATR)', category: 'Volatility & Other Tools' },
    { id: 'keltner', name: 'Keltner Channels', category: 'Volatility & Other Tools' },
    { id: 'fibonacci', name: 'Fibonacci Retracement', category: 'Volatility & Other Tools' },
  ];

  const categories = [...new Set(indicators.map(i => i.category))];

  const filteredIndicators = indicators.filter(indicator =>
    indicator.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    indicator.category.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getIndicatorsByCategory = (category) => {
    return filteredIndicators.filter(i => i.category === category);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>📚 Technical Indicators Encyclopedia</h2>
          <button onClick={onClose} className="close-btn">×</button>
        </div>

        <div className="search-section">
          <input
            type="text"
            placeholder="🔍 Search indicators..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>

        <div className="modal-layout">
          {/* Navigation Sidebar */}
          <div className="navigation-sidebar">
            <h4>Quick Navigation</h4>
            {categories.map((category) => {
              const categoryIndicators = getIndicatorsByCategory(category);
              if (categoryIndicators.length === 0) return null;

              return (
                <div key={category} className="nav-category">
                  <div className="nav-category-title">{category}</div>
                  <ul className="nav-list">
                    {categoryIndicators.map((indicator) => (
                      <li
                        key={indicator.id}
                        className={`nav-item ${activeSection === indicator.id ? 'active' : ''}`}
                        onClick={() => scrollToSection(indicator.id)}
                      >
                        {indicator.name}
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>

          {/* Main Content */}
          <div className="modal-body">
            {/* TREND INDICATORS */}
            <div className="category-header">
              <h2>📈 Trend Indicators</h2>
              <p>Indicators that identify the direction and strength of market trends</p>
            </div>

            {/* Moving Averages */}
            <section id="ma" className="indicator-section">
              <h3 className="indicator-title">Moving Averages (SMA & EMA)</h3>

              <div className="indicator-subsection">
                <h4>What are Moving Averages?</h4>
                <p>
                  Moving Averages smooth out price data by creating a constantly updated average price. They help identify
                  trend direction and potential support/resistance levels. Two common types are Simple Moving Average (SMA)
                  and Exponential Moving Average (EMA).
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>How are they calculated?</h4>
                <div className="formula">
                  <code>SMA = Sum of closing prices over N periods / N</code><br/>
                  <code>EMA = (Close - Previous EMA) × Multiplier + Previous EMA</code><br/>
                  <code>Multiplier = 2 / (N + 1)</code>
                </div>
                <p className="formula-note">
                  Common periods: 20-day (short-term), 50-day (medium-term), 200-day (long-term). EMA reacts faster to price changes.
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>How to interpret?</h4>
                <ul className="interpretation-list">
                  <li><strong>Price above MA:</strong> <span className="bullish">Bullish trend</span> - MA acts as support</li>
                  <li><strong>Price below MA:</strong> <span className="bearish">Bearish trend</span> - MA acts as resistance</li>
                  <li><strong>Short MA crosses above Long MA:</strong> <span className="bullish">"Golden Cross"</span> - Strong BUY signal</li>
                  <li><strong>Short MA crosses below Long MA:</strong> <span className="bearish">"Death Cross"</span> - Strong SELL signal</li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> 50-day MA crosses above 200-day MA (Golden Cross)</p>
                <p><strong>Signal:</strong> <span className="bullish">STRONG BUY</span> - Major bullish trend reversal</p>
              </div>
            </section>

            {/* MACD */}
            <section id="macd" className="indicator-section">
              <h3 className="indicator-title">MACD (Moving Average Convergence Divergence)</h3>

              <div className="indicator-subsection">
                <h4>What is MACD?</h4>
                <p>
                  MACD is a trend-following momentum indicator that shows the relationship between two moving averages
                  of a stock's price. It consists of the MACD line, signal line, and histogram.
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>Calculation</h4>
                <div className="formula">
                  <code>MACD Line = 12-period EMA - 26-period EMA</code><br/>
                  <code>Signal Line = 9-period EMA of MACD Line</code><br/>
                  <code>Histogram = MACD Line - Signal Line</code>
                </div>
              </div>

              <div className="indicator-subsection">
                <h4>Interpretation</h4>
                <ul className="interpretation-list">
                  <li><strong>MACD crosses above Signal:</strong> <span className="bullish">Bullish crossover</span> - BUY signal</li>
                  <li><strong>MACD crosses below Signal:</strong> <span className="bearish">Bearish crossover</span> - SELL signal</li>
                  <li><strong>Histogram growing:</strong> Trend strengthening</li>
                  <li><strong>Histogram shrinking:</strong> Trend weakening</li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> MACD line crosses above signal line below zero</p>
                <p><strong>Signal:</strong> <span className="bullish">BUY</span> - Early bullish momentum shift</p>
              </div>
            </section>

            {/* ADX */}
            <section id="adx" className="indicator-section">
              <h3 className="indicator-title">Average Directional Index (ADX)</h3>

              <div className="indicator-subsection">
                <h4>What is ADX?</h4>
                <p>
                  ADX measures the strength of a trend, regardless of direction. It ranges from 0 to 100 and is used
                  to determine whether the market is trending or ranging. It's often used with +DI and -DI indicators.
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>Calculation</h4>
                <div className="formula">
                  <code>+DM = Current High - Previous High (if positive)</code><br/>
                  <code>-DM = Previous Low - Current Low (if positive)</code><br/>
                  <code>ADX = 100 × EMA of |((+DI) - (-DI)) / ((+DI) + (-DI))|</code>
                </div>
                <p className="formula-note">Standard period is 14 days</p>
              </div>

              <div className="indicator-subsection">
                <h4>Interpretation</h4>
                <ul className="interpretation-list">
                  <li><strong>ADX &lt; 20:</strong> <span className="neutral">Weak trend</span> - Range-bound market</li>
                  <li><strong>ADX 20-25:</strong> Trend starting to develop</li>
                  <li><strong>ADX 25-50:</strong> <span className="bullish">Strong trend</span></li>
                  <li><strong>ADX &gt; 50:</strong> <span className="bullish">Very strong trend</span></li>
                  <li><strong>+DI above -DI:</strong> Bullish direction</li>
                  <li><strong>-DI above +DI:</strong> Bearish direction</li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> ADX rises from 18 to 28 while +DI crosses above -DI</p>
                <p><strong>Signal:</strong> <span className="bullish">BUY</span> - Strong bullish trend forming</p>
              </div>
            </section>

            {/* Parabolic SAR */}
            <section id="psar" className="indicator-section">
              <h3 className="indicator-title">Parabolic SAR (Stop and Reverse)</h3>

              <div className="indicator-subsection">
                <h4>What is Parabolic SAR?</h4>
                <p>
                  Parabolic SAR provides potential entry and exit points. It appears as dots above or below the price,
                  indicating the direction of momentum and potential reversal points. "SAR" stands for Stop And Reverse.
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>Calculation</h4>
                <div className="formula">
                  <code>SAR = Prior SAR + AF × (Prior EP - Prior SAR)</code><br/>
                  <code>AF = Acceleration Factor (starts at 0.02, max 0.20)</code><br/>
                  <code>EP = Extreme Point (highest high or lowest low in current trend)</code>
                </div>
              </div>

              <div className="indicator-subsection">
                <h4>Interpretation</h4>
                <ul className="interpretation-list">
                  <li><strong>Dots below price:</strong> <span className="bullish">Uptrend</span> - Hold long positions</li>
                  <li><strong>Dots above price:</strong> <span className="bearish">Downtrend</span> - Hold short positions</li>
                  <li><strong>Dots flip from below to above:</strong> <span className="bearish">SELL signal</span> - Trend reversal</li>
                  <li><strong>Dots flip from above to below:</strong> <span className="bullish">BUY signal</span> - Trend reversal</li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> SAR dots flip from above to below the price after downtrend</p>
                <p><strong>Signal:</strong> <span className="bullish">BUY</span> - Potential bullish reversal</p>
              </div>
            </section>

            {/* Ichimoku Cloud */}
            <section id="ichimoku" className="indicator-section">
              <h3 className="indicator-title">Ichimoku Cloud</h3>

              <div className="indicator-subsection">
                <h4>What is Ichimoku Cloud?</h4>
                <p>
                  Ichimoku Cloud is a comprehensive indicator that defines support/resistance, identifies trend direction,
                  gauges momentum, and provides trading signals. It consists of five lines creating a "cloud" (Kumo).
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>Components</h4>
                <div className="formula">
                  <code>Tenkan-sen (Conversion) = (9-period high + 9-period low) / 2</code><br/>
                  <code>Kijun-sen (Base) = (26-period high + 26-period low) / 2</code><br/>
                  <code>Senkou Span A = (Tenkan-sen + Kijun-sen) / 2, plotted 26 periods ahead</code><br/>
                  <code>Senkou Span B = (52-period high + 52-period low) / 2, plotted 26 periods ahead</code><br/>
                  <code>Chikou Span (Lagging) = Close plotted 26 periods back</code>
                </div>
              </div>

              <div className="indicator-subsection">
                <h4>Interpretation</h4>
                <ul className="interpretation-list">
                  <li><strong>Price above cloud:</strong> <span className="bullish">Bullish trend</span></li>
                  <li><strong>Price below cloud:</strong> <span className="bearish">Bearish trend</span></li>
                  <li><strong>Price in cloud:</strong> <span className="neutral">Consolidation/transition</span></li>
                  <li><strong>Tenkan crosses above Kijun:</strong> <span className="bullish">BUY signal</span></li>
                  <li><strong>Tenkan crosses below Kijun:</strong> <span className="bearish">SELL signal</span></li>
                  <li><strong>Green cloud (Span A > Span B):</strong> Bullish support</li>
                  <li><strong>Red cloud (Span A &lt; Span B):</strong> Bearish resistance</li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> Price breaks above cloud, Tenkan crosses above Kijun, cloud turns green</p>
                <p><strong>Signal:</strong> <span className="bullish">STRONG BUY</span> - Multiple bullish confirmations</p>
              </div>
            </section>

            {/* MOMENTUM INDICATORS */}
            <div className="category-header">
              <h2>⚡ Momentum Indicators</h2>
              <p>Indicators that measure the rate of price changes and trend strength</p>
            </div>

            {/* RSI */}
            <section id="rsi" className="indicator-section">
              <h3 className="indicator-title">Relative Strength Index (RSI)</h3>

              <div className="indicator-subsection">
                <h4>What is RSI?</h4>
                <p>
                  RSI is a momentum oscillator that measures the speed and magnitude of price changes.
                  It oscillates between 0 and 100 and helps identify overbought or oversold conditions.
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>Calculation</h4>
                <div className="formula">
                  <code>RSI = 100 - (100 / (1 + RS))</code><br/>
                  <code>RS = Average Gain / Average Loss (over 14 periods)</code>
                </div>
              </div>

              <div className="indicator-subsection">
                <h4>Interpretation</h4>
                <ul className="interpretation-list">
                  <li><strong>RSI &gt; 70:</strong> <span className="bearish">Overbought</span> - Potential reversal down</li>
                  <li><strong>RSI &lt; 30:</strong> <span className="bullish">Oversold</span> - Potential reversal up</li>
                  <li><strong>RSI crosses 50:</strong> Momentum shift</li>
                  <li><strong>Bullish divergence:</strong> Price makes lower low, RSI makes higher low - <span className="bullish">BUY</span></li>
                  <li><strong>Bearish divergence:</strong> Price makes higher high, RSI makes lower high - <span className="bearish">SELL</span></li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> RSI reaches 78 after extended rally</p>
                <p><strong>Signal:</strong> <span className="bearish">SELL/HOLD</span> - Overbought, consider taking profits</p>
              </div>
            </section>

            {/* Stochastic Oscillator */}
            <section id="stochastic" className="indicator-section">
              <h3 className="indicator-title">Stochastic Oscillator</h3>

              <div className="indicator-subsection">
                <h4>What is Stochastic Oscillator?</h4>
                <p>
                  The Stochastic Oscillator compares a stock's closing price to its price range over a specific period.
                  It consists of two lines: %K (fast) and %D (slow, 3-day SMA of %K). Values range from 0 to 100.
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>Calculation</h4>
                <div className="formula">
                  <code>%K = 100 × (Close - Lowest Low) / (Highest High - Lowest Low)</code><br/>
                  <code>%D = 3-period SMA of %K</code><br/>
                  <code>Typically calculated over 14 periods</code>
                </div>
              </div>

              <div className="indicator-subsection">
                <h4>Interpretation</h4>
                <ul className="interpretation-list">
                  <li><strong>%K &gt; 80:</strong> <span className="bearish">Overbought</span> - Potential sell opportunity</li>
                  <li><strong>%K &lt; 20:</strong> <span className="bullish">Oversold</span> - Potential buy opportunity</li>
                  <li><strong>%K crosses above %D:</strong> <span className="bullish">Bullish signal</span></li>
                  <li><strong>%K crosses below %D:</strong> <span className="bearish">Bearish signal</span></li>
                  <li><strong>Divergence with price:</strong> Strong reversal signal</li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> %K crosses above %D while both are below 20 (oversold)</p>
                <p><strong>Signal:</strong> <span className="bullish">STRONG BUY</span> - Bullish reversal from oversold</p>
              </div>
            </section>

            {/* CCI */}
            <section id="cci" className="indicator-section">
              <h3 className="indicator-title">Commodity Channel Index (CCI)</h3>

              <div className="indicator-subsection">
                <h4>What is CCI?</h4>
                <p>
                  CCI measures the current price level relative to an average price level over a given period.
                  It identifies cyclical trends and overbought/oversold levels. Values typically range between -100 and +100,
                  but can exceed these levels.
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>Calculation</h4>
                <div className="formula">
                  <code>Typical Price = (High + Low + Close) / 3</code><br/>
                  <code>CCI = (Typical Price - SMA) / (0.015 × Mean Deviation)</code><br/>
                  <code>Standard period: 20 days</code>
                </div>
              </div>

              <div className="indicator-subsection">
                <h4>Interpretation</h4>
                <ul className="interpretation-list">
                  <li><strong>CCI &gt; +100:</strong> <span className="bearish">Overbought</span> - Strong uptrend or reversal warning</li>
                  <li><strong>CCI &lt; -100:</strong> <span className="bullish">Oversold</span> - Strong downtrend or reversal warning</li>
                  <li><strong>CCI crosses above -100:</strong> <span className="bullish">BUY signal</span></li>
                  <li><strong>CCI crosses below +100:</strong> <span className="bearish">SELL signal</span></li>
                  <li><strong>CCI between -100 and +100:</strong> <span className="neutral">Normal range</span></li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> CCI drops to -150 then crosses back above -100</p>
                <p><strong>Signal:</strong> <span className="bullish">BUY</span> - Emerging from oversold territory</p>
              </div>
            </section>

            {/* VOLUME INDICATORS */}
            <div className="category-header">
              <h2>📊 Volume Indicators</h2>
              <p>Indicators that analyze trading volume to confirm trends and spot reversals</p>
            </div>

            {/* OBV */}
            <section id="obv" className="indicator-section">
              <h3 className="indicator-title">On-Balance Volume (OBV)</h3>

              <div className="indicator-subsection">
                <h4>What is OBV?</h4>
                <p>
                  OBV uses volume flow to predict changes in stock price. It's a cumulative indicator that adds volume
                  on up days and subtracts volume on down days. Rising OBV suggests accumulation (bullish), while
                  falling OBV suggests distribution (bearish).
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>Calculation</h4>
                <div className="formula">
                  <code>If Close &gt; Previous Close: OBV = Previous OBV + Volume</code><br/>
                  <code>If Close &lt; Previous Close: OBV = Previous OBV - Volume</code><br/>
                  <code>If Close = Previous Close: OBV = Previous OBV</code>
                </div>
              </div>

              <div className="indicator-subsection">
                <h4>Interpretation</h4>
                <ul className="interpretation-list">
                  <li><strong>OBV rising with price:</strong> <span className="bullish">Healthy uptrend</span> - Volume confirms</li>
                  <li><strong>OBV falling with price:</strong> <span className="bearish">Healthy downtrend</span> - Volume confirms</li>
                  <li><strong>Price rising, OBV flat/falling:</strong> <span className="bearish">Weak uptrend</span> - Possible reversal</li>
                  <li><strong>Price falling, OBV rising:</strong> <span className="bullish">Accumulation</span> - Possible reversal up</li>
                  <li><strong>OBV breakout before price:</strong> Leading indicator of price breakout</li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> OBV breaks to new high while price is still consolidating</p>
                <p><strong>Signal:</strong> <span className="bullish">BUY</span> - OBV leading, price breakout likely</p>
              </div>
            </section>

            {/* VWAP */}
            <section id="vwap" className="indicator-section">
              <h3 className="indicator-title">Volume Weighted Average Price (VWAP)</h3>

              <div className="indicator-subsection">
                <h4>What is VWAP?</h4>
                <p>
                  VWAP gives the average price a stock has traded at throughout the day, weighted by volume.
                  It's primarily used by institutional traders and resets each trading day. Price above VWAP
                  indicates bullish sentiment, below indicates bearish sentiment.
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>Calculation</h4>
                <div className="formula">
                  <code>VWAP = Σ (Typical Price × Volume) / Σ Volume</code><br/>
                  <code>Typical Price = (High + Low + Close) / 3</code><br/>
                  <code>Calculated cumulatively throughout the trading day</code>
                </div>
              </div>

              <div className="indicator-subsection">
                <h4>Interpretation</h4>
                <ul className="interpretation-list">
                  <li><strong>Price above VWAP:</strong> <span className="bullish">Bullish</span> - Buyers in control</li>
                  <li><strong>Price below VWAP:</strong> <span className="bearish">Bearish</span> - Sellers in control</li>
                  <li><strong>Price crosses above VWAP:</strong> <span className="bullish">BUY signal</span></li>
                  <li><strong>Price crosses below VWAP:</strong> <span className="bearish">SELL signal</span></li>
                  <li><strong>VWAP as support/resistance:</strong> Price often bounces off VWAP</li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> Price dips to VWAP in uptrend and bounces with increased volume</p>
                <p><strong>Signal:</strong> <span className="bullish">BUY</span> - VWAP acting as support</p>
              </div>
            </section>

            {/* A/D Line */}
            <section id="ad" className="indicator-section">
              <h3 className="indicator-title">Accumulation/Distribution Line (A/D Line)</h3>

              <div className="indicator-subsection">
                <h4>What is A/D Line?</h4>
                <p>
                  The A/D Line uses volume and price to assess whether a stock is being accumulated (bought)
                  or distributed (sold). It considers where the close is relative to the high-low range and
                  multiplies this by volume to create a cumulative indicator.
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>Calculation</h4>
                <div className="formula">
                  <code>Money Flow Multiplier = ((Close - Low) - (High - Close)) / (High - Low)</code><br/>
                  <code>Money Flow Volume = Money Flow Multiplier × Volume</code><br/>
                  <code>A/D Line = Previous A/D + Money Flow Volume</code>
                </div>
              </div>

              <div className="indicator-subsection">
                <h4>Interpretation</h4>
                <ul className="interpretation-list">
                  <li><strong>A/D rising with price:</strong> <span className="bullish">Accumulation</span> - Strong buying pressure</li>
                  <li><strong>A/D falling with price:</strong> <span className="bearish">Distribution</span> - Strong selling pressure</li>
                  <li><strong>Price up, A/D down:</strong> <span className="bearish">Bearish divergence</span> - Weak rally</li>
                  <li><strong>Price down, A/D up:</strong> <span className="bullish">Bullish divergence</span> - Potential reversal</li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> Price makes lower lows but A/D Line makes higher lows</p>
                <p><strong>Signal:</strong> <span className="bullish">BUY</span> - Bullish divergence, accumulation occurring</p>
              </div>
            </section>

            {/* VOLATILITY & OTHER TOOLS */}
            <div className="category-header">
              <h2>📉 Volatility & Other Tools</h2>
              <p>Indicators that measure price volatility and identify key levels</p>
            </div>

            {/* Bollinger Bands */}
            <section id="bb" className="indicator-section">
              <h3 className="indicator-title">Bollinger Bands</h3>

              <div className="indicator-subsection">
                <h4>What are Bollinger Bands?</h4>
                <p>
                  Bollinger Bands consist of three lines: a middle band (moving average) and two outer bands representing
                  standard deviations. They expand and contract based on volatility and help identify overbought/oversold
                  conditions and potential breakouts.
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>Calculation</h4>
                <div className="formula">
                  <code>Middle Band = 20-period SMA</code><br/>
                  <code>Upper Band = Middle Band + (2 × Standard Deviation)</code><br/>
                  <code>Lower Band = Middle Band - (2 × Standard Deviation)</code>
                </div>
              </div>

              <div className="indicator-subsection">
                <h4>Interpretation</h4>
                <ul className="interpretation-list">
                  <li><strong>Price touches Upper Band:</strong> <span className="bearish">Overbought</span></li>
                  <li><strong>Price touches Lower Band:</strong> <span className="bullish">Oversold</span></li>
                  <li><strong>Bands squeeze (narrow):</strong> Low volatility, breakout coming</li>
                  <li><strong>Bands expand (wide):</strong> High volatility, strong trend</li>
                  <li><strong>Price walks the band:</strong> Very strong trend</li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> Bands squeeze then price breaks above upper band with volume</p>
                <p><strong>Signal:</strong> <span className="bullish">BUY</span> - Bullish breakout from consolidation</p>
              </div>
            </section>

            {/* ATR */}
            <section id="atr" className="indicator-section">
              <h3 className="indicator-title">Average True Range (ATR)</h3>

              <div className="indicator-subsection">
                <h4>What is ATR?</h4>
                <p>
                  ATR measures market volatility by calculating the average range between high and low prices
                  over a specified period. Higher ATR indicates higher volatility. It doesn't indicate trend
                  direction, only volatility magnitude.
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>Calculation</h4>
                <div className="formula">
                  <code>True Range = Max of:</code><br/>
                  <code>  - Current High - Current Low</code><br/>
                  <code>  - |Current High - Previous Close|</code><br/>
                  <code>  - |Current Low - Previous Close|</code><br/>
                  <code>ATR = 14-period average of True Range</code>
                </div>
              </div>

              <div className="indicator-subsection">
                <h4>Interpretation</h4>
                <ul className="interpretation-list">
                  <li><strong>Rising ATR:</strong> Increasing volatility - Strong trend or breakout</li>
                  <li><strong>Falling ATR:</strong> Decreasing volatility - Consolidation or weak trend</li>
                  <li><strong>High ATR:</strong> Wide stop-losses needed, larger price swings expected</li>
                  <li><strong>Low ATR:</strong> Tight stop-losses possible, smaller moves expected</li>
                  <li><strong>Use for position sizing:</strong> Adjust position size based on volatility</li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> ATR suddenly spikes from 2.0 to 4.5 during breakout</p>
                <p><strong>Signal:</strong> <span className="neutral">High volatility</span> - Strong move occurring, widen stops</p>
              </div>
            </section>

            {/* Keltner Channels */}
            <section id="keltner" className="indicator-section">
              <h3 className="indicator-title">Keltner Channels</h3>

              <div className="indicator-subsection">
                <h4>What are Keltner Channels?</h4>
                <p>
                  Keltner Channels are volatility-based envelopes set above and below an EMA. They're similar
                  to Bollinger Bands but use ATR instead of standard deviation. They help identify overbought/oversold
                  conditions and trend direction.
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>Calculation</h4>
                <div className="formula">
                  <code>Middle Line = 20-period EMA</code><br/>
                  <code>Upper Channel = EMA + (2 × ATR)</code><br/>
                  <code>Lower Channel = EMA - (2 × ATR)</code>
                </div>
              </div>

              <div className="indicator-subsection">
                <h4>Interpretation</h4>
                <ul className="interpretation-list">
                  <li><strong>Price above upper channel:</strong> <span className="bullish">Strong uptrend</span> - Overbought but momentum strong</li>
                  <li><strong>Price below lower channel:</strong> <span className="bearish">Strong downtrend</span> - Oversold but momentum strong</li>
                  <li><strong>Price returns to middle line:</strong> Potential reversal or consolidation</li>
                  <li><strong>Breakout above/below channel:</strong> Strong trend initiation</li>
                  <li><strong>Channels narrowing:</strong> Consolidation, potential breakout ahead</li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> Price breaks above upper channel with strong volume</p>
                <p><strong>Signal:</strong> <span className="bullish">BUY</span> - Strong bullish breakout momentum</p>
              </div>
            </section>

            {/* Fibonacci Retracement */}
            <section id="fibonacci" className="indicator-section">
              <h3 className="indicator-title">Fibonacci Retracement</h3>

              <div className="indicator-subsection">
                <h4>What is Fibonacci Retracement?</h4>
                <p>
                  Fibonacci Retracement uses horizontal lines to indicate areas of support or resistance at the
                  key Fibonacci levels before the price continues in the original direction. Based on the Fibonacci
                  sequence, traders use these levels to identify potential reversal points.
                </p>
              </div>

              <div className="indicator-subsection">
                <h4>Key Levels</h4>
                <div className="formula">
                  <code>Key Fibonacci Ratios:</code><br/>
                  <code>0% - Start of move (swing low or high)</code><br/>
                  <code>23.6% - Shallow retracement</code><br/>
                  <code>38.2% - Moderate retracement</code><br/>
                  <code>50.0% - Half retracement (not Fibonacci but widely used)</code><br/>
                  <code>61.8% - "Golden Ratio" - Strong support/resistance</code><br/>
                  <code>78.6% - Deep retracement</code><br/>
                  <code>100% - End of move</code>
                </div>
              </div>

              <div className="indicator-subsection">
                <h4>Interpretation</h4>
                <ul className="interpretation-list">
                  <li><strong>38.2% retracement:</strong> Shallow pullback in strong trend</li>
                  <li><strong>50% retracement:</strong> Moderate pullback, common reversal point</li>
                  <li><strong>61.8% retracement:</strong> <span className="bullish">Golden ratio</span> - Most significant level</li>
                  <li><strong>Price bounces at Fib level:</strong> Continuation signal in trend direction</li>
                  <li><strong>Price breaks through Fib level:</strong> Trend weakening, next level target</li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Example:</strong> After rally, price retraces to 61.8% Fibonacci level and bounces with volume</p>
                <p><strong>Signal:</strong> <span className="bullish">BUY</span> - Golden ratio support holding, uptrend likely to resume</p>
              </div>
            </section>

            {/* Combined Strategy */}
            <section className="indicator-section">
              <h3 className="indicator-title">🎯 Using Indicators Together</h3>

              <div className="indicator-subsection">
                <h4>Multi-Indicator Strategy</h4>
                <p>
                  Combine indicators from different categories for stronger signals:
                </p>
                <ul className="interpretation-list">
                  <li><strong>Trend + Momentum:</strong> Confirm trend direction with momentum strength</li>
                  <li><strong>Trend + Volume:</strong> Validate trend with volume confirmation</li>
                  <li><strong>Momentum + Volatility:</strong> Time entries at optimal risk/reward</li>
                  <li><strong>Volume + Price Action:</strong> Confirm breakouts and reversals</li>
                </ul>
              </div>

              <div className="example-box">
                <p><strong>Strong Bullish Confluence Example:</strong></p>
                <ul>
                  <li>✅ ADX &gt; 25 (strong trend)</li>
                  <li>✅ Price above 50 & 200 MA (uptrend)</li>
                  <li>✅ RSI bounces from 40 (healthy momentum)</li>
                  <li>✅ OBV rising (volume confirming)</li>
                  <li>✅ Price bounces off lower Bollinger Band</li>
                </ul>
                <p><strong>Signal:</strong> <span className="bullish">STRONG BUY</span> - Multiple confirmations across categories</p>
              </div>
            </section>

            {/* Best Practices */}
            <section className="indicator-section">
              <h3 className="indicator-title">💡 Best Practices</h3>
              <ul className="interpretation-list">
                <li><strong>Use 2-3 indicators minimum:</strong> One from each category (trend, momentum, volume)</li>
                <li><strong>Avoid redundant indicators:</strong> Don't use multiple similar indicators (e.g., RSI + Stochastic)</li>
                <li><strong>Timeframe matters:</strong> Higher timeframes give more reliable signals</li>
                <li><strong>Volume validates:</strong> Always check volume to confirm signals</li>
                <li><strong>Watch for divergences:</strong> When indicators disagree with price action</li>
                <li><strong>Context is key:</strong> Consider overall market conditions and fundamentals</li>
                <li><strong>Backtest strategies:</strong> Test indicator combinations before live trading</li>
                <li><strong>Risk management first:</strong> No indicator prevents losses - always use stop-losses</li>
              </ul>
            </section>

            {/* Disclaimer */}
            <section className="disclaimer-section">
              <h4>⚠️ Important Disclaimer</h4>
              <p>
                Technical indicators are analytical tools, not guarantees. They should be used as part of a
                comprehensive trading strategy that includes fundamental analysis, risk management, and consideration
                of market conditions. Past performance does not guarantee future results. Always do your own research
                and consider consulting with a financial advisor before making investment decisions.
              </p>
            </section>
          </div>
        </div>

        <div className="modal-footer">
          <button onClick={onClose} className="close-modal-btn">Close</button>
        </div>
      </div>

      <style jsx>{`
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.75);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 20px;
        }

        .modal-content {
          background: white;
          border-radius: 12px;
          max-width: 1400px;
          width: 100%;
          max-height: 90vh;
          display: flex;
          flex-direction: column;
          box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 24px 30px 16px 30px;
          border-bottom: 2px solid #e5e7eb;
        }

        .modal-header h2 {
          margin: 0;
          color: #111827;
          font-size: 28px;
        }

        .close-btn {
          background: transparent;
          border: none;
          font-size: 36px;
          cursor: pointer;
          color: #6b7280;
          line-height: 1;
          padding: 0;
          width: 40px;
          height: 40px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 8px;
          transition: all 0.2s;
        }

        .close-btn:hover {
          background: #f3f4f6;
          color: #111827;
        }

        .search-section {
          padding: 16px 30px;
          border-bottom: 1px solid #e5e7eb;
          background: #f9fafb;
        }

        .search-input {
          width: 100%;
          padding: 12px 16px;
          border: 2px solid #e5e7eb;
          border-radius: 8px;
          font-size: 15px;
          transition: all 0.2s;
        }

        .search-input:focus {
          outline: none;
          border-color: #667eea;
          box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        .modal-layout {
          display: flex;
          flex: 1;
          overflow: hidden;
        }

        .navigation-sidebar {
          width: 280px;
          background: #f9fafb;
          border-right: 2px solid #e5e7eb;
          overflow-y: auto;
          padding: 20px;
          flex-shrink: 0;
        }

        .navigation-sidebar h4 {
          margin: 0 0 16px 0;
          color: #111827;
          font-size: 16px;
          font-weight: 700;
        }

        .nav-category {
          margin-bottom: 20px;
        }

        .nav-category-title {
          font-size: 13px;
          font-weight: 700;
          color: #667eea;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 8px;
          padding-bottom: 6px;
          border-bottom: 2px solid #667eea;
        }

        .nav-list {
          list-style: none;
          padding: 0;
          margin: 0;
        }

        .nav-item {
          padding: 8px 12px;
          margin: 4px 0;
          cursor: pointer;
          border-radius: 6px;
          font-size: 13px;
          color: #4b5563;
          transition: all 0.2s;
        }

        .nav-item:hover {
          background: #e5e7eb;
          color: #111827;
        }

        .nav-item.active {
          background: #667eea;
          color: white;
          font-weight: 600;
        }

        .modal-body {
          overflow-y: auto;
          padding: 30px;
          flex: 1;
        }

        .category-header {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          padding: 20px 24px;
          border-radius: 12px;
          margin-bottom: 30px;
        }

        .category-header h2 {
          margin: 0 0 8px 0;
          font-size: 26px;
        }

        .category-header p {
          margin: 0;
          opacity: 0.95;
          font-size: 15px;
        }

        .indicator-section {
          margin-bottom: 40px;
          padding-bottom: 30px;
          border-bottom: 2px solid #e5e7eb;
        }

        .indicator-section:last-of-type {
          border-bottom: none;
        }

        .indicator-title {
          color: #111827;
          font-size: 22px;
          margin-bottom: 20px;
          padding-bottom: 12px;
          border-bottom: 3px solid #667eea;
        }

        .indicator-subsection {
          margin-bottom: 24px;
        }

        .indicator-subsection h4 {
          color: #374151;
          font-size: 17px;
          margin-bottom: 12px;
          font-weight: 600;
        }

        .indicator-subsection p {
          color: #4b5563;
          line-height: 1.7;
          margin-bottom: 12px;
          font-size: 15px;
        }

        .formula {
          background: #f9fafb;
          border-left: 4px solid #667eea;
          padding: 16px;
          border-radius: 6px;
          margin: 12px 0;
          font-family: 'Courier New', monospace;
        }

        .formula code {
          color: #374151;
          font-size: 13px;
          line-height: 1.8;
        }

        .formula-note {
          font-size: 13px;
          color: #6b7280;
          font-style: italic;
          margin-top: 8px;
        }

        .interpretation-list {
          list-style: none;
          padding: 0;
          margin: 12px 0;
        }

        .interpretation-list li {
          padding: 10px 14px;
          margin-bottom: 8px;
          background: #f9fafb;
          border-radius: 6px;
          color: #374151;
          line-height: 1.6;
          font-size: 14px;
        }

        .interpretation-list li strong {
          color: #111827;
        }

        .bullish {
          color: #10b981;
          font-weight: 600;
        }

        .bearish {
          color: #ef4444;
          font-weight: 600;
        }

        .neutral {
          color: #f59e0b;
          font-weight: 600;
        }

        .example-box {
          background: #fef3c7;
          border: 2px solid #fbbf24;
          border-radius: 8px;
          padding: 18px;
          margin: 12px 0;
        }

        .example-box p {
          margin: 6px 0;
          color: #78350f;
          font-size: 14px;
        }

        .example-box strong {
          color: #451a03;
        }

        .example-box ul {
          list-style: none;
          padding: 0;
          margin: 12px 0;
        }

        .example-box ul li {
          padding: 6px 0;
          color: #78350f;
          font-size: 14px;
        }

        .disclaimer-section {
          background: #fee2e2;
          border: 2px solid #ef4444;
          border-radius: 8px;
          padding: 20px;
          margin-top: 30px;
        }

        .disclaimer-section h4 {
          color: #7f1d1d;
          margin-bottom: 12px;
        }

        .disclaimer-section p {
          color: #7f1d1d;
          line-height: 1.6;
          margin: 0;
          font-size: 14px;
        }

        .modal-footer {
          padding: 20px 30px;
          border-top: 2px solid #e5e7eb;
          display: flex;
          justify-content: flex-end;
        }

        .close-modal-btn {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          border: none;
          padding: 12px 32px;
          border-radius: 8px;
          font-size: 16px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .close-modal-btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }

        /* Scrollbar styling */
        .modal-body::-webkit-scrollbar,
        .navigation-sidebar::-webkit-scrollbar {
          width: 10px;
        }

        .modal-body::-webkit-scrollbar-track,
        .navigation-sidebar::-webkit-scrollbar-track {
          background: #f3f4f6;
          border-radius: 10px;
        }

        .modal-body::-webkit-scrollbar-thumb,
        .navigation-sidebar::-webkit-scrollbar-thumb {
          background: #667eea;
          border-radius: 10px;
        }

        .modal-body::-webkit-scrollbar-thumb:hover,
        .navigation-sidebar::-webkit-scrollbar-thumb:hover {
          background: #5568d3;
        }

        @media (max-width: 1024px) {
          .navigation-sidebar {
            display: none;
          }
        }
      `}</style>
    </div>
  );
};

export default IndicatorInfo;
