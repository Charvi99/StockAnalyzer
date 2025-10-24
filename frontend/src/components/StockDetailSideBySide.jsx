import React, { useState, useEffect, useCallback, useRef } from 'react';
import StockChart from './StockChart';
import TechnicalAnalysis from './TechnicalAnalysis';
import CandlestickPatterns from './CandlestickPatterns';
import ChartPatterns from './ChartPatterns';
import TradingStrategies from './TradingStrategies';
import SentimentAnalysis from './SentimentAnalysis';
import OverviewTab from './OverviewTab';
import { fetchStockData, getStockPrices, getRecommendation } from '../services/api';
import './StockDetailSideBySide.css';

const StockDetailSideBySide = ({ stock, onClose }) => {
  const [prices, setPrices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState(null);
  const [fetchResult, setFetchResult] = useState(null);
  const [period, setPeriod] = useState('1y');
  const [interval, setInterval] = useState('1d');
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
      // Load 10 years of data (3650 days) to ensure we get all available historical data
      const data = await getStockPrices(stock.stock_id, 3650);
      setPrices(data.prices);
    } catch (err) {
      setError('Failed to load price data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [stock.stock_id]);

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

      const result = await fetchStockData(stock.stock_id, period, interval);
      setFetchResult(result);

      if (result.success) {
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
          <button onClick={onClose} className="close-btn-sbs">×</button>
        </div>

        <div className="fetch-controls-sbs">
          {/* Left Section - Fetch Data Controls */}
          <div className="controls-left-section">
            <div className="control-group-sbs">
              <label>Period:</label>
              <select value={period} onChange={(e) => setPeriod(e.target.value)}>
                <option value="1d">1 Day</option>
                <option value="5d">5 Days</option>
                <option value="1mo">1 Month</option>
                <option value="3mo">3 Months</option>
                <option value="6mo">6 Months</option>
                <option value="1y">1 Year</option>
                <option value="2y">2 Years</option>
                <option value="5y">5 Years</option>
                <option value="max">Max</option>
              </select>
            </div>

            <div className="control-group-sbs">
              <label>Interval:</label>
              <select value={interval} onChange={(e) => setInterval(e.target.value)}>
                <option value="1m">1 Minute</option>
                <option value="5m">5 Minutes</option>
                <option value="15m">15 Minutes</option>
                <option value="1h">1 Hour</option>
                <option value="1d">1 Day</option>
                <option value="1wk">1 Week</option>
                <option value="1mo">1 Month</option>
              </select>
            </div>

            <button onClick={handleFetchData} disabled={fetching} className="fetch-btn-sbs">
              {fetching ? 'Fetching...' : 'Fetch Data'}
            </button>

            {fetchResult && (
              <div className={`fetch-result-sbs ${fetchResult.success ? 'success' : 'error'}`}>
                <span>{fetchResult.message}</span>
                {fetchResult.success && (
                  <span className="fetch-stats-sbs">
                    {' '}| Fetched: {fetchResult.records_fetched} | Saved: {fetchResult.records_saved} new
                  </span>
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
              </div>

              <div className="keyboard-hints-sbs">
                <strong>⌨️ Keyboard Shortcuts:</strong> Y/C = Confirm | N/R = Reject | Delete/X = Remove | ↑↓ = Navigate
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
