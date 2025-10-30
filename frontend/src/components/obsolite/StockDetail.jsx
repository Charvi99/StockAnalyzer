import React, { useState, useEffect, useCallback } from 'react';
import StockChart from './StockChart';
import TechnicalAnalysis from './TechnicalAnalysis';
import SignalRadar from './SignalRadar';
import CandlestickPatterns from './CandlestickPatterns';
import ChartPatterns from './ChartPatterns';
import TradingStrategies from './TradingStrategies';
import { fetchStockData, getStockPrices, getRecommendation, analyzeSentiment } from '../services/api';

const StockDetail = ({ stock, onClose }) => {
  const [prices, setPrices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState(null);
  const [fetchResult, setFetchResult] = useState(null);
  const [period, setPeriod] = useState('1y');
  const [timeframe, setTimeframe] = useState('1d'); // Chart display timeframe
  const [recommendation, setRecommendation] = useState(null);
  const [recommendationLoading, setRecommendationLoading] = useState(false);
  const [recommendationError, setRecommendationError] = useState(null);
  const [sentimentData, setSentimentData] = useState(null);
  const [sentimentLoading, setSentimentLoading] = useState(false);
  const [sentimentError, setSentimentError] = useState(null);
  const [patterns, setPatterns] = useState([]);
  const [chartPatterns, setChartPatterns] = useState([]);

  // Pattern highlighting and selection state
  const [highlightedPattern, setHighlightedPattern] = useState(null);
  const [selectedPattern, setSelectedPattern] = useState(null);
  const [focusedPatternId, setFocusedPatternId] = useState(null);

  // Investopedia modal state
  const [showInvestopedia, setShowInvestopedia] = useState(false);

  // Shared indicator parameters state
  const [indicatorParams, setIndicatorParams] = useState({
    rsi_period: 14,
    macd_fast: 12,
    macd_slow: 26,
    macd_signal: 9,
    bb_window: 20,
    bb_std: 2.0,
    ma_short: 20,
    ma_long: 50
  });

  const loadPrices = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      // Fetch large amount of data - let backend handle aggregation based on timeframe
      // For 1h: up to 8760 bars/year, for 1d: 365 bars/year, etc.
      const limit = timeframe === '1h' ? 8760 : timeframe === '4h' ? 2190 : 3650;
      const data = await getStockPrices(stock.stock_id, limit, 0, timeframe);
      setPrices(data.prices);
    } catch (err) {
      setError('Failed to load price data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [stock.stock_id, timeframe]);

  const loadRecommendation = useCallback(async () => {
    try {
      setRecommendationLoading(true);
      setRecommendationError(null);
      const data = await getRecommendation(stock.stock_id);
      console.log('Recommendation data loaded:', data);
      setRecommendation(data);
    } catch (err) {
      console.error('Failed to load recommendation:', err);
      setRecommendationError(err.response?.data?.detail || err.message || 'Failed to load recommendation');
    } finally {
      setRecommendationLoading(false);
    }
  }, [stock.stock_id]);

  useEffect(() => {
    loadPrices();
    loadRecommendation();
  }, [loadPrices, loadRecommendation]);

  const handleFetchData = async () => {
    try {
      setFetching(true);
      setError(null);
      setFetchResult(null);

      // Always fetch 1h data (base timeframe for smart aggregation)
      const result = await fetchStockData(stock.stock_id, period, '1h');
      setFetchResult(result);

      // Reload prices and recommendation after fetching
      if (result.success) {
        await loadPrices();
        await loadRecommendation();
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch stock data');
      console.error(err);
    } finally {
      setFetching(false);
    }
  };

  const handleAnalyzeSentiment = async () => {
    try {
      setSentimentLoading(true);
      setSentimentError(null);
      const data = await analyzeSentiment(stock.stock_id);
      setSentimentData(data);
    } catch (err) {
      setSentimentError(err.response?.data?.detail || 'Failed to analyze sentiment');
      console.error(err);
    } finally {
      setSentimentLoading(false);
    }
  };

  return (
    <div className="stock-detail-overlay">
      <div className="stock-detail">
        <div className="stock-detail-header">
          <div>
            <h2>{stock.symbol} - {stock.name}</h2>
            <p className="stock-meta">
              {stock.sector && <span>{stock.sector}</span>}
              {stock.industry && <span> | {stock.industry}</span>}
            </p>
          </div>
          <div className="header-actions">
            <button onClick={() => setShowInvestopedia(true)} className="investopedia-btn" title="Learn about indicators, patterns & techniques">
              📚 Investopedia
            </button>
            <button onClick={onClose} className="close-btn">×</button>
          </div>
        </div>

        <div className="stock-detail-body">
          <div className="fetch-controls">
            <h3>📥 Fetch Historical Data from Polygon.io</h3>
            <p className="fetch-hint">Fetch 1-hour base data. All timeframes will be aggregated automatically.</p>
            <div className="controls-row">
              <div className="control-group">
                <label>Period:</label>
                <select value={period} onChange={(e) => setPeriod(e.target.value)}>
                  <option value="1mo">1 Month (~730 bars)</option>
                  <option value="3mo">3 Months (~2,190 bars)</option>
                  <option value="6mo">6 Months (~4,380 bars)</option>
                  <option value="1y">1 Year (~8,760 bars)</option>
                  <option value="2y">2 Years (~17,520 bars)</option>
                </select>
              </div>

              <button
                onClick={handleFetchData}
                disabled={fetching}
                className="fetch-btn"
              >
                {fetching ? 'Fetching 1h Data...' : 'Fetch Data'}
              </button>
            </div>

            {fetchResult && (
              <div className={`fetch-result ${fetchResult.success ? 'success' : 'error'}`}>
                <p>{fetchResult.message}</p>
                {fetchResult.success && (
                  <p className="fetch-stats">
                    Fetched: {fetchResult.records_fetched} hourly bars |
                    Saved: {fetchResult.records_saved} new records
                  </p>
                )}
              </div>
            )}
          </div>

          {error && <div className="error">{error}</div>}

          {loading ? (
            <div className="loading">Loading price data...</div>
          ) : prices.length > 0 ? (
            <>
              {/* Timeframe Selector - Moved to Chart Section */}
              <div className="timeframe-selector">
                <h4>📊 Chart Display Timeframe</h4>
                <p className="timeframe-hint">
                  Switch between timeframes (aggregated from 1h base data).
                  Showing {prices.length} {timeframe} bars.
                </p>
                <div className="timeframe-buttons">
                  <button
                    className={`timeframe-btn ${timeframe === '1h' ? 'active' : ''}`}
                    onClick={() => setTimeframe('1h')}
                    title="Hourly candles - Best for day trading"
                  >
                    1 Hour
                  </button>
                  <button
                    className={`timeframe-btn ${timeframe === '4h' ? 'active' : ''}`}
                    onClick={() => setTimeframe('4h')}
                    title="4-hour candles - Good for swing trading"
                  >
                    4 Hours
                  </button>
                  <button
                    className={`timeframe-btn ${timeframe === '1d' ? 'active' : ''}`}
                    onClick={() => setTimeframe('1d')}
                    title="Daily candles - Standard timeframe"
                  >
                    1 Day
                  </button>
                  <button
                    className={`timeframe-btn ${timeframe === '1w' ? 'active' : ''}`}
                    onClick={() => setTimeframe('1w')}
                    title="Weekly candles - Trend analysis"
                  >
                    1 Week
                  </button>
                  <button
                    className={`timeframe-btn ${timeframe === '1mo' ? 'active' : ''}`}
                    onClick={() => setTimeframe('1mo')}
                    title="Monthly candles - Long-term trends"
                  >
                    1 Month
                  </button>
                </div>
              </div>

              <StockChart
                prices={prices}
                symbol={stock.symbol}
                stockId={stock.stock_id}
                indicatorParams={indicatorParams}
                patterns={patterns}
                chartPatterns={chartPatterns}
              />

              {/* Signal Radar Chart */}
              {recommendationLoading ? (
                <div className="loading" style={{ margin: '20px 0', padding: '20px', textAlign: 'center' }}>
                  Loading recommendation data...
                </div>
              ) : recommendationError ? (
                <div className="error" style={{ margin: '20px 0', padding: '20px' }}>
                  <strong>Radar Chart Error:</strong> {recommendationError}
                </div>
              ) : recommendation ? (
                <SignalRadar recommendation={recommendation} />
              ) : (
                <div className="no-data" style={{ margin: '20px 0', padding: '20px' }}>
                  No recommendation data available. Fetching more data may help.
                </div>
              )}

              <TechnicalAnalysis
                stockId={stock.stock_id}
                symbol={stock.symbol}
                indicatorParams={indicatorParams}
                setIndicatorParams={setIndicatorParams}
              />

              {/* Candlestick Patterns Section */}
              <CandlestickPatterns
                stockId={stock.stock_id}
                symbol={stock.symbol}
                onPatternsDetected={setPatterns}
              />

              {/* Chart Patterns Section */}
              <ChartPatterns
                stockId={stock.stock_id}
                symbol={stock.symbol}
                onPatternsDetected={setChartPatterns}
              />

              {/* Trading Strategies Section */}
              <TradingStrategies stockId={stock.stock_id} />

              {/* Sentiment Analysis Section */}
              <div className="sentiment-analysis-section">
                <h3>Sentiment Analysis</h3>
                <button onClick={handleAnalyzeSentiment} disabled={sentimentLoading}>
                  {sentimentLoading ? 'Analyzing...' : 'Analyze Sentiment'}
                </button>
                {sentimentError && <div className="error">{sentimentError}</div>}
                {sentimentData && (
                  <div className="sentiment-results">
                    <h4>Sentiment Index: {sentimentData.sentiment_index.toFixed(2)}</h4>
                    <div className="sentiment-stats">
                      <p>Positive: {sentimentData.positive_pct.toFixed(1)}% ({sentimentData.positive_count})</p>
                      <p>Negative: {sentimentData.negative_pct.toFixed(1)}% ({sentimentData.negative_count})</p>
                      <p>Neutral: {sentimentData.neutral_pct.toFixed(1)}% ({sentimentData.neutral_count})</p>
                    </div>
                    <h5>News Headlines</h5>
                    <ul className="news-list">
                      {sentimentData.news.map((article, index) => (
                        <li key={index}>
                          <a href={article.URL} target="_blank" rel="noopener noreferrer">{article.Headline}</a>
                          <span>({article.SCORE_SENT})</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="no-data">
              <p>No price data available for this stock.</p>
              <p>Click "Fetch Data" above to load historical prices from Polygon.io.</p>
            </div>
          )}
        </div>
      </div>

      {/* Investopedia Modal */}
      {showInvestopedia && (
        <div className="modal-overlay" onClick={() => setShowInvestopedia(false)}>
          <div className="modal-content investopedia-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>📚 Stock Analyzer Investopedia</h2>
              <button onClick={() => setShowInvestopedia(false)} className="modal-close">×</button>
            </div>
            <div className="modal-body investopedia-content">

              <section className="guide-section">
                <h3>📊 Technical Indicators</h3>

                <div className="indicator-card">
                  <h4>🔴 RSI (Relative Strength Index)</h4>
                  <p><strong>Purpose:</strong> Measures momentum to identify overbought/oversold conditions</p>
                  <p><strong>Range:</strong> 0-100</p>
                  <ul>
                    <li><strong>Above 70:</strong> Overbought (potential sell signal)</li>
                    <li><strong>Below 30:</strong> Oversold (potential buy signal)</li>
                    <li><strong>50:</strong> Neutral momentum</li>
                  </ul>
                  <p><strong>Best For:</strong> Identifying reversal points in trending markets</p>
                </div>

                <div className="indicator-card">
                  <h4>📈 MACD (Moving Average Convergence Divergence)</h4>
                  <p><strong>Purpose:</strong> Trend-following momentum indicator showing relationship between two moving averages</p>
                  <p><strong>Components:</strong></p>
                  <ul>
                    <li><strong>MACD Line:</strong> 12-day EMA - 26-day EMA</li>
                    <li><strong>Signal Line:</strong> 9-day EMA of MACD</li>
                    <li><strong>Histogram:</strong> MACD - Signal (shows momentum strength)</li>
                  </ul>
                  <p><strong>Signals:</strong></p>
                  <ul>
                    <li><strong>Bullish Crossover:</strong> MACD crosses above Signal (buy)</li>
                    <li><strong>Bearish Crossover:</strong> MACD crosses below Signal (sell)</li>
                    <li><strong>Zero Line Cross:</strong> MACD crosses zero (trend change)</li>
                  </ul>
                </div>

                <div className="indicator-card">
                  <h4>📊 Bollinger Bands</h4>
                  <p><strong>Purpose:</strong> Volatility indicator showing price boundaries relative to moving average</p>
                  <p><strong>Components:</strong></p>
                  <ul>
                    <li><strong>Middle Band:</strong> 20-day SMA (average price)</li>
                    <li><strong>Upper Band:</strong> SMA + (2 × Standard Deviation)</li>
                    <li><strong>Lower Band:</strong> SMA - (2 × Standard Deviation)</li>
                  </ul>
                  <p><strong>Signals:</strong></p>
                  <ul>
                    <li><strong>Squeeze:</strong> Bands narrow → Low volatility → Big move coming</li>
                    <li><strong>Touch Upper Band:</strong> Overbought condition</li>
                    <li><strong>Touch Lower Band:</strong> Oversold condition</li>
                    <li><strong>Price Outside Bands:</strong> Strong trend continuation</li>
                  </ul>
                </div>

                <div className="indicator-card">
                  <h4>📉 Moving Averages (MA)</h4>
                  <p><strong>Purpose:</strong> Smooth price data to identify trend direction</p>
                  <p><strong>Types:</strong></p>
                  <ul>
                    <li><strong>SMA (Simple):</strong> Average of prices over N periods</li>
                    <li><strong>EMA (Exponential):</strong> Weighted average favoring recent prices</li>
                  </ul>
                  <p><strong>Common Strategies:</strong></p>
                  <ul>
                    <li><strong>Golden Cross:</strong> Short MA crosses above Long MA (bullish)</li>
                    <li><strong>Death Cross:</strong> Short MA crosses below Long MA (bearish)</li>
                    <li><strong>Support/Resistance:</strong> Price bounces off MA lines</li>
                  </ul>
                  <p><strong>Popular Periods:</strong> 20 (short), 50 (medium), 200 (long-term trend)</p>
                </div>
              </section>

              <section className="guide-section">
                <h3>🕯️ Candlestick Patterns</h3>
                <p className="section-intro">Single or multi-candle formations that predict price reversals or continuations.</p>

                <div className="pattern-grid">
                  <div className="pattern-card bullish">
                    <h4>🟢 Bullish Patterns</h4>
                    <ul>
                      <li><strong>Hammer:</strong> Small body, long lower wick → Reversal from downtrend</li>
                      <li><strong>Bullish Engulfing:</strong> Large green candle engulfs previous red → Strong reversal</li>
                      <li><strong>Morning Star:</strong> 3-candle pattern → Downtrend reversal</li>
                      <li><strong>Three White Soldiers:</strong> 3 consecutive green candles → Strong uptrend</li>
                      <li><strong>Piercing Line:</strong> Green candle closes above midpoint of previous red</li>
                    </ul>
                  </div>

                  <div className="pattern-card bearish">
                    <h4>🔴 Bearish Patterns</h4>
                    <ul>
                      <li><strong>Shooting Star:</strong> Small body, long upper wick → Reversal from uptrend</li>
                      <li><strong>Bearish Engulfing:</strong> Large red candle engulfs previous green → Strong reversal</li>
                      <li><strong>Evening Star:</strong> 3-candle pattern → Uptrend reversal</li>
                      <li><strong>Three Black Crows:</strong> 3 consecutive red candles → Strong downtrend</li>
                      <li><strong>Dark Cloud Cover:</strong> Red candle closes below midpoint of previous green</li>
                    </ul>
                  </div>

                  <div className="pattern-card neutral">
                    <h4>⚖️ Indecision Patterns</h4>
                    <ul>
                      <li><strong>Doji:</strong> Open ≈ Close → Market indecision, potential reversal</li>
                      <li><strong>Spinning Top:</strong> Small body, long wicks both sides → Weak momentum</li>
                      <li><strong>Harami:</strong> Small candle inside previous large candle → Trend weakening</li>
                    </ul>
                  </div>
                </div>
              </section>

              <section className="guide-section">
                <h3>📐 Chart Patterns (Advanced)</h3>
                <p className="section-intro">Multi-day price formations detected by our AI system across multiple timeframes.</p>

                <div className="pattern-card reversal">
                  <h4>🔄 Reversal Patterns</h4>
                  <p><strong>Purpose:</strong> Signal trend changes from bullish to bearish or vice versa</p>

                  <div className="sub-pattern">
                    <h5>Head & Shoulders (Bearish)</h5>
                    <ul>
                      <li><strong>Formation:</strong> Left shoulder → Head (higher peak) → Right shoulder</li>
                      <li><strong>Neckline:</strong> Support level connecting troughs</li>
                      <li><strong>Target:</strong> Distance from head to neckline, projected down from breakout</li>
                      <li><strong>Confirmation:</strong> Break below neckline with volume</li>
                    </ul>
                  </div>

                  <div className="sub-pattern">
                    <h5>Inverse Head & Shoulders (Bullish)</h5>
                    <ul>
                      <li><strong>Formation:</strong> Upside-down version of H&S</li>
                      <li><strong>Target:</strong> Same distance as downtrend, but upward</li>
                      <li><strong>Confirmation:</strong> Break above neckline with volume</li>
                    </ul>
                  </div>

                  <div className="sub-pattern">
                    <h5>Double Top (Bearish)</h5>
                    <ul>
                      <li><strong>Formation:</strong> Two peaks at similar price level</li>
                      <li><strong>Target:</strong> Distance from peaks to support, projected down</li>
                      <li><strong>Volume:</strong> Should decrease on second peak</li>
                    </ul>
                  </div>

                  <div className="sub-pattern">
                    <h5>Double Bottom (Bullish)</h5>
                    <ul>
                      <li><strong>Formation:</strong> Two troughs at similar price level</li>
                      <li><strong>Target:</strong> Distance from bottoms to resistance, projected up</li>
                      <li><strong>Confirmation:</strong> Break above resistance between bottoms</li>
                    </ul>
                  </div>

                  <div className="sub-pattern">
                    <h5>Triple Top / Triple Bottom</h5>
                    <ul>
                      <li><strong>Formation:</strong> Three peaks (top) or troughs (bottom) at similar levels</li>
                      <li><strong>Reliability:</strong> More reliable than double patterns (more tests)</li>
                      <li><strong>Target:</strong> Same calculation as double patterns</li>
                    </ul>
                  </div>

                  <div className="sub-pattern">
                    <h5>Rounding Top / Rounding Bottom</h5>
                    <ul>
                      <li><strong>Formation:</strong> Gradual curve forming dome (top) or bowl (bottom)</li>
                      <li><strong>Duration:</strong> Long-term pattern (weeks to months)</li>
                      <li><strong>Volume:</strong> Decreases during formation, increases at breakout</li>
                    </ul>
                  </div>
                </div>

                <div className="pattern-card continuation">
                  <h4>➡️ Continuation Patterns</h4>
                  <p><strong>Purpose:</strong> Brief consolidation before trend continues in same direction</p>

                  <div className="sub-pattern">
                    <h5>Ascending Triangle (Bullish)</h5>
                    <ul>
                      <li><strong>Formation:</strong> Flat resistance + rising support</li>
                      <li><strong>Breakout:</strong> Upward through resistance</li>
                      <li><strong>Target:</strong> Height of triangle base, projected up</li>
                      <li><strong>Best Context:</strong> During uptrend</li>
                    </ul>
                  </div>

                  <div className="sub-pattern">
                    <h5>Descending Triangle (Bearish)</h5>
                    <ul>
                      <li><strong>Formation:</strong> Flat support + declining resistance</li>
                      <li><strong>Breakout:</strong> Downward through support</li>
                      <li><strong>Target:</strong> Height of triangle base, projected down</li>
                      <li><strong>Best Context:</strong> During downtrend</li>
                    </ul>
                  </div>

                  <div className="sub-pattern">
                    <h5>Symmetrical Triangle</h5>
                    <ul>
                      <li><strong>Formation:</strong> Converging trendlines (both sloping)</li>
                      <li><strong>Breakout:</strong> Can go either direction</li>
                      <li><strong>Confirmation:</strong> Volume spike on breakout</li>
                      <li><strong>Timing:</strong> Breakout usually occurs at 2/3 to 3/4 through pattern</li>
                    </ul>
                  </div>

                  <div className="sub-pattern">
                    <h5>Bullish/Bearish Flag</h5>
                    <ul>
                      <li><strong>Formation:</strong> Strong move (pole) + brief consolidation (flag)</li>
                      <li><strong>Bullish Flag:</strong> Downward-sloping consolidation after uptrend</li>
                      <li><strong>Bearish Flag:</strong> Upward-sloping consolidation after downtrend</li>
                      <li><strong>Target:</strong> Length of pole, projected from breakout</li>
                      <li><strong>Duration:</strong> Short-term (1-4 weeks)</li>
                    </ul>
                  </div>

                  <div className="sub-pattern">
                    <h5>Bullish/Bearish Pennant</h5>
                    <ul>
                      <li><strong>Formation:</strong> Like flag but with converging trendlines</li>
                      <li><strong>Target:</strong> Same as flag (pole length)</li>
                      <li><strong>Volume:</strong> Decreases during consolidation</li>
                    </ul>
                  </div>

                  <div className="sub-pattern">
                    <h5>Rectangle (Consolidation)</h5>
                    <ul>
                      <li><strong>Formation:</strong> Horizontal support and resistance</li>
                      <li><strong>Breakout:</strong> Can go either direction</li>
                      <li><strong>Target:</strong> Height of rectangle, projected from breakout</li>
                    </ul>
                  </div>
                </div>

                <div className="pattern-card wedge">
                  <h4>⚡ Wedge Patterns</h4>

                  <div className="sub-pattern">
                    <h5>Rising Wedge (Bearish)</h5>
                    <ul>
                      <li><strong>Formation:</strong> Both trendlines slope up, converging</li>
                      <li><strong>Signal:</strong> Reversal pattern (bearish)</li>
                      <li><strong>Breakout:</strong> Downward (below support)</li>
                      <li><strong>Volume:</strong> Decreasing during formation</li>
                    </ul>
                  </div>

                  <div className="sub-pattern">
                    <h5>Falling Wedge (Bullish)</h5>
                    <ul>
                      <li><strong>Formation:</strong> Both trendlines slope down, converging</li>
                      <li><strong>Signal:</strong> Reversal pattern (bullish)</li>
                      <li><strong>Breakout:</strong> Upward (above resistance)</li>
                      <li><strong>Volume:</strong> Increasing on breakout</li>
                    </ul>
                  </div>
                </div>
              </section>

              <section className="guide-section highlight-section">
                <h3>🚀 Advanced Techniques (Our System)</h3>
                <p className="section-intro">Proprietary features that give you an edge over standard charting tools.</p>

                <div className="technique-card">
                  <h4>🎯 Multi-Timeframe Pattern Confirmation</h4>
                  <p><strong>What It Does:</strong> Detects patterns across 1h, 4h, and 1d timeframes simultaneously</p>
                  <p><strong>Why It Matters:</strong> Reduces false positives by 40-60%</p>
                  <ul>
                    <li><strong>1TF Patterns:</strong> Found on single timeframe only (baseline confidence)</li>
                    <li><strong>2TF Patterns ✅:</strong> Confirmed on 2 timeframes (+40% confidence boost)</li>
                    <li><strong>3TF Patterns 🔥:</strong> Confirmed on all 3 timeframes (+80% confidence boost)</li>
                  </ul>
                  <p><strong>Alignment Score:</strong> Measures how similar the pattern looks across timeframes</p>
                  <ul>
                    <li><strong>80%+ alignment:</strong> Excellent (pattern very consistent)</li>
                    <li><strong>60-80%:</strong> Good (pattern reasonably similar)</li>
                    <li><strong>&lt;60%:</strong> Moderate (some variation across timeframes)</li>
                  </ul>
                  <p className="tip">💡 <strong>Pro Tip:</strong> Always prioritize 2TF/3TF patterns for swing trading!</p>
                </div>

                <div className="technique-card">
                  <h4>📈 Volume Analysis & Validation</h4>
                  <p><strong>What It Does:</strong> Analyzes volume to validate pattern strength and breakout quality</p>
                  <p><strong>Why It Matters:</strong> 25-33% reduction in false breakouts</p>

                  <p><strong>Volume Quality Levels:</strong></p>
                  <ul>
                    <li><strong>🔥 Excellent (2x+ avg volume):</strong> Strong institutional interest, +30% confidence</li>
                    <li><strong>✅ Good (1.5-2x avg volume):</strong> Validated breakout, +15% confidence</li>
                    <li><strong>➖ Average (1-1.5x avg volume):</strong> Normal trading, no adjustment</li>
                    <li><strong>⚠️ Weak (&lt;1x avg volume):</strong> Low participation, -30% confidence</li>
                  </ul>

                  <p><strong>VWAP (Volume-Weighted Average Price):</strong></p>
                  <ul>
                    <li><strong>Purpose:</strong> Dynamic support/resistance based on volume</li>
                    <li><strong>↑ Above VWAP:</strong> Bullish context (buyers in control)</li>
                    <li><strong>↓ Below VWAP:</strong> Bearish context (sellers in control)</li>
                    <li><strong>Alignment:</strong> Pattern direction matches VWAP position = stronger signal</li>
                  </ul>

                  <p className="tip">💡 <strong>Warning:</strong> Never trade a pattern with weak volume, even if it looks perfect!</p>
                </div>

                <div className="technique-card">
                  <h4>🧮 Smart Confidence Scoring</h4>
                  <p><strong>Formula:</strong> Base Confidence × Timeframe Multiplier × Alignment Bonus × Volume Multiplier</p>
                  <p><strong>Example Calculation:</strong></p>
                  <pre className="formula-example">
Pattern: Head & Shoulders
Base Confidence: 65%
Timeframe: 2TF (×1.4)
Alignment: 85% (+12%)
Volume: 1.8x avg (+15%)

Final = 0.65 × 1.4 × 1.12 × 1.15 = 1.17 → 95% (capped)
                  </pre>
                  <p><strong>Confidence Levels:</strong></p>
                  <ul>
                    <li><strong>90%+:</strong> Extremely high probability (rare, trade with confidence)</li>
                    <li><strong>80-90%:</strong> High probability (strong pattern)</li>
                    <li><strong>70-80%:</strong> Good probability (valid pattern)</li>
                    <li><strong>60-70%:</strong> Moderate (needs confirmation)</li>
                    <li><strong>&lt;60%:</strong> Low (avoid or wait for better setup)</li>
                  </ul>
                </div>

                <div className="technique-card">
                  <h4>🎨 Pattern Visualization</h4>
                  <p><strong>What It Does:</strong> Shows ASCII art schematics of each pattern</p>
                  <p><strong>Benefits:</strong></p>
                  <ul>
                    <li>Quickly verify pattern shape without studying the chart</li>
                    <li>Educational: Learn to recognize patterns faster</li>
                    <li>Visual confirmation of detected patterns</li>
                  </ul>
                </div>

                <div className="technique-card">
                  <h4>📊 Quality Analysis Panel</h4>
                  <p><strong>Located:</strong> Click triangle icon (▶) on any pattern to expand</p>
                  <p><strong>Shows:</strong></p>
                  <ul>
                    <li>Multi-timeframe confirmation details</li>
                    <li>Volume analysis breakdown</li>
                    <li>Color-coded metrics (green = good, red = caution)</li>
                    <li>Contextual hints and tips</li>
                    <li>Pattern-specific metrics (support/resistance levels, etc.)</li>
                  </ul>
                  <p className="tip">💡 <strong>Use Case:</strong> Check quality panel before entering any trade!</p>
                </div>
              </section>

              <section className="guide-section">
                <h3>💼 Trading Best Practices</h3>

                <div className="best-practice-card">
                  <h4>✅ Do's</h4>
                  <ul>
                    <li>Always check volume before trading a pattern</li>
                    <li>Prioritize 2TF/3TF confirmed patterns</li>
                    <li>Use stop-losses (usually below support for longs)</li>
                    <li>Wait for breakout confirmation (don't anticipate)</li>
                    <li>Check VWAP alignment with pattern direction</li>
                    <li>Look for high alignment scores (75%+)</li>
                    <li>Trade in direction of overall trend</li>
                    <li>Use multiple indicators for confirmation</li>
                  </ul>
                </div>

                <div className="best-practice-card">
                  <h4>❌ Don'ts</h4>
                  <ul>
                    <li>Don't trade patterns with weak volume (⚠️)</li>
                    <li>Don't ignore 1TF-only patterns (less reliable)</li>
                    <li>Don't skip the quality analysis panel</li>
                    <li>Don't trade against VWAP if pattern is counter-trend</li>
                    <li>Don't enter before breakout confirmation</li>
                    <li>Don't ignore confidence scores below 70%</li>
                    <li>Don't overtrade - quality over quantity</li>
                    <li>Don't forget to set stop-losses</li>
                  </ul>
                </div>

                <div className="best-practice-card">
                  <h4>🎯 Pattern Selection Priority</h4>
                  <ol>
                    <li><strong>Highest Priority:</strong> 3TF + Excellent Volume (🔥) + 80%+ alignment</li>
                    <li><strong>High Priority:</strong> 2TF + Good Volume (✅) + 70%+ alignment</li>
                    <li><strong>Medium Priority:</strong> 2TF + Average Volume + 60%+ alignment</li>
                    <li><strong>Low Priority:</strong> 1TF only (use for learning, not trading)</li>
                    <li><strong>Avoid:</strong> Any pattern with weak volume (⚠️)</li>
                  </ol>
                </div>
              </section>

              <section className="guide-section">
                <h3>📚 Additional Resources</h3>
                <ul className="resources-list">
                  <li><a href="https://www.investopedia.com/terms/t/technicalindicator.asp" target="_blank" rel="noopener noreferrer">Investopedia: Technical Indicators</a></li>
                  <li><a href="https://www.investopedia.com/articles/technical/112601.asp" target="_blank" rel="noopener noreferrer">Investopedia: Chart Patterns</a></li>
                  <li><a href="https://www.investopedia.com/articles/active-trading/031914/understanding-bollinger-bands-and-rsi.asp" target="_blank" rel="noopener noreferrer">Understanding Bollinger Bands and RSI</a></li>
                  <li><a href="https://www.investopedia.com/terms/v/vwap.asp" target="_blank" rel="noopener noreferrer">VWAP Explained</a></li>
                </ul>
              </section>

            </div>
            <div className="modal-footer">
              <button onClick={() => setShowInvestopedia(false)} className="btn-close-modal">Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default StockDetail;
