import React, { useState, useEffect, useCallback } from 'react';
import { analyzeSentiment, getSentimentHistory, getLatestSentiment } from '../services/api';

const SentimentAnalysis = ({ stockId, symbol, onSentimentUpdated }) => {
  const [analyzing, setAnalyzing] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [latestSentiment, setLatestSentiment] = useState(null);
  const [sentimentHistory, setSentimentHistory] = useState([]);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [error, setError] = useState(null);
  const [params, setParams] = useState({
    limit_per_ticker: 50,
    threshold: 0.9
  });

  const loadLatestSentiment = useCallback(async () => {
    try {
      const data = await getLatestSentiment(stockId);
      setLatestSentiment(data);
    } catch (err) {
      console.log('No sentiment data yet');
    }
  }, [stockId]);

  const loadSentimentHistory = useCallback(async () => {
    try {
      setLoadingHistory(true);
      const data = await getSentimentHistory(stockId, 30);
      setSentimentHistory(data);
    } catch (err) {
      console.log('No sentiment history yet');
    } finally {
      setLoadingHistory(false);
    }
  }, [stockId]);

  useEffect(() => {
    loadLatestSentiment();
    loadSentimentHistory();
  }, [loadLatestSentiment, loadSentimentHistory]);

  const handleAnalyze = async () => {
    try {
      setAnalyzing(true);
      setError(null);
      setAnalysisResult(null);

      const result = await analyzeSentiment(stockId, params);
      setAnalysisResult(result);
      setLatestSentiment(result);

      // Reload history
      await loadSentimentHistory();

      // Notify parent component to update recommendation/radar chart
      if (onSentimentUpdated) {
        onSentimentUpdated();
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Sentiment analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const getSentimentColor = (index) => {
    if (index === null || index === undefined) return '#6b7280';
    if (index >= 60) return '#10b981'; // Green
    if (index >= 40) return '#f59e0b'; // Yellow
    return '#ef4444'; // Red
  };

  const getSentimentLabel = (index) => {
    if (index === null || index === undefined) return 'Unknown';
    if (index >= 70) return 'Very Bullish';
    if (index >= 60) return 'Bullish';
    if (index >= 40) return 'Neutral';
    if (index >= 30) return 'Bearish';
    return 'Very Bearish';
  };

  return (
    <div className="sentiment-analysis">
      <div className="sentiment-header">
        <h3>Sentiment Analysis for {symbol}</h3>
        <p className="sentiment-subtitle">Analyze market sentiment from news articles</p>
      </div>

      {/* Latest Sentiment Display */}
      {latestSentiment && (
        <div className="sentiment-latest">
          <h4>Latest Sentiment</h4>
          <div className="sentiment-score-card">
            <div
              className="sentiment-index-large"
              style={{ color: getSentimentColor(latestSentiment.sentiment_index) }}
            >
              {latestSentiment.sentiment_index.toFixed(0)}
            </div>
            <div className="sentiment-label">
              {getSentimentLabel(latestSentiment.sentiment_index)}
            </div>
            <div className="sentiment-date">
              {new Date(latestSentiment.timestamp).toLocaleString()}
            </div>
          </div>

          <div className="sentiment-breakdown">
            <div className="sentiment-stat">
              <div className="stat-label">Positive</div>
              <div className="stat-value" style={{ color: '#10b981' }}>
                {latestSentiment.positive_count} ({latestSentiment.positive_pct.toFixed(1)}%)
              </div>
            </div>
            <div className="sentiment-stat">
              <div className="stat-label">Neutral</div>
              <div className="stat-value" style={{ color: '#6b7280' }}>
                {latestSentiment.neutral_count} ({latestSentiment.neutral_pct.toFixed(1)}%)
              </div>
            </div>
            <div className="sentiment-stat">
              <div className="stat-label">Negative</div>
              <div className="stat-value" style={{ color: '#ef4444' }}>
                {latestSentiment.negative_count} ({latestSentiment.negative_pct.toFixed(1)}%)
              </div>
            </div>
          </div>

          <div className="sentiment-info">
            <p><strong>Total Articles:</strong> {latestSentiment.total_articles}</p>
            <p><strong>Trend:</strong> {latestSentiment.trend}</p>
          </div>
        </div>
      )}

      {/* Analysis Parameters */}
      <div className="sentiment-params">
        <h4>Analysis Parameters</h4>
        <div className="param-group">
          <label>
            Articles to Fetch:
            <input
              type="number"
              value={params.limit_per_ticker}
              onChange={(e) => setParams({...params, limit_per_ticker: parseInt(e.target.value)})}
              min="10"
              max="200"
            />
          </label>
        </div>
        <div className="param-group">
          <label>
            Confidence Threshold:
            <input
              type="number"
              value={params.threshold}
              onChange={(e) => setParams({...params, threshold: parseFloat(e.target.value)})}
              min="0.5"
              max="1.0"
              step="0.05"
            />
          </label>
        </div>
      </div>

      {/* Analyze Button */}
      <button
        onClick={handleAnalyze}
        disabled={analyzing}
        className="analyze-sentiment-btn"
      >
        {analyzing ? 'Analyzing...' : 'Analyze Sentiment'}
      </button>

      {error && (
        <div className="sentiment-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Analysis Results */}
      {analysisResult && analysisResult.news && (
        <div className="sentiment-news">
          <h4>Recent News Articles ({analysisResult.news.length})</h4>
          <div className="news-list">
            {analysisResult.news.map((article, idx) => (
              <div key={idx} className="news-article">
                <div className="news-header">
                  <span
                    className="news-sentiment"
                    style={{
                      color: article.sentiment === 'positive' ? '#10b981' :
                             article.sentiment === 'negative' ? '#ef4444' : '#6b7280'
                    }}
                  >
                    {article.sentiment === 'positive' ? '📈' :
                     article.sentiment === 'negative' ? '📉' : '📊'}
                    {article.sentiment}
                  </span>
                  <span className="news-confidence">
                    {(article.confidence * 100).toFixed(0)}% confident
                  </span>
                </div>
                <h5 className="news-title">
                  <a href={article.url} target="_blank" rel="noopener noreferrer">
                    {article.title}
                  </a>
                </h5>
                <div className="news-meta">
                  <span>{article.source}</span>
                  <span>{new Date(article.published_at).toLocaleDateString()}</span>
                </div>
                {article.summary && (
                  <p className="news-summary">{article.summary}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sentiment History */}
      {loadingHistory ? (
        <div className="sentiment-history">
          <h4>Sentiment History</h4>
          <div className="loading-sbs">Loading history...</div>
        </div>
      ) : sentimentHistory.length > 0 && (
        <div className="sentiment-history">
          <h4>Sentiment History</h4>
          <div className="history-list">
            {sentimentHistory.map((item, idx) => (
              <div key={idx} className="history-item">
                <div className="history-date">
                  {new Date(item.timestamp).toLocaleDateString()}
                </div>
                <div
                  className="history-index"
                  style={{ color: getSentimentColor(item.sentiment_index) }}
                >
                  {item.sentiment_index.toFixed(0)}
                </div>
                <div className="history-breakdown">
                  <span style={{ color: '#10b981' }}>
                    +{item.positive_count}
                  </span>
                  <span style={{ color: '#6b7280' }}>
                    ={item.neutral_count}
                  </span>
                  <span style={{ color: '#ef4444' }}>
                    -{item.negative_count}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <style jsx>{`
        .sentiment-analysis {
          padding: 20px;
        }

        .sentiment-header {
          margin-bottom: 24px;
        }

        .sentiment-header h3 {
          margin: 0 0 8px 0;
          font-size: 20px;
          color: #111827;
        }

        .sentiment-subtitle {
          margin: 0;
          color: #6b7280;
          font-size: 14px;
        }

        .sentiment-latest {
          background: #f9fafb;
          border-radius: 12px;
          padding: 20px;
          margin-bottom: 24px;
        }

        .sentiment-latest h4 {
          margin: 0 0 16px 0;
          font-size: 16px;
          color: #374151;
        }

        .sentiment-score-card {
          text-align: center;
          margin-bottom: 20px;
        }

        .sentiment-index-large {
          font-size: 64px;
          font-weight: 800;
          line-height: 1;
        }

        .sentiment-label {
          font-size: 18px;
          font-weight: 600;
          color: #374151;
          margin-top: 8px;
        }

        .sentiment-date {
          font-size: 12px;
          color: #9ca3af;
          margin-top: 4px;
        }

        .sentiment-breakdown {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 16px;
          margin-bottom: 16px;
        }

        .sentiment-stat {
          text-align: center;
          padding: 12px;
          background: white;
          border-radius: 8px;
        }

        .stat-label {
          font-size: 12px;
          color: #6b7280;
          margin-bottom: 4px;
        }

        .stat-value {
          font-size: 18px;
          font-weight: 700;
        }

        .sentiment-info {
          padding-top: 16px;
          border-top: 1px solid #e5e7eb;
        }

        .sentiment-info p {
          margin: 4px 0;
          font-size: 14px;
          color: #374151;
        }

        .sentiment-params {
          background: #f9fafb;
          border-radius: 12px;
          padding: 20px;
          margin-bottom: 16px;
        }

        .sentiment-params h4 {
          margin: 0 0 16px 0;
          font-size: 16px;
          color: #374151;
        }

        .param-group {
          margin-bottom: 12px;
        }

        .param-group label {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 14px;
          color: #374151;
        }

        .param-group input {
          width: 100px;
          padding: 6px 12px;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          font-size: 14px;
        }

        .analyze-sentiment-btn {
          width: 100%;
          padding: 12px;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          border: none;
          border-radius: 8px;
          font-size: 16px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          margin-bottom: 16px;
        }

        .analyze-sentiment-btn:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }

        .analyze-sentiment-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .sentiment-error {
          background: #fee2e2;
          border: 1px solid #fecaca;
          color: #dc2626;
          padding: 12px;
          border-radius: 8px;
          margin-bottom: 16px;
          font-size: 14px;
        }

        .sentiment-news {
          margin-top: 24px;
        }

        .sentiment-news h4 {
          margin: 0 0 16px 0;
          font-size: 18px;
          color: #111827;
        }

        .news-list {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .news-article {
          background: #f9fafb;
          border-radius: 12px;
          padding: 16px;
          border: 1px solid #e5e7eb;
        }

        .news-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }

        .news-sentiment {
          font-size: 14px;
          font-weight: 600;
          text-transform: capitalize;
        }

        .news-confidence {
          font-size: 12px;
          color: #6b7280;
        }

        .news-title {
          margin: 0 0 8px 0;
          font-size: 16px;
        }

        .news-title a {
          color: #111827;
          text-decoration: none;
        }

        .news-title a:hover {
          color: #667eea;
          text-decoration: underline;
        }

        .news-meta {
          display: flex;
          gap: 12px;
          font-size: 12px;
          color: #9ca3af;
          margin-bottom: 8px;
        }

        .news-summary {
          font-size: 14px;
          color: #374151;
          margin: 8px 0 0 0;
          line-height: 1.5;
        }

        .sentiment-history {
          margin-top: 24px;
        }

        .sentiment-history h4 {
          margin: 0 0 16px 0;
          font-size: 18px;
          color: #111827;
        }

        .history-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-height: 300px;
          overflow-y: auto;
        }

        .history-item {
          display: grid;
          grid-template-columns: 120px 80px 1fr;
          align-items: center;
          padding: 12px;
          background: #f9fafb;
          border-radius: 8px;
          border: 1px solid #e5e7eb;
        }

        .history-date {
          font-size: 14px;
          color: #374151;
        }

        .history-index {
          font-size: 24px;
          font-weight: 700;
          text-align: center;
        }

        .history-breakdown {
          display: flex;
          gap: 12px;
          justify-content: flex-end;
          font-size: 14px;
          font-weight: 600;
        }
      `}</style>
    </div>
  );
};

export default SentimentAnalysis;
