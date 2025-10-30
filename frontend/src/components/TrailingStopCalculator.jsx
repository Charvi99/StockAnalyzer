import React, { useState } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const TrailingStopCalculator = ({ stockId, symbol, currentPrice }) => {
  const [calculating, setCalculating] = useState(false);
  const [trailingData, setTrailingData] = useState(null);
  const [error, setError] = useState(null);

  // Input parameters
  const [entryPrice, setEntryPrice] = useState(currentPrice || 0);
  const [direction, setDirection] = useState('long');
  const [atrMultiplier, setAtrMultiplier] = useState(1.0);

  const calculateTrailingStop = async () => {
    try {
      setCalculating(true);
      setError(null);

      const response = await axios.post(
        `${API_URL}/api/v1/stocks/${stockId}/trailing-stop`,
        null,
        {
          params: {
            entry_price: entryPrice,
            current_price: currentPrice,
            direction: direction,
            trailing_atr_multiplier: atrMultiplier
          }
        }
      );

      setTrailingData(response.data);
    } catch (err) {
      console.error('Error calculating trailing stop:', err);
      setError(err.response?.data?.detail || 'Failed to calculate trailing stop');
    } finally {
      setCalculating(false);
    }
  };

  const getRecommendationInfo = (rec) => {
    const recommendations = {
      'move_stop_to_breakeven': {
        icon: '↗️',
        text: 'Move Stop to Breakeven',
        color: '#3b82f6',
        desc: 'Price moved 1.5 ATR in your favor - protect capital'
      },
      'consider_partial_profit': {
        icon: '💰',
        text: 'Consider Partial Profit',
        color: '#10b981',
        desc: 'Price moved 3 ATR in your favor - take some profits'
      }
    };

    return recommendations[rec] || null;
  };

  const getProfitColor = (profit) => {
    if (profit > 0) return '#10b981';
    if (profit < 0) return '#ef4444';
    return '#6b7280';
  };

  return (
    <div className="trailing-stop-calculator">
      <h3>🎯 Trailing Stop Calculator</h3>
      <p className="subtitle">Protect your profits with ATR-based trailing stops</p>

      {/* Info Box - What is this? */}
      <div className="info-box-ts">
        <div className="info-icon-ts">ℹ️</div>
        <div className="info-content-ts">
          <div className="info-title-ts">What does this do?</div>
          <p>
            <strong>Trailing stops follow price upward but never move down.</strong> This locks in profits as your trade moves in your favor,
            while giving the stock room to breathe. Enter your position details to see where your stop should be.
          </p>
          <p><strong>Example:</strong> You bought at $100, price is now $110. The trailing stop might be at $107 -
          giving you $7/share profit protection while allowing normal volatility.</p>
        </div>
      </div>

      {/* Input Parameters */}
      <div className="calculator-inputs">
        <div className="input-row">
          <div className="input-group">
            <label>Entry Price ($)</label>
            <input
              type="number"
              value={entryPrice}
              onChange={(e) => setEntryPrice(parseFloat(e.target.value) || 0)}
              step="0.01"
            />
          </div>
          <div className="input-group">
            <label>Current Price ($)</label>
            <input
              type="number"
              value={currentPrice}
              disabled
              className="disabled-input"
            />
          </div>
        </div>

        <div className="input-row">
          <div className="input-group">
            <label>Direction</label>
            <select value={direction} onChange={(e) => setDirection(e.target.value)}>
              <option value="long">Long</option>
              <option value="short">Short</option>
            </select>
          </div>
          <div className="input-group">
            <label>ATR Multiplier</label>
            <input
              type="number"
              value={atrMultiplier}
              onChange={(e) => setAtrMultiplier(parseFloat(e.target.value) || 1.0)}
              min="0.5"
              max="3"
              step="0.1"
            />
          </div>
        </div>

        <button
          onClick={calculateTrailingStop}
          disabled={calculating}
          className="calculate-btn"
        >
          {calculating ? 'Calculating...' : '🎯 Calculate Trailing Stop'}
        </button>
      </div>

      {error && (
        <div className="error-message">
          <strong>Error:</strong> {error}
        </div>
      )}

      {trailingData && (
        <div className="results-section">
          {/* Trailing Stop Level */}
          <div className="result-card primary">
            <div className="card-icon">📍</div>
            <div className="card-content">
              <div className="card-label">Trailing Stop Level</div>
              <div className="card-value">${trailingData.trailing_stop}</div>
              <div className="card-subtitle">
                Place your stop-loss here to lock in profits
              </div>
            </div>
          </div>

          {/* Profit & ATR Info */}
          <div className="info-grid">
            <div className="info-card">
              <div className="info-label">Current Profit</div>
              <div
                className="info-value"
                style={{ color: getProfitColor(trailingData.profit) }}
              >
                ${trailingData.profit.toFixed(2)}
              </div>
              <div className="info-progress">
                {trailingData.profit > 0 ? '📈' : trailingData.profit < 0 ? '📉' : '➖'}
              </div>
            </div>

            <div className="info-card">
              <div className="info-label">Profit in ATRs</div>
              <div className="info-value">
                {trailingData.profit_atr_multiple.toFixed(2)}x
              </div>
              <div className="info-progress">
                {trailingData.profit_atr_multiple >= 3 ? '🔥' :
                 trailingData.profit_atr_multiple >= 1.5 ? '⚡' : '💤'}
              </div>
            </div>

            <div className="info-card">
              <div className="info-label">Current ATR</div>
              <div className="info-value">${trailingData.atr.toFixed(2)}</div>
              <div className="info-progress">📊</div>
            </div>
          </div>

          {/* Recommendation */}
          {trailingData.recommendation && (
            <div className="recommendation-card">
              {(() => {
                const recInfo = getRecommendationInfo(trailingData.recommendation);
                return (
                  <>
                    <div className="rec-icon">{recInfo.icon}</div>
                    <div className="rec-content">
                      <div className="rec-title" style={{ color: recInfo.color }}>
                        {recInfo.text}
                      </div>
                      <div className="rec-desc">{recInfo.desc}</div>
                    </div>
                  </>
                );
              })()}
            </div>
          )}

          {/* Visual Guide */}
          <div className="visual-guide">
            <div className="guide-title">How Trailing Stops Work:</div>
            <div className="guide-steps">
              <div className="guide-step">
                <div className="step-number">1</div>
                <div className="step-text">
                  <strong>As price rises</strong>, the trailing stop follows {atrMultiplier}x ATR below
                </div>
              </div>
              <div className="guide-step">
                <div className="step-number">2</div>
                <div className="step-text">
                  <strong>If price falls</strong>, the stop stays fixed (never moves down)
                </div>
              </div>
              <div className="guide-step">
                <div className="step-number">3</div>
                <div className="step-text">
                  <strong>Locks in profits</strong> automatically without being too tight
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .trailing-stop-calculator {
          background: white;
          border-radius: 12px;
          padding: 20px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .trailing-stop-calculator h3 {
          margin: 0 0 8px 0;
          font-size: 18px;
          color: #111827;
        }

        .subtitle {
          margin: 0 0 20px 0;
          font-size: 13px;
          color: #6b7280;
        }

        .calculator-inputs {
          display: flex;
          flex-direction: column;
          gap: 12px;
          margin-bottom: 20px;
        }

        .input-row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }

        .input-group {
          display: flex;
          flex-direction: column;
        }

        .input-group label {
          font-size: 12px;
          color: #6b7280;
          margin-bottom: 4px;
          font-weight: 500;
        }

        .input-group input,
        .input-group select {
          padding: 8px 12px;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          font-size: 14px;
        }

        .disabled-input {
          background: #f3f4f6;
          color: #6b7280;
          cursor: not-allowed;
        }

        .calculate-btn {
          padding: 10px 16px;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          border: none;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .calculate-btn:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }

        .calculate-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .error-message {
          background: #fee2e2;
          border: 1px solid #fecaca;
          color: #dc2626;
          padding: 12px;
          border-radius: 8px;
          margin-bottom: 16px;
          font-size: 14px;
        }

        .results-section {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .result-card.primary {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          padding: 20px;
          border-radius: 12px;
          display: flex;
          align-items: center;
          gap: 16px;
          color: white;
        }

        .card-icon {
          font-size: 36px;
          line-height: 1;
        }

        .card-content {
          flex: 1;
        }

        .card-label {
          font-size: 12px;
          opacity: 0.9;
          margin-bottom: 4px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          font-weight: 600;
        }

        .card-value {
          font-size: 32px;
          font-weight: 800;
          margin-bottom: 4px;
        }

        .card-subtitle {
          font-size: 13px;
          opacity: 0.85;
        }

        .info-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
        }

        .info-card {
          background: #f9fafb;
          padding: 16px;
          border-radius: 8px;
          text-align: center;
        }

        .info-label {
          font-size: 11px;
          color: #6b7280;
          margin-bottom: 8px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          font-weight: 600;
        }

        .info-value {
          font-size: 20px;
          font-weight: 700;
          color: #111827;
          margin-bottom: 4px;
        }

        .info-progress {
          font-size: 18px;
        }

        .recommendation-card {
          background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
          padding: 16px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          gap: 16px;
          border-left: 4px solid #f59e0b;
        }

        .rec-icon {
          font-size: 32px;
        }

        .rec-content {
          flex: 1;
        }

        .rec-title {
          font-size: 16px;
          font-weight: 700;
          margin-bottom: 4px;
        }

        .rec-desc {
          font-size: 13px;
          color: #92400e;
        }

        .visual-guide {
          background: #f9fafb;
          padding: 16px;
          border-radius: 8px;
          border: 1px solid #e5e7eb;
        }

        .guide-title {
          font-size: 13px;
          font-weight: 600;
          color: #374151;
          margin-bottom: 12px;
        }

        .guide-steps {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .guide-step {
          display: flex;
          align-items: flex-start;
          gap: 12px;
        }

        .step-number {
          width: 24px;
          height: 24px;
          background: #667eea;
          color: white;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 12px;
          font-weight: 700;
          flex-shrink: 0;
        }

        .step-text {
          font-size: 13px;
          color: #4b5563;
          line-height: 1.6;
        }

        .step-text strong {
          color: #111827;
        }

        .info-box-ts {
          background: #eff6ff;
          padding: 12px;
          border-radius: 8px;
          border: 1px solid #bfdbfe;
          margin-bottom: 16px;
          display: flex;
          gap: 12px;
        }

        .info-icon-ts {
          font-size: 24px;
          flex-shrink: 0;
        }

        .info-content-ts {
          flex: 1;
        }

        .info-title-ts {
          font-size: 13px;
          font-weight: 700;
          color: #1e40af;
          margin-bottom: 6px;
        }

        .info-content-ts p {
          font-size: 12px;
          color: #1e3a8a;
          line-height: 1.5;
          margin: 0 0 6px 0;
        }

        .info-content-ts p:last-child {
          margin-bottom: 0;
        }
      `}</style>
    </div>
  );
};

export default TrailingStopCalculator;
