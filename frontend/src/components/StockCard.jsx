import React, { useState } from 'react';
import { fetchStockData, getDashboardAnalysis } from '../services/api';

// Sector colors and icons
const SECTOR_CONFIG = {
  'Technology': { color: '#667eea', icon: '💻', bgLight: '#eef2ff' },
  'Healthcare': { color: '#059669', icon: '⚕️', bgLight: '#d1fae5' },
  'Financial': { color: '#2563eb', icon: '💰', bgLight: '#dbeafe' },
  'Consumer Goods': { color: '#ea580c', icon: '🛍️', bgLight: '#ffedd5' },
  'Energy': { color: '#ca8a04', icon: '⚡', bgLight: '#fef9c3' },
  'Industrials': { color: '#78716c', icon: '🏭', bgLight: '#f5f5f4' },
  'Retail': { color: '#dc2626', icon: '🏪', bgLight: '#fee2e2' },
  'Real Estate': { color: '#0891b2', icon: '🏢', bgLight: '#cffafe' },
  'Materials': { color: '#a16207', icon: '⛏️', bgLight: '#fef3c7' },
  'Entertainment': { color: '#c026d3', icon: '🎬', bgLight: '#fae8ff' },
  'Consumer Services': { color: '#f97316', icon: '🔔', bgLight: '#fed7aa' },
  'Automotive': { color: '#0d9488', icon: '🚗', bgLight: '#ccfbf1' },
  'Telecommunications': { color: '#4f46e5', icon: '📡', bgLight: '#e0e7ff' },
  'Utilities': { color: '#0369a1', icon: '💡', bgLight: '#e0f2fe' },
  'Transportation': { color: '#7c2d12', icon: '✈️', bgLight: '#fed7aa' },
  'Leisure': { color: '#be185d', icon: '🎨', bgLight: '#fce7f3' },
  'Aerospace': { color: '#1e40af', icon: '🚀', bgLight: '#dbeafe' },
  'Consumer Cyclical': { color: '#ea580c', icon: '🔄', bgLight: '#ffedd5' },
};

const getSectorConfig = (sector) => {
  return SECTOR_CONFIG[sector] || { color: '#6b7280', icon: '📊', bgLight: '#f3f4f6' };
};

const StockCard = ({ stock, onViewDetails, onUntrack, onAnalysisComplete }) => {
  const [isFetchingData, setIsFetchingData] = useState(false);
  const sectorConfig = getSectorConfig(stock.sector);

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
      {/* Colored top border for sector indication */}
      <div className="sector-indicator" style={{ background: sectorConfig.color }}></div>

      <div className="stock-card-header">
        <div className="title-section">
          <div className="symbol-row">
            <span className="sector-icon">{sectorConfig.icon}</span>
            <h3>{stock.symbol}</h3>
          </div>
          <p className="company-name">{stock.name || 'N/A'}</p>
        </div>
        <div className="stock-meta">
          <span
            className="sector-badge"
            style={{
              background: sectorConfig.bgLight,
              color: sectorConfig.color,
              borderColor: sectorConfig.color
            }}
          >
            {stock.sector || 'N/A'}
          </span>
          {stock.industry && (
            <span className="industry-badge">
              {stock.industry}
            </span>
          )}
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
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
          transition: all 0.3s;
          overflow: hidden;
          position: relative;
        }

        .stock-card:hover {
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
          transform: translateY(-2px);
        }

        .sector-indicator {
          height: 4px;
          width: 100%;
        }

        .stock-card-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          padding: 20px;
          padding-bottom: 16px;
          border-bottom: 1px solid #e5e7eb;
        }

        .title-section {
          flex: 1;
          min-width: 0;
        }

        .symbol-row {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 4px;
        }

        .sector-icon {
          font-size: 20px;
        }

        .stock-card-header h3 {
          margin: 0;
          font-size: 24px;
          font-weight: 700;
          color: #111827;
        }

        .company-name {
          margin: 0;
          font-size: 13px;
          color: #6b7280;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .stock-meta {
          display: flex;
          flex-direction: column;
          gap: 6px;
          align-items: flex-end;
          margin-left: 12px;
        }

        .sector-badge {
          font-size: 11px;
          font-weight: 600;
          padding: 4px 10px;
          border-radius: 12px;
          border: 1px solid;
          white-space: nowrap;
        }

        .industry-badge {
          font-size: 10px;
          background: #f9fafb;
          padding: 3px 8px;
          border-radius: 8px;
          color: #6b7280;
          white-space: nowrap;
          max-width: 120px;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .error-section {
          padding: 24px 20px;
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

        .loading-section {
          padding: 24px 20px;
          text-align: center;
        }

        .status-text {
          color: #6b7280;
          font-size: 14px;
        }

        .analysis-section {
          padding: 20px;
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
