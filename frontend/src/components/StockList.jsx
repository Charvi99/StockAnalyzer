import React, { useState, useEffect } from 'react';
import { getDashboardAnalysisChunk, getStocks, updateStock, fetchStockData, checkAnalysisCompleteness, triggerBatchAnalysis, getRecentUpdates, getAnalysisByIds } from '../services/api';
import StockDetailSideBySide from './StockDetailSideBySide';
import AddStockModal from './AddStockModal';
import StockCard from './StockCard';
import IndicatorInfo from './IndicatorInfo';
import { ToastContainer } from './Toast';

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
  const [groupBySector] = useState(true); // Always group by sector for better organization
  const [collapsedSectors, setCollapsedSectors] = useState(new Set());
  const [batchFetching, setBatchFetching] = useState(false);
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0, currentSymbol: '' });
  const [showInvestopedia, setShowInvestopedia] = useState(false);

  // Progressive loading state
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState({ loaded: 0, total: 0 });

  // Auto-trigger state (Phase 2)
  const [autoTriggerActive, setAutoTriggerActive] = useState(false);
  const [autoTriggerProgress, setAutoTriggerProgress] = useState({ triggered: 0, total: 0, message: '' });
  const [analyzingStockIds, setAnalyzingStockIds] = useState(new Set());

  // Auto-refresh state (for real-time updates after analysis)
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);

  // Filter and search state
  const [searchQuery, setSearchQuery] = useState('');
  const [filterRecommendation, setFilterRecommendation] = useState('ALL'); // ALL, BUY, HOLD, SELL
  const [filterConfidence, setFilterConfidence] = useState(0); // 0-100

  // Toast notifications (Phase 4)
  const [toasts, setToasts] = useState([]);

  // Helper function to show toast notifications
  const showToast = (message, type = 'info', duration = 3000) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type, duration }]);
  };

  const removeToast = (id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  };

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

          console.log(`Progress: ${loadedCount}/${totalStocks} stocks analyzed`);
        } catch (chunkErr) {
          console.error(`Failed to load chunk at offset ${offset}:`, chunkErr);
          // Continue with next chunk even if one fails
        }
      }

      console.log('All analysis data loaded!');
      setLoadingAnalysis(false);

      // STEP 3: Check completeness and auto-trigger analysis for incomplete stocks
      try {
        console.log('Step 3: Checking analysis completeness...');
        const stockIds = basicStocks.map(s => s.id);
        const completenessResult = await checkAnalysisCompleteness(stockIds, 24, 0.80, false);

        console.log(`Completeness check: ${completenessResult.total_checked} stocks checked, ${completenessResult.needs_analysis_count} need analysis`);

        if (completenessResult.needs_analysis_count > 0) {
          const incompleteStockIds = completenessResult.stocks
            .filter(s => s.needs_refresh)
            .map(s => s.stock_id);

          console.log(`Auto-triggering analysis for ${incompleteStockIds.length} incomplete stocks...`);
          setAutoTriggerActive(true);
          setAutoTriggerProgress({
            triggered: 0,
            total: incompleteStockIds.length,
            message: 'Preparing background analysis...'
          });

          // Mark stocks as analyzing
          setAnalyzingStockIds(new Set(incompleteStockIds));

          // Trigger batch analysis
          const triggerResult = await triggerBatchAnalysis(incompleteStockIds);
          console.log(`✅ Triggered analysis for ${triggerResult.triggered_count} stocks`);

          setAutoTriggerProgress({
            triggered: triggerResult.triggered_count,
            total: incompleteStockIds.length,
            message: `Running analysis for ${triggerResult.triggered_count} stocks...`
          });

          // auto-trigger progress banner auto-hides after 30s
          setTimeout(() => {
            setAutoTriggerActive(false);
          }, 30000);

          // Per-stock "Analyzing..." badges are cleared by the poll (checkForUpdates)
          // when each stock's fresh data lands — NO blind timer. analyze_stock_comprehensive
          // sets last_comprehensive_analysis on completion (even partial), and the poll's
          // server-timestamp watermark reliably catches every stock, so a fallback that
          // nukes all badges prematurely would only cause false "done" signals again.
        } else {
          console.log('✅ All stocks have fresh analysis data, no auto-trigger needed');
        }
      } catch (autoTriggerErr) {
        console.error('❌ Auto-trigger check failed:', autoTriggerErr);
        // Don't show error to user - this is a background operation
      }

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

  // Phase 4: Efficient polling - Only fetch changed stocks using recent-updates & get-by-ids
  useEffect(() => {
    if (!autoRefreshEnabled) return;

    // Start ~60s in the past to absorb client/server clock skew on the first poll.
    let lastPollTime = new Date(Date.now() - 60000).toISOString();

    const checkForUpdates = async () => {
      try {
        // Only fetch IDs of updated stocks (cheap), then full data for just those.
        const recentUpdates = await getRecentUpdates(lastPollTime);

        if (recentUpdates.count > 0) {
          const updatedStockIds = recentUpdates.updates.map(u => u.stock_id);
          const updatedData = await getAnalysisByIds(updatedStockIds);

          // Merge only the changed stocks; unchanged stocks keep their object ref so
          // a memoized StockCard skips re-rendering them.
          setStocks(prevStocks => {
            const updatedMap = new Map(updatedData.stocks.map(s => [s.stock_id, s]));
            return prevStocks.map(stock =>
              updatedMap.has(stock.stock_id)
                ? { ...updatedMap.get(stock.stock_id), _loading: false }
                : stock
            );
          });

          // Clear the "Analyzing..." badge for stocks whose fresh data just landed —
          // the real completion signal (badge stays until the stock is actually updated,
          // not cleared by a blind timer).
          setAnalyzingStockIds(prev => {
            if (prev.size === 0) return prev;
            const next = new Set(prev);
            updatedStockIds.forEach(id => next.delete(id));
            return next;
          });

          // Toast = the "these tickers are really updated" signal the user watches for.
          const symbols = recentUpdates.updates.map(u => u.symbol).slice(0, 3).join(', ');
          const message = recentUpdates.count <= 3
            ? `${symbols} updated`
            : `${symbols} and ${recentUpdates.count - 3} more updated`;
          showToast(message, 'success', 4000);

          setLastRefresh(new Date());

          // Advance the watermark from the SERVER's timestamps (max updated_at), NOT
          // the client clock: client/server clock skew made the poll step over some
          // completions, leaving their "Analyzing..." badges stuck. (The verbose
          // per-tick console.logs that retained large response objects in dev-mode
          // memory were removed here too — they caused the tab to balloon ~75->495MB.)
          const maxServerTs = recentUpdates.updates.reduce((mx, u) => {
            const t = new Date(u.updated_at).getTime();
            return Number.isFinite(t) && t > mx ? t : mx;
          }, 0);
          if (maxServerTs) lastPollTime = new Date(maxServerTs).toISOString();
        }
      } catch (err) {
        console.error('[POLL] Auto-refresh check failed:', err.message);
      }
    };

    // Check immediately on mount
    checkForUpdates();

    // Then check every 30 seconds
    const refreshInterval = setInterval(checkForUpdates, 30000);

    return () => clearInterval(refreshInterval);
  }, [autoRefreshEnabled]);

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

  const handleBatchFetch6Months = async () => {
    if (!window.confirm(`Fetch 1 months of 1-hour data for all ${stocks.length} stocks?\n\nThis will take approximately ${Math.ceil(stocks.length * 2 / 60)} minutes.\n\nYou can continue using the app while this runs in the background.`)) {
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
        // Fetch 1 months of 1-hour data for swing trading
        await fetchStockData(stock.stock_id, '1mo', '1h');
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

  // Force immediate analysis for HIGH priority stocks
  const handleForceAnalysis = async () => {
    if (autoTriggerActive) {
      showToast('⚠️ Analysis already in progress', 'warning', 3000);
      return;
    }

    try {
      setAutoTriggerActive(true);
      setAutoTriggerProgress({ triggered: 0, total: 0, message: 'Fetching HIGH priority stocks...' });

      // Get all stock IDs (backend will filter by priority)
      const stockIds = stocks.map(s => s.stock_id);

      showToast('🚀 Triggering analysis for HIGH priority stocks...', 'info', 3000);

      // Trigger batch analysis with HIGH priority override
      const result = await triggerBatchAnalysis(stockIds, 'high');

      setAutoTriggerProgress({
        triggered: result.triggered_count,
        total: result.triggered_count,
        message: `✅ Triggered ${result.triggered_count} HIGH priority analyses`
      });

      showToast(`✅ ${result.triggered_count} analyses triggered! Watch the cards for updates.`, 'success', 5000);

      // Mark triggered stocks as analyzing
      const triggeredIds = new Set(result.tasks.map(t => t.stock_id));
      setAnalyzingStockIds(triggeredIds);

      // Reset after 2 seconds
      setTimeout(() => {
        setAutoTriggerActive(false);
        setAutoTriggerProgress({ triggered: 0, total: 0, message: '' });
      }, 2000);

    } catch (err) {
      console.error('Force analysis failed:', err);
      showToast(`❌ Force analysis failed: ${err.message}`, 'error', 5000);
      setAutoTriggerActive(false);
      setAutoTriggerProgress({ triggered: 0, total: 0, message: '' });
    }
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

  // Apply filters and search
  const filteredStocks = stocks.filter(stock => {
    // Search filter (symbol or name)
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      const symbolMatch = stock.symbol?.toLowerCase().includes(query);
      const nameMatch = stock.name?.toLowerCase().includes(query);
      if (!symbolMatch && !nameMatch) return false;
    }

    // Recommendation filter
    if (filterRecommendation !== 'ALL') {
      // API returns final_recommendation field, not recommendation
      if (stock.final_recommendation !== filterRecommendation) return false;
    }

    // Confidence filter
    if (filterConfidence > 0) {
      // API returns overall_confidence field (0-1), not confidence (0-100)
      // Convert to percentage for comparison
      const confidence = (stock.overall_confidence || 0) * 100;
      if (confidence < filterConfidence) return false;
    }

    return true;
  });

  // Group stocks by sector
  const stocksBySector = filteredStocks.reduce((acc, stock) => {
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
            onClick={() => setAutoRefreshEnabled(!autoRefreshEnabled)}
            className={autoRefreshEnabled ? 'refresh-btn active' : 'refresh-btn'}
            title={autoRefreshEnabled ? 'Auto-refresh ON (every 30s)' : 'Auto-refresh OFF'}
          >
            {autoRefreshEnabled ? '🔄 Live' : '⏸️ Paused'}
            {lastRefresh && <span className="last-refresh" style={{ fontSize: '0.7em', marginLeft: '4px' }}>
              {new Date(lastRefresh).toLocaleTimeString()}
            </span>}
          </button>
          <button
            onClick={handleBatchFetch6Months}
            className="debug-btn"
            disabled={batchFetching || stocks.length === 0}
            title="Fetch 6 months"
          >
            {batchFetching ? '⏳ Fetching...' : '🔧 Fetch 1M 1h Data'}
          </button>
          <button
            onClick={handleForceAnalysis}
            className="force-analysis-btn"
            disabled={autoTriggerActive || stocks.length === 0}
            title="Force immediate analysis for HIGH priority stocks"
          >
            {autoTriggerActive ? '⚡ Analyzing...' : '⚡ Force Analysis'}
          </button>
          <button
            onClick={() => setShowInvestopedia(true)}
            className="investopedia-btn-main"
            title="Learn about indicators, patterns & techniques"
          >
            📚 Investopedia
          </button>
          <button onClick={() => setShowAddModal(true)} className="add-stock-btn">
            + Add Stock
          </button>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="filters-container">
        <div className="search-box">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            placeholder="Search stocks by symbol or name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="search-input"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="clear-search"
              title="Clear search"
            >
              ✕
            </button>
          )}
        </div>

        <div className="filter-section">
          <div className="filter-group">
            <label>Recommendation:</label>
            <div className="recommendation-buttons">
              <button
                onClick={() => setFilterRecommendation('ALL')}
                className={filterRecommendation === 'ALL' ? 'filter-btn active' : 'filter-btn'}
              >
                All
              </button>
              <button
                onClick={() => setFilterRecommendation('BUY')}
                className={filterRecommendation === 'BUY' ? 'filter-btn active buy' : 'filter-btn'}
              >
                🟢 BUY
              </button>
              <button
                onClick={() => setFilterRecommendation('HOLD')}
                className={filterRecommendation === 'HOLD' ? 'filter-btn active hold' : 'filter-btn'}
              >
                🟡 HOLD
              </button>
              <button
                onClick={() => setFilterRecommendation('SELL')}
                className={filterRecommendation === 'SELL' ? 'filter-btn active sell' : 'filter-btn'}
              >
                🔴 SELL
              </button>
            </div>
          </div>

          <div className="filter-group">
            <label>
              Minimum Confidence: {filterConfidence}%
              {filterConfidence > 0 && (
                <button
                  onClick={() => setFilterConfidence(0)}
                  className="reset-filter"
                  title="Reset confidence filter"
                >
                  Reset
                </button>
              )}
            </label>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={filterConfidence}
              onChange={(e) => setFilterConfidence(Number(e.target.value))}
              className="confidence-slider"
            />
            <div className="slider-labels">
              <span>0%</span>
              <span>50%</span>
              <span>100%</span>
            </div>
          </div>
        </div>

        <div className="filter-summary">
          Showing {filteredStocks.length} of {stocks.length} stocks
          {(searchQuery || filterRecommendation !== 'ALL' || filterConfidence > 0) && (
            <button
              onClick={() => {
                setSearchQuery('');
                setFilterRecommendation('ALL');
                setFilterConfidence(0);
              }}
              className="clear-all-filters"
            >
              Clear all filters
            </button>
          )}
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

      {/* Auto-Trigger Progress Indicator (Phase 2) */}
      {autoTriggerActive && autoTriggerProgress.total > 0 && (
        <div className="batch-progress-bar auto-trigger-progress">
          <div className="progress-info">
            <span className="progress-text">
              🤖 {autoTriggerProgress.message} ({autoTriggerProgress.triggered}/{autoTriggerProgress.total})
            </span>
            <span className="progress-percent">
              Background
            </span>
          </div>
          <div className="progress-track">
            <div
              className="progress-fill auto-trigger"
              style={{ width: `${(autoTriggerProgress.triggered / autoTriggerProgress.total) * 100}%` }}
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
                        isAnalyzing={analyzingStockIds.has(stock.stock_id)}
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
              isAnalyzing={analyzingStockIds.has(stock.stock_id)}
            />
          ))}
        </div>
      )}

      {selectedStock && (
        <StockDetailSideBySide
          stock={selectedStock}
          onClose={() => setSelectedStock(null)}
          initialRecommendation={selectedStock}
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

        .batch-progress-bar.auto-trigger-progress {
          border-left-color: #667eea;
          background: linear-gradient(135deg, #f8f9ff 0%, #ffffff 100%);
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

        .progress-fill.auto-trigger {
          background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        }
        .refresh-btn {
          background: #f3f4f6; /* Neutral background */
          color: #4b5563;
          border: 1px solid #d1d5db;
          padding: 12px 20px;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .refresh-btn:hover {
          background: #e5e7eb;
        }

        .refresh-btn.active {
          background: #10b981; /* Distinct color for 'Live' state */
          color: white;
          border-color: #059669;
        }

        .refresh-btn.active .last-refresh {
          color: white;
        }
        /* ---------------------------------------------------- */

        /* --- Move investopedia-btn-main styles here (New Block) --- */
        .investopedia-btn-main {
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

        .investopedia-btn-main:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
        }

        /* ================================================
           SEARCH AND FILTERS
           ================================================ */
        .filters-container {
          background: white;
          border-radius: 12px;
          padding: 24px;
          margin-bottom: 24px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
          border-left: 4px solid #667eea;
        }

        .search-box {
          position: relative;
          margin-bottom: 24px;
        }

        .search-icon {
          position: absolute;
          left: 16px;
          top: 50%;
          transform: translateY(-50%);
          font-size: 18px;
          pointer-events: none;
          opacity: 0.5;
        }

        .search-input {
          width: 100%;
          padding: 14px 48px 14px 48px;
          font-size: 15px;
          border: 2px solid #e5e7eb;
          border-radius: 10px;
          outline: none;
          transition: all 0.2s;
        }

        .search-input:focus {
          border-color: #667eea;
          box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        .clear-search {
          position: absolute;
          right: 12px;
          top: 50%;
          transform: translateY(-50%);
          background: #f3f4f6;
          border: none;
          width: 28px;
          height: 28px;
          border-radius: 50%;
          cursor: pointer;
          font-size: 14px;
          color: #6b7280;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .clear-search:hover {
          background: #e5e7eb;
          color: #374151;
        }

        .filter-section {
          display: flex;
          gap: 32px;
          margin-bottom: 20px;
          flex-wrap: wrap;
        }

        .filter-group {
          flex: 1;
          min-width: 280px;
        }

        .filter-group label {
          display: block;
          font-weight: 600;
          color: #374151;
          font-size: 14px;
          margin-bottom: 12px;
        }

        .recommendation-buttons {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }

        .filter-btn {
          flex: 1;
          min-width: 80px;
          padding: 10px 16px;
          background: #f9fafb;
          border: 2px solid #e5e7eb;
          border-radius: 8px;
          color: #374151;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          text-align: center;
        }

        .filter-btn:hover {
          background: #f3f4f6;
          border-color: #d1d5db;
        }

        .filter-btn.active {
          background: #667eea;
          border-color: #667eea;
          color: white;
          transform: scale(1.05);
          box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
        }

        .filter-btn.active.buy {
          background: linear-gradient(135deg, #10b981 0%, #059669 100%);
          border-color: #10b981;
        }

        .filter-btn.active.hold {
          background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
          border-color: #f59e0b;
        }

        .filter-btn.active.sell {
          background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
          border-color: #ef4444;
        }

        .confidence-slider {
          width: 100%;
          height: 8px;
          -webkit-appearance: none;
          appearance: none;
          background: linear-gradient(to right, #e5e7eb 0%, #667eea 100%);
          border-radius: 4px;
          outline: none;
          cursor: pointer;
        }

        .confidence-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 20px;
          height: 20px;
          background: #667eea;
          border-radius: 50%;
          cursor: pointer;
          box-shadow: 0 2px 6px rgba(102, 126, 234, 0.4);
          transition: all 0.2s;
        }

        .confidence-slider::-webkit-slider-thumb:hover {
          transform: scale(1.2);
          box-shadow: 0 3px 10px rgba(102, 126, 234, 0.6);
        }

        .confidence-slider::-moz-range-thumb {
          width: 20px;
          height: 20px;
          background: #667eea;
          border-radius: 50%;
          cursor: pointer;
          border: none;
          box-shadow: 0 2px 6px rgba(102, 126, 234, 0.4);
          transition: all 0.2s;
        }

        .confidence-slider::-moz-range-thumb:hover {
          transform: scale(1.2);
          box-shadow: 0 3px 10px rgba(102, 126, 234, 0.6);
        }

        .slider-labels {
          display: flex;
          justify-content: space-between;
          margin-top: 8px;
          font-size: 12px;
          color: #6b7280;
        }

        .reset-filter {
          margin-left: 12px;
          padding: 4px 10px;
          background: #f3f4f6;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          font-size: 11px;
          font-weight: 600;
          color: #6b7280;
          cursor: pointer;
          transition: all 0.2s;
        }

        .reset-filter:hover {
          background: #e5e7eb;
          color: #374151;
        }

        .filter-summary {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-top: 16px;
          border-top: 1px solid #e5e7eb;
          font-size: 14px;
          color: #6b7280;
          font-weight: 600;
        }

        .clear-all-filters {
          padding: 8px 16px;
          background: #fee2e2;
          color: #dc2626;
          border: 1px solid #fecaca;
          border-radius: 6px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .clear-all-filters:hover {
          background: #fecaca;
          border-color: #fca5a5;
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

          .debug-btn,
          .add-stock-btn,


          .stocks-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>

      {/* Investopedia Modal */}
      {showInvestopedia && <IndicatorInfo onClose={() => setShowInvestopedia(false)} />}

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
  );
};

export default StockList;
