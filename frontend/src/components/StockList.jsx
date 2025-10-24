import React, { useState, useEffect } from 'react';
import { getDashboardAnalysis, getDashboardAnalysisChunk, getStocks, updateStock, fetchStockData, detectChartPatterns } from '../services/api';
import StockDetailSideBySide from './StockDetailSideBySide';
import AddStockModal from './AddStockModal';
import StockCard from './StockCard';

// Sector colors matching StockCard
const SECTOR_CONFIG = {
  'Technology': { color: '#667eea', icon: '💻', bgLight: '#eef2ff' },
  'Healthcare': { color: '#059669', icon: '⚕️', bgLight: '#d1fae5' },
  'Financial': { color: '#2563eb', icon: '💰', bgLight: '#dbeafe' },
  'Consumer Goods': { color: '#ea580c', icon: '🛍️', bgLight: '#ffedd5' },
  'Energy': { color: '#ca8a04', icon: '⚡', bgLight: '#fef9c3' },
  'Industrials': { color: '#78716c', icon: '🏭', bgLight: '#f5f5f4' },
  'Retail': { color: '#dc2626', icon: '🏪', bgLight: '#fee2e2' },
  'Real Estate': { color: '#0891b2', icon: '🏢', bgLight: '#cffafe' },
  'Materials': { color: '#a16207', icon: '⛏️', bgLight: '#fef3c7' },
  'Entertainment': { color: '#c026d3', icon: '🎬', bgLight: '#fae8ff' },
  'Consumer Services': { color: '#f97316', icon: '🔔', bgLight: '#fed7aa' },
  'Automotive': { color: '#0d9488', icon: '🚗', bgLight: '#ccfbf1' },
  'Telecommunications': { color: '#4f46e5', icon: '📡', bgLight: '#e0e7ff' },
  'Utilities': { color: '#0369a1', icon: '💡', bgLight: '#e0f2fe' },
  'Transportation': { color: '#7c2d12', icon: '✈️', bgLight: '#fed7aa' },
  'Leisure': { color: '#be185d', icon: '🎨', bgLight: '#fce7f3' },
  'Aerospace': { color: '#1e40af', icon: '🚀', bgLight: '#dbeafe' },
  'Consumer Cyclical': { color: '#ea580c', icon: '🔄', bgLight: '#ffedd5' },
};

const getSectorConfig = (sector) => {
  return SECTOR_CONFIG[sector] || { color: '#6b7280', icon: '📊', bgLight: '#f3f4f6' };
};

