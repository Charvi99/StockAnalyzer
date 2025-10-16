import React, { useState, useEffect, useRef, useCallback } from 'react';
import { analyzeComplete } from '../services/api';

const StockCard = ({ stock, onViewDetails, onUntrack }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('starting');
  const [error, setError] = useState(null);
  const [nextRefresh, setNextRefresh] = useState(null);
  const refreshIntervalRef = useRef(null);
  const countdownIntervalRef = useRef(null);

  const startCountdown = useCallback(() => {
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
    }

    countdownIntervalRef.current = setInterval(() => {
      setNextRefresh(new Date(Date.now() + 15 * 60 * 1000));
    }, 60000); // Update every minute
  }, []);

  const runAnalysis = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setProgress(0);
      setStatus('starting');

      // Simulate progress for better UX
      const progressSteps = [
        { progress: 25, status: 'fetching_data', delay: 500 },
        { progress: 50, status: 'technical_analysis', delay: 800 },
        { progress: 75, status: 'ml_prediction', delay: 600 },
        { progress: 90, status: 'sentiment_analysis', delay: 500 }
      ];

      // Run progress animation
      for (const step of progressSteps) {
        await new Promise(resolve => setTimeout(resolve, step.delay));
        setProgress(step.progress);
        setStatus(step.status);
      }

      // Call the actual API
      const result = await analyzeComplete(stock.id);

      setProgress(100);
      setStatus('completed');

      if (result.status === 'completed') {
        setAnalysis(result.recommendation);
        setLoading(false);

        // Set next refresh time
        const nextTime = new Date(Date.now() + 15 * 60 * 1000);
        setNextRefresh(nextTime);

        // Start countdown timer
        startCountdown();
      } else if (result.status === 'error') {
        setError(result.error || 'Analysis failed');
        setLoading(false);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to analyze stock');
      setLoading(false);
      console.error('Analysis error:', err);
    }
  }, [stock.id, startCountdown]);

  useEffect(() => {
    // Run initial analysis
    runAnalysis();

    // Set up 15-minute auto-refresh
    refreshIntervalRef.current = setInterval(() => {
      runAnalysis();
    }, 15 * 60 * 1000); // 15 minutes

    // Cleanup on unmount
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current);
      }
    };
  }, [runAnalysis]);

  const handleManualRefresh = () => {
    // Clear existing interval
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
    }

    // Run analysis
    runAnalysis();

    // Restart the interval
    refreshIntervalRef.current = setInterval(() => {
      runAnalysis();
    }, 15 * 60 * 1000);
  };

  const getTimeUntilRefresh = () => {
    if (!nextRefresh) return '';
    const diff = nextRefresh - new Date();
    const minutes = Math.floor(diff / 60000);
    return `${minutes}m`;
  };

  const getRecommendationColor = (recommendation) => {
    if (!recommendation) return '#6b7280';
    switch (recommendation) {
      case 'BUY':
        return '#10b981';
      case 'SELL':
        return '#ef4444';
      case 'HOLD':
        return '#f59e0b';
      default:
        return '#6b7280';
    }
  };

  const getStatusMessage = () => {
    switch (status) {
      case 'fetching_data':
        return 'Fetching latest data...';
      case 'technical_analysis':
        return 'Running technical analysis...';
      case 'ml_prediction':
        return 'Running ML predictions...';
      case 'sentiment_analysis':
        return 'Analyzing sentiment...';
      case 'completed':
        return 'Complete';
      default:
        return 'Starting analysis...';
    }
  };

  return (
    <div className="stock-card">
      <div className="stock-card-header">
        <div>
          <h3>{stock.symbol}</h3>
          <p className="stock-name">{stock.name || 'N/A'}</p>
        </div>
        <div className="stock-meta">
          <span className="sector">{stock.sector || 'N/A'}</span>
          {!loading && nextRefresh && (
            <button
              onClick={handleManualRefresh}
              className="refresh-btn"
              title={`Next auto-refresh in ${getTimeUntilRefresh()}`}
            >
              🔄 {getTimeUntilRefresh()}
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="loading-section">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="status-text">{getStatusMessage()}</p>
          <p className="progress-text">{progress}%</p>
        </div>
      ) : error ? (
        <div className="error-section">
          <p className="error-text">⚠️ {error}</p>
          <button onClick={runAnalysis} className="retry-btn">
            Retry Analysis
          </button>
        </div>
      ) : analysis ? (
        <div className="analysis-section">
          <div
            className="recommendation-badge"
            style={{
              background: getRecommendationColor(analysis.final_recommendation) + '20',
              borderColor: getRecommendationColor(analysis.final_recommendation)
            }}
          >
            <div className="recommendation-label">RECOMMENDATION</div>
            <div
              className="recommendation-value"
              style={{ color: getRecommendationColor(analysis.final_recommendation) }}
            >
              {analysis.final_recommendation}
            </div>
            <div className="confidence-label">
              {(analysis.overall_confidence * 100).toFixed(0)}% confidence
            </div>
          </div>

          <div className="signals-grid">
            <div className="signal-item">
              <div className="signal-label">Technical</div>
              <div
                className="signal-value"
                style={{ color: getRecommendationColor(analysis.technical_recommendation) }}
              >
                {analysis.technical_recommendation}
              </div>
            </div>
            <div className="signal-item">
              <div className="signal-label">ML Model</div>
              <div
                className="signal-value"
                style={{ color: getRecommendationColor(analysis.ml_recommendation) }}
              >
                {analysis.ml_recommendation || 'N/A'}
              </div>
            </div>
            <div className="signal-item">
              <div className="signal-label">Sentiment</div>
              <div className="signal-value">
                {analysis.sentiment_index !== null
                  ? analysis.sentiment_index.toFixed(0)
                  : 'N/A'
                }
              </div>
            </div>
            <div className="signal-item">
              <div className="signal-label">Price</div>
              <div className="signal-value">
                ${analysis.current_price?.toFixed(2) || 'N/A'}
              </div>
            </div>
          </div>

          <div className="card-actions">
            <button onClick={() => onViewDetails(stock)} className="view-details-btn">
              View Details
            </button>
            <button onClick={() => onUntrack(stock.id)} className="untrack-btn-small">
              Untrack
            </button>
          </div>
        </div>
      ) : null}

      <style jsx>{`
        .stock-card {
          background: white;
          border-radius: 12px;
          padding: 20px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
          transition: all 0.3s;
        }

        .stock-card:hover {
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
          transform: translateY(-2px);
        }

        .stock-card-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 16px;
          padding-bottom: 12px;
          border-bottom: 1px solid #e5e7eb;
        }

        .stock-card-header h3 {
          margin: 0;
          font-size: 24px;
          font-weight: 700;
          color: #111827;
        }

        .stock-name {
          margin: 4px 0 0 0;
          font-size: 13px;
          color: #6b7280;
        }

        .stock-meta {
          display: flex;
          flex-direction: column;
          gap: 6px;
          align-items: flex-end;
        }

        .sector {
          font-size: 11px;
          background: #f3f4f6;
          padding: 4px 8px;
          border-radius: 4px;
          color: #374151;
        }

        .refresh-btn {
          background: #f3f4f6;
          border: 1px solid #e5e7eb;
          padding: 4px 8px;
          border-radius: 6px;
          font-size: 11px;
          cursor: pointer;
          transition: all 0.2s;
          color: #374151;
          font-weight: 500;
        }

        .refresh-btn:hover {
          background: #667eea;
          color: white;
          border-color: #667eea;
          transform: scale(1.05);
        }

        .loading-section {
          padding: 24px 0;
        }

        .progress-bar {
          width: 100%;
          height: 8px;
          background: #e5e7eb;
          border-radius: 4px;
          overflow: hidden;
          margin-bottom: 12px;
        }

        .progress-fill {
          height: 100%;
          background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
          transition: width 0.3s ease;
        }

        .status-text {
          font-size: 14px;
          color: #374151;
          margin: 8px 0 4px 0;
        }

        .progress-text {
          font-size: 12px;
          color: #6b7280;
          margin: 0;
        }

        .error-section {
          padding: 24px 0;
          text-align: center;
        }

        .error-text {
          color: #dc2626;
          font-size: 14px;
          margin-bottom: 12px;
        }

        .retry-btn {
          background: #667eea;
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 6px;
          cursor: pointer;
          font-size: 13px;
        }

        .retry-btn:hover {
          background: #5568d3;
        }

        .analysis-section {
          padding: 12px 0;
        }

        .recommendation-badge {
          border: 2px solid;
          border-radius: 12px;
          padding: 16px;
          text-align: center;
          margin-bottom: 16px;
        }

        .recommendation-label {
          font-size: 11px;
          font-weight: 600;
          letter-spacing: 0.5px;
          color: #6b7280;
          margin-bottom: 8px;
        }

        .recommendation-value {
          font-size: 32px;
          font-weight: 800;
          margin-bottom: 4px;
        }

        .confidence-label {
          font-size: 12px;
          color: #6b7280;
        }

        .signals-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
          margin-bottom: 16px;
        }

        .signal-item {
          background: #f9fafb;
          padding: 12px;
          border-radius: 8px;
        }

        .signal-label {
          font-size: 11px;
          color: #6b7280;
          margin-bottom: 4px;
          font-weight: 500;
        }

        .signal-value {
          font-size: 16px;
          font-weight: 700;
          color: #111827;
        }

        .card-actions {
          display: flex;
          gap: 8px;
        }

        .view-details-btn {
          flex: 1;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          border: none;
          padding: 10px;
          border-radius: 8px;
          font-weight: 600;
          cursor: pointer;
          font-size: 14px;
          transition: all 0.2s;
        }

        .view-details-btn:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }

        .untrack-btn-small {
          background: #fef2f2;
          color: #dc2626;
          border: 1px solid #fecaca;
          padding: 10px 16px;
          border-radius: 8px;
          font-weight: 600;
          cursor: pointer;
          font-size: 14px;
          transition: all 0.2s;
        }

        .untrack-btn-small:hover {
          background: #fee2e2;
        }
      `}</style>
    </div>
  );
};

export default StockCard;
