import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const OrderCalculator = ({ stockId, symbol }) => {
  const [calculating, setCalculating] = useState(false);
  const [orderData, setOrderData] = useState(null);
  const [error, setError] = useState(null);
  const [accountSize, setAccountSize] = useState(10000);
  const [riskPercentage, setRiskPercentage] = useState(2.0);

  const calculateOrder = useCallback(async () => {
    try {
      setCalculating(true);
      setError(null);

      const response = await axios.post(
        `${API_URL}/api/v1/stocks/${stockId}/order-calculator`,
        null,
        {
          params: {
            account_size: accountSize,
            risk_percentage: riskPercentage
          }
        }
      );

      setOrderData(response.data);
    } catch (err) {
      console.error('Error calculating order:', err);
      setError(err.response?.data?.detail || 'Failed to calculate order parameters');
    } finally {
      setCalculating(false);
    }
  }, [stockId, accountSize, riskPercentage]);

  useEffect(() => {
    if (stockId) {
      calculateOrder();
    }
  }, [stockId, calculateOrder]);

  const getRecommendationColor = (rec) => {
    if (rec === 'BUY') return '#10b981';
    if (rec === 'SELL') return '#ef4444';
    return '#f59e0b';
  };

  const getRiskRewardColor = (ratio) => {
    if (ratio >= 2.0) return '#10b981'; // Green
    if (ratio >= 1.5) return '#f59e0b'; // Yellow
    return '#ef4444'; // Red
  };

  return (
    <div className="order-calculator">
      <h3>📊 Order Calculator</h3>

      {/* Input Parameters */}
      <div className="calculator-inputs">
        <div className="input-group">
          <label>Account Size ($)</label>
          <input
            type="number"
            value={accountSize}
            onChange={(e) => setAccountSize(parseFloat(e.target.value) || 10000)}
            min="100"
            max="10000000"
            step="1000"
          />
        </div>
        <div className="input-group">
          <label>Risk per Trade (%)</label>
          <input
            type="number"
            value={riskPercentage}
            onChange={(e) => setRiskPercentage(parseFloat(e.target.value) || 2.0)}
            min="0.5"
            max="10"
            step="0.5"
          />
        </div>
        <button
          onClick={calculateOrder}
          disabled={calculating}
          className="calculate-btn"
        >
          {calculating ? 'Calculating...' : 'Recalculate'}
        </button>
      </div>

      {error && (
        <div className="calculator-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      {orderData && (
        <div className="order-results">
          {/* Recommendation Badge */}
          <div
            className="recommendation-badge"
            style={{ backgroundColor: getRecommendationColor(orderData.recommendation) }}
          >
            <div className="rec-signal">{orderData.recommendation}</div>
            <div className="rec-confidence">{(orderData.confidence * 100).toFixed(0)}% confidence</div>
          </div>

          {/* Price Levels */}
          <div className="price-levels">
            <div className="level-item current">
              <span className="level-label">Current Price</span>
              <span className="level-value">${orderData.current_price.toFixed(2)}</span>
            </div>
            <div className="level-item entry">
              <span className="level-label">Entry Price</span>
              <span className="level-value">${orderData.entry_price.toFixed(2)}</span>
            </div>
            <div className="level-item stop-loss">
              <span className="level-label">Stop Loss</span>
              <span className="level-value">
                ${orderData.stop_loss.toFixed(2)}
                <span className="percentage">({orderData.stop_loss_percentage}%)</span>
              </span>
            </div>
            <div className="level-item take-profit">
              <span className="level-label">Take Profit</span>
              <span className="level-value">
                ${orderData.take_profit.toFixed(2)}
                <span className="percentage">({orderData.take_profit_percentage}%)</span>
              </span>
            </div>
          </div>

          {/* Risk/Reward & Position Sizing */}
          <div className="position-info">
            <div className="info-card">
              <div className="info-label">Risk/Reward Ratio</div>
              <div
                className="info-value large"
                style={{ color: getRiskRewardColor(orderData.risk_reward_ratio) }}
              >
                {orderData.risk_reward_ratio.toFixed(2)}:1
              </div>
            </div>
            <div className="info-card">
              <div className="info-label">Position Size</div>
              <div className="info-value">{orderData.position_size.toFixed(2)} shares</div>
            </div>
            <div className="info-card">
              <div className="info-label">Position Value</div>
              <div className="info-value">${orderData.position_value.toFixed(2)}</div>
            </div>
            <div className="info-card">
              <div className="info-label">Risk Amount</div>
              <div className="info-value risk">${orderData.risk_amount.toFixed(2)}</div>
            </div>
          </div>

          {/* Support/Resistance */}
          {(orderData.nearest_support || orderData.nearest_resistance) && (
            <div className="support-resistance">
              {orderData.nearest_support && (
                <div className="sr-level support">
                  <span className="sr-label">Support</span>
                  <span className="sr-value">${orderData.nearest_support.toFixed(2)}</span>
                </div>
              )}
              {orderData.nearest_resistance && (
                <div className="sr-level resistance">
                  <span className="sr-label">Resistance</span>
                  <span className="sr-value">${orderData.nearest_resistance.toFixed(2)}</span>
                </div>
              )}
              {orderData.atr && (
                <div className="sr-level atr">
                  <span className="sr-label">ATR</span>
                  <span className="sr-value">${orderData.atr.toFixed(2)}</span>
                </div>
              )}
            </div>
          )}

          {/* Position Warnings */}
          {orderData.position_warnings && orderData.position_warnings.length > 0 && (
            <div className="warnings-section">
              <div className="warnings-title">⚠️ Position Warnings:</div>
              <ul className="warnings-list">
                {orderData.position_warnings.map((warning, idx) => (
                  <li key={idx}>{warning}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Reasoning */}
          {orderData.reasoning && orderData.reasoning.length > 0 && (
            <div className="reasoning">
              <div className="reasoning-title">Calculation Method:</div>
              <ul className="reasoning-list">
                {orderData.reasoning.map((reason, idx) => (
                  <li key={idx}>{reason}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <style jsx>{`
        .order-calculator {
          background: white;
          border-radius: 12px;
          padding: 20px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .order-calculator h3 {
          margin: 0 0 20px 0;
          font-size: 18px;
          color: #111827;
        }

        .calculator-inputs {
          display: grid;
          grid-template-columns: 1fr 1fr auto;
          gap: 12px;
          margin-bottom: 20px;
          align-items: end;
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

        .input-group input {
          padding: 8px 12px;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          font-size: 14px;
        }

        .calculate-btn {
          padding: 8px 16px;
          background: #667eea;
          color: white;
          border: none;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .calculate-btn:hover:not(:disabled) {
          background: #5568d3;
        }

        .calculate-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .calculator-error {
          background: #fee2e2;
          border: 1px solid #fecaca;
          color: #dc2626;
          padding: 12px;
          border-radius: 8px;
          margin-bottom: 16px;
          font-size: 14px;
        }

        .order-results {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .recommendation-badge {
          text-align: center;
          padding: 16px;
          border-radius: 8px;
          color: white;
        }

        .rec-signal {
          font-size: 24px;
          font-weight: 800;
          letter-spacing: 2px;
        }

        .rec-confidence {
          font-size: 14px;
          opacity: 0.9;
          margin-top: 4px;
        }

        .price-levels {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
        }

        .level-item {
          background: #f9fafb;
          padding: 12px;
          border-radius: 8px;
          border-left: 4px solid #d1d5db;
        }

        .level-item.current {
          border-left-color: #6b7280;
        }

        .level-item.entry {
          border-left-color: #3b82f6;
        }

        .level-item.stop-loss {
          border-left-color: #ef4444;
        }

        .level-item.take-profit {
          border-left-color: #10b981;
        }

        .level-label {
          display: block;
          font-size: 11px;
          color: #6b7280;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 4px;
        }

        .level-value {
          display: block;
          font-size: 18px;
          font-weight: 700;
          color: #111827;
        }

        .percentage {
          font-size: 12px;
          font-weight: 500;
          color: #6b7280;
          margin-left: 6px;
        }

        .position-info {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
        }

        .info-card {
          background: #f9fafb;
          padding: 12px;
          border-radius: 8px;
          text-align: center;
        }

        .info-label {
          font-size: 11px;
          color: #6b7280;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 6px;
        }

        .info-value {
          font-size: 16px;
          font-weight: 700;
          color: #111827;
        }

        .info-value.large {
          font-size: 24px;
        }

        .info-value.risk {
          color: #ef4444;
        }

        .support-resistance {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
          padding: 12px;
          background: #f9fafb;
          border-radius: 8px;
        }

        .sr-level {
          text-align: center;
        }

        .sr-label {
          display: block;
          font-size: 10px;
          color: #6b7280;
          font-weight: 600;
          text-transform: uppercase;
          margin-bottom: 4px;
        }

        .sr-value {
          display: block;
          font-size: 14px;
          font-weight: 700;
        }

        .sr-level.support .sr-value {
          color: #10b981;
        }

        .sr-level.resistance .sr-value {
          color: #ef4444;
        }

        .sr-level.atr .sr-value {
          color: #667eea;
        }

        .warnings-section {
          background: #fef3c7;
          padding: 12px;
          border-radius: 8px;
          border-left: 4px solid #f59e0b;
        }

        .warnings-title {
          font-size: 12px;
          font-weight: 700;
          color: #92400e;
          margin-bottom: 8px;
        }

        .warnings-list {
          margin: 0;
          padding-left: 20px;
          font-size: 13px;
          color: #92400e;
          line-height: 1.6;
        }

        .warnings-list li {
          margin-bottom: 4px;
        }

        .reasoning {
          background: #f9fafb;
          padding: 12px;
          border-radius: 8px;
          border-left: 4px solid #667eea;
        }

        .reasoning-title {
          font-size: 12px;
          font-weight: 600;
          color: #374151;
          margin-bottom: 8px;
        }

        .reasoning-list {
          margin: 0;
          padding-left: 20px;
          font-size: 13px;
          color: #6b7280;
          line-height: 1.6;
        }

        .reasoning-list li {
          margin-bottom: 4px;
        }
      `}</style>
    </div>
  );
};

export default OrderCalculator;
