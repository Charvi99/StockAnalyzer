import React, { useState } from 'react';
import { fetchStockData } from '../services/api';
import FetchCountdown from './FetchCountdown';

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

// Priority configuration
const PRIORITY_CONFIG = {
  'high': {
    color: '#dc2626',
    bgLight: '#fee2e2',
    icon: '🔥',
    label: 'High Priority',
    description: 'Updated hourly'
  },
  'medium': {
    color: '#f59e0b',
    bgLight: '#fef3c7',
    icon: '⚡',
    label: 'Medium Priority',
    description: 'Updated every 4h'
  },
  'low': {
    color: '#6b7280',
    bgLight: '#f3f4f6',
    icon: '📊',
    label: 'Low Priority',
    description: 'Updated daily'
  },
};

const getPriorityConfig = (priority) => {
  return PRIORITY_CONFIG[priority] || PRIORITY_CONFIG['medium'];
};

const StockCard = ({ stock, onViewDetails, onUntrack, onAnalysisComplete, isAnalyzing }) => {
  const [isFetchingData, setIsFetchingData] = useState(false);
  const sectorConfig = getSectorConfig(stock.sector);
  const priorityConfig = getPriorityConfig(stock.priority);

  // Calculate completeness score (0-100)
  const completenessScore = stock.analysis_score !== undefined
    ? Math.round(stock.analysis_score * 100)
    : 0;

  const handleFetchData = async () => {
    try {
      setIsFetchingData(true);
      // Fetch 1 month of 1-hour data for swing trading
      await fetchStockData(stock.stock_id, '1mo', '1h');
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

  // Helper function to get signal badge styling
  const getSignalBadgeStyle = (signalType) => {
    switch (signalType) {
      case 'dividend_exit':
        return {
          borderColor: '#ef4444',
          background: '#fee2e2',
          color: '#dc2626',
          icon: '💰'
        };
      case 'dividend_entry':
        return {
          borderColor: '#10b981',
          background: '#d1fae5',
          color: '#059669',
          icon: '💰'
        };
      case 'split_entry':
        return {
          borderColor: '#3b82f6',
          background: '#dbeafe',
          color: '#1d4ed8',
          icon: '✂️'
        };
      case 'split_exit':
        return {
          borderColor: '#ef4444',
          background: '#fee2e2',
          color: '#dc2626',
          icon: '✂️'
        };
      case 'split_reentry':
        return {
          borderColor: '#10b981',
          background: '#d1fae5',
          color: '#059669',
          icon: '✂️'
        };
      default:
        return {
          borderColor: '#6b7280',
          background: '#f3f4f6',
          color: '#6b7280',
          icon: '📊'
        };
    }
  };

  return (
    <div className={`stock-card ${isAnalyzing ? 'analyzing' : ''}`}>
      {/* Loading overlay for progressive loading */}
      {stock._loading && (
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <div className="loading-text">Loading analysis...</div>
        </div>
      )}

      {/* Analyzing indicator - pulsing badge */}
      {isAnalyzing && (
        <div className="analyzing-badge">
          <div className="analyzing-spinner"></div>
          <span>Analyzing...</span>
        </div>
      )}

      {/* Colored top border for sector indication */}
      <div className="sector-indicator" style={{ background: sectorConfig.color }}></div>

      {/* Fetch countdown timer (top-right corner) */}
      {stock.next_fetch_at && (
        <FetchCountdown
          nextFetchAt={stock.next_fetch_at}
          lastFetchAt={stock.last_fetch_at}
          compact={true}
        />
      )}

      <div className="stock-card-header">
        <div className="title-section">
          <div className="symbol-row">
            <span className="sector-icon">{sectorConfig.icon}</span>
            <h3>{stock.symbol}</h3>
          </div>
          <p className="company-name">{stock.name || 'N/A'}</p>
        </div>
        <div className="stock-meta">
          {/* Completeness Score Badge */}
          <span
            className="completeness-badge"
            style={{
              background: completenessScore >= 80 ? '#d1fae5' : completenessScore >= 50 ? '#fef3c7' : '#fee2e2',
              color: completenessScore >= 80 ? '#059669' : completenessScore >= 50 ? '#d97706' : '#dc2626',
              borderColor: completenessScore >= 80 ? '#10b981' : completenessScore >= 50 ? '#f59e0b' : '#ef4444'
            }}
            title={`Analysis completeness: ${completenessScore}%`}
          >
            {completenessScore >= 80 ? '✓' : completenessScore >= 50 ? '⚠' : '✗'} {completenessScore}%
          </span>
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
          {stock.priority && (
            <span
              className="priority-badge"
              style={{
                background: priorityConfig.bgLight,
                color: priorityConfig.color,
                borderColor: priorityConfig.color
              }}
              title={`${priorityConfig.label} - ${priorityConfig.description}`}
            >
              {priorityConfig.icon} {stock.priority}
            </span>
          )}
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
          {/* Dividend/Split Signal Badge - Prominent Display */}
          {stock.dividend_split_signal && (
            <div
              className="dividend-split-badge"
              style={{
                borderColor: getSignalBadgeStyle(stock.dividend_split_signal.signal_type).borderColor,
                background: getSignalBadgeStyle(stock.dividend_split_signal.signal_type).background,
                color: getSignalBadgeStyle(stock.dividend_split_signal.signal_type).color
              }}
              title={stock.dividend_split_signal.reasoning}
            >
              <div className="signal-header">
                <span className="signal-icon">
                  {getSignalBadgeStyle(stock.dividend_split_signal.signal_type).icon}
                </span>
                <span className="signal-title">
                  {stock.dividend_split_signal.signal_type.includes('dividend') ? 'DIVIDEND' : 'SPLIT'} SIGNAL
                </span>
              </div>
              <div className="signal-body">
                <div className="signal-days">
                  {stock.dividend_split_signal.days_until >= 0
                    ? `${stock.dividend_split_signal.days_until} days until event`
                    : `${Math.abs(stock.dividend_split_signal.days_until)} days since event`
                  }
                </div>
                <div className="signal-strength-badge">
                  {stock.dividend_split_signal.signal_strength}
                </div>
              </div>
            </div>
          )}

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
              <div className="signal-label">📊 Technical</div>
              <div
                className="signal-value"
                style={{ color: getRecommendationColor(stock.technical_recommendation) }}
              >
                {stock.technical_recommendation}
              </div>
            </div>
            <div className="signal-item">
              <div className="signal-label">📈 Chart Patterns</div>
              <div
                className="signal-value"
                style={{ color: getRecommendationColor(stock.chart_pattern_signal) }}
              >
                {stock.chart_pattern_signal || 'N/A'}
                {stock.chart_pattern_count > 0 && (
                  <span className="count-badge"> ({stock.chart_pattern_count})</span>
                )}
              </div>
            </div>
            <div className="signal-item">
              <div className="signal-label">🕯️ Candlestick</div>
              <div
                className="signal-value"
                style={{ color: getRecommendationColor(stock.candlestick_signal) }}
              >
                {stock.candlestick_signal || 'N/A'}
                {stock.candlestick_pattern_count > 0 && (
                  <span className="count-badge"> ({stock.candlestick_pattern_count})</span>
                )}
              </div>
            </div>
            <div className="signal-item">
              <div className="signal-label">💭 Sentiment</div>
              <div className="signal-value">
                {stock.sentiment_index !== null
                  ? stock.sentiment_index.toFixed(0)
                  : 'N/A'
                }
              </div>
            </div>
            <div className="signal-item">
              <div className="signal-label">💰 Price</div>
              <div className="signal-value">
                ${stock.current_price?.toFixed(2) || 'N/A'}
              </div>
            </div>
            <div className="signal-item">
              <div className="signal-label">🤖 ML Model</div>
              <div
                className="signal-value"
                style={{ color: getRecommendationColor(stock.ml_recommendation) }}
              >
                {stock.ml_recommendation || 'N/A'}
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

        /* Pulsing animation for analyzing state */
        .stock-card.analyzing {
          animation: pulse-card 2s ease-in-out infinite;
        }

        @keyframes pulse-card {
          0%, 100% {
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
          }
          50% {
            box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
          }
        }

        /* Analyzing badge */
        .analyzing-badge {
          position: absolute;
          top: 12px;
          left: 50%;
          transform: translateX(-50%);
          z-index: 15;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          padding: 8px 14px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: 8px;
          box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
          animation: pulse-analyzing 1.5s ease-in-out infinite;
        }

        @keyframes pulse-analyzing {
          0%, 100% {
            transform: translateX(-50%) scale(1);
            opacity: 1;
          }
          50% {
            transform: translateX(-50%) scale(1.05);
            opacity: 0.9;
          }
        }

        .analyzing-spinner {
          width: 14px;
          height: 14px;
          border: 2px solid rgba(255, 255, 255, 0.3);
          border-top-color: white;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        .loading-overlay {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(255, 255, 255, 0.9);
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          z-index: 10;
          border-radius: 12px;
        }

        .loading-spinner {
          width: 40px;
          height: 40px;
          border: 4px solid #e5e7eb;
          border-top-color: #667eea;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        .loading-text {
          margin-top: 12px;
          color: #6b7280;
          font-size: 14px;
          font-weight: 500;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
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

        .completeness-badge {
          font-size: 11px;
          font-weight: 700;
          padding: 4px 10px;
          border-radius: 12px;
          border: 2px solid;
          white-space: nowrap;
          animation: fade-in 0.3s ease-out;
        }

        @keyframes fade-in {
          from {
            opacity: 0;
            transform: translateY(-4px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .sector-badge {
          font-size: 11px;
          font-weight: 600;
          padding: 4px 10px;
          border-radius: 12px;
          border: 1px solid;
          white-space: nowrap;
        }

        .priority-badge {
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

        /* Dividend/Split Signal Badge */
        .dividend-split-badge {
          border: 2px solid;
          border-radius: 12px;
          padding: 14px;
          margin-bottom: 16px;
          cursor: pointer;
          transition: all 0.2s;
          animation: pulse-badge 2s infinite;
        }

        .dividend-split-badge:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }

        @keyframes pulse-badge {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.85;
          }
        }

        .signal-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 8px;
        }

        .signal-icon {
          font-size: 18px;
        }

        .signal-title {
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.5px;
        }

        .signal-body {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .signal-days {
          font-size: 13px;
          font-weight: 600;
        }

        .signal-strength-badge {
          background: rgba(0, 0, 0, 0.1);
          padding: 4px 10px;
          border-radius: 8px;
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
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

        .count-badge {
          font-size: 12px;
          color: #6b7280;
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
