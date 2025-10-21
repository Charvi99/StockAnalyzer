import React, { useState, useEffect } from 'react';
import { executeStrategy, backtestStrategy, executeAllStrategies, listStrategies } from '../services/api';
import './TradingStrategies.css';

const TradingStrategies = ({ stockId }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [strategies, setStrategies] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [strategyResult, setStrategyResult] = useState(null);
  const [backtestResult, setBacktestResult] = useState(null);
  const [consensusResult, setConsensusResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('execute'); // 'execute', 'backtest', 'consensus'

  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    try {
      const response = await listStrategies();
      setStrategies(response.strategies || []);
      if (response.strategies && response.strategies.length > 0) {
        setSelectedStrategy(response.strategies[0].name);
      }
    } catch (err) {
      console.error('Error loading strategies:', err);
      setError('Failed to load strategies');
    }
  };

  const handleExecuteStrategy = async () => {
    if (!selectedStrategy) return;

    setLoading(true);
    setError(null);
    setStrategyResult(null);

    try {
      const result = await executeStrategy(stockId, {
        strategy_name: selectedStrategy
      });
      setStrategyResult(result);
    } catch (err) {
      console.error('Error executing strategy:', err);
      setError('Failed to execute strategy');
    } finally {
      setLoading(false);
    }
  };

  const handleBacktest = async () => {
    if (!selectedStrategy) return;

    setLoading(true);
    setError(null);
    setBacktestResult(null);

    try {
      const result = await backtestStrategy(stockId, {
        strategy_name: selectedStrategy,
        initial_balance: 10000
      });
      setBacktestResult(result);
    } catch (err) {
      console.error('Error running backtest:', err);
      setError('Failed to run backtest');
    } finally {
      setLoading(false);
    }
  };

  const handleExecuteAll = async () => {
    setLoading(true);
    setError(null);
    setConsensusResult(null);

    try {
      const result = await executeAllStrategies(stockId);
      setConsensusResult(result);
    } catch (err) {
      console.error('Error executing all strategies:', err);
      setError('Failed to execute all strategies');
    } finally {
      setLoading(false);
    }
  };

  const getSignalClass = (signal) => {
    if (!signal) return '';
    switch (signal.toUpperCase()) {
      case 'BUY':
        return 'signal-buy';
      case 'SELL':
        return 'signal-sell';
      case 'HOLD':
        return 'signal-hold';
      default:
        return '';
    }
  };

  const getSignalEmoji = (signal) => {
    if (!signal) return '';
    switch (signal.toUpperCase()) {
      case 'BUY':
        return '📈';
      case 'SELL':
        return '📉';
      case 'HOLD':
        return '⏸️';
      default:
        return '';
    }
  };

  const renderStrategySelector = () => (
    <div className="strategy-selector">
      <label>Select Strategy:</label>
      <select
        value={selectedStrategy || ''}
        onChange={(e) => setSelectedStrategy(e.target.value)}
        disabled={loading}
      >
        {strategies.map((strategy) => (
          <option key={strategy.name} value={strategy.name}>
            {strategy.name}
          </option>
        ))}
      </select>
      {selectedStrategy && (
        <div className="strategy-description">
          {strategies.find(s => s.name === selectedStrategy)?.description}
        </div>
      )}
    </div>
  );

  const renderExecuteTab = () => (
    <div className="strategy-tab-content">
      {renderStrategySelector()}

      <button
        className="execute-button"
        onClick={handleExecuteStrategy}
        disabled={loading || !selectedStrategy}
      >
        {loading ? 'Executing...' : 'Execute Strategy'}
      </button>

      {strategyResult && (
        <div className="strategy-result">
          <div className={`signal-box ${getSignalClass(strategyResult.signal)}`}>
            <div className="signal-header">
              <span className="signal-emoji">{getSignalEmoji(strategyResult.signal)}</span>
              <span className="signal-text">{strategyResult.signal}</span>
            </div>
            <div className="confidence-bar">
              <div
                className="confidence-fill"
                style={{ width: `${strategyResult.confidence * 100}%` }}
              />
              <span className="confidence-text">
                Confidence: {(strategyResult.confidence * 100).toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="result-details">
            <h4>Details:</h4>
            {strategyResult.details?.entry_price && (
              <div className="detail-item">
                <span className="detail-label">Entry Price:</span>
                <span className="detail-value">${strategyResult.details.entry_price}</span>
              </div>
            )}
            {strategyResult.details?.stop_loss && (
              <div className="detail-item">
                <span className="detail-label">Stop Loss:</span>
                <span className="detail-value">${strategyResult.details.stop_loss}</span>
              </div>
            )}
            {strategyResult.details?.take_profit && (
              <div className="detail-item">
                <span className="detail-label">Take Profit:</span>
                <span className="detail-value">${strategyResult.details.take_profit}</span>
              </div>
            )}
            {strategyResult.details?.reason && (
              <div className="detail-item full-width">
                <span className="detail-label">Reason:</span>
                <span className="detail-value">{strategyResult.details.reason}</span>
              </div>
            )}

            {/* Show all other details */}
            {Object.entries(strategyResult.details || {}).map(([key, value]) => {
              if (['entry_price', 'exit_price', 'stop_loss', 'take_profit', 'reason'].includes(key)) {
                return null;
              }
              return (
                <div key={key} className="detail-item">
                  <span className="detail-label">{key.replace(/_/g, ' ')}:</span>
                  <span className="detail-value">
                    {typeof value === 'number' ? value.toFixed(2) : value}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );

  const renderBacktestTab = () => (
    <div className="strategy-tab-content">
      {renderStrategySelector()}

      <button
        className="execute-button"
        onClick={handleBacktest}
        disabled={loading || !selectedStrategy}
      >
        {loading ? 'Running Backtest...' : 'Run Backtest'}
      </button>

      {backtestResult && (
        <div className="backtest-result">
          <div className="backtest-summary">
            <div className="summary-item">
              <span className="summary-label">Total Return:</span>
              <span className={`summary-value ${backtestResult.total_return >= 0 ? 'positive' : 'negative'}`}>
                {backtestResult.total_return >= 0 ? '+' : ''}{backtestResult.total_return?.toFixed(2)}%
              </span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Total Trades:</span>
              <span className="summary-value">{backtestResult.total_trades}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Win Rate:</span>
              <span className="summary-value">{backtestResult.win_rate?.toFixed(1)}%</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Max Drawdown:</span>
              <span className="summary-value negative">{backtestResult.max_drawdown?.toFixed(2)}%</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Winning Trades:</span>
              <span className="summary-value positive">{backtestResult.winning_trades}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Losing Trades:</span>
              <span className="summary-value negative">{backtestResult.losing_trades}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Final Balance:</span>
              <span className="summary-value">${backtestResult.final_balance?.toFixed(2)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderConsensusTab = () => (
    <div className="strategy-tab-content">
      <button
        className="execute-button"
        onClick={handleExecuteAll}
        disabled={loading}
      >
        {loading ? 'Executing All Strategies...' : 'Execute All Strategies'}
      </button>

      {consensusResult && (
        <div className="consensus-result">
          <div className={`consensus-box ${getSignalClass(consensusResult.consensus)}`}>
            <h4>Consensus Signal</h4>
            <div className="consensus-signal">
              <span className="signal-emoji">{getSignalEmoji(consensusResult.consensus)}</span>
              <span className="signal-text">{consensusResult.consensus}</span>
            </div>
            <div className="signal-counts">
              <div className="count-item buy">
                <span>BUY: {consensusResult.signal_counts?.buy}</span>
              </div>
              <div className="count-item hold">
                <span>HOLD: {consensusResult.signal_counts?.hold}</span>
              </div>
              <div className="count-item sell">
                <span>SELL: {consensusResult.signal_counts?.sell}</span>
              </div>
            </div>
          </div>

          <div className="individual-results">
            <h4>Individual Strategy Results:</h4>
            {consensusResult.results?.map((result, index) => (
              <div key={index} className={`individual-result ${getSignalClass(result.signal)}`}>
                <div className="result-header">
                  <span className="strategy-name">{result.strategy_name}</span>
                  <span className="signal-badge">
                    {getSignalEmoji(result.signal)} {result.signal}
                  </span>
                </div>
                {result.confidence && (
                  <div className="confidence-mini">
                    Confidence: {(result.confidence * 100).toFixed(1)}%
                  </div>
                )}
                {result.details?.reason && (
                  <div className="result-reason">{result.details.reason}</div>
                )}
                {result.error && (
                  <div className="result-error">Error: {result.error}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="trading-strategies-container">
      <div className="strategies-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="header-title">
          <span className="header-icon">🎯</span>
          <h3>Trading Strategies</h3>
          {strategies.length > 0 && (
            <span className="strategy-count">({strategies.length} available)</span>
          )}
        </div>
        <span className={`expand-icon ${isExpanded ? 'expanded' : ''}`}>▼</span>
      </div>

      {isExpanded && (
        <div className="strategies-body">
          {error && <div className="error-message">{error}</div>}

          <div className="strategy-tabs">
            <button
              className={`tab-button ${activeTab === 'execute' ? 'active' : ''}`}
              onClick={() => setActiveTab('execute')}
            >
              Execute Strategy
            </button>
            <button
              className={`tab-button ${activeTab === 'backtest' ? 'active' : ''}`}
              onClick={() => setActiveTab('backtest')}
            >
              Backtest
            </button>
            <button
              className={`tab-button ${activeTab === 'consensus' ? 'active' : ''}`}
              onClick={() => setActiveTab('consensus')}
            >
              Consensus
            </button>
          </div>

          <div className="tab-content">
            {activeTab === 'execute' && renderExecuteTab()}
            {activeTab === 'backtest' && renderBacktestTab()}
            {activeTab === 'consensus' && renderConsensusTab()}
          </div>
        </div>
      )}
    </div>
  );
};

export default TradingStrategies;
