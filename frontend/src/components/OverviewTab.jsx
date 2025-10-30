import React from 'react';
import SignalRadar from './SignalRadar';
import OrderCalculator from './OrderCalculator';

const OverviewTab = ({ stock, recommendation, recommendationLoading, recommendationError }) => {
  if (recommendationLoading) {
    return (
      <div className="overview-tab">
        <div className="loading">Loading overview...</div>
      </div>
    );
  }

  if (recommendationError) {
    return (
      <div className="overview-tab">
        <div className="error-message">
          <strong>Error loading recommendation:</strong> {recommendationError}
        </div>
      </div>
    );
  }

  if (!recommendation) {
    return (
      <div className="overview-tab">
        <div className="no-data">No recommendation data available</div>
      </div>
    );
  }

  const getFinalRecommendationColor = () => {
    if (recommendation.final_recommendation === 'BUY') return '#10b981';
    if (recommendation.final_recommendation === 'SELL') return '#ef4444';
    return '#f59e0b';
  };

  const getRiskLevelColor = () => {
    if (recommendation.risk_level === 'LOW') return '#10b981';
    if (recommendation.risk_level === 'HIGH') return '#ef4444';
    return '#f59e0b';
  };

  return (
    <div className="overview-tab">
      {/* Final Recommendation Card */}
      <div
        className="final-recommendation"
        style={{ borderLeftColor: getFinalRecommendationColor() }}
      >
        <div className="rec-header">
          <div>
            <h2 className="rec-symbol">{stock.symbol}</h2>
            <p className="rec-name">{stock.name}</p>
          </div>
          <div className="rec-badge" style={{ backgroundColor: getFinalRecommendationColor() }}>
            {recommendation.final_recommendation}
          </div>
        </div>
        <div className="rec-details">
          <div className="rec-stat">
            <span className="stat-label">Confidence</span>
            <span className="stat-value">{(recommendation.overall_confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="rec-stat">
            <span className="stat-label">Risk Level</span>
            <span className="stat-value" style={{ color: getRiskLevelColor() }}>
              {recommendation.risk_level}
            </span>
          </div>
          <div className="rec-stat">
            <span className="stat-label">Current Price</span>
            <span className="stat-value">${recommendation.current_price.toFixed(2)}</span>
          </div>
        </div>
      </div>

      {/* Signal Radar Chart */}
      <div className="radar-section">
        <SignalRadar recommendation={recommendation} />
      </div>

      {/* Statistics Dashboard */}
      <div className="statistics-dashboard">
        <h3>📊 Analysis Summary</h3>

        <div className="stats-grid">
          {/* Technical Analysis */}
          <div className="stat-card">
            <div className="stat-card-header">
              <span className="stat-icon">📈</span>
              <span className="stat-title">Technical Analysis</span>
            </div>
            <div className="stat-card-body">
              <div className="stat-row">
                <span className="stat-name">Signal</span>
                <span className={`stat-badge ${recommendation.technical_recommendation?.toLowerCase()}`}>
                  {recommendation.technical_recommendation || 'N/A'}
                </span>
              </div>
              <div className="stat-row">
                <span className="stat-name">Confidence</span>
                <span className="stat-number">
                  {((recommendation.technical_confidence || 0) * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>

          {/* ML Prediction */}
          {recommendation.ml_recommendation && (
            <div className="stat-card">
              <div className="stat-card-header">
                <span className="stat-icon">🤖</span>
                <span className="stat-title">ML Prediction</span>
              </div>
              <div className="stat-card-body">
                <div className="stat-row">
                  <span className="stat-name">Signal</span>
                  <span className={`stat-badge ${recommendation.ml_recommendation?.toLowerCase()}`}>
                    {recommendation.ml_recommendation || 'N/A'}
                  </span>
                </div>
                <div className="stat-row">
                  <span className="stat-name">Confidence</span>
                  <span className="stat-number">
                    {((recommendation.ml_confidence || 0) * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Sentiment Analysis */}
          {recommendation.sentiment_index !== null && recommendation.sentiment_index !== undefined && (
            <div className="stat-card">
              <div className="stat-card-header">
                <span className="stat-icon">💭</span>
                <span className="stat-title">Sentiment</span>
              </div>
              <div className="stat-card-body">
                <div className="stat-row">
                  <span className="stat-name">Index</span>
                  <span
                    className="stat-number large"
                    style={{
                      color: recommendation.sentiment_index >= 60 ? '#10b981' :
                        recommendation.sentiment_index >= 40 ? '#f59e0b' : '#ef4444'
                    }}
                  >
                    {recommendation.sentiment_index.toFixed(0)}
                  </span>
                </div>
                <div className="stat-row">
                  <span className="stat-name">Trend</span>
                  <span className="stat-text">{recommendation.sentiment_trend || 'Neutral'}</span>
                </div>
              </div>
            </div>
          )}

          {/* Candlestick Patterns */}
          {(recommendation.candlestick_signal || recommendation.candlestick_confidence) && (
            <div className="stat-card">
              <div className="stat-card-header">
                <span className="stat-icon">🕯️</span>
                <span className="stat-title">Candlestick Patterns</span>
              </div>
              <div className="stat-card-body">
                <div className="stat-row">
                  <span className="stat-name">Signal</span>
                  <span className={`stat-badge ${recommendation.candlestick_signal?.toLowerCase()}`}>
                    {recommendation.candlestick_signal || 'NEUTRAL'}
                  </span>
                </div>
                <div className="stat-row">
                  <span className="stat-name">Confidence</span>
                  <span className="stat-number">
                    {((recommendation.candlestick_confidence || 0) * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Chart Patterns */}
          {(recommendation.chart_pattern_signal || recommendation.chart_pattern_confidence) && (
            <div className="stat-card">
              <div className="stat-card-header">
                <span className="stat-icon">📊</span>
                <span className="stat-title">Chart Patterns</span>
              </div>
              <div className="stat-card-body">
                <div className="stat-row">
                  <span className="stat-name">Signal</span>
                  <span className={`stat-badge ${recommendation.chart_pattern_signal?.toLowerCase()}`}>
                    {recommendation.chart_pattern_signal || 'NEUTRAL'}
                  </span>
                </div>
                <div className="stat-row">
                  <span className="stat-name">Confidence</span>
                  <span className="stat-number">
                    {((recommendation.chart_pattern_confidence || 0) * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Market Regime - NEW */}
          <div className="stat-card highlight">
            <div className="stat-card-header">
              <span className="stat-icon">🔍</span>
              <span className="stat-title">Market Regime</span>
            </div>
            <div className="stat-card-body">
              <div className="stat-row">
                <span className="stat-name">Available In</span>
                <span className="stat-badge new">Risk Tools Tab</span>
              </div>
              <div className="stat-info">
                TCR + MA + Volatility analysis shows if market is trending, channeling, or ranging
              </div>
            </div>
          </div>

          {/* Risk Management Tools - NEW */}
          <div className="stat-card highlight">
            <div className="stat-card-header">
              <span className="stat-icon">🔥</span>
              <span className="stat-title">Risk Management</span>
            </div>
            <div className="stat-card-body">
              <div className="stat-row">
                <span className="stat-name">Available In</span>
                <span className="stat-badge new">Risk Tools Tab</span>
              </div>
              <div className="stat-info">
                Trailing stops, portfolio heat monitoring, and position sizing tools
              </div>
            </div>
          </div>
        </div>

        {/* Reasoning */}
        {recommendation.reasoning && recommendation.reasoning.length > 0 && (
          <div className="reasoning-section">
            <h4>Analysis Reasoning</h4>
            <ul className="reasoning-list">
              {recommendation.reasoning.map((reason, idx) => (
                <li key={idx}>{reason}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Order Calculator */}
      <div className="calculator-section">
        <OrderCalculator stockId={stock.stock_id} symbol={stock.symbol} />
      </div>

      <style jsx>{`
        .overview-tab {
          padding: 20px;
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .loading, .error-message, .no-data {
          padding: 40px;
          text-align: center;
          color: #6b7280;
        }

        .error-message {
          background: #fee2e2;
          border: 1px solid #fecaca;
          color: #dc2626;
          border-radius: 8px;
        }

        .final-recommendation {
          background: white;
          border-radius: 12px;
          padding: 24px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
          border-left: 6px solid #667eea;
        }

        .rec-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 20px;
        }

        .rec-symbol {
          margin: 0;
          font-size: 28px;
          font-weight: 800;
          color: #111827;
        }

        .rec-name {
          margin: 4px 0 0 0;
          font-size: 14px;
          color: #6b7280;
        }

        .rec-badge {
          padding: 12px 24px;
          border-radius: 8px;
          color: white;
          font-size: 20px;
          font-weight: 800;
          letter-spacing: 1px;
        }

        .rec-details {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 16px;
        }

        .rec-stat {
          background: #f9fafb;
          padding: 12px;
          border-radius: 8px;
          text-align: center;
        }

        .stat-label {
          display: block;
          font-size: 11px;
          color: #6b7280;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 6px;
        }

        .stat-value {
          display: block;
          font-size: 20px;
          font-weight: 700;
          color: #111827;
        }

        .statistics-dashboard {
          background: white;
          border-radius: 12px;
          padding: 20px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .statistics-dashboard h3 {
          margin: 0 0 20px 0;
          font-size: 18px;
          color: #111827;
        }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 16px;
          margin-bottom: 20px;
        }

        .stat-card {
          background: #f9fafb;
          border-radius: 8px;
          overflow: hidden;
          border: 1px solid #e5e7eb;
        }

        .stat-card-header {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          padding: 12px;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .stat-icon {
          font-size: 18px;
        }

        .stat-title {
          font-size: 13px;
          font-weight: 600;
        }

        .stat-card-body {
          padding: 12px;
        }

        .stat-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 6px 0;
        }

        .stat-row:not(:last-child) {
          border-bottom: 1px solid #e5e7eb;
        }

        .stat-name {
          font-size: 12px;
          color: #6b7280;
          font-weight: 500;
        }

        .stat-badge {
          padding: 4px 12px;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .stat-badge.buy {
          background: #d1fae5;
          color: #065f46;
        }

        .stat-badge.sell {
          background: #fee2e2;
          color: #991b1b;
        }

        .stat-badge.hold {
          background: #fef3c7;
          color: #92400e;
        }

        .stat-badge.new {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          font-weight: 700;
          letter-spacing: 0.5px;
        }

        .stat-card.highlight {
          border: 2px solid #667eea;
          background: linear-gradient(135deg, #f9fafb 0%, #ffffff 100%);
        }

        .stat-info {
          font-size: 12px;
          color: #6b7280;
          line-height: 1.5;
          margin-top: 8px;
          font-style: italic;
        }

        .stat-number {
          font-size: 16px;
          font-weight: 700;
          color: #111827;
        }

        .stat-number.large {
          font-size: 24px;
        }

        .stat-text {
          font-size: 13px;
          color: #374151;
          font-weight: 600;
        }

        .reasoning-section {
          background: #f9fafb;
          padding: 16px;
          border-radius: 8px;
          border-left: 4px solid #667eea;
        }

        .reasoning-section h4 {
          margin: 0 0 12px 0;
          font-size: 14px;
          color: #374151;
          font-weight: 600;
        }

        .reasoning-list {
          margin: 0;
          padding-left: 20px;
          font-size: 13px;
          color: #6b7280;
          line-height: 1.8;
        }

        .reasoning-list li {
          margin-bottom: 6px;
        }

        .radar-section, .calculator-section {
          background: white;
          border-radius: 12px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
          overflow: hidden;
        }
      `}</style>
    </div>
  );
};

export default OverviewTab;
