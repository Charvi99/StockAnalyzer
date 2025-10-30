import React, { useState } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const PortfolioHeatMonitor = () => {
  const [calculating, setCalculating] = useState(false);
  const [heatData, setHeatData] = useState(null);
  const [error, setError] = useState(null);

  // Input parameters
  const [accountCapital, setAccountCapital] = useState(10000);
  const [maxHeatPercent, setMaxHeatPercent] = useState(6.0);
  const [positions, setPositions] = useState([
    { id: 1, symbol: 'AAPL', entry_price: 150, stop_loss: 145, position_size: 10 },
    { id: 2, symbol: 'GOOGL', entry_price: 140, stop_loss: 136, position_size: 8 },
  ]);

  const addPosition = () => {
    setPositions([
      ...positions,
      { id: Date.now(), symbol: '', entry_price: 0, stop_loss: 0, position_size: 0 }
    ]);
  };

  const removePosition = (id) => {
    setPositions(positions.filter(p => p.id !== id));
  };

  const updatePosition = (id, field, value) => {
    setPositions(positions.map(p =>
      p.id === id ? { ...p, [field]: value } : p
    ));
  };

  const calculateHeat = async () => {
    try {
      setCalculating(true);
      setError(null);

      // Filter out empty positions
      const validPositions = positions.filter(p =>
        p.entry_price > 0 && p.stop_loss > 0 && p.position_size > 0
      );

      if (validPositions.length === 0) {
        setError('Please add at least one valid position');
        setCalculating(false);
        return;
      }

      const response = await axios.post(
        `${API_URL}/api/v1/portfolio/risk`,
        {
          open_positions: validPositions.map(p => ({
            entry_price: p.entry_price,
            stop_loss: p.stop_loss,
            position_size: p.position_size
          })),
          account_capital: accountCapital,
          max_portfolio_heat_percent: maxHeatPercent
        }
      );

      setHeatData(response.data);
    } catch (err) {
      console.error('Error calculating portfolio heat:', err);
      setError(err.response?.data?.detail || 'Failed to calculate portfolio heat');
    } finally {
      setCalculating(false);
    }
  };

  const getHeatColor = (heatPercent, maxPercent) => {
    const ratio = heatPercent / maxPercent;
    if (ratio >= 0.9) return '#ef4444'; // Red - danger
    if (ratio >= 0.7) return '#f59e0b'; // Amber - warning
    if (ratio >= 0.5) return '#3b82f6'; // Blue - caution
    return '#10b981'; // Green - safe
  };

  const getHeatStatus = (heatPercent, maxPercent) => {
    const ratio = heatPercent / maxPercent;
    if (ratio >= 0.9) return { text: 'DANGER', icon: '🔴' };
    if (ratio >= 0.7) return { text: 'WARNING', icon: '⚠️' };
    if (ratio >= 0.5) return { text: 'CAUTION', icon: '🟡' };
    return { text: 'SAFE', icon: '✅' };
  };

  return (
    <div className="portfolio-heat-monitor">
      <h3>🔥 Portfolio Heat Monitor</h3>
      <p className="subtitle">Track total risk across ALL your open positions (not just this stock)</p>

      {/* Info Box - What is this? */}
      <div className="info-box-phm">
        <div className="info-icon-phm">ℹ️</div>
        <div className="info-content-phm">
          <div className="info-title-phm">What does this do?</div>
          <p>
            <strong>Prevents over-leveraging by tracking total risk across your entire portfolio.</strong> Add all your open positions
            (from any stocks) to see if you're risking too much. Professional traders keep total risk under 6% of capital.
          </p>
          <p><strong>Example:</strong> With $10,000 capital and 6% max heat, you can risk up to $600 total. If you have 3 positions
          risking $150 each ($450 total), you still have $150 capacity for new trades.</p>
        </div>
      </div>

      {/* Account Settings */}
      <div className="settings-section">
        <div className="input-group">
          <label>Account Capital ($)</label>
          <input
            type="number"
            value={accountCapital}
            onChange={(e) => setAccountCapital(parseFloat(e.target.value) || 10000)}
            min="100"
            step="1000"
          />
        </div>
        <div className="input-group">
          <label>Max Heat Allowed (%)</label>
          <input
            type="number"
            value={maxHeatPercent}
            onChange={(e) => setMaxHeatPercent(parseFloat(e.target.value) || 6.0)}
            min="1"
            max="20"
            step="0.5"
          />
        </div>
      </div>

      {/* Positions List */}
      <div className="positions-section">
        <div className="positions-header">
          <h4>Open Positions ({positions.length})</h4>
          <button onClick={addPosition} className="add-btn">+ Add Position</button>
        </div>

        {/* Column Headers */}
        {positions.length > 0 && (
          <div className="position-headers">
            <div className="header-number">#</div>
            <div className="header-label">Symbol</div>
            <div className="header-label">Entry $</div>
            <div className="header-label">Stop $</div>
            <div className="header-label">Shares</div>
            <div className="header-spacer"></div>
          </div>
        )}

        <div className="positions-list">
          {positions.map((position, index) => (
            <div key={position.id} className="position-row">
              <div className="position-number">{index + 1}</div>
              <input
                type="text"
                placeholder="AAPL"
                value={position.symbol}
                onChange={(e) => updatePosition(position.id, 'symbol', e.target.value)}
                className="input-symbol"
                title="Stock symbol (e.g., AAPL, TSLA)"
              />
              <input
                type="number"
                placeholder="150.00"
                value={position.entry_price || ''}
                onChange={(e) => updatePosition(position.id, 'entry_price', parseFloat(e.target.value) || 0)}
                className="input-price"
                title="Your entry price"
              />
              <input
                type="number"
                placeholder="145.00"
                value={position.stop_loss || ''}
                onChange={(e) => updatePosition(position.id, 'stop_loss', parseFloat(e.target.value) || 0)}
                className="input-price"
                title="Your stop-loss price"
              />
              <input
                type="number"
                placeholder="10"
                value={position.position_size || ''}
                onChange={(e) => updatePosition(position.id, 'position_size', parseInt(e.target.value) || 0)}
                className="input-size"
                title="Number of shares"
              />
              <button
                onClick={() => removePosition(position.id)}
                className="remove-btn"
                title="Remove this position"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>

      <button
        onClick={calculateHeat}
        disabled={calculating}
        className="calculate-btn"
      >
        {calculating ? 'Calculating...' : '🔥 Calculate Portfolio Heat'}
      </button>

      {error && (
        <div className="error-message">
          <strong>Error:</strong> {error}
        </div>
      )}

      {heatData && (
        <div className="results-section">
          {/* Heat Gauge */}
          <div className="heat-gauge-card">
            <div className="gauge-header">
              <div className="gauge-title">Portfolio Heat</div>
              <div className="gauge-subtitle">
                {getHeatStatus(heatData.portfolio_heat_percent, heatData.max_allowed_heat_percent).icon}
                {' '}
                {getHeatStatus(heatData.portfolio_heat_percent, heatData.max_allowed_heat_percent).text}
              </div>
            </div>

            <div className="heat-value" style={{
              color: getHeatColor(heatData.portfolio_heat_percent, heatData.max_allowed_heat_percent)
            }}>
              {heatData.portfolio_heat_percent.toFixed(2)}%
            </div>

            <div className="heat-bar">
              <div
                className="heat-fill"
                style={{
                  width: `${Math.min((heatData.portfolio_heat_percent / heatData.max_allowed_heat_percent) * 100, 100)}%`,
                  background: getHeatColor(heatData.portfolio_heat_percent, heatData.max_allowed_heat_percent)
                }}
              ></div>
            </div>

            <div className="heat-range">
              <span>0%</span>
              <span className="max-marker">Max: {heatData.max_allowed_heat_percent}%</span>
              <span>20%</span>
            </div>
          </div>

          {/* Risk Metrics */}
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-icon">💵</div>
              <div className="metric-content">
                <div className="metric-label">Total Risk Amount</div>
                <div className="metric-value">${heatData.total_risk_amount.toFixed(2)}</div>
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-icon">📊</div>
              <div className="metric-content">
                <div className="metric-label">Positions at Risk</div>
                <div className="metric-value">{heatData.positions_at_risk}</div>
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-icon">
                {heatData.can_add_position ? '✅' : '🚫'}
              </div>
              <div className="metric-content">
                <div className="metric-label">Can Add Position?</div>
                <div className="metric-value">
                  {heatData.can_add_position ? 'YES' : 'NO'}
                </div>
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-icon">💰</div>
              <div className="metric-content">
                <div className="metric-label">Remaining Capacity</div>
                <div className="metric-value">${heatData.remaining_risk_capacity.toFixed(2)}</div>
              </div>
            </div>
          </div>

          {/* Warning */}
          {!heatData.can_add_position && (
            <div className="warning-card">
              <div className="warning-icon">⚠️</div>
              <div className="warning-content">
                <div className="warning-title">Portfolio Heat Too High!</div>
                <div className="warning-text">
                  You cannot add more positions. Close existing positions or increase your account capital.
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <style jsx>{`
        .portfolio-heat-monitor {
          background: white;
          border-radius: 12px;
          padding: 20px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .portfolio-heat-monitor h3 {
          margin: 0 0 8px 0;
          font-size: 18px;
          color: #111827;
        }

        .subtitle {
          margin: 0 0 20px 0;
          font-size: 13px;
          color: #6b7280;
        }

        .settings-section {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          margin-bottom: 20px;
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

        .positions-section {
          background: #f9fafb;
          padding: 16px;
          border-radius: 8px;
          margin-bottom: 16px;
        }

        .positions-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }

        .positions-header h4 {
          margin: 0;
          font-size: 14px;
          color: #374151;
        }

        .position-headers {
          display: grid;
          grid-template-columns: 30px 80px 80px 80px 60px 40px;
          gap: 8px;
          padding: 8px;
          background: #e5e7eb;
          border-radius: 6px;
          margin-bottom: 8px;
        }

        .header-number,
        .header-label {
          font-size: 11px;
          font-weight: 700;
          color: #374151;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .header-spacer {
          width: 40px;
        }

        .info-box-phm {
          background: #eff6ff;
          padding: 12px;
          border-radius: 8px;
          border: 1px solid #bfdbfe;
          margin-bottom: 16px;
          display: flex;
          gap: 12px;
        }

        .info-icon-phm {
          font-size: 24px;
          flex-shrink: 0;
        }

        .info-content-phm {
          flex: 1;
        }

        .info-title-phm {
          font-size: 13px;
          font-weight: 700;
          color: #1e40af;
          margin-bottom: 6px;
        }

        .info-content-phm p {
          font-size: 12px;
          color: #1e3a8a;
          line-height: 1.5;
          margin: 0 0 6px 0;
        }

        .info-content-phm p:last-child {
          margin-bottom: 0;
        }

        .add-btn {
          padding: 6px 12px;
          background: #10b981;
          color: white;
          border: none;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .add-btn:hover {
          background: #059669;
        }

        .positions-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .position-row {
          display: grid;
          grid-template-columns: 30px 80px 80px 80px 60px 40px;
          gap: 8px;
          align-items: center;
          background: white;
          padding: 8px;
          border-radius: 6px;
        }

        .position-number {
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
        }

        .position-row input {
          padding: 6px 8px;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          font-size: 12px;
        }

        .input-symbol {
          text-transform: uppercase;
          font-weight: 600;
        }

        .remove-btn {
          width: 28px;
          height: 28px;
          background: #ef4444;
          color: white;
          border: none;
          border-radius: 4px;
          font-size: 18px;
          font-weight: 700;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s;
        }

        .remove-btn:hover {
          background: #dc2626;
        }

        .calculate-btn {
          width: 100%;
          padding: 12px 16px;
          background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
          color: white;
          border: none;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          margin-bottom: 16px;
        }

        .calculate-btn:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
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

        .heat-gauge-card {
          background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
          padding: 24px;
          border-radius: 12px;
          color: white;
        }

        .gauge-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }

        .gauge-title {
          font-size: 14px;
          opacity: 0.9;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          font-weight: 600;
        }

        .gauge-subtitle {
          font-size: 13px;
          font-weight: 700;
          opacity: 0.95;
        }

        .heat-value {
          font-size: 48px;
          font-weight: 800;
          margin-bottom: 16px;
          text-align: center;
        }

        .heat-bar {
          width: 100%;
          height: 12px;
          background: rgba(255, 255, 255, 0.2);
          border-radius: 6px;
          overflow: hidden;
          margin-bottom: 8px;
        }

        .heat-fill {
          height: 100%;
          transition: width 0.5s ease, background 0.3s ease;
          border-radius: 6px;
        }

        .heat-range {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
          opacity: 0.7;
        }

        .max-marker {
          font-weight: 700;
          opacity: 1;
        }

        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
        }

        .metric-card {
          background: #f9fafb;
          padding: 16px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .metric-icon {
          font-size: 28px;
        }

        .metric-content {
          flex: 1;
        }

        .metric-label {
          font-size: 11px;
          color: #6b7280;
          margin-bottom: 4px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          font-weight: 600;
        }

        .metric-value {
          font-size: 18px;
          font-weight: 700;
          color: #111827;
        }

        .warning-card {
          background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
          padding: 16px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          gap: 16px;
          border-left: 4px solid #f59e0b;
        }

        .warning-icon {
          font-size: 32px;
        }

        .warning-content {
          flex: 1;
        }

        .warning-title {
          font-size: 16px;
          font-weight: 700;
          color: #92400e;
          margin-bottom: 4px;
        }

        .warning-text {
          font-size: 13px;
          color: #92400e;
        }
      `}</style>
    </div>
  );
};

export default PortfolioHeatMonitor;
