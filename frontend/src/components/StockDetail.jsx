import React, { useState, useEffect, useCallback } from 'react';
import StockChart from './StockChart';
import TechnicalAnalysis from './TechnicalAnalysis';
import SignalRadar from './SignalRadar';
import { fetchStockData, getStockPrices, getRecommendation, analyzeSentiment } from '../services/api';

const StockDetail = ({ stock, onClose }) => {
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
  const [sentimentData, setSentimentData] = useState(null);
  const [sentimentLoading, setSentimentLoading] = useState(false);
  const [sentimentError, setSentimentError] = useState(null);

  const loadPrices = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getStockPrices(stock.id, 365);
      setPrices(data.prices);
    } catch (err) {
      setError('Failed to load price data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [stock.id]);

  const loadRecommendation = useCallback(async () => {
    try {
      setRecommendationLoading(true);
      setRecommendationError(null);
      const data = await getRecommendation(stock.id);
      console.log('Recommendation data loaded:', data);
      setRecommendation(data);
    } catch (err) {
      console.error('Failed to load recommendation:', err);
      setRecommendationError(err.response?.data?.detail || err.message || 'Failed to load recommendation');
    } finally {
      setRecommendationLoading(false);
    }
  }, [stock.id]);

  useEffect(() => {
    loadPrices();
    loadRecommendation();
  }, [loadPrices, loadRecommendation]);

  const handleFetchData = async () => {
    try {
      setFetching(true);
      setError(null);
      setFetchResult(null);

      const result = await fetchStockData(stock.id, period, interval);
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
      const data = await analyzeSentiment(stock.id);
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
          <button onClick={onClose} className="close-btn">×</button>
        </div>

        <div className="stock-detail-body">
          <div className="fetch-controls">
            <h3>Fetch Stock Data</h3>
            <div className="controls-row">
              <div className="control-group">
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

              <div className="control-group">
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

              <button
                onClick={handleFetchData}
                disabled={fetching}
                className="fetch-btn"
              >
                {fetching ? 'Fetching...' : 'Fetch Data'}
              </button>
            </div>

            {fetchResult && (
              <div className={`fetch-result ${fetchResult.success ? 'success' : 'error'}`}>
                <p>{fetchResult.message}</p>
                {fetchResult.success && (
                  <p className="fetch-stats">
                    Fetched: {fetchResult.records_fetched} |
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
              <StockChart prices={prices} symbol={stock.symbol} />

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

              <TechnicalAnalysis stockId={stock.id} symbol={stock.symbol} />

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
    </div>
  );
};

export default StockDetail;
