import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const MarketRegime = ({ stockId, symbol }) => {
  const [loading, setLoading] = useState(false);
  const [regimeData, setRegimeData] = useState(null);
  const [error, setError] = useState(null);

  const loadRegimeData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await axios.get(
        `${API_URL}/api/v1/stocks/${stockId}/market-regime`
      );

      setRegimeData(response.data);
    } catch (err) {
      console.error('Error loading market regime:', err);
      setError(err.response?.data?.detail || 'Failed to load market regime');
    } finally {
      setLoading(false);
    }
  }, [stockId]);

  useEffect(() => {
    if (stockId) {
      loadRegimeData();
    }
  }, [stockId, loadRegimeData]);

  const getRegimeColor = (regime) => {
    const colors = {
      'trend': '#10b981',      // Green
      'channel': '#3b82f6',    // Blue
      'range': '#f59e0b'       // Amber
    };
    return colors[regime] || '#6b7280';
  };

  const getDirectionColor = (direction) => {
    if (direction.includes('bullish')) return '#10b981';  // Green
    if (direction.includes('bearish')) return '#ef4444';  // Red
    return '#6b7280';  // Gray
  };

  const getVolatilityColor = (volatility) => {
    const colors = {
      'low_vol': '#10b981',     // Green
      'normal_vol': '#3b82f6',  // Blue
      'high_vol': '#ef4444'     // Red
    };
    return colors[volatility] || '#6b7280';
  };

  const getRiskLevelColor = (riskLevel) => {
    const colors = {
      'low': '#10b981',
      'medium': '#f59e0b',
      'high': '#ef4444'
    };
    return colors[riskLevel] || '#6b7280';
  };

  const getRegimeIcon = (regime) => {
    const icons = {
      'trend': '📈',
      'channel': '〰️',
      'range': '↔️'
    };
    return icons[regime] || '📊';
  };

  const getDirectionIcon = (direction) => {
    if (direction.includes('bullish')) return '🟢';
    if (direction.includes('bearish')) return '🔴';
    return '⚪';
  };

  const getVolatilityIcon = (volatility) => {
    const icons = {
      'low_vol': '🔵',
      'normal_vol': '🟡',
      'high_vol': '🔴'
    };
    return icons[volatility] || '⚪';
  };

  const formatRegimeName = (regime) => {
    const names = {
      'trend': 'Trending',
      'channel': 'Channeling',
      'range': 'Ranging'
    };
    return names[regime] || regime;
  };

  const formatDirectionName = (direction) => {
    const names = {
      'bullish': 'Bullish',
      'bearish': 'Bearish',
      'bullish_weak': 'Bullish (Weak)',
      'bearish_weak': 'Bearish (Weak)',
      'neutral': 'Neutral'
    };
    return names[direction] || direction;
  };

  const formatVolatilityName = (volatility) => {
    const names = {
      'low_vol': 'Low Volatility',
      'normal_vol': 'Normal Volatility',
      'high_vol': 'High Volatility'
    };
    return names[volatility] || volatility;
  };

  if (loading) {
    return (
      <div className="market-regime-loading">
        Loading market regime analysis...
      </div>
    );
  }

  if (error) {
    return (
      <div className="market-regime-error">
        <strong>Error:</strong> {error}
      </div>
    );
  }

  if (!regimeData) {
    return null;
  }

  return (
    <div className="market-regime">
      <h3>📊 Market Regime Analysis</h3>
      <p className="subtitle">TCR + MA Slope + Volatility Detection</p>

      {/* Main Regime Cards - Compact */}
      <div className="regime-summary">
        {/* Regime Type */}
        <div className="regime-item" style={{ borderLeftColor: getRegimeColor(regimeData.regime) }}>
          <div className="item-header">
            <span className="item-icon">{getRegimeIcon(regimeData.regime)}</span>
            <span className="item-label">Market Structure</span>
          </div>
          <div className="item-value" style={{ color: getRegimeColor(regimeData.regime) }}>
            {formatRegimeName(regimeData.regime)}
          </div>
          <div className="item-explanation">
            ADX: {regimeData.adx} -
            {regimeData.adx >= 25 ? ' Strong trend' :
             regimeData.adx >= 20 ? ' Channel' :
             ' Ranging/sideways'}
          </div>
        </div>

        {/* Direction */}
        <div className="regime-item" style={{ borderLeftColor: getDirectionColor(regimeData.direction) }}>
          <div className="item-header">
            <span className="item-icon">{getDirectionIcon(regimeData.direction)}</span>
            <span className="item-label">Direction</span>
          </div>
          <div className="item-value" style={{ color: getDirectionColor(regimeData.direction) }}>
            {formatDirectionName(regimeData.direction)}
          </div>
          <div className="item-explanation">
            +DI {regimeData.plus_di} vs -DI {regimeData.minus_di} -
            {regimeData.plus_di > regimeData.minus_di ? ' Buyers stronger' : ' Sellers stronger'}
          </div>
        </div>

        {/* Volatility */}
        <div className="regime-item" style={{ borderLeftColor: getVolatilityColor(regimeData.volatility_regime) }}>
          <div className="item-header">
            <span className="item-icon">{getVolatilityIcon(regimeData.volatility_regime)}</span>
            <span className="item-label">Volatility</span>
          </div>
          <div className="item-value" style={{ color: getVolatilityColor(regimeData.volatility_regime) }}>
            {formatVolatilityName(regimeData.volatility_regime)}
          </div>
          <div className="item-explanation">
            ATR ${regimeData.atr} - {regimeData.atr_percentile}th percentile
          </div>
        </div>
      </div>

      {/* Recommendation - Compact */}
      <div className="recommendation-compact" style={{ borderLeftColor: getRiskLevelColor(regimeData.risk_level) }}>
        <div className="rec-compact-header">
          <span className="rec-icon">💡</span>
          <span className="rec-text">{regimeData.recommendation}</span>
          <span className="rec-badge-compact" style={{ backgroundColor: getRiskLevelColor(regimeData.risk_level) }}>
            {regimeData.risk_level.toUpperCase()}
          </span>
        </div>
        <div className="rec-compact-detail">
          Strategy: {regimeData.suggested_strategy}
        </div>
      </div>

      {/* Price & MA Context - Simplified */}
      <div className="price-context">
        <div className="price-row">
          <span className="ctx-label">Price:</span>
          <span className="ctx-value">${regimeData.current_price}</span>
          <span className="ctx-sep">|</span>
          <span className="ctx-label">MA20:</span>
          <span className="ctx-value">${regimeData.current_ma20}</span>
          <span className="ctx-sep">|</span>
          <span className="ctx-label">MA50:</span>
          <span className="ctx-value">${regimeData.current_ma50}</span>
        </div>
        <div className="price-explanation">
          MA20 {regimeData.ma20_slope > 0 ? '▲' : regimeData.ma20_slope < 0 ? '▼' : '→'}
          {regimeData.ma20_slope > 0 ? ' rising' : regimeData.ma20_slope < 0 ? ' falling' : ' flat'},
          MA50 {regimeData.ma50_slope > 0 ? '▲' : regimeData.ma50_slope < 0 ? '▼' : '→'}
          {regimeData.ma50_slope > 0 ? ' rising' : regimeData.ma50_slope < 0 ? ' falling' : ' flat'}
        </div>
      </div>

      <style jsx>{`
        .market-regime {
          background: white;
          border-radius: 8px;
          padding: 12px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .market-regime h3 {
          margin: 0 0 2px 0;
          font-size: 14px;
          color: #111827;
        }

        .subtitle {
          margin: 0 0 10px 0;
          font-size: 11px;
          color: #6b7280;
        }

        .regime-summary {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
          margin-bottom: 10px;
        }

        .regime-item {
          background: #f9fafb;
          padding: 8px;
          border-radius: 6px;
          border-left: 3px solid;
        }

        .item-header {
          display: flex;
          align-items: center;
          gap: 4px;
          margin-bottom: 4px;
        }

        .item-icon {
          font-size: 16px;
          line-height: 1;
        }

        .item-label {
          font-size: 9px;
          color: #6b7280;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          font-weight: 600;
        }

        .item-value {
          font-size: 13px;
          font-weight: 700;
          margin-bottom: 3px;
        }

        .item-explanation {
          font-size: 9px;
          color: #6b7280;
          line-height: 1.3;
        }

        .recommendation-compact {
          background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%);
          padding: 8px;
          border-radius: 6px;
          border-left: 3px solid;
          margin-bottom: 8px;
        }

        .rec-compact-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 4px;
        }

        .rec-icon {
          font-size: 16px;
        }

        .rec-text {
          flex: 1;
          font-size: 12px;
          font-weight: 700;
          color: #111827;
        }

        .rec-badge-compact {
          padding: 2px 8px;
          border-radius: 10px;
          font-size: 9px;
          font-weight: 700;
          color: white;
          letter-spacing: 0.5px;
        }

        .rec-compact-detail {
          font-size: 10px;
          color: #4b5563;
          padding-left: 24px;
        }

        .price-context {
          background: #f9fafb;
          padding: 8px;
          border-radius: 6px;
        }

        .price-row {
          display: flex;
          align-items: center;
          gap: 6px;
          margin-bottom: 4px;
          flex-wrap: wrap;
        }

        .ctx-label {
          font-size: 10px;
          color: #6b7280;
          font-weight: 500;
        }

        .ctx-value {
          font-size: 11px;
          font-weight: 700;
          color: #111827;
        }

        .ctx-sep {
          color: #d1d5db;
          font-size: 10px;
        }

        .price-explanation {
          font-size: 10px;
          color: #6b7280;
          line-height: 1.3;
        }

        .market-regime-loading,
        .market-regime-error {
          background: #f9fafb;
          padding: 20px;
          border-radius: 8px;
          text-align: center;
          font-size: 14px;
          color: #6b7280;
        }

        .market-regime-error {
          background: #fee2e2;
          color: #dc2626;
          border: 1px solid #fecaca;
        }
      `}</style>
    </div>
  );
};

export default MarketRegime;
