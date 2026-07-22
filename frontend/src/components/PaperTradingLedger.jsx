import React, { useState, useEffect, useCallback } from 'react';
import {
  getLedgerAccounts,
  getLedgerTrades,
  getLedgerEquity,
  getLedgerSummary,
  getLedgerHealth,
} from '../services/api';
import EngineCard from './EngineCard';
import EngineDetail from './EngineDetail';
import './PaperTradingLedger.css';

// ── number formatting helpers ────────────────────────────────────────────────
const fmtMoney = (n) =>
  n == null ? '—' : Number(n).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
const fmtPct = (n, digits = 1) =>
  n == null ? '—' : `${(Number(n) * 100).toFixed(digits)}%`;
const fmtNum = (n, digits = 2) =>
  n == null ? '—' : Number(n).toFixed(digits);
const fmtSigned = (n) => {
  if (n == null) return '—';
  const v = Number(n);
  const s = v.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
  return v > 0 ? `+${s}` : s;
};
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '');
const pnlClass = (n) => (n == null ? '' : Number(n) > 0 ? 'ptl-pos' : Number(n) < 0 ? 'ptl-neg' : '');

/**
 * PaperTradingLedger — the dashboard for measuring recommendation quality and
 * A/B-scoring the two engines (audit decision D35).
 *
 * Two modes:
 *   - Dashboard (default, no stockId): a comparison strip + a card grid (one
 *     EngineCard per account); clicking a card opens EngineDetail (equity-vs-SPY,
 *     trades w/ reasoning, read-only config). Mounted at the app level.
 *   - Per-stock (stockId set): that stock's open/closed paper trades. Mounted as
 *     a tab in StockDetailSideBySide.
 *
 * Read-only; data from the Phase-1 ledger endpoints (updates once per trading day
 * via the Celery beat). A refresh button re-fetches.
 */
