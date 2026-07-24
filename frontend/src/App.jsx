import React, { useState, useEffect } from 'react';
import StockList from './components/StockList';
import PaperTradingLedger from './components/PaperTradingLedger';
import GADashboard from './components/GADashboard';
import MarketStatus from './components/MarketStatus';
import { checkHealth } from './services/api';
import './App.css';

function App() {
  const [healthStatus, setHealthStatus] = useState(null);
  const [view, setView] = useState('stocks'); // 'stocks' | 'ledger' | 'ga'

  useEffect(() => {
    // Check API health on load
    const fetchHealth = async () => {
      try {
        const health = await checkHealth();
        setHealthStatus(health);
      } catch (error) {
        console.error('Health check failed:', error);
        setHealthStatus({ status: 'error', message: 'Cannot connect to API' });
      }
    };
    fetchHealth();
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <div className="header-top">
          <h1>Stock Analyzer</h1>
          <div className="view-toggle">
            <button
              className={`view-btn ${view === 'stocks' ? 'active' : ''}`}
              onClick={() => setView('stocks')}
            >
              📈 Stocks
            </button>
            <button
              className={`view-btn ${view === 'ledger' ? 'active' : ''}`}
              onClick={() => setView('ledger')}
            >
              📒 Paper Trading
            </button>
            <button
              className={`view-btn ${view === 'ga' ? 'active' : ''}`}
              onClick={() => setView('ga')}
            >
              🧬 GA Lab
            </button>
          </div>
          <div className="health-status">
            {healthStatus && (
              <span className={`status ${healthStatus.status}`}>
                API Status: {healthStatus.status}
                {healthStatus.database && ` | DB: ${healthStatus.database}`}
              </span>
            )}
          </div>
        </div>

        {/* Market Status Bar */}
        <div className="market-status-container">
          <MarketStatus />
        </div>
      </header>

      <main className="App-main">
        <div className="container">
          {view === 'ledger' ? (
            <section className="stocks-section">
              <PaperTradingLedger />
            </section>
          ) : view === 'ga' ? (
            <section className="stocks-section">
              <GADashboard />
            </section>
          ) : (
            <section className="stocks-section">
              <StockList />
            </section>
          )}

          <section className="info">
              <h3>Project Team</h3>
              <ul>
                  <li>
                      <strong>[Jakub Charvat]</strong>
                      <p>Role: Lead Developer</p>
                      <p>Connect: <a href="[https://github.com/Charvi99]">GitHub</a> | <a href="mailto:[jakubcharvat99@gmail.com]">Email</a></p>
                  </li>
                  <li>
                      <strong>[Claude AI]</strong>
                      <p>Ultra developer</p>
                      <p>Connect: <a href="[https://claude.ai/new]">Claude page</a></p>
                  </li>
                  {/* Add more list items for each co-creator */}
                </ul>
            </section>
        </div>
      </main>
    </div>
  );
}

export default App;
