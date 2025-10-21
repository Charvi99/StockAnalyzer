import React, { useState } from 'react';
import { fetchStockData, getDashboardAnalysis } from '../services/api';

const StockCard = ({ stock, onViewDetails, onUntrack, onAnalysisComplete }) => {
  const [isFetchingData, setIsFetchingData] = useState(false);

  const handleFetchData = async () => {
    try {
      setIsFetchingData(true);
      await fetchStockData(stock.stock_id, '1y', '1d');
      onAnalysisComplete(); // This will trigger a refresh of the dashboard data
    } catch (err) {
      console.error('Fetch data error:', err);
    } finally {
      setIsFetchingData(false);
    }
  };

  const getRecommendationColor = (recommendation) => {
    if (!recommendation) return '#6b7280';
    switch (recommendation) {
      case 'BUY':
        return '#10b981';
      case 'SELL':
        return '#ef4444';
      case 'HOLD':
        return '#f59e0b';
      default:
        return '#6b7280';
    }
  };

  return (
    <div className="stock-card">
      <div className="stock-card-header">
        <div>
          <h3>{stock.symbol}</h3>
        </div>
        <div className="stock-meta">
          <span className="sector">{stock.sector || 'N/A'}</span>
        </div>
      </div>

      {stock.error ? (
        <div className="error-section">
          <p className="error-text">⚠️ {stock.error}</p>
          {stock.error.includes('Insufficient price data') ? (
            <button onClick={handleFetchData} className="retry-btn" disabled={isFetchingData}>
              {isFetchingData ? 'Fetching...' : 'Fetch Data'}
            </button>
          ) : (
            <button onClick={onAnalysisComplete} className="retry-btn">
              Retry Analysis
            </button>
          )}
        </div>
      ) : stock.final_recommendation ? (
        <div className="analysis-section">
          <div
            className="recommendation-badge"
            style={{
              background: getRecommendationColor(stock.final_recommendation) + '20',
              borderColor: getRecommendationColor(stock.final_recommendation)
            }}
          >
            <div className="recommendation-label">RECOMMENDATION</div>
            <div
              className="recommendation-value"
              style={{ color: getRecommendationColor(stock.final_recommendation) }}
            >
              {stock.final_recommendation}
            </div>
            <div className="confidence-label">
              {(stock.overall_confidence * 100).toFixed(0)}% confidence
            </div>
          </div>

          <div className="signals-grid">
            <div className="signal-item">
              <div className="signal-label">Technical</div>
              <div
                className="signal-value"
                style={{ color: getRecommendationColor(stock.technical_recommendation) }}
              >
                {stock.technical_recommendation}
              </div>
            </div>
            <div className="signal-item">
              <div className="signal-label">ML Model</div>
              <div
                className="signal-value"
                style={{ color: getRecommendationColor(stock.ml_recommendation) }}
              >
                {stock.ml_recommendation || 'N/A'}
              </div>
            </div>
            <div className="signal-item">
              <div className="signal-label">Sentiment</div>
              <div className="signal-value">
                {stock.sentiment_index !== null
                  ? stock.sentiment_index.toFixed(0)
                  : 'N/A'
                }
              </div>
            </div>
            <div className="signal-item">
              <div className="signal-label">Price</div>
              <div className="signal-value">
                ${stock.current_price?.toFixed(2) || 'N/A'}
              </div>
            </div>
          </div>

          <div className="card-actions">
            <button onClick={() => onViewDetails(stock)} className="view-details-btn">
              View Details
            </button>
            <button onClick={() => onUntrack(stock.stock_id)} className="untrack-btn-small">
              Untrack
            </button>
          </div>
        </div>
      ) : (
        <div className="loading-section">
          <p className="status-text">Analysis data not available.</p>
        </div>
      )}

      <style jsx>{`
        .stock-card {
          background: white;
          border-radius: 12px;
          padding: 20px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
          transition: all 0.3s;
        }

        .stock-card:hover {
          box-shadow: 0 44px 16px rgba(0, 0, 0, 0.15);
          transform: translateY(-2px);
        }

        .stock-card-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 16px;
          padding-bottom: 12px;
          border-bottom: 1px solid #e5e7eb;
        }

        .stock-card-header h3 {
          margin: 0;
          font-size: 24px;
          font-weight: 700;
          color: #111827;
        }

        .stock-name {
          margin: 4px 0 0 0;
          font-size: 13px;
          color: #6b7280;
        }

        .stock-meta {
          display: flex;
          flex-direction: column;
          gap: 6px;
          align-items: flex-end;
        }

        .sector {
          font-size: 11px;
          background: #f3f4f6;
          padding: 4px 8px;
          border-radius: 4px;
          color: #374151;
        }

        .error-section {
          padding: 24px 0;
          text-align: center;
        }

        .error-text {
          color: #dc2626;
          font-size: 14px;
          margin-bottom: 12px;
        }

        .retry-btn {
          background: #667eea;
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 6px;
          cursor: pointer;
          font-size: 13px;
        }

        .retry-btn:hover {
          background: #5568d3;
        }

        .analysis-section {
          padding: 12px 0;
        }

        .recommendation-badge {
          border: 2px solid;
          border-radius: 12px;
          padding: 16px;
          text-align: center;
          margin-bottom: 16px;
        }

        .recommendation-label {
          font-size: 11px;
          font-weight: 600;
          letter-spacing: 0.5px;
          color: #6b7280;
          margin-bottom: 8px;
        }

        .recommendation-value {
          font-size: 32px;
          font-weight: 800;
          margin-bottom: 4px;
        }

        .confidence-label {
          font-size: 12px;
          color: #6b7280;
        }

        .signals-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
          margin-bottom: 16px;
        }

        .signal-item {
          background: #f9fafb;
          padding: 12px;
          border-radius: 8px;
        }

        .signal-label {
          font-size: 11px;
          color: #6b7280;
          margin-bottom: 4px;
          font-weight: 500;
        }

        .signal-value {
          font-size: 16px;
          font-weight: 700;
          color: #111827;
        }

        .card-actions {
          display: flex;
          gap: 8px;
        }

        .view-details-btn {
          flex: 1;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          border: none;
          padding: 10px;
          border-radius: 8px;
          font-weight: 600;
          cursor: pointer;
          font-size: 14px;
          transition: all 0.2s;
        }

        .view-details-btn:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }

        .untrack-btn-small {
          background: #fef2f2;
          color: #dc2626;
          border: 1px solid #fecaca;
          padding: 10px 16px;
          border-radius: 8px;
          font-weight: 600;
          cursor: pointer;
          font-size: 14px;
          transition: all 0.2s;
        }

        .untrack-btn-small:hover {
          background: #fee2e2;
        }
      `}</style>
    </div>
  );
};

export default StockCard;