const PaperTradingLedger = ({ stockId = null, symbol = null }) => {
  const [accounts, setAccounts] = useState([]);
  const [equity, setEquity] = useState({ series: {}, benchmark: [] });
  const [summary, setSummary] = useState({ engines: {} });
  const [health, setHealth] = useState({ engines: [] });
  const [trades, setTrades] = useState([]);
  const [tradeFilter, setTradeFilter] = useState({ engine: '', status: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [selectedEngine, setSelectedEngine] = useState(null);

  const loadDashboard = useCallback(async () => {
    try {
      setError(null);
      const [acct, eq, sum, hl] = await Promise.all([
        getLedgerAccounts(),
        getLedgerEquity(null, 90),
        getLedgerSummary(),
        getLedgerHealth(),
      ]);
      setAccounts(acct.accounts || []);
      setEquity(eq || { series: {}, benchmark: [] });
      setSummary(sum || { engines: {} });
      setHealth(hl || { engines: [] });
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load ledger');
    }
  }, []);

  const loadTrades = useCallback(async () => {
    try {
      setError(null);
      const data = await getLedgerTrades({
        stockId: stockId ?? undefined,
        engine: tradeFilter.engine || undefined,
        status: tradeFilter.status || undefined,
        limit: 200,
      });
      setTrades(data.trades || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load trades');
    }
  }, [stockId, tradeFilter]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      if (stockId) {
        await loadTrades();
      } else {
        await loadDashboard();
      }
      setLastRefresh(new Date().toLocaleTimeString());
    } finally {
      setLoading(false);
    }
  }, [stockId, loadDashboard, loadTrades]);

  useEffect(() => { refresh(); }, [refresh]);

  // ── per-stock mode ────────────────────────────────────────────────────────
  if (stockId) {
    return (
      <div className="ptl ptl--stock">
        <div className="ptl-toolbar">
          <h3>📒 Paper Trades — {symbol}</h3>
          <button onClick={refresh} disabled={loading} className="ptl-refresh">
            {loading ? 'Refreshing…' : '↻ Refresh'}
          </button>
        </div>
        {error && <div className="ptl-error">{error}</div>}
        <div className="ptl-filters">
          <select value={tradeFilter.engine} onChange={(e) => setTradeFilter((f) => ({ ...f, engine: e.target.value }))}>
            <option value="">All engines</option>
            <option value="engine_1">Engine #1</option>
            <option value="engine_2">Engine #2</option>
          </select>
          <select value={tradeFilter.status} onChange={(e) => setTradeFilter((f) => ({ ...f, status: e.target.value }))}>
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="closed">Closed</option>
          </select>
          <span className="ptl-count">{trades.length} trade{trades.length === 1 ? '' : 's'}</span>
        </div>
        <TradesTable trades={trades} />
      </div>
    );
  }

  // ── dashboard mode ────────────────────────────────────────────────────────
  const engineNames = Object.keys(summary.engines || {});
  const healthFor = (eng) => (health.engines || []).find((h) => h.engine === eng) || null;

  // Drill-in: render EngineDetail with the engine-specific slices already loaded.
  if (selectedEngine) {
    const acct = accounts.find((a) => a.engine === selectedEngine) || null;
    return (
      <div className="ptl ptl--dashboard">
        {error && <div className="ptl-error">{error}</div>}
        <EngineDetail
          engine={selectedEngine}
          account={acct}
          summary={(summary.engines || {})[selectedEngine]}
          healthEntry={healthFor(selectedEngine)}
          equitySeries={(equity.series || {})[selectedEngine]}
          benchmark={equity.benchmark}
          onBack={() => setSelectedEngine(null)}
        />
      </div>
    );
  }

  return (
    <div className="ptl ptl--dashboard">
      <div className="ptl-toolbar">
        <h2>📒 Paper-Trading Ledger</h2>
        <div className="ptl-toolbar-right">
          {lastRefresh && <span className="ptl-updated">Updated {lastRefresh}</span>}
          <button onClick={refresh} disabled={loading} className="ptl-refresh">
            {loading ? 'Refreshing…' : '↻ Refresh'}
          </button>
        </div>
      </div>
      {error && <div className="ptl-error">{error}</div>}

      {/* A/B comparison strip */}
      {engineNames.length > 0 && (
        <section className="ptl-section">
          <h4>A/B Comparison</h4>
          <table className="ptl-scorecard">
            <thead>
              <tr>
                <th>Metric</th>
                {engineNames.map((eng) => <th key={eng}>{eng.replace('_', ' #')}</th>)}
              </tr>
            </thead>
            <tbody>
              <ScoreRow label="Equity" engines={engineNames} acct={accounts} get={(a) => fmtMoney(a?.equity)} strong />
              <ScoreRow label="All-time return" engines={engineNames} acct={accounts} get={(a) => (a && a.starting_cash ? fmtPct((a.equity - a.starting_cash) / a.starting_cash, 2) : '—')} />
              <ScoreRow label="Win rate" engines={engineNames} get={(eng) => fmtPct(summary.engines[eng]?.win_rate, 0)} />
              <ScoreRow label="Avg realized R" engines={engineNames} get={(eng) => fmtNum(summary.engines[eng]?.avg_realized_r)} />
              <ScoreRow label="Avg hold (days)" engines={engineNames} get={(eng) => fmtNum(summary.engines[eng]?.avg_hold_days, 1)} />
              <ScoreRow label="Total realized P&L" engines={engineNames} get={(eng) => fmtSigned(summary.engines[eng]?.total_realized_pnl)} strong />
            </tbody>
          </table>
        </section>
      )}

      {/* Engine cards */}
      <div className="ptl-cards">
        {accounts.map((a) => (
          <EngineCard
            key={a.engine}
            engine={a.engine}
            account={a}
            summary={(summary.engines || {})[a.engine]}
            series={(equity.series || {})[a.engine]}
            healthEntry={healthFor(a.engine)}
            onClick={() => setSelectedEngine(a.engine)}
          />
        ))}
        {accounts.length === 0 && <div className="ptl-empty">No paper accounts found.</div>}
      </div>
    </div>
  );
};

// ── small presentational helpers ─────────────────────────────────────────────
const ScoreRow = ({ label, engines, acct, get, strong }) => (
  <tr>
    <td className="ptl-score-label">{label}</td>
    {engines.map((eng) => {
      const val = acct ? get(acct.find((a) => a.engine === eng)) : get(eng);
      return <td key={eng} className={strong ? 'ptl-strong' : ''}>{val}</td>;
    })}
  </tr>
);

const TradesTable = ({ trades }) => {
  if (!trades.length) {
    return <div className="ptl-empty">No paper trades for this stock yet.</div>;
  }
  return (
    <div className="ptl-table-wrap">
      <table className="ptl-trades">
        <thead>
          <tr>
            <th>Engine</th><th>Signal</th><th>Status</th>
            <th>Entry</th><th>SL / TP</th><th>Size</th>
            <th>Exit</th><th>Realized</th><th>Unrealized</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.id} className={`ptl-trade--${t.status}`}>
              <td>{t.engine.replace('_', ' #')}</td>
              <td>{t.signal_at_entry}{t.entry_confidence != null && ` (${fmtPct(t.entry_confidence)})`}</td>
              <td><span className={`ptl-badge ptl-badge--${t.status}`}>{t.status}</span></td>
              <td>{fmtMoney(t.entry_price)}<span className="ptl-date">{fmtDate(t.entry_date)}</span></td>
              <td>{fmtMoney(t.stop_loss)} / {fmtMoney(t.take_profit)}</td>
              <td>{t.position_size}</td>
              <td>
                {t.exit_reason ? `${t.exit_reason}` : '—'}
                {t.exit_price != null && ` @ ${fmtMoney(t.exit_price)}`}
                {t.exit_date && <span className="ptl-date">{fmtDate(t.exit_date)}</span>}
              </td>
              <td className={pnlClass(t.realized_pnl)}>{fmtSigned(t.realized_pnl)}</td>
              <td className={pnlClass(t.unrealized_pnl)}>{fmtSigned(t.unrealized_pnl)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default PaperTradingLedger;
