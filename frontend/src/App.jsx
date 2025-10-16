import React, { useState, useEffect } from 'react';
import StockList from './components/StockList';
import { checkHealth } from './services/api';
import './App.css';

function App() {
  const [healthStatus, setHealthStatus] = useState(null);

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
        <h1>Stock Analyzer</h1>
        <div className="health-status">
          {healthStatus && (
            <span className={`status ${healthStatus.status}`}>
              API Status: {healthStatus.status}
              {healthStatus.database && ` | DB: ${healthStatus.database}`}
            </span>
          )}
        </div>
      </header>

      <main className="App-main">
        <div className="container">
          <section className="intro">
            <h2>Welcome to Stock Analyzer</h2>
            <p>
              This application helps you analyze and predict stock market trends.
              Phase 1 setup is complete with a working backend API and database.
            </p>
          </section>

          <section className="stocks-section">
            <StockList />
          </section>

          <section className="info">
            <h3>What's Next?</h3>
            <ul>
              <li><strong>Phase 2:</strong> Data Pipeline - Fetch and store historical stock data</li>
              <li><strong>Phase 3:</strong> Analysis & Predictions - Implement ML models</li>
              <li><strong>Phase 4:</strong> Comparison & Tracking - Track prediction accuracy</li>
              <li><strong>Phase 5:</strong> Enhancement - Advanced features and authentication</li>
            </ul>
          </section>
        </div>
      </main>
    </div>
  );
}

export default App;