const StockList = () => {
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedStock, setSelectedStock] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [groupBySector, setGroupBySector] = useState(true);
  const [collapsedSectors, setCollapsedSectors] = useState(new Set());
  const [batchFetching, setBatchFetching] = useState(false);
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0, currentSymbol: '' });
  const [batchDetecting, setBatchDetecting] = useState(false);
  const [detectProgress, setDetectProgress] = useState({ current: 0, total: 0, currentSymbol: '', totalPatterns: 0 });

  // Progressive loading state
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState({ loaded: 0, total: 0 });
  const [stocksWithoutAnalysis, setStocksWithoutAnalysis] = useState(new Set());

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setLoadingAnalysis(true);
      setError(null);

      // STEP 1: Load basic stock info FAST (just stocks table, no analysis)
      console.log('Step 1: Loading basic stock info...');
      const basicStocks = await getStocks(true); // tracked only
      console.log(`Loaded ${basicStocks.length} stocks (basic info only)`);

      // Create initial stock objects with loading state
      const initialStocks = basicStocks.map(stock => ({
        stock_id: stock.id,
        symbol: stock.symbol,
        name: stock.name,
        sector: stock.sector,
        industry: stock.industry,
        is_tracked: stock.is_tracked,
        // Mark as loading (no analysis data yet)
        _loading: true,
        // Placeholder values
        recommendation: null,
        confidence: null,
        signals: null,
        current_price: null,
        change_percent: null,
        indicators: null,
        ml_prediction: null,
        sentiment: null,
        patterns: null,
        chart_patterns: null,
        strategies: null
      }));

      // Show stocks immediately with loading state
      setStocks(initialStocks);
      setStocksWithoutAnalysis(new Set(initialStocks.map(s => s.stock_id)));
      setAnalysisProgress({ loaded: 0, total: basicStocks.length });
      setLoading(false); // Done loading structure, now loading analysis

      // STEP 2: Load analysis data in chunks
      const CHUNK_SIZE = 50;
      const totalStocks = basicStocks.length;
      let loadedCount = 0;

      console.log(`Step 2: Loading analysis data in chunks of ${CHUNK_SIZE}...`);

      for (let offset = 0; offset < totalStocks; offset += CHUNK_SIZE) {
        try {
          console.log(`Loading chunk: offset=${offset}, limit=${CHUNK_SIZE}`);
          const chunkData = await getDashboardAnalysisChunk(offset, CHUNK_SIZE);

          // Update stocks with analysis data
          setStocks(prevStocks => {
            const updatedStocks = [...prevStocks];
            chunkData.forEach(analyzedStock => {
              const index = updatedStocks.findIndex(s => s.stock_id === analyzedStock.stock_id);
              if (index !== -1) {
                updatedStocks[index] = { ...analyzedStock, _loading: false };
              }
            });
            return updatedStocks;
          });

          // Update progress
          loadedCount += chunkData.length;
          setAnalysisProgress({ loaded: loadedCount, total: totalStocks });
          setStocksWithoutAnalysis(prev => {
            const newSet = new Set(prev);
            chunkData.forEach(stock => newSet.delete(stock.stock_id));
            return newSet;
          });

          console.log(`Progress: ${loadedCount}/${totalStocks} stocks analyzed`);
        } catch (chunkErr) {
          console.error(`Failed to load chunk at offset ${offset}:`, chunkErr);
          // Continue with next chunk even if one fails
        }
      }

      console.log('All analysis data loaded!');
      setLoadingAnalysis(false);

    } catch (err) {
      setError('Failed to fetch dashboard data');
      console.error(err);
      setLoading(false);
      setLoadingAnalysis(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const handleStockAdded = async (newStock) => {
    try {
      setStocks((prevStocks) => [...prevStocks, newStock]);
      console.log(`Fetching initial historical data for ${newStock.symbol}...`);
      await fetchStockData(newStock.id, '1y', '1d');
      console.log(`Initial data for ${newStock.symbol} fetched successfully.`);
      // Refresh the whole dashboard to get the new stock's analysis
      fetchDashboardData();
    } catch (err) {
      console.error(`Failed to fetch initial data for ${newStock.symbol}:`, err);
      setError(`Failed to fetch initial data for ${newStock.symbol}.`);
    }
  };

  const handleUntrack = async (stockId) => {
    if (window.confirm('Remove this stock from your watchlist?')) {
      try {
        await updateStock(stockId, { is_tracked: false });
        fetchDashboardData(); // Refresh the list
      } catch (err) {
        setError('Failed to untrack stock');
        console.error(err);
      }
    }
  };

  const handleBatchFetch5Years = async () => {
    if (!window.confirm(`Fetch 5 years of historical data for all ${stocks.length} stocks?\n\nThis will take approximately ${Math.ceil(stocks.length * 2 / 60)} minutes.\n\nYou can continue using the app while this runs in the background.`)) {
      return;
    }

    setBatchFetching(true);
    setBatchProgress({ current: 0, total: stocks.length, currentSymbol: '' });

    let successful = 0;
    let failed = 0;
    const failedStocks = [];

    for (let i = 0; i < stocks.length; i++) {
      const stock = stocks[i];
      setBatchProgress({
        current: i + 1,
        total: stocks.length,
        currentSymbol: stock.symbol
      });

      try {
        await fetchStockData(stock.stock_id, '5y', '1d');
        successful++;
        console.log(`✓ ${stock.symbol} (${i + 1}/${stocks.length})`);
      } catch (err) {
        failed++;
        failedStocks.push(stock.symbol);
        console.error(`✗ ${stock.symbol}: ${err.message}`);
      }

      // Small delay to avoid overwhelming the API
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    setBatchFetching(false);
    setBatchProgress({ current: 0, total: 0, currentSymbol: '' });

    // Show summary
    const summary = `Batch fetch complete!\n\n✓ Successful: ${successful}\n✗ Failed: ${failed}${failedStocks.length > 0 ? '\n\nFailed stocks:\n' + failedStocks.join(', ') : ''}`;
    alert(summary);

    // Refresh dashboard
    fetchDashboardData();
  };

  const toggleSectorCollapse = (sector) => {
    setCollapsedSectors(prev => {
      const newSet = new Set(prev);
      if (newSet.has(sector)) {
        newSet.delete(sector);
      } else {
        newSet.add(sector);
      }
      return newSet;
    });
  };

  // Group stocks by sector
  const stocksBySector = stocks.reduce((acc, stock) => {
    const sector = stock.sector || 'Uncategorized';
    if (!acc[sector]) {
      acc[sector] = [];
    }
    acc[sector].push(stock);
    return acc;
  }, {});

  // Sort sectors by number of stocks (descending)
  const sortedSectors = Object.keys(stocksBySector).sort((a, b) => {
    return stocksBySector[b].length - stocksBySector[a].length;
  });

  if (loading) return <div className="loading">Loading dashboard...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="stock-list">
      <div className="stock-list-header">
        <div className="header-content">
          <h1>Stock Analysis Dashboard</h1>
          <p className="subtitle">Auto-analyzing {stocks.length} stocks in your watchlist</p>
        </div>
        <div className="header-actions">
          <button
            onClick={() => setGroupBySector(!groupBySector)}
            className="toggle-group-btn"
            title={groupBySector ? "Show all stocks" : "Group by sector"}
          >
            {groupBySector ? '📋 Show All' : '📊 Group by Sector'}
          </button>
          <button
            onClick={handleBatchFetch5Years}
            className="debug-btn"
            disabled={batchFetching || stocks.length === 0}
            title="Fetch 5 years of historical data for all stocks"
          >
            {batchFetching ? '⏳ Fetching...' : '🔧 Fetch 5Y Data'}
          </button>
          <button onClick={() => setShowAddModal(true)} className="add-stock-btn">
            + Add Stock
          </button>
        </div>
      </div>

      {/* Batch Progress Indicator */}
      {batchFetching && (
        <div className="batch-progress-bar">
          <div className="progress-info">
            <span className="progress-text">
              Fetching {batchProgress.currentSymbol} ({batchProgress.current}/{batchProgress.total})
            </span>
            <span className="progress-percent">
              {Math.round((batchProgress.current / batchProgress.total) * 100)}%
            </span>
          </div>
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{ width: `${(batchProgress.current / batchProgress.total) * 100}%` }}
            ></div>
          </div>
        </div>
      )}

      {/* Analysis Loading Progress Indicator */}
      {loadingAnalysis && analysisProgress.total > 0 && (
        <div className="batch-progress-bar analysis-progress">
          <div className="progress-info">
            <span className="progress-text">
              Loading analysis data... ({analysisProgress.loaded}/{analysisProgress.total})
            </span>
            <span className="progress-percent">
              {Math.round((analysisProgress.loaded / analysisProgress.total) * 100)}%
            </span>
          </div>
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{ width: `${(analysisProgress.loaded / analysisProgress.total) * 100}%` }}
            ></div>
          </div>
        </div>
      )}

      {stocks.length === 0 ? (
        <div className="empty-state">
          <p>No stocks in your watchlist yet.</p>
          <p>Click "Add Stock" to start tracking and analyzing stocks!</p>
        </div>
      ) : groupBySector ? (
        // Grouped by sector view
        <div className="sectors-container">
          {sortedSectors.map((sector) => {
            const sectorStocks = stocksBySector[sector];
            const sectorConfig = getSectorConfig(sector);
            const isCollapsed = collapsedSectors.has(sector);

            return (
              <div key={sector} className="sector-section">
                <div
                  className="sector-header"
                  onClick={() => toggleSectorCollapse(sector)}
                  style={{
                    background: sectorConfig.bgLight,
                    borderLeft: `4px solid ${sectorConfig.color}`,
                  }}
                >
                  <div className="sector-title">
                    <span className="sector-icon">{sectorConfig.icon}</span>
                    <h2 style={{ color: sectorConfig.color }}>{sector}</h2>
                    <span className="stock-count">{sectorStocks.length} stocks</span>
                  </div>
                  <span className="collapse-indicator">{isCollapsed ? '▶' : '▼'}</span>
                </div>

                {!isCollapsed && (
                  <div className="stocks-grid">
                    {sectorStocks.map((stock) => (
                      <StockCard
                        key={stock.stock_id}
                        stock={stock}
                        onViewDetails={() => setSelectedStock(stock)}
                        onUntrack={handleUntrack}
                        onAnalysisComplete={fetchDashboardData}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        // All stocks grid view
        <div className="stocks-grid">
          {stocks.map((stock) => (
            <StockCard
              key={stock.stock_id}
              stock={stock}
              onViewDetails={() => setSelectedStock(stock)}
              onUntrack={handleUntrack}
              onAnalysisComplete={fetchDashboardData}
            />
          ))}
        </div>
      )}

      {selectedStock && (
        <StockDetailSideBySide
          stock={selectedStock}
          onClose={() => setSelectedStock(null)}
        />
      )}

      {showAddModal && (
        <AddStockModal
          onClose={() => setShowAddModal(false)}
          onStockAdded={handleStockAdded}
        />
      )}

      <style jsx>{`
        .stock-list {
          padding: 20px;
          max-width: 1400px;
          margin: 0 auto;
        }

        .stock-list-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 32px;
          padding-bottom: 20px;
          border-bottom: 2px solid #e5e7eb;
        }

        .header-content h1 {
          margin: 0 0 8px 0;
          font-size: 32px;
          font-weight: 800;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .subtitle {
          margin: 0;
          color: #6b7280;
          font-size: 14px;
        }

        .header-actions {
          display: flex;
          gap: 12px;
        }

        .toggle-group-btn {
          background: white;
          color: #667eea;
          border: 2px solid #667eea;
          padding: 12px 20px;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .toggle-group-btn:hover {
          background: #667eea;
          color: white;
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }

        .debug-btn {
          background: #f59e0b;
          color: white;
          border: none;
          padding: 12px 20px;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .debug-btn:hover:not(:disabled) {
          background: #d97706;
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(245, 158, 11, 0.4);
        }

        .debug-btn:disabled {
          background: #d1d5db;
          cursor: not-allowed;
          opacity: 0.6;
        }

        .add-stock-btn {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          border: none;
          padding: 12px 24px;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .add-stock-btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
        }

        .empty-state {
          text-align: center;
          padding: 80px 20px;
          background: #f9fafb;
          border-radius: 12px;
          color: #6b7280;
        }

        .empty-state p:first-child {
          font-size: 20px;
          font-weight: 600;
          color: #374151;
          margin-bottom: 8px;
        }

        .sectors-container {
          display: flex;
          flex-direction: column;
          gap: 24px;
        }

        .sector-section {
          background: white;
          border-radius: 12px;
          overflow: hidden;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        }

        .sector-header {
          padding: 16px 20px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          cursor: pointer;
          transition: all 0.2s;
          user-select: none;
        }

        .sector-header:hover {
          opacity: 0.9;
        }

        .sector-title {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .sector-icon {
          font-size: 24px;
        }

        .sector-title h2 {
          margin: 0;
          font-size: 20px;
          font-weight: 700;
        }

        .stock-count {
          font-size: 13px;
          color: #6b7280;
          background: white;
          padding: 4px 12px;
          border-radius: 12px;
          font-weight: 600;
        }

        .collapse-indicator {
          font-size: 14px;
          color: #6b7280;
          transition: transform 0.2s;
        }

        .stocks-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
          gap: 24px;
          padding: 24px;
        }

        .sector-section .stocks-grid {
          background: #fafafa;
        }

        .batch-progress-bar {
          background: white;
          border-radius: 12px;
          padding: 20px;
          margin-bottom: 24px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
          border-left: 4px solid #f59e0b;
        }

        .progress-info {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }

        .progress-text {
          font-size: 14px;
          font-weight: 600;
          color: #374151;
        }

        .progress-percent {
          font-size: 14px;
          font-weight: 700;
          color: #f59e0b;
        }

        .progress-track {
          height: 8px;
          background: #f3f4f6;
          border-radius: 4px;
          overflow: hidden;
        }

        .progress-fill {
          height: 100%;
          background: linear-gradient(90deg, #f59e0b 0%, #d97706 100%);
          transition: width 0.3s ease;
          border-radius: 4px;
        }

        @media (max-width: 768px) {
          .stock-list-header {
            flex-direction: column;
            align-items: flex-start;
            gap: 16px;
          }

          .header-actions {
            width: 100%;
            flex-direction: column;
          }

          .toggle-group-btn,
          .debug-btn,
          .add-stock-btn {
            width: 100%;
          }

          .stocks-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
};

export default StockList;
