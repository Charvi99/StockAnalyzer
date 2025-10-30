import React, { useState, useEffect, useCallback, useRef } from 'react';
import StockChart from './StockChart';
import TechnicalAnalysis from './TechnicalAnalysis';
import CandlestickPatterns from './CandlestickPatterns';
import ChartPatterns from './ChartPatterns';
import TradingStrategies from './TradingStrategies';
import SentimentAnalysis from './SentimentAnalysis';
import OverviewTab from './OverviewTab';
import TrailingStopCalculator from './TrailingStopCalculator';
import PortfolioHeatMonitor from './PortfolioHeatMonitor';
import MarketRegime from './MarketRegime';
import { fetchStockData, getStockPrices, getRecommendation } from '../services/api';
import './StockDetailSideBySide.css';

const StockDetailSideBySide = ({ stock, onClose }) => {
  const [prices, setPrices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState(null);
  const [fetchResult, setFetchResult] = useState(null);
  const [period, setPeriod] = useState('1mo'); // Default to 1 month for swing trading
  const [timeframe, setTimeframe] = useState('1d'); // Chart display timeframe
  const [recommendation, setRecommendation] = useState(null);
  const [recommendationLoading, setRecommendationLoading] = useState(false);
  const [recommendationError, setRecommendationError] = useState(null);
  const [patterns, setPatterns] = useState([]);
  const [chartPatterns, setChartPatterns] = useState([]);

  // Pattern highlighting and selection state
  const [highlightedPattern, setHighlightedPattern] = useState(null);
  const [activeTab, setActiveTab] = useState('chart-patterns'); // 'chart-patterns', 'technical', 'signals'
  const [rightPanelTab, setRightPanelTab] = useState('overview'); // 'overview', 'chart'

  const chartPatternsRef = useRef(null);

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
      setRecommendation(data);
    } catch (err) {
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

      // Fetch 1h data for swing trading (base timeframe for smart aggregation)
      const result = await fetchStockData(stock.stock_id, period, '1h');
      setFetchResult(result);

      if (result.success) {
        // Small delay to ensure data is saved to database
        await new Promise(resolve => setTimeout(resolve, 500));

        // Reload prices and recommendation with fresh data
        await loadPrices();
        await loadRecommendation();
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch stock data');
    } finally {
      setFetching(false);
    }
  };

  // Pattern highlighting handlers
  const handlePatternHover = useCallback((pattern) => {
    setHighlightedPattern(pattern);
  }, []);

  const handlePatternLeave = useCallback(() => {
    setHighlightedPattern(null);
  }, []);

  // Get visible chart patterns (those that user toggled on)
  const visibleChartPatterns = chartPatterns.filter(p => p && p.id);

  return (
    <div className="stock-detail-overlay-sbs">
      <div className="stock-detail-sbs">
        <div className="stock-detail-header-sbs">
          <div className="header-left">
            <h2>{stock.symbol} - {stock.name}</h2>
            <p className="stock-meta">
              {stock.sector && <span>{stock.sector}</span>}
              {stock.industry && <span> | {stock.industry}</span>}
            </p>
          </div>
          <div className="header-actions">
            <button onClick={onClose} className="close-btn-sbs">×</button>
          </div>
        </div>

        <div className="fetch-controls-sbs">
          {/* Left Section - Fetch Data Controls */}
          <div className="controls-left-section">
            <div className="fetch-controls-row">
              <label>Period:</label>
              <select value={period} onChange={(e) => setPeriod(e.target.value)} className="period-select-sbs">
                <option value="1mo">1 Month (~730 bars)</option>
                <option value="3mo">3 Months (~2,190 bars)</option>
                <option value="6mo">6 Months (~4,380 bars)</option>
                <option value="1y">1 Year (~8,760 bars)</option>
                <option value="2y">2 Years (~17,520 bars)</option>
              </select>

              <button onClick={handleFetchData} disabled={fetching} className="fetch-btn-sbs">
                {fetching ? 'Fetching 1h Data...' : 'Fetch Data'}
              </button>
            </div>

            {fetchResult && (
              <div className={`fetch-result-sbs ${fetchResult.success ? 'success' : 'error'}`}>
                <p>{fetchResult.message}</p>
                {fetchResult.success && (
                  <p className="fetch-stats-sbs">
                    Fetched: {fetchResult.records_fetched} hourly bars | Saved: {fetchResult.records_saved} new records
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Right Section - Right Panel Tabs */}
          <div className="controls-right-section">
            <div className="right-panel-tabs">
              <button
                className={`right-tab-btn ${rightPanelTab === 'overview' ? 'active' : ''}`}
                onClick={() => setRightPanelTab('overview')}
              >
                📊 Overview
              </button>
              <button
                className={`right-tab-btn ${rightPanelTab === 'chart' ? 'active' : ''}`}
                onClick={() => setRightPanelTab('chart')}
              >
                📈 Chart
              </button>
            </div>
          </div>
        </div>

        {error && <div className="error-sbs">{error}</div>}

        {loading ? (
          <div className="loading-sbs">Loading price data...</div>
        ) : prices.length > 0 ? (
          <div className="content-split-sbs">
            {/* LEFT SIDE - Scrollable Pattern List */}
            <div className="panels-container-sbs">
              <div className="tab-nav-sbs">
                <button
                  className={`tab-btn-sbs ${activeTab === 'chart-patterns' ? 'active' : ''}`}
                  onClick={() => setActiveTab('chart-patterns')}
                >
                  📊 Chart Patterns
                </button>
                <button
                  className={`tab-btn-sbs ${activeTab === 'candlestick' ? 'active' : ''}`}
                  onClick={() => setActiveTab('candlestick')}
                >
                  🕯️ Candlestick Patterns
                </button>
                <button
                  className={`tab-btn-sbs ${activeTab === 'technical' ? 'active' : ''}`}
                  onClick={() => setActiveTab('technical')}
                >
                  📈 Technical Analysis
                </button>
                <button
                  className={`tab-btn-sbs ${activeTab === 'strategies' ? 'active' : ''}`}
                  onClick={() => setActiveTab('strategies')}
                >
                  🎯 Trading Strategies
                </button>
                <button
                  className={`tab-btn-sbs ${activeTab === 'sentiment' ? 'active' : ''}`}
                  onClick={() => setActiveTab('sentiment')}
                >
                  💭 Sentiment Analysis
                </button>
                <button
                  className={`tab-btn-sbs ${activeTab === 'risk-tools' ? 'active' : ''}`}
                  onClick={() => setActiveTab('risk-tools')}
                >
                  🔥 Risk Tools
                </button>
              </div>

              <div className="tab-content-sbs">
                {activeTab === 'chart-patterns' && (
                  <ChartPatterns
                    ref={chartPatternsRef}
                    stockId={stock.stock_id}
                    symbol={stock.symbol}
                    onPatternsDetected={setChartPatterns}
                    onPatternsUpdated={loadRecommendation}
                    onPatternHover={handlePatternHover}
                    onPatternLeave={handlePatternLeave}
                    highlightedPattern={highlightedPattern}
                    enableKeyboardShortcuts={true}
                  />
                )}

                {activeTab === 'candlestick' && (
                  <CandlestickPatterns
                    stockId={stock.stock_id}
                    symbol={stock.symbol}
                    onPatternsDetected={setPatterns}
                    onPatternsUpdated={loadRecommendation}
                    onPatternHover={handlePatternHover}
                    onPatternLeave={handlePatternLeave}
                  />
                )}

                {activeTab === 'technical' && (
                  <TechnicalAnalysis
                    stockId={stock.stock_id}
                    symbol={stock.symbol}
                    indicatorParams={indicatorParams}
                    setIndicatorParams={setIndicatorParams}
                    onAnalysisUpdated={loadRecommendation}
                  />
                )}

                {activeTab === 'strategies' && (
                  <TradingStrategies stockId={stock.stock_id} />
                )}

                {activeTab === 'sentiment' && (
                  <SentimentAnalysis
                    stockId={stock.stock_id}
                    symbol={stock.symbol}
                    onSentimentUpdated={loadRecommendation}
                  />
                )}

                {activeTab === 'risk-tools' && (
                  <div className="risk-tools-container">
                    <MarketRegime
                      stockId={stock.stock_id}
                      symbol={stock.symbol}
                    />
                    <div style={{ marginTop: '20px' }}>
                      <TrailingStopCalculator
                        stockId={stock.stock_id}
                        symbol={stock.symbol}
                        currentPrice={prices.length > 0 ? prices[prices.length - 1].close : 0}
                      />
                    </div>
                    <div style={{ marginTop: '20px' }}>
                      <PortfolioHeatMonitor />
                    </div>
                  </div>
                )}
              </div>

              <div className="keyboard-hints-sbs">
                <strong>⌨️ Keyboard Shortcuts:</strong> ↑↓ = Navigate Patterns
              </div>
            </div>

            {/* RIGHT SIDE - Content Panel */}
            <div className="chart-panel-sbs">
              {/* Right Panel Content */}
              <div className="right-panel-content">
                {rightPanelTab === 'overview' && (
                  <OverviewTab
                    stock={stock}
                    recommendation={recommendation}
                    recommendationLoading={recommendationLoading}
                    recommendationError={recommendationError}
                  />
                )}

                {rightPanelTab === 'chart' && (
                  <div className="chart-only-view">
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
                      chartPatterns={visibleChartPatterns}
                      highlightedPattern={highlightedPattern}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="no-data-sbs">
            <p>No price data available for this stock.</p>
            <p>Click "Fetch Data" above to load historical prices.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default StockDetailSideBySide;
