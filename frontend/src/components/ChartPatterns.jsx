import React, { useState, useEffect } from 'react';
import { detectChartPatterns, getChartPatterns, confirmChartPattern, deleteChartPattern } from '../services/api';

const ChartPatterns = ({ stockId, symbol, onPatternsDetected }) => {
  const [patterns, setPatterns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({
    total_patterns: 0,
    reversal_patterns: 0,
    continuation_patterns: 0,
    bullish_count: 0,
    bearish_count: 0,
    neutral_count: 0
  });
  const [filterType, setFilterType] = useState('all'); // 'all', 'reversal', 'continuation'
  const [filterSignal, setFilterSignal] = useState('all'); // 'all', 'bullish', 'bearish', 'neutral'
  const [expandedPattern, setExpandedPattern] = useState(null);
  const [visiblePatterns, setVisiblePatterns] = useState(new Set()); // Track which patterns are visible on chart
  const [isExpanded, setIsExpanded] = useState(true); // Collapsible section state
  const [daysFilter, setDaysFilter] = useState(''); // Days filter for pattern detection/loading (empty = all)
  const [removeOverlaps, setRemoveOverlaps] = useState(true); // Remove overlapping patterns
  const [excludeRoundingPatterns, setExcludeRoundingPatterns] = useState(false); // Exclude Rounding Top/Bottom
  const [showAdvancedOptions, setShowAdvancedOptions] = useState(false); // Show/hide advanced options
  const [overlapThreshold, setOverlapThreshold] = useState(10); // Overlap threshold percentage (10% default)
  const [peakOrder, setPeakOrder] = useState(5); // Peak detection sensitivity
  const [minConfidence, setMinConfidence] = useState(0); // Minimum confidence (0 = disabled)
  const [minRSquared, setMinRSquared] = useState(0); // Minimum R² (0 = disabled)

  // Load patterns on mount
  useEffect(() => {
    loadPatterns();
  }, [stockId]);

  const loadPatterns = async () => {
    setLoading(true);
    setError(null);
    try {
      // Use daysFilter if specified, otherwise get all patterns
      const params = {};
      if (daysFilter && parseInt(daysFilter) > 0) {
        params.days = parseInt(daysFilter);
      }
      const data = await getChartPatterns(stockId, params);
      setPatterns(data.patterns);

      // No patterns visible initially - user must toggle them on
      setVisiblePatterns(new Set());

      // Pass empty array initially
      if (onPatternsDetected) {
        onPatternsDetected([]);
      }
    } catch (err) {
      console.error('Error loading chart patterns:', err);
      setError('Failed to load chart patterns');
    } finally {
      setLoading(false);
    }
  };

  const togglePatternVisibility = (patternId) => {
    setVisiblePatterns(prev => {
      const newSet = new Set(prev);
      if (newSet.has(patternId)) {
        newSet.delete(patternId);
      } else {
        newSet.add(patternId);
      }

      // Pass only visible patterns to parent for chart visualization
      if (onPatternsDetected) {
        const visiblePatternsList = patterns.filter(p => newSet.has(p.id));
        console.log('[ChartPatterns] Toggling pattern visibility:', patternId);
        console.log('[ChartPatterns] Visible patterns count:', visiblePatternsList.length);
        console.log('[ChartPatterns] Visible patterns:', visiblePatternsList);
        onPatternsDetected(visiblePatternsList);
      }

      return newSet;
    });
  };

  const handleDetectPatterns = async () => {
    setDetecting(true);
    setError(null);
    try {
      // Use daysFilter if specified, otherwise detect in all available data
      const days = daysFilter && parseInt(daysFilter) > 0 ? parseInt(daysFilter) : null;

      // Build exclude patterns list
      const excludePatterns = [];
      if (excludeRoundingPatterns) {
        excludePatterns.push('Rounding Top', 'Rounding Bottom');
      }

      const result = await detectChartPatterns(
        stockId,
        days,
        20,
        removeOverlaps,
        excludePatterns,
        overlapThreshold / 100, // Convert percentage to decimal
        peakOrder,
        minConfidence / 100, // Convert percentage to decimal
        minRSquared / 100 // Convert percentage to decimal
      );
      setStats({
        total_patterns: result.total_patterns,
        reversal_patterns: result.reversal_patterns,
        continuation_patterns: result.continuation_patterns,
        bullish_count: result.bullish_count,
        bearish_count: result.bearish_count,
        neutral_count: result.neutral_count
      });

      // Reload patterns from database
      await loadPatterns();
    } catch (err) {
      console.error('Error detecting chart patterns:', err);
      setError(err.response?.data?.detail || 'Failed to detect chart patterns');
    } finally {
      setDetecting(false);
    }
  };

  const handleConfirmPattern = async (patternId, confirmed) => {
    try {
      await confirmChartPattern(patternId, confirmed, '', 'user');

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
      await deleteChartPattern(patternId);
      setPatterns(prev => prev.filter(p => p.id !== patternId));
    } catch (err) {
      console.error('Error deleting pattern:', err);
      alert('Failed to delete pattern');
    }
  };

  const getSignalColor = (signal) => {
    switch (signal) {
      case 'bullish': return '#28a745';
      case 'bearish': return '#dc3545';
      case 'neutral': return '#6c757d';
      default: return '#6c757d';
    }
  };

  const getSignalIcon = (signal) => {
    switch (signal) {
      case 'bullish': return '📈';
      case 'bearish': return '📉';
      case 'neutral': return '➖';
      default: return '❓';
    }
  };

  const getTypeColor = (type) => {
    switch (type) {
      case 'reversal': return '#f39c12';
      case 'continuation': return '#3498db';
      default: return '#95a5a6';
    }
  };

  const filteredPatterns = patterns.filter(p => {
    if (filterType !== 'all' && p.pattern_type !== filterType) return false;
    if (filterSignal !== 'all' && p.signal !== filterSignal) return false;
    return true;
  });

  const pendingCount = patterns.filter(p => p.user_confirmed === null).length;
  const confirmedCount = patterns.filter(p => p.user_confirmed === true).length;
  const rejectedCount = patterns.filter(p => p.user_confirmed === false).length;

  return (
    <div className="chart-patterns">
      <div className="patterns-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="header-title">
          <span className="header-icon">📊</span>
          <h3>Chart Patterns</h3>
          {patterns.length > 0 && (
            <span className="pattern-count">({patterns.length})</span>
          )}
        </div>
        <div className="header-controls" onClick={(e) => e.stopPropagation()}>
          <div className="days-filter-group">
            <label htmlFor="days-input">Days:</label>
            <input
              id="days-input"
              type="number"
              min="30"
              max="3650"
              placeholder="All"
              value={daysFilter}
              onChange={(e) => setDaysFilter(e.target.value)}
              className="days-input"
              title="Number of days to analyze (leave empty for all data)"
            />
            <button
              onClick={loadPatterns}
              disabled={loading}
              className="btn-refresh"
              title="Refresh patterns with current days filter"
            >
              🔄
            </button>
          </div>
          <button
            onClick={handleDetectPatterns}
            disabled={detecting}
            className="btn-detect"
          >
            {detecting ? '🔍 Detecting...' : '🔍 Detect Chart Patterns'}
          </button>
        </div>
        <span className={`expand-icon ${isExpanded ? 'expanded' : ''}`}>▼</span>
      </div>

      {isExpanded && (
        <div className="patterns-body">

      {/* Advanced Options */}
      <div className="advanced-options-section">
        <button
          className="toggle-advanced-btn"
          onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
        >
          {showAdvancedOptions ? '▼' : '▶'} Advanced Options
        </button>

        {showAdvancedOptions && (
          <div className="advanced-options">
            <div className="options-grid">
              <div className="option-section">
                <h4>Pattern Filtering</h4>
                <div className="option-item">
                  <label>
                    <input
                      type="checkbox"
                      checked={removeOverlaps}
                      onChange={(e) => setRemoveOverlaps(e.target.checked)}
                    />
                    Remove overlapping patterns
                  </label>
                </div>
                {removeOverlaps && (
                  <div className="option-item slider-item">
                    <label>
                      Overlap threshold: {overlapThreshold}%
                      <input
                        type="range"
                        min="5"
                        max="50"
                        value={overlapThreshold}
                        onChange={(e) => setOverlapThreshold(parseInt(e.target.value))}
                        className="slider"
                      />
                    </label>
                    <span className="slider-hint">Lower = more patterns kept</span>
                  </div>
                )}
                <div className="option-item">
                  <label>
                    <input
                      type="checkbox"
                      checked={excludeRoundingPatterns}
                      onChange={(e) => setExcludeRoundingPatterns(e.target.checked)}
                    />
                    Exclude Rounding Top/Bottom
                  </label>
                </div>
              </div>

              <div className="option-section">
                <h4>Detection Sensitivity</h4>
                <div className="option-item slider-item">
                  <label>
                    Peak sensitivity: {peakOrder}
                    <input
                      type="range"
                      min="3"
                      max="12"
                      value={peakOrder}
                      onChange={(e) => setPeakOrder(parseInt(e.target.value))}
                      className="slider"
                    />
                  </label>
                  <span className="slider-hint">Lower = more peaks detected</span>
                </div>
              </div>

              <div className="option-section">
                <h4>Quality Thresholds</h4>
                <div className="option-item slider-item">
                  <label>
                    Min confidence: {minConfidence}%
                    <input
                      type="range"
                      min="0"
                      max="80"
                      step="5"
                      value={minConfidence}
                      onChange={(e) => setMinConfidence(parseInt(e.target.value))}
                      className="slider"
                    />
                  </label>
                  <span className="slider-hint">0 = no minimum</span>
                </div>
                <div className="option-item slider-item">
                  <label>
                    Min trendline R²: {minRSquared}%
                    <input
                      type="range"
                      min="0"
                      max="90"
                      step="5"
                      value={minRSquared}
                      onChange={(e) => setMinRSquared(parseInt(e.target.value))}
                      className="slider"
                    />
                  </label>
                  <span className="slider-hint">0 = no minimum</span>
                </div>
              </div>
            </div>

            <div className="apply-note">
              ⚠️ After changing these options, click "🔍 Detect Chart Patterns" to apply the changes
            </div>
            <div className="info-text">
              💡 For training data collection: Use low thresholds (10% overlap, peak 5, no quality minimums) to get many pattern candidates.
              Then manually confirm/reject them to build your ML dataset.
            </div>
          </div>
        )}
      </div>

      {stats.total_patterns > 0 && (
        <div className="detection-stats">
          <div className="stat-badge">
            <span className="stat-label">Total:</span>
            <span className="stat-value">{stats.total_patterns}</span>
          </div>
          <div className="stat-badge reversal">
            <span className="stat-label">🔄 Reversal:</span>
            <span className="stat-value">{stats.reversal_patterns}</span>
          </div>
          <div className="stat-badge continuation">
            <span className="stat-label">➡️ Continuation:</span>
            <span className="stat-value">{stats.continuation_patterns}</span>
          </div>
          <div className="stat-badge bullish">
            <span className="stat-label">📈 Bullish:</span>
            <span className="stat-value">{stats.bullish_count}</span>
          </div>
          <div className="stat-badge bearish">
            <span className="stat-label">📉 Bearish:</span>
            <span className="stat-value">{stats.bearish_count}</span>
          </div>
        </div>
      )}

      {error && <div className="error-message">❌ {error}</div>}

      {loading && <div className="loading-message">Loading chart patterns...</div>}

      {!loading && patterns.length > 0 && (
        <>
          <div className="pattern-filters">
            <div className="filter-group">
              <label>Type:</label>
              <button
                className={`filter-btn ${filterType === 'all' ? 'active' : ''}`}
                onClick={() => setFilterType('all')}
              >
                All
              </button>
              <button
                className={`filter-btn ${filterType === 'reversal' ? 'active' : ''}`}
                onClick={() => setFilterType('reversal')}
              >
                🔄 Reversal
              </button>
              <button
                className={`filter-btn ${filterType === 'continuation' ? 'active' : ''}`}
                onClick={() => setFilterType('continuation')}
              >
                ➡️ Continuation
              </button>
            </div>
            <div className="filter-group">
              <label>Signal:</label>
              <button
                className={`filter-btn ${filterSignal === 'all' ? 'active' : ''}`}
                onClick={() => setFilterSignal('all')}
              >
                All
              </button>
              <button
                className={`filter-btn ${filterSignal === 'bullish' ? 'active' : ''}`}
                onClick={() => setFilterSignal('bullish')}
              >
                📈 Bullish
              </button>
              <button
                className={`filter-btn ${filterSignal === 'bearish' ? 'active' : ''}`}
                onClick={() => setFilterSignal('bearish')}
              >
                📉 Bearish
              </button>
              <button
                className={`filter-btn ${filterSignal === 'neutral' ? 'active' : ''}`}
                onClick={() => setFilterSignal('neutral')}
              >
                ➖ Neutral
              </button>
            </div>
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
                    <span className="pattern-icon">{getSignalIcon(pattern.signal)}</span>
                    <h4>{pattern.pattern_name}</h4>
                    <span
                      className="pattern-type-badge"
                      style={{ backgroundColor: getTypeColor(pattern.pattern_type) }}
                    >
                      {pattern.pattern_type}
                    </span>
                    <span
                      className="signal-badge"
                      style={{ backgroundColor: getSignalColor(pattern.signal) }}
                    >
                      {pattern.signal}
                    </span>
                  </div>
                  <div className="card-controls">
                    <button
                      className={`visibility-btn ${visiblePatterns.has(pattern.id) ? 'visible' : 'hidden'}`}
                      onClick={() => togglePatternVisibility(pattern.id)}
                      title={visiblePatterns.has(pattern.id) ? 'Hide pattern on chart' : 'Show pattern on chart'}
                    >
                      {visiblePatterns.has(pattern.id) ? '👁️' : '👁️‍🗨️'}
                    </button>
                    <button
                      className="expand-btn"
                      onClick={() => setExpandedPattern(expandedPattern === pattern.id ? null : pattern.id)}
                    >
                      {expandedPattern === pattern.id ? '▼' : '▶'}
                    </button>
                  </div>
                </div>

                <div className="pattern-info">
                  <div className="info-item">
                    <span className="label">Start:</span>
                    <span className="value">{new Date(pattern.start_date).toLocaleDateString()}</span>
                  </div>
                  <div className="info-item">
                    <span className="label">End:</span>
                    <span className="value">{new Date(pattern.end_date).toLocaleDateString()}</span>
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

                    <div className="price-levels">
                      <h5>Key Price Levels:</h5>
                      <div className="levels-grid">
                        {pattern.breakout_price && (
                          <div className="level-item">
                            <span className="level-label">Breakout:</span>
                            <span className="level-value">${parseFloat(pattern.breakout_price).toFixed(2)}</span>
                          </div>
                        )}
                        {pattern.target_price && (
                          <div className="level-item">
                            <span className="level-label">Target:</span>
                            <span className="level-value target">${parseFloat(pattern.target_price).toFixed(2)}</span>
                          </div>
                        )}
                        {pattern.stop_loss && (
                          <div className="level-item">
                            <span className="level-label">Stop Loss:</span>
                            <span className="level-value stop">${parseFloat(pattern.stop_loss).toFixed(2)}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {pattern.key_points && Object.keys(pattern.key_points).length > 0 && (
                      <div className="key-points">
                        <h5>Key Points:</h5>
                        <div className="points-list">
                          {Object.entries(pattern.key_points).map(([key, value]) => (
                            <div key={key} className="point-item">
                              <span className="point-label">{key}:</span>
                              <span className="point-value">
                                {typeof value === 'object' ? JSON.stringify(value) : value}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {pattern.trendlines && Object.keys(pattern.trendlines).length > 0 && (
                      <div className="trendlines-info">
                        <h5>Trendlines:</h5>
                        <div className="trendlines-list">
                          {Object.entries(pattern.trendlines).map(([key, value]) => (
                            <div key={key} className="trendline-item">
                              <span className="trendline-label">{key}:</span>
                              <span className="trendline-value">
                                {typeof value === 'object' ?
                                  `slope: ${value.slope?.toFixed(4)}, r²: ${value.r_squared?.toFixed(3)}` :
                                  value}
                              </span>
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
          <p>No chart patterns detected yet.</p>
          <p>Click "Detect Chart Patterns" to analyze for Head & Shoulders, Triangles, Cup & Handle, etc.</p>
        </div>
      )}
        </div>
      )}

      <style jsx>{`
        .chart-patterns {
          margin: 20px 0;
          background: white;
          border-radius: 8px;
          padding: 20px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .patterns-header {
          background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
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
          background: linear-gradient(135deg, #e08e0b 0%, #cf6e1a 100%);
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
          align-items: center;
        }

        .days-filter-group {
          display: flex;
          align-items: center;
          gap: 6px;
          background: rgba(255, 255, 255, 0.9);
          padding: 5px 10px;
          border-radius: 5px;
        }

        .days-filter-group label {
          font-size: 13px;
          font-weight: 600;
          color: #e67e22;
          margin: 0;
        }

        .days-input {
          width: 80px;
          padding: 6px 8px;
          border: 2px solid #e67e22;
          border-radius: 4px;
          font-size: 13px;
          font-weight: 600;
          color: #333;
          background: white;
        }

        .days-input:focus {
          outline: none;
          border-color: #d35400;
          box-shadow: 0 0 0 3px rgba(230, 126, 34, 0.1);
        }

        .days-input::placeholder {
          color: #999;
          font-weight: normal;
        }

        .btn-refresh {
          background: #f39c12;
          color: white;
          border: 2px solid #f39c12;
          padding: 6px 10px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
          transition: all 0.3s;
        }

        .btn-refresh:hover:not(:disabled) {
          background: #e08e0b;
          border-color: #e08e0b;
          transform: translateY(-1px);
        }

        .btn-refresh:disabled {
          opacity: 0.6;
          cursor: not-allowed;
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

        .advanced-options-section {
          margin-bottom: 15px;
          background: white;
          border-radius: 6px;
          border: 1px solid #e5e7eb;
        }

        .toggle-advanced-btn {
          width: 100%;
          text-align: left;
          padding: 10px 15px;
          background: white;
          border: none;
          cursor: pointer;
          font-size: 13px;
          font-weight: 600;
          color: #666;
          transition: all 0.2s;
          border-radius: 6px;
        }

        .toggle-advanced-btn:hover {
          background: #f9fafb;
          color: #333;
        }

        .advanced-options {
          padding: 15px;
          border-top: 1px solid #e5e7eb;
          background: #f9fafb;
        }

        .options-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 20px;
          margin-bottom: 15px;
        }

        .option-section {
          background: white;
          padding: 12px;
          border-radius: 6px;
          border: 1px solid #e5e7eb;
        }

        .option-section h4 {
          margin: 0 0 10px 0;
          font-size: 13px;
          font-weight: 700;
          color: #f39c12;
          border-bottom: 2px solid #f39c12;
          padding-bottom: 5px;
        }

        .option-item {
          margin-bottom: 12px;
        }

        .option-item label {
          display: flex;
          flex-direction: column;
          gap: 6px;
          font-size: 13px;
          color: #333;
          cursor: pointer;
          font-weight: 600;
        }

        .option-item input[type="checkbox"] {
          width: 16px;
          height: 16px;
          cursor: pointer;
          margin-right: 8px;
        }

        .slider-item label {
          cursor: default;
        }

        .slider {
          width: 100%;
          height: 6px;
          border-radius: 3px;
          background: #e5e7eb;
          outline: none;
          cursor: pointer;
        }

        .slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 16px;
          height: 16px;
          border-radius: 50%;
          background: #f39c12;
          cursor: pointer;
        }

        .slider::-moz-range-thumb {
          width: 16px;
          height: 16px;
          border-radius: 50%;
          background: #f39c12;
          cursor: pointer;
          border: none;
        }

        .slider-hint {
          font-size: 11px;
          color: #666;
          font-weight: normal;
          font-style: italic;
        }

        .apply-note {
          margin: 12px 0 8px 0;
          padding: 10px;
          background: #fff3cd;
          border-left: 3px solid #f39c12;
          border-radius: 4px;
          font-size: 12px;
          color: #856404;
          line-height: 1.5;
          font-weight: 600;
        }

        .info-text {
          margin-top: 8px;
          padding: 10px;
          background: #e7f3ff;
          border-left: 3px solid #3498db;
          border-radius: 4px;
          font-size: 12px;
          color: #0c5460;
          line-height: 1.5;
        }

        .btn-detect {
          background: white;
          color: #e67e22;
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
          flex-wrap: wrap;
        }

        .stat-badge {
          background: #f8f9fa;
          padding: 8px 16px;
          border-radius: 5px;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .stat-badge.reversal {
          background: #fff3cd;
          color: #856404;
        }

        .stat-badge.continuation {
          background: #d1ecf1;
          color: #0c5460;
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
          flex-direction: column;
          gap: 10px;
          margin-bottom: 15px;
        }

        .filter-group {
          display: flex;
          gap: 10px;
          align-items: center;
        }

        .filter-group label {
          font-size: 13px;
          font-weight: 600;
          color: #666;
          min-width: 50px;
        }

        .filter-btn {
          background: #f8f9fa;
          border: 2px solid #ddd;
          padding: 6px 14px;
          border-radius: 5px;
          cursor: pointer;
          font-size: 12px;
          font-weight: 600;
          transition: all 0.2s;
        }

        .filter-btn:hover {
          border-color: #f39c12;
          background: #f0f0f0;
        }

        .filter-btn.active {
          background: #f39c12;
          color: white;
          border-color: #f39c12;
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
          border-color: #f39c12;
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

        .pattern-type-badge, .signal-badge {
          padding: 3px 10px;
          border-radius: 4px;
          color: white;
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
        }

        .card-controls {
          display: flex;
          gap: 8px;
          align-items: center;
        }

        .visibility-btn {
          background: #f0f0f0;
          border: none;
          padding: 5px 10px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 18px;
          transition: all 0.2s;
        }

        .visibility-btn:hover {
          background: #e0e0e0;
          transform: scale(1.1);
        }

        .visibility-btn.visible {
          background: #d4edda;
          border: 1px solid #28a745;
        }

        .visibility-btn.hidden {
          opacity: 0.5;
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
          flex-wrap: wrap;
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

        .pattern-description h5,
        .price-levels h5,
        .key-points h5,
        .trendlines-info h5 {
          margin: 0 0 8px 0;
          color: #333;
          font-size: 13px;
          font-weight: 700;
        }

        .pattern-description p {
          margin: 0;
          color: #666;
          font-size: 13px;
          line-height: 1.5;
        }

        .price-levels,
        .key-points,
        .trendlines-info {
          margin-top: 12px;
        }

        .levels-grid {
          display: flex;
          gap: 15px;
          flex-wrap: wrap;
        }

        .level-item {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .level-label {
          font-size: 11px;
          color: #666;
          font-weight: 600;
        }

        .level-value {
          font-size: 14px;
          color: #333;
          font-weight: 700;
        }

        .level-value.target {
          color: #28a745;
        }

        .level-value.stop {
          color: #dc3545;
        }

        .points-list,
        .trendlines-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .point-item,
        .trendline-item {
          display: flex;
          gap: 8px;
          font-size: 12px;
        }

        .point-label,
        .trendline-label {
          color: #666;
          font-weight: 600;
          min-width: 100px;
        }

        .point-value,
        .trendline-value {
          color: #333;
          font-family: monospace;
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

// Chart pattern descriptions
const getPatternDescription = (patternName) => {
  const descriptions = {
    // Reversal Patterns
    'Head and Shoulders': 'A bearish reversal pattern with three peaks: left shoulder, head (highest), and right shoulder. Forms after an uptrend. Neckline breakout confirms the pattern. Target: Height of head projected downward from neckline.',

    'Inverse Head and Shoulders': 'A bullish reversal pattern with three troughs: left shoulder, head (lowest), and right shoulder. Forms after a downtrend. Neckline breakout confirms. Target: Height of head projected upward from neckline.',

    'Double Top': 'Bearish reversal with two peaks at similar price levels, separated by a trough. Forms after uptrend. Breakdown below support confirms. Target: Height of peaks to trough projected downward.',

    'Double Bottom': 'Bullish reversal with two troughs at similar price levels, separated by a peak. Forms after downtrend. Breakout above resistance confirms. Target: Height of trough to peak projected upward.',

    // Triangle Patterns
    'Ascending Triangle': 'Bullish continuation pattern with horizontal resistance and rising support. Shows accumulation. Breakout above resistance expected. Target: Height of triangle at widest point projected upward.',

    'Descending Triangle': 'Bearish continuation pattern with horizontal support and falling resistance. Shows distribution. Breakdown below support expected. Target: Height of triangle projected downward.',

    'Symmetrical Triangle': 'Neutral consolidation with converging trendlines. Breakout direction determines bias. Usually continues prior trend. Target: Height at base projected in breakout direction.',

    // Continuation Patterns
    'Cup and Handle': 'Bullish continuation resembling a teacup. Rounded bottom (cup) followed by small consolidation (handle). Breakout above handle resistance continues uptrend. Target: Cup depth projected upward.',

    'Flag': 'Brief consolidation in steep trend, forming rectangular channel against trend direction. Bullish/bearish flags continue prior trend. Quick pattern formation (1-3 weeks). Target: Flagpole height projected.',

    'Pennant': 'Similar to flag but forms small symmetrical triangle. Brief consolidation after strong move. Continues prior trend. Forms within 1-3 weeks. Target: Pennant pole height projected in trend direction.',

    'Rising Wedge': 'Bearish reversal/continuation with converging upward trendlines. Both support and resistance rising but converging. Usually breaks downward. Shows weakening momentum despite rising prices.',

    'Falling Wedge': 'Bullish reversal/continuation with converging downward trendlines. Both support and resistance falling but converging. Usually breaks upward. Shows weakening selling pressure.'
  };

  return descriptions[patternName] || 'Chart pattern detected in price action. Represents potential trend continuation or reversal based on historical price movements and trendline analysis.';
};

export default ChartPatterns;
