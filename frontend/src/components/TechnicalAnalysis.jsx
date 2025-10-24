import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import IndicatorInfo from './IndicatorInfo';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const TechnicalAnalysis = ({ stockId, symbol, indicatorParams, setIndicatorParams, onAnalysisUpdated }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showInfoModal, setShowInfoModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState({
    trend: true,
    momentum: true,
    volume: true,
    volatility: true
  });

  const defaultParams = {
    rsi_period: 14,
    macd_fast: 12,
    macd_slow: 26,
    macd_signal: 9,
    bb_window: 20,
    bb_std: 2.0,
    ma_short: 20,
    ma_long: 50
  };

  const handleParamChange = (key, value) => {
    // If empty string, keep the previous value instead of setting to 0
    if (value === '' || value === null || value === undefined) {
      return;
    }

    const numValue = parseFloat(value);
    // Only update if it's a valid number
    if (!isNaN(numValue)) {
      setIndicatorParams(prev => ({
        ...prev,
        [key]: numValue
      }));
    }
  };

  const handleParamBlur = (key, value) => {
    // If field is empty on blur, restore default value
    if (value === '' || value === null || value === undefined || isNaN(parseFloat(value))) {
      setIndicatorParams(prev => ({
        ...prev,
        [key]: defaultParams[key]
      }));
    }
  };

  const resetToDefaults = () => {
    setIndicatorParams(defaultParams);
  };

  const fetchAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${API_URL}/api/v1/stocks/${stockId}/analyze`, {
        period: '3mo',
        ...indicatorParams
      });

      setAnalysis(response.data);

      // Notify parent component to update recommendation/radar chart
      if (onAnalysisUpdated) {
        onAnalysisUpdated();
      }
    } catch (err) {
      console.error('Error fetching analysis:', err);

      // Handle different error formats
      let errorMessage = 'Failed to fetch analysis';

      if (err.response?.data) {
        const data = err.response.data;

        // Handle Pydantic validation errors (array format)
        if (Array.isArray(data.detail)) {
          errorMessage = data.detail.map(e => {
            const field = e.loc ? e.loc.join('.') : 'unknown';
            return `${field}: ${e.msg}`;
          }).join(', ');
        }
        // Handle string detail
        else if (typeof data.detail === 'string') {
          errorMessage = data.detail;
        }
        // Handle object detail
        else if (typeof data.detail === 'object') {
          errorMessage = JSON.stringify(data.detail);
        }
      } else if (err.message) {
        errorMessage = err.message;
      }

      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [stockId, indicatorParams, onAnalysisUpdated]);

  // Auto-load analysis on mount
  useEffect(() => {
    fetchAnalysis();
  }, [fetchAnalysis]);

  const toggleCategory = (category) => {
    setExpandedCategories(prev => ({
      ...prev,
      [category]: !prev[category]
    }));
  };

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

  const safeToFixed = (value, decimals) => {
    return (value !== null && value !== undefined) ? value.toFixed(decimals) : 'N/A';
  };

  // Categorize indicators
  const categorizeIndicators = (indicators) => {
    if (!indicators) return { trend: {}, momentum: {}, volume: {}, volatility: {} };

    return {
      trend: {
        'Moving Averages': indicators.Moving_Averages,
        'MACD': indicators.MACD,
        'ADX': indicators.ADX,
        'Parabolic SAR': indicators.Parabolic_SAR,
      },
      momentum: {
        'RSI': indicators.RSI,
        'Stochastic': indicators.Stochastic,
        'CCI': indicators.CCI,
      },
      volume: {
        'OBV': indicators.OBV,
        'VWAP': indicators.VWAP,
        'A/D Line': indicators.AD_Line,
      },
      volatility: {
        'Bollinger Bands': indicators.Bollinger_Bands,
        'ATR': indicators.ATR,
        'Keltner Channels': indicators.Keltner_Channels,
      }
    };
  };

  const renderIndicatorValue = (name, data) => {
    if (!data) return null;

    return (
      <div key={name} className="indicator-card">
        <div className="indicator-header">
          <h4>{name}</h4>
          {data.signal && (
            <div className="signal-badge" style={{ backgroundColor: getRecommendationColor(data.signal) }}>
              {getSignalIcon(data.signal)} {data.signal}
            </div>
          )}
        </div>
        <div className="indicator-body">
          {/* RSI */}
          {name === 'RSI' && data.value !== undefined && (
            <div className="indicator-values">
              <div className="value-item">
                <span className="label">Value:</span>
                <span className="value">{safeToFixed(data.value, 2)}</span>
              </div>
            </div>
          )}

          {/* MACD */}
          {name === 'MACD' && (
            <div className="indicator-values">
              <div className="value-item">
                <span className="label">MACD:</span>
                <span className="value">{safeToFixed(data.macd, 4)}</span>
              </div>
              <div className="value-item">
                <span className="label">Signal:</span>
                <span className="value">{safeToFixed(data.signal_line, 4)}</span>
              </div>
              <div className="value-item">
                <span className="label">Histogram:</span>
                <span className="value">{safeToFixed(data.histogram, 4)}</span>
              </div>
            </div>
          )}

          {/* Bollinger Bands */}
          {name === 'Bollinger Bands' && (
            <div className="indicator-values">
              <div className="value-item">
                <span className="label">Upper:</span>
                <span className="value">${safeToFixed(data.upper, 2)}</span>
              </div>
              <div className="value-item">
                <span className="label">Middle:</span>
                <span className="value">${safeToFixed(data.middle, 2)}</span>
              </div>
              <div className="value-item">
                <span className="label">Lower:</span>
                <span className="value">${safeToFixed(data.lower, 2)}</span>
              </div>
            </div>
          )}

          {/* Moving Averages */}
          {name === 'Moving Averages' && (
            <div className="indicator-values">
              <div className="value-item">
                <span className="label">Short MA:</span>
                <span className="value">${safeToFixed(data.ma_short, 2)}</span>
              </div>
              <div className="value-item">
                <span className="label">Long MA:</span>
                <span className="value">${safeToFixed(data.ma_long, 2)}</span>
              </div>
            </div>
          )}

          {/* ADX */}
          {name === 'ADX' && (
            <div className="indicator-values">
              <div className="value-item">
                <span className="label">ADX:</span>
                <span className="value">{safeToFixed(data.value, 2)}</span>
              </div>
              <div className="value-item">
                <span className="label">+DI:</span>
                <span className="value">{safeToFixed(data.plus_di, 2)}</span>
              </div>
              <div className="value-item">
                <span className="label">-DI:</span>
                <span className="value">{safeToFixed(data.minus_di, 2)}</span>
              </div>
            </div>
          )}

          {/* Parabolic SAR */}
          {name === 'Parabolic SAR' && (
            <div className="indicator-values">
              <div className="value-item">
                <span className="label">SAR:</span>
                <span className="value">${safeToFixed(data.value, 2)}</span>
              </div>
              <div className="value-item">
                <span className="label">Trend:</span>
                <span className="value">{data.trend === 1 ? 'Uptrend' : data.trend === -1 ? 'Downtrend' : 'N/A'}</span>
              </div>
            </div>
          )}

          {/* Stochastic */}
          {name === 'Stochastic' && (
            <div className="indicator-values">
              <div className="value-item">
                <span className="label">%K:</span>
                <span className="value">{safeToFixed(data.k, 2)}</span>
              </div>
              <div className="value-item">
                <span className="label">%D:</span>
                <span className="value">{safeToFixed(data.d, 2)}</span>
              </div>
            </div>
          )}

          {/* CCI */}
          {name === 'CCI' && (
            <div className="indicator-values">
              <div className="value-item">
                <span className="label">CCI:</span>
                <span className="value">{safeToFixed(data.value, 2)}</span>
              </div>
            </div>
          )}

          {/* OBV */}
          {name === 'OBV' && (
            <div className="indicator-values">
              <div className="value-item">
                <span className="label">OBV:</span>
                <span className="value">{data.value ? data.value.toLocaleString() : 'N/A'}</span>
              </div>
            </div>
          )}

          {/* VWAP */}
          {name === 'VWAP' && (
            <div className="indicator-values">
              <div className="value-item">
                <span className="label">VWAP:</span>
                <span className="value">${safeToFixed(data.value, 2)}</span>
              </div>
            </div>
          )}

          {/* A/D Line */}
          {name === 'A/D Line' && (
            <div className="indicator-values">
              <div className="value-item">
                <span className="label">A/D Line:</span>
                <span className="value">{data.value ? data.value.toLocaleString() : 'N/A'}</span>
              </div>
            </div>
          )}

          {/* ATR */}
          {name === 'ATR' && (
            <div className="indicator-values">
              <div className="value-item">
                <span className="label">ATR:</span>
                <span className="value">{safeToFixed(data.value, 2)}</span>
              </div>
            </div>
          )}

          {/* Keltner Channels */}
          {name === 'Keltner Channels' && (
            <div className="indicator-values">
              <div className="value-item">
                <span className="label">Upper:</span>
                <span className="value">${safeToFixed(data.upper, 2)}</span>
              </div>
              <div className="value-item">
                <span className="label">Middle:</span>
                <span className="value">${safeToFixed(data.middle, 2)}</span>
              </div>
              <div className="value-item">
                <span className="label">Lower:</span>
                <span className="value">${safeToFixed(data.lower, 2)}</span>
              </div>
            </div>
          )}

          {data.reason && <p className="indicator-reason">{data.reason}</p>}
        </div>
      </div>
    );
  };

  const renderCategory = (categoryName, categoryTitle, categoryIcon, indicators) => {
    const isExpanded = expandedCategories[categoryName];
    const hasIndicators = Object.values(indicators).some(ind => ind !== undefined && ind !== null);

    if (!hasIndicators) return null;

    return (
      <div key={categoryName} className="category-section">
        <div className="category-header" onClick={() => toggleCategory(categoryName)}>
          <div className="category-title">
            <span className="category-icon">{categoryIcon}</span>
            <h3>{categoryTitle}</h3>
            <span className="indicator-count">
              ({Object.values(indicators).filter(ind => ind !== undefined && ind !== null).length})
            </span>
          </div>
          <span className={`expand-icon ${isExpanded ? 'expanded' : ''}`}>▼</span>
        </div>

        {isExpanded && (
          <div className="indicators-grid">
            {Object.entries(indicators).map(([name, data]) => {
              if (!data) return null;
              return renderIndicatorValue(name, data);
            })}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="technical-analysis">
      <div className="analysis-header">
        <h3>📊 Technical Analysis</h3>
        <div className="header-buttons">
          <button onClick={() => setShowInfoModal(true)} className="btn-info" title="Learn about indicators">
            ℹ️ Indicator Guide
          </button>
          <button onClick={fetchAnalysis} disabled={loading} className="btn-analyze">
            {loading ? 'Refreshing...' : 'Refresh Analysis'}
          </button>
        </div>
      </div>

      {showInfoModal && <IndicatorInfo onClose={() => setShowInfoModal(false)} />}

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

          {/* Settings Panel */}
          <div className="settings-panel">
            <div className="settings-header" onClick={() => setShowSettings(!showSettings)}>
              <div className="settings-title">
                <span className="settings-icon">⚙️</span>
                <h3>Indicator Parameters</h3>
              </div>
              <span className={`expand-icon ${showSettings ? 'expanded' : ''}`}>▼</span>
            </div>

            {showSettings && (
              <div className="settings-body">
                <div className="settings-grid">
                  {/* Trend Indicators */}
                  <div className="param-section">
                    <h4>📈 Trend Indicators</h4>
                    <div className="param-group">
                      <label>
                        <span className="param-label">MA Short Period:</span>
                        <input
                          type="number"
                          min="1"
                          max="200"
                          value={indicatorParams.ma_short}
                          onChange={(e) => handleParamChange('ma_short', e.target.value)}
                          onBlur={(e) => handleParamBlur('ma_short', e.target.value)}
                        />
                      </label>
                      <label>
                        <span className="param-label">MA Long Period:</span>
                        <input
                          type="number"
                          min="1"
                          max="200"
                          value={indicatorParams.ma_long}
                          onChange={(e) => handleParamChange('ma_long', e.target.value)}
                          onBlur={(e) => handleParamBlur('ma_long', e.target.value)}
                        />
                      </label>
                      <label>
                        <span className="param-label">MACD Fast:</span>
                        <input
                          type="number"
                          min="1"
                          max="50"
                          value={indicatorParams.macd_fast}
                          onChange={(e) => handleParamChange('macd_fast', e.target.value)}
                          onBlur={(e) => handleParamBlur('macd_fast', e.target.value)}
                        />
                      </label>
                      <label>
                        <span className="param-label">MACD Slow:</span>
                        <input
                          type="number"
                          min="1"
                          max="100"
                          value={indicatorParams.macd_slow}
                          onChange={(e) => handleParamChange('macd_slow', e.target.value)}
                          onBlur={(e) => handleParamBlur('macd_slow', e.target.value)}
                        />
                      </label>
                      <label>
                        <span className="param-label">MACD Signal:</span>
                        <input
                          type="number"
                          min="1"
                          max="50"
                          value={indicatorParams.macd_signal}
                          onChange={(e) => handleParamChange('macd_signal', e.target.value)}
                          onBlur={(e) => handleParamBlur('macd_signal', e.target.value)}
                        />
                      </label>
                    </div>
                  </div>

                  {/* Momentum Indicators */}
                  <div className="param-section">
                    <h4>⚡ Momentum Indicators</h4>
                    <div className="param-group">
                      <label>
                        <span className="param-label">RSI Period:</span>
                        <input
                          type="number"
                          min="2"
                          max="50"
                          value={indicatorParams.rsi_period}
                          onChange={(e) => handleParamChange('rsi_period', e.target.value)}
                          onBlur={(e) => handleParamBlur('rsi_period', e.target.value)}
                        />
                      </label>
                    </div>
                  </div>

                  {/* Volatility Indicators */}
                  <div className="param-section">
                    <h4>📉 Volatility Indicators</h4>
                    <div className="param-group">
                      <label>
                        <span className="param-label">Bollinger Bands Window:</span>
                        <input
                          type="number"
                          min="2"
                          max="100"
                          value={indicatorParams.bb_window}
                          onChange={(e) => handleParamChange('bb_window', e.target.value)}
                          onBlur={(e) => handleParamBlur('bb_window', e.target.value)}
                        />
                      </label>
                      <label>
                        <span className="param-label">Bollinger Bands Std Dev:</span>
                        <input
                          type="number"
                          min="0.1"
                          max="5"
                          step="0.1"
                          value={indicatorParams.bb_std}
                          onChange={(e) => handleParamChange('bb_std', e.target.value)}
                          onBlur={(e) => handleParamBlur('bb_std', e.target.value)}
                        />
                      </label>
                    </div>
                  </div>
                </div>

                <div className="settings-actions">
                  <button onClick={resetToDefaults} className="btn-reset">
                    ↺ Reset to Defaults
                  </button>
                  <button onClick={fetchAnalysis} disabled={loading} className="btn-apply">
                    {loading ? 'Applying...' : '✓ Apply & Recalculate'}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Categorized Indicators */}
          <div className="categories-container">
            {(() => {
              if (!analysis.indicators) {
                return <div className="no-indicators">No indicator data available</div>;
              }

              console.log('Analysis indicators:', analysis.indicators);
              const categorized = categorizeIndicators(analysis.indicators);
              console.log('Categorized:', categorized);

              const trendSection = renderCategory('trend', 'Trend Indicators', '📈', categorized.trend);
              const momentumSection = renderCategory('momentum', 'Momentum Indicators', '⚡', categorized.momentum);
              const volumeSection = renderCategory('volume', 'Volume Indicators', '📊', categorized.volume);
              const volatilitySection = renderCategory('volatility', 'Volatility Indicators', '📉', categorized.volatility);

              // If no categories have data, show a message
              if (!trendSection && !momentumSection && !volumeSection && !volatilitySection) {
                return (
                  <div className="no-indicators">
                    <p>No categorized indicators available.</p>
                    <p>Available indicators: {Object.keys(analysis.indicators).join(', ')}</p>
                  </div>
                );
              }

              return (
                <>
                  {trendSection}
                  {momentumSection}
                  {volumeSection}
                  {volatilitySection}
                </>
              );
            })()}
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

        .header-buttons {
          display: flex;
          gap: 10px;
        }

        .btn-info {
          background: #f0f0f0;
          color: #333;
          border: 2px solid #ddd;
          padding: 10px 20px;
          border-radius: 5px;
          cursor: pointer;
          font-size: 14px;
          font-weight: 600;
          transition: all 0.3s;
        }

        .btn-info:hover {
          background: #667eea;
          color: white;
          border-color: #667eea;
          transform: translateY(-2px);
          box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
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

        .categories-container {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .category-section {
          background: white;
          border: 1px solid #ddd;
          border-radius: 8px;
          overflow: hidden;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .category-header {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          padding: 15px 20px;
          cursor: pointer;
          display: flex;
          justify-content: space-between;
          align-items: center;
          user-select: none;
          transition: all 0.3s;
        }

        .category-header:hover {
          background: linear-gradient(135deg, #5568d3 0%, #653a8b 100%);
        }

        .category-title {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .category-icon {
          font-size: 24px;
        }

        .category-title h3 {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
        }

        .indicator-count {
          font-size: 14px;
          opacity: 0.9;
          margin-left: 5px;
        }

        .expand-icon {
          font-size: 16px;
          transition: transform 0.3s;
        }

        .expand-icon.expanded {
          transform: rotate(180deg);
        }

        .indicators-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 15px;
          padding: 20px;
          background: #f9fafb;
        }

        .indicator-card {
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          padding: 15px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
          transition: all 0.3s;
        }

        .indicator-card:hover {
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
          transform: translateY(-2px);
        }

        .indicator-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
          padding-bottom: 10px;
          border-bottom: 2px solid #e5e7eb;
        }

        .indicator-header h4 {
          margin: 0;
          color: #333;
          font-size: 16px;
          font-weight: 600;
        }

        .signal-badge {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          padding: 4px 12px;
          color: white;
          border-radius: 5px;
          font-size: 12px;
          font-weight: 600;
        }

        .indicator-body {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .indicator-values {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .value-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 6px 0;
        }

        .value-item .label {
          font-size: 13px;
          color: #666;
          font-weight: 500;
        }

        .value-item .value {
          font-size: 14px;
          color: #111;
          font-weight: 600;
        }

        .indicator-reason {
          font-style: italic;
          color: #666;
          margin-top: 8px;
          font-size: 13px;
          padding-top: 8px;
          border-top: 1px solid #e5e7eb;
        }

        .no-indicators {
          background: #fff3cd;
          border: 2px solid #ffc107;
          border-radius: 8px;
          padding: 20px;
          text-align: center;
          margin: 20px 0;
        }

        .no-indicators p {
          margin: 10px 0;
          color: #856404;
          font-size: 14px;
        }

        /* Settings Panel Styles */
        .settings-panel {
          background: white;
          border: 2px solid #667eea;
          border-radius: 8px;
          overflow: hidden;
          box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
        }

        .settings-header {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          padding: 15px 20px;
          cursor: pointer;
          display: flex;
          justify-content: space-between;
          align-items: center;
          user-select: none;
          transition: all 0.3s;
        }

        .settings-header:hover {
          background: linear-gradient(135deg, #5568d3 0%, #653a8b 100%);
        }

        .settings-title {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .settings-icon {
          font-size: 24px;
        }

        .settings-title h3 {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
        }

        .settings-body {
          padding: 20px;
          background: #f9fafb;
        }

        .settings-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 20px;
          margin-bottom: 20px;
        }

        .param-section {
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          padding: 15px;
        }

        .param-section h4 {
          margin: 0 0 15px 0;
          color: #333;
          font-size: 16px;
          font-weight: 600;
          padding-bottom: 10px;
          border-bottom: 2px solid #e5e7eb;
        }

        .param-group {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .param-group label {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
        }

        .param-label {
          font-size: 14px;
          color: #666;
          font-weight: 500;
          flex: 1;
        }

        .param-group input[type="number"] {
          width: 80px;
          padding: 8px 10px;
          border: 1px solid #ddd;
          border-radius: 5px;
          font-size: 14px;
          text-align: center;
          transition: all 0.3s;
        }

        .param-group input[type="number"]:focus {
          outline: none;
          border-color: #667eea;
          box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        .param-group input[type="number"]:hover {
          border-color: #667eea;
        }

        .settings-actions {
          display: flex;
          gap: 10px;
          justify-content: flex-end;
          padding-top: 15px;
          border-top: 2px solid #e5e7eb;
        }

        .btn-reset {
          background: #f8f9fa;
          color: #666;
          border: 2px solid #ddd;
          padding: 10px 20px;
          border-radius: 5px;
          cursor: pointer;
          font-size: 14px;
          font-weight: 600;
          transition: all 0.3s;
        }

        .btn-reset:hover {
          background: #e9ecef;
          border-color: #adb5bd;
          color: #333;
        }

        .btn-apply {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          border: none;
          padding: 10px 20px;
          border-radius: 5px;
          cursor: pointer;
          font-size: 14px;
          font-weight: 600;
          transition: all 0.3s;
          box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
        }

        .btn-apply:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }

        .btn-apply:disabled {
          background: #6c757d;
          cursor: not-allowed;
          opacity: 0.6;
        }
      `}</style>
    </div>
  );
};

export default TechnicalAnalysis;
