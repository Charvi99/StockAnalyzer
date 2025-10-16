import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const TechnicalAnalysis = ({ stockId, symbol }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${API_URL}/api/v1/stocks/${stockId}/analyze`, {
        period: '3mo',
        rsi_period: 14,
        macd_fast: 12,
        macd_slow: 26,
        macd_signal: 9,
        bb_window: 20,
        bb_std: 2.0,
        ma_short: 20,
        ma_long: 50
      });

      setAnalysis(response.data);
    } catch (err) {
      console.error('Error fetching analysis:', err);
      setError(err.response?.data?.detail || 'Failed to fetch analysis');
    } finally {
      setLoading(false);
    }
  }, [stockId]);

  // Auto-load analysis on mount
  useEffect(() => {
    fetchAnalysis();
  }, [fetchAnalysis]);

  const getRecommendationColor = (rec) => {
    switch (rec) {
      case 'BUY': return '#28a745';
      case 'SELL': return '#dc3545';
      case 'HOLD': return '#ffc107';
      default: return '#6c757d';
    }
  };

  const getSignalIcon = (signal) => {
    switch (signal) {
      case 'BUY': return '📈';
      case 'SELL': return '📉';
      case 'HOLD': return '⏸️';
      default: return '❓';
    }
  };

  const renderIndicator = (name, data) => {
    if (!data) return null;

    const safeToFixed = (value, decimals) => {
      return (value !== null && value !== undefined) ? value.toFixed(decimals) : 'N/A';
    };

    return (
      <div key={name} className="indicator-card">
        <h4>{name.replace(/_/g, ' ')}</h4>
        <div className="indicator-details">
          {data.value !== undefined && data.value !== null && (
            <p><strong>Value:</strong> {safeToFixed(data.value, 2)}</p>
          )}
          {data.upper !== null && data.upper !== undefined && (
            <>
              <p><strong>Upper Band:</strong> ${safeToFixed(data.upper, 2)}</p>
              <p><strong>Middle Band:</strong> ${safeToFixed(data.middle, 2)}</p>
              <p><strong>Lower Band:</strong> ${safeToFixed(data.lower, 2)}</p>
            </>
          )}
          {data.macd !== undefined && data.macd !== null && (
            <>
              <p><strong>MACD:</strong> {safeToFixed(data.macd, 4)}</p>
              <p><strong>Signal:</strong> {safeToFixed(data.signal_line, 4)}</p>
              <p><strong>Histogram:</strong> {safeToFixed(data.histogram, 4)}</p>
            </>
          )}
          {data.ma_short !== null && data.ma_short !== undefined && (
            <>
              <p><strong>Short MA:</strong> ${safeToFixed(data.ma_short, 2)}</p>
              <p><strong>Long MA:</strong> ${safeToFixed(data.ma_long, 2)}</p>
            </>
          )}
          {data.signal && (
            <div className="signal-badge" style={{ backgroundColor: getRecommendationColor(data.signal) }}>
              {getSignalIcon(data.signal)} {data.signal}
            </div>
          )}
          {data.reason && <p className="indicator-reason">{data.reason}</p>}
        </div>
      </div>
    );
  };

  return (
    <div className="technical-analysis">
      <div className="analysis-header">
        <h3>📊 Technical Analysis</h3>
        <button onClick={fetchAnalysis} disabled={loading} className="btn-analyze">
          {loading ? 'Refreshing...' : 'Refresh Analysis'}
        </button>
      </div>

      {error && <div className="error-message">❌ {error}</div>}

      {loading && !analysis && (
        <div className="loading-message">
          🔄 Loading technical analysis...
        </div>
      )}

      {analysis && (
        <div className="analysis-results">
          {/* Overall Recommendation */}
          <div className="recommendation-card">
            <h3>Overall Recommendation</h3>
            <div
              className="recommendation-badge large"
              style={{ backgroundColor: getRecommendationColor(analysis.recommendation) }}
            >
              {getSignalIcon(analysis.recommendation)} <strong>{analysis.recommendation}</strong>
            </div>
            <div className="confidence-meter">
              <div className="confidence-label">Confidence: {(analysis.confidence * 100).toFixed(0)}%</div>
              <div className="confidence-bar">
                <div
                  className="confidence-fill"
                  style={{
                    width: `${analysis.confidence * 100}%`,
                    backgroundColor: getRecommendationColor(analysis.recommendation)
                  }}
                />
              </div>
            </div>
            <p className="recommendation-reason">{analysis.reason}</p>
            <div className="signal-summary">
              <span className="signal-count buy">📈 Buy: {analysis.signal_counts.buy}</span>
              <span className="signal-count sell">📉 Sell: {analysis.signal_counts.sell}</span>
              <span className="signal-count hold">⏸️ Hold: {analysis.signal_counts.hold}</span>
            </div>
          </div>

          {/* Current Price Info */}
          <div className="price-info">
            <h4>{symbol}</h4>
            <p className="current-price">${analysis.current_price.toFixed(2)}</p>
            <p className="timestamp">
              {new Date(analysis.timestamp).toLocaleString()}
            </p>
          </div>

          {/* Individual Indicators */}
          <div className="indicators-grid">
            {Object.entries(analysis.indicators || {}).map(([name, data]) =>
              renderIndicator(name, data)
            )}
          </div>
        </div>
      )}

      <style jsx>{`
        .technical-analysis {
          margin: 20px 0;
        }

        .analysis-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
        }

        .btn-analyze {
          background: #007bff;
          color: white;
          border: none;
          padding: 10px 20px;
          border-radius: 5px;
          cursor: pointer;
          font-size: 14px;
          transition: background 0.3s;
        }

        .btn-analyze:hover:not(:disabled) {
          background: #0056b3;
        }

        .btn-analyze:disabled {
          background: #6c757d;
          cursor: not-allowed;
        }

        .error-message {
          background: #f8d7da;
          color: #721c24;
          padding: 12px;
          border-radius: 5px;
          margin: 10px 0;
        }

        .loading-message {
          background: #e7f3ff;
          color: #004085;
          padding: 20px;
          border-radius: 8px;
          text-align: center;
          margin: 20px 0;
          font-size: 16px;
        }

        .analysis-results {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .recommendation-card {
          background: white;
          border: 2px solid #ddd;
          border-radius: 8px;
          padding: 20px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .recommendation-badge {
          display: inline-block;
          padding: 15px 30px;
          color: white;
          border-radius: 8px;
          font-size: 24px;
          margin: 15px 0;
          font-weight: bold;
        }

        .confidence-meter {
          margin: 15px 0;
        }

        .confidence-label {
          font-size: 14px;
          margin-bottom: 5px;
          color: #666;
        }

        .confidence-bar {
          width: 100%;
          height: 20px;
          background: #e9ecef;
          border-radius: 10px;
          overflow: hidden;
        }

        .confidence-fill {
          height: 100%;
          transition: width 0.3s ease;
        }

        .recommendation-reason {
          margin: 15px 0;
          font-size: 16px;
          color: #333;
        }

        .signal-summary {
          display: flex;
          gap: 15px;
          margin-top: 15px;
        }

        .signal-count {
          padding: 8px 12px;
          border-radius: 5px;
          font-size: 14px;
          font-weight: 500;
        }

        .signal-count.buy {
          background: #d4edda;
          color: #155724;
        }

        .signal-count.sell {
          background: #f8d7da;
          color: #721c24;
        }

        .signal-count.hold {
          background: #fff3cd;
          color: #856404;
        }

        .price-info {
          background: #f8f9fa;
          border-radius: 8px;
          padding: 15px;
          text-align: center;
        }

        .price-info h4 {
          margin: 0 0 10px 0;
          color: #666;
        }

        .current-price {
          font-size: 32px;
          font-weight: bold;
          color: #007bff;
          margin: 10px 0;
        }

        .timestamp {
          font-size: 12px;
          color: #999;
          margin: 5px 0 0 0;
        }

        .indicators-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 15px;
        }

        .indicator-card {
          background: white;
          border: 1px solid #ddd;
          border-radius: 8px;
          padding: 15px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .indicator-card h4 {
          margin: 0 0 15px 0;
          color: #333;
          text-transform: capitalize;
          font-size: 16px;
          border-bottom: 2px solid #007bff;
          padding-bottom: 8px;
        }

        .indicator-details p {
          margin: 8px 0;
          font-size: 14px;
          color: #555;
        }

        .signal-badge {
          display: inline-block;
          padding: 8px 16px;
          color: white;
          border-radius: 5px;
          font-size: 14px;
          margin: 10px 0;
          font-weight: 600;
        }

        .indicator-reason {
          font-style: italic;
          color: #666;
          margin-top: 10px !important;
          font-size: 13px !important;
        }
      `}</style>
    </div>
  );
};

export default TechnicalAnalysis;
