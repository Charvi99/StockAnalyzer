import React, { useState, useEffect } from 'react';
import { getStocks, updateStock } from '../services/api';
import StockDetail from './StockDetail';
import AddStockModal from './AddStockModal';
import StockCard from './StockCard';

const StockList = () => {
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedStock, setSelectedStock] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);

  useEffect(() => {
    fetchStocks();
  }, []);

  const fetchStocks = async () => {
    try {
      setLoading(true);
      const data = await getStocks(true); // Get only tracked stocks
      setStocks(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch stocks');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleStockAdded = (newStock) => {
    setStocks([...stocks, newStock]);
  };

  const handleUntrack = async (stockId) => {
    if (window.confirm('Remove this stock from your watchlist?')) {
      try {
        await updateStock(stockId, { is_tracked: false });
        fetchStocks(); // Refresh the list
      } catch (err) {
        setError('Failed to untrack stock');
        console.error(err);
      }
    }
  };

  if (loading) return <div className="loading">Loading stocks...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="stock-list">
      <div className="stock-list-header">
        <div className="header-content">
          <h1>Stock Analysis Dashboard</h1>
          <p className="subtitle">Auto-analyzing {stocks.length} stocks in your watchlist</p>
        </div>
        <button onClick={() => setShowAddModal(true)} className="add-stock-btn">
          + Add Stock
        </button>
      </div>

      {stocks.length === 0 ? (
        <div className="empty-state">
          <p>No stocks in your watchlist yet.</p>
          <p>Click "Add Stock" to start tracking and analyzing stocks!</p>
        </div>
      ) : (
        <div className="stocks-grid">
          {stocks.map((stock) => (
            <StockCard
              key={stock.id}
              stock={stock}
              onViewDetails={setSelectedStock}
              onUntrack={handleUntrack}
            />
          ))}
        </div>
      )}

      {selectedStock && (
        <StockDetail
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

        .stocks-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
          gap: 24px;
        }

        @media (max-width: 768px) {
          .stocks-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
};

export default StockList;
