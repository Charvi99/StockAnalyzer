import React, { useState, useEffect, useCallback } from 'react';
import { detectPatterns, getPatterns, confirmPattern, deletePattern } from '../services/api';

const CandlestickPatterns = ({ stockId, symbol, onPatternsDetected, onPatternsUpdated }) => {
  const [patterns, setPatterns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({ total_patterns: 0, bullish_patterns: 0, bearish_patterns: 0 });
  const [filterType, setFilterType] = useState('all'); // 'all', 'bullish', 'bearish'
  const [expandedPattern, setExpandedPattern] = useState(null);
  const [isExpanded, setIsExpanded] = useState(true); // Collapsible section state

  const loadPatterns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPatterns(stockId, { days: 90 });
      setPatterns(data.patterns);

      // Pass patterns to parent for chart markers
      if (onPatternsDetected) {
        onPatternsDetected(data.patterns);
      }
    } catch (err) {
      console.error('Error loading patterns:', err);
      setError('Failed to load patterns');
    } finally {
      setLoading(false);
    }
  }, [stockId, onPatternsDetected]);

  // Load patterns on mount
  useEffect(() => {
    loadPatterns();
  }, [loadPatterns]);

  const handleDetectPatterns = async () => {
    setDetecting(true);
    setError(null);
    try {
      const result = await detectPatterns(stockId, 90);
      setStats({
        total_patterns: result.total_patterns,
        bullish_patterns: result.bullish_patterns,
        bearish_patterns: result.bearish_patterns
      });

      // Reload patterns from database
      await loadPatterns();

      // Notify parent component to update recommendation/radar chart
      if (onPatternsUpdated) {
        onPatternsUpdated();
      }
    } catch (err) {
      console.error('Error detecting patterns:', err);
      setError(err.response?.data?.detail || 'Failed to detect patterns');
    } finally {
      setDetecting(false);
    }
  };

  const handleConfirmPattern = async (patternId, confirmed) => {
    try {
      await confirmPattern(patternId, confirmed, '', 'user');

      // Update local state
      setPatterns(prev => prev.map(p =>
        p.id === patternId
          ? { ...p, user_confirmed: confirmed, confirmed_at: new Date().toISOString() }
          : p
      ));
    } catch (err) {
      console.error('Error confirming pattern:', err);
      alert('Failed to confirm pattern');
    }
  };

  const handleDeletePattern = async (patternId) => {
    if (!window.confirm('Are you sure you want to delete this pattern?')) return;

    try {
      await deletePattern(patternId);
      setPatterns(prev => prev.filter(p => p.id !== patternId));
    } catch (err) {
      console.error('Error deleting pattern:', err);
      alert('Failed to delete pattern');
    }
  };

  const getPatternTypeColor = (type) => {
    switch (type) {
      case 'bullish': return '#28a745';
      case 'bearish': return '#dc3545';
      default: return '#6c757d';
    }
  };

  const getPatternIcon = (type) => {
    return type === 'bullish' ? '📈' : type === 'bearish' ? '📉' : '➖';
  };

  const filteredPatterns = patterns.filter(p => {
    if (filterType === 'all') return true;
    return p.pattern_type === filterType;
  });

  const pendingCount = patterns.filter(p => p.user_confirmed === null).length;
  const confirmedCount = patterns.filter(p => p.user_confirmed === true).length;
  const rejectedCount = patterns.filter(p => p.user_confirmed === false).length;

  return (
    <div className="candlestick-patterns">
      <div className="patterns-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="header-title">
          <span className="header-icon">🕯️</span>
          <h3>Candlestick Patterns</h3>
          {patterns.length > 0 && (
            <span className="pattern-count">({patterns.length})</span>
          )}
        </div>
        <div className="header-controls" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={handleDetectPatterns}
            disabled={detecting}
            className="btn-detect"
          >
            {detecting ? '🔍 Detecting...' : '🔍 Detect Patterns'}
          </button>
        </div>
        <span className={`expand-icon ${isExpanded ? 'expanded' : ''}`}>▼</span>
      </div>

      {isExpanded && (
        <div className="patterns-body">


      {stats.total_patterns > 0 && (
        <div className="detection-stats">
          <div className="stat-badge">
            <span className="stat-label">Total:</span>
            <span className="stat-value">{stats.total_patterns}</span>
          </div>
          <div className="stat-badge bullish">
            <span className="stat-label">📈 Bullish:</span>
            <span className="stat-value">{stats.bullish_patterns}</span>
          </div>
          <div className="stat-badge bearish">
            <span className="stat-label">📉 Bearish:</span>
            <span className="stat-value">{stats.bearish_patterns}</span>
          </div>
        </div>
      )}

      {error && <div className="error-message">❌ {error}</div>}

      {loading && <div className="loading-message">Loading patterns...</div>}

      {!loading && patterns.length > 0 && (
        <>
          <div className="pattern-filters">
            <button
              className={`filter-btn ${filterType === 'all' ? 'active' : ''}`}
              onClick={() => setFilterType('all')}
            >
              All ({patterns.length})
            </button>
            <button
              className={`filter-btn ${filterType === 'bullish' ? 'active' : ''}`}
              onClick={() => setFilterType('bullish')}
            >
              📈 Bullish ({patterns.filter(p => p.pattern_type === 'bullish').length})
            </button>
            <button
              className={`filter-btn ${filterType === 'bearish' ? 'active' : ''}`}
              onClick={() => setFilterType('bearish')}
            >
              📉 Bearish ({patterns.filter(p => p.pattern_type === 'bearish').length})
            </button>
          </div>

          <div className="confirmation-stats">
            <span className="conf-stat pending">⏳ Pending: {pendingCount}</span>
            <span className="conf-stat confirmed">✅ Confirmed: {confirmedCount}</span>
            <span className="conf-stat rejected">❌ Rejected: {rejectedCount}</span>
          </div>

          <div className="patterns-list">
            {filteredPatterns.map(pattern => (
              <div
                key={pattern.id}
                className={`pattern-card ${pattern.user_confirmed === true ? 'confirmed' : pattern.user_confirmed === false ? 'rejected' : 'pending'}`}
              >
                <div className="pattern-card-header">
                  <div className="pattern-title">
                    <span className="pattern-icon">{getPatternIcon(pattern.pattern_type)}</span>
                    <h4>{pattern.pattern_name}</h4>
                    <span
                      className="pattern-type-badge"
                      style={{ backgroundColor: getPatternTypeColor(pattern.pattern_type) }}
                    >
                      {pattern.pattern_type}
                    </span>
                  </div>
                  <button
                    className="expand-btn"
                    onClick={() => setExpandedPattern(expandedPattern === pattern.id ? null : pattern.id)}
                  >
                    {expandedPattern === pattern.id ? '▼' : '▶'}
                  </button>
                </div>

                <div className="pattern-info">
                  <div className="info-item">
                    <span className="label">Date:</span>
                    <span className="value">{new Date(pattern.timestamp).toLocaleDateString()}</span>
                  </div>
                  <div className="info-item">
                    <span className="label">Confidence:</span>
                    <span className="value">{(pattern.confidence_score * 100).toFixed(0)}%</span>
                  </div>
                  {pattern.user_confirmed !== null && (
                    <div className="info-item">
                      <span className="label">Status:</span>
                      <span className={`status ${pattern.user_confirmed ? 'confirmed' : 'rejected'}`}>
                        {pattern.user_confirmed ? '✅ Confirmed' : '❌ Rejected'}
                      </span>
                    </div>
                  )}
                </div>

                {expandedPattern === pattern.id && (
                  <div className="pattern-details">
                    <div className="pattern-description">
                      <h5>Pattern Description:</h5>
                      <p>{getPatternDescription(pattern.pattern_name)}</p>
                    </div>
                    {pattern.candle_data && pattern.candle_data.candles && (
                      <div className="candle-data">
                        <h5>Candles ({pattern.candle_data.candles.length}):</h5>
                        <div className="candles-grid">
                          {pattern.candle_data.candles.slice(-3).map((candle, idx) => (
                            <div key={idx} className="mini-candle">
                              <div className="candle-date">
                                {new Date(candle.timestamp).toLocaleDateString()}
                              </div>
                              <div className="candle-prices">
                                <span>O: {candle.open?.toFixed(2)}</span>
                                <span>H: {candle.high?.toFixed(2)}</span>
                                <span>L: {candle.low?.toFixed(2)}</span>
                                <span>C: {candle.close?.toFixed(2)}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="pattern-actions">
                  {pattern.user_confirmed === null && (
                    <>
                      <button
                        className="btn-confirm"
                        onClick={() => handleConfirmPattern(pattern.id, true)}
                        title="Confirm this pattern is correct"
                      >
                        ✅ Confirm
                      </button>
                      <button
                        className="btn-reject"
                        onClick={() => handleConfirmPattern(pattern.id, false)}
                        title="Reject this pattern as incorrect"
                      >
                        ❌ Reject
                      </button>
                    </>
                  )}
                  <button
                    className="btn-delete"
                    onClick={() => handleDeletePattern(pattern.id)}
                    title="Delete this pattern"
                  >
                    🗑️ Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {!loading && patterns.length === 0 && (
        <div className="no-patterns">
          <p>No patterns detected yet.</p>
          <p>Click "Detect Patterns" to analyze candlestick patterns.</p>
        </div>
      )}
        </div>
      )}

      <style jsx>{`
        .candlestick-patterns {
          margin: 20px 0;
          background: white;
          border-radius: 8px;
          padding: 20px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .patterns-header {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          padding: 15px 20px;
          cursor: pointer;
          display: flex;
          justify-content: space-between;
          align-items: center;
          user-select: none;
          transition: all 0.3s;
          border-radius: 8px 8px 0 0;
        }

        .patterns-header:hover {
          background: linear-gradient(135deg, #5568d3 0%, #653a8b 100%);
        }

        .header-title {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .header-icon {
          font-size: 24px;
        }

        .patterns-header h3 {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
        }

        .pattern-count {
          font-size: 14px;
          opacity: 0.9;
          margin-left: 5px;
        }

        .header-controls {
          display: flex;
          gap: 10px;
        }

        .expand-icon {
          font-size: 16px;
          transition: transform 0.3s;
        }

        .expand-icon.expanded {
          transform: rotate(180deg);
        }

        .patterns-body {
          padding: 20px;
          background: #f9fafb;
        }

        .btn-detect {
          background: white;
          color: #764ba2;
          border: 2px solid white;
          padding: 8px 16px;
          border-radius: 5px;
          cursor: pointer;
          font-size: 14px;
          font-weight: 600;
          transition: all 0.3s;
        }

        .btn-detect:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(255, 255, 255, 0.4);
          background: #f8f9fa;
        }

        .btn-detect:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .detection-stats {
          display: flex;
          gap: 10px;
          margin-bottom: 15px;
        }

        .stat-badge {
          background: #f8f9fa;
          padding: 8px 16px;
          border-radius: 5px;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .stat-badge.bullish {
          background: #d4edda;
          color: #155724;
        }

        .stat-badge.bearish {
          background: #f8d7da;
          color: #721c24;
        }

        .stat-label {
          font-size: 13px;
          font-weight: 500;
        }

        .stat-value {
          font-size: 16px;
          font-weight: 700;
        }

        .pattern-filters {
          display: flex;
          gap: 10px;
          margin-bottom: 15px;
        }

        .filter-btn {
          background: #f8f9fa;
          border: 2px solid #ddd;
          padding: 8px 16px;
          border-radius: 5px;
          cursor: pointer;
          font-size: 13px;
          font-weight: 600;
          transition: all 0.2s;
        }

        .filter-btn:hover {
          border-color: #667eea;
          background: #f0f0f0;
        }

        .filter-btn.active {
          background: #667eea;
          color: white;
          border-color: #667eea;
        }

        .confirmation-stats {
          display: flex;
          gap: 15px;
          margin-bottom: 15px;
          font-size: 13px;
        }

        .conf-stat {
          padding: 4px 12px;
          border-radius: 4px;
          font-weight: 500;
        }

        .conf-stat.pending {
          background: #fff3cd;
          color: #856404;
        }

        .conf-stat.confirmed {
          background: #d4edda;
          color: #155724;
        }

        .conf-stat.rejected {
          background: #f8d7da;
          color: #721c24;
        }

        .patterns-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .pattern-card {
          background: white;
          border: 2px solid #e5e7eb;
          border-radius: 8px;
          padding: 15px;
          transition: all 0.3s;
        }

        .pattern-card.confirmed {
          border-color: #28a745;
          background: #f8fff9;
        }

        .pattern-card.rejected {
          border-color: #dc3545;
          background: #fff8f8;
        }

        .pattern-card.pending {
          border-color: #ffc107;
        }

        .pattern-card:hover {
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        .pattern-card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 10px;
        }

        .pattern-title {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .pattern-icon {
          font-size: 24px;
        }

        .pattern-title h4 {
          margin: 0;
          color: #333;
          font-size: 16px;
        }

        .pattern-type-badge {
          padding: 3px 10px;
          border-radius: 4px;
          color: white;
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
        }

        .expand-btn {
          background: #f0f0f0;
          border: none;
          padding: 5px 10px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
        }

        .expand-btn:hover {
          background: #e0e0e0;
        }

        .pattern-info {
          display: flex;
          gap: 20px;
          margin-bottom: 12px;
        }

        .info-item {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 13px;
        }

        .info-item .label {
          color: #666;
          font-weight: 500;
        }

        .info-item .value {
          color: #111;
          font-weight: 600;
        }

        .status.confirmed {
          color: #28a745;
        }

        .status.rejected {
          color: #dc3545;
        }

        .pattern-details {
          background: #f9fafb;
          border-radius: 6px;
          padding: 12px;
          margin-bottom: 12px;
        }

        .pattern-description h5 {
          margin: 0 0 8px 0;
          color: #333;
          font-size: 13px;
        }

        .pattern-description p {
          margin: 0;
          color: #666;
          font-size: 13px;
          line-height: 1.5;
        }

        .candle-data {
          margin-top: 12px;
        }

        .candle-data h5 {
          margin: 0 0 8px 0;
          color: #333;
          font-size: 13px;
        }

        .candles-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
          gap: 8px;
        }

        .mini-candle {
          background: white;
          border: 1px solid #ddd;
          border-radius: 4px;
          padding: 8px;
        }

        .candle-date {
          font-size: 11px;
          color: #666;
          margin-bottom: 4px;
          font-weight: 600;
        }

        .candle-prices {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 4px;
          font-size: 11px;
          color: #333;
        }

        .pattern-actions {
          display: flex;
          gap: 8px;
        }

        .pattern-actions button {
          padding: 6px 12px;
          border-radius: 4px;
          border: none;
          cursor: pointer;
          font-size: 12px;
          font-weight: 600;
          transition: all 0.2s;
        }

        .btn-confirm {
          background: #28a745;
          color: white;
        }

        .btn-confirm:hover {
          background: #218838;
        }

        .btn-reject {
          background: #dc3545;
          color: white;
        }

        .btn-reject:hover {
          background: #c82333;
        }

        .btn-delete {
          background: #6c757d;
          color: white;
        }

        .btn-delete:hover {
          background: #5a6268;
        }

        .error-message {
          background: #f8d7da;
          color: #721c24;
          padding: 12px;
          border-radius: 5px;
          margin-bottom: 15px;
        }

        .loading-message {
          text-align: center;
          padding: 40px;
          color: #666;
          font-size: 14px;
        }

        .no-patterns {
          text-align: center;
          padding: 40px;
          color: #666;
        }

        .no-patterns p {
          margin: 8px 0;
          font-size: 14px;
        }
      `}</style>
    </div>
  );
};

// Pattern descriptions
const getPatternDescription = (patternName) => {
  const descriptions = {
    'Hammer': 'Bullish reversal pattern with small body at top and long lower shadow. Indicates buyers pushed price up after sellers drove it down.',
    'Inverted Hammer': 'Bullish reversal with small body at bottom and long upper shadow. Shows buying pressure despite selling attempts.',
    'Bullish Marubozu': 'Strong bullish candle with large body and no shadows. Indicates very strong buying pressure.',
    'Dragonfly Doji': 'Bullish reversal with tiny body and long lower shadow. Shows rejection of lower prices.',
    'Bullish Engulfing': 'Large bullish candle completely engulfs previous bearish candle. Strong reversal signal.',
    'Piercing Line': 'Bullish candle closes above midpoint of previous bearish candle. Moderate bullish reversal.',
    'Tweezer Bottom': 'Two candles with matching lows. Indicates support level and potential reversal.',
    'Bullish Kicker': 'Gap up from bearish to bullish candle. Very strong bullish signal.',
    'Bullish Harami': 'Small bullish candle within previous bearish. Early sign of reversal.',
    'Bullish Counterattack': 'Bullish candle closes at same level as previous bearish. Shows buying pressure.',
    'Morning Star': 'Three-candle bullish reversal: bearish, small body, bullish. Strong reversal pattern.',
    'Morning Doji Star': 'Three-candle pattern with doji in middle. Very strong bullish reversal.',
    'Three White Soldiers': 'Three consecutive bullish candles with higher closes. Very strong uptrend signal.',
    'Three Inside Up': 'Bullish harami followed by bullish candle. Confirmed reversal pattern.',
    'Three Outside Up': 'Bullish engulfing followed by bullish candle. Strong confirmed reversal.',
    'Bullish Abandoned Baby': 'Rare pattern with doji gapping below trend. Very strong reversal.',
    'Rising Three Methods': 'Bullish continuation with small consolidation. Trend likely continues.',
    'Upside Tasuki Gap': 'Gap up with partial fill. Bullish continuation pattern.',
    'Mat Hold': 'Bullish continuation after consolidation. Strong uptrend resumption.',
    'Rising Window': 'Gap up between candles. Bullish continuation signal.',

    'Hanging Man': 'Bearish reversal at top of uptrend. Similar to hammer but bearish context.',
    'Shooting Star': 'Bearish reversal with small body and long upper shadow. Indicates rejection of higher prices.',
    'Bearish Marubozu': 'Strong bearish candle with large body and no shadows. Very strong selling pressure.',
    'Gravestone Doji': 'Bearish reversal with tiny body and long upper shadow. Shows rejection of higher prices.',
    'Bearish Engulfing': 'Large bearish candle engulfs previous bullish. Strong reversal signal.',
    'Dark Cloud Cover': 'Bearish candle closes below midpoint of previous bullish. Moderate bearish reversal.',
    'Tweezer Top': 'Two candles with matching highs. Indicates resistance and potential reversal.',
    'Bearish Kicker': 'Gap down from bullish to bearish. Very strong bearish signal.',
    'Bearish Harami': 'Small bearish candle within previous bullish. Early reversal sign.',
    'Bearish Counterattack': 'Bearish candle closes at same level as previous bullish. Shows selling pressure.',
    'Evening Star': 'Three-candle bearish reversal: bullish, small body, bearish. Strong reversal.',
    'Evening Doji Star': 'Three-candle pattern with doji. Very strong bearish reversal.',
    'Three Black Crows': 'Three consecutive bearish candles with lower closes. Very strong downtrend.',
    'Three Inside Down': 'Bearish harami followed by bearish candle. Confirmed reversal.',
    'Three Outside Down': 'Bearish engulfing followed by bearish candle. Strong confirmed reversal.',
    'Bearish Abandoned Baby': 'Rare pattern with doji gapping above trend. Very strong reversal.',
    'Falling Three Methods': 'Bearish continuation with small consolidation. Downtrend continues.',
    'Downside Tasuki Gap': 'Gap down with partial fill. Bearish continuation.',
    'On Neck Line': 'Weak bearish continuation. Small bounce at support.',
    'Falling Window': 'Gap down between candles. Bearish continuation signal.'
  };

  return descriptions[patternName] || 'Pattern detected in price action.';
};

export default CandlestickPatterns;
