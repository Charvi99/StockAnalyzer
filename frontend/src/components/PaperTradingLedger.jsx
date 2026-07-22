import React, { useState, useEffect, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import {
  getLedgerAccounts,
  getLedgerTrades,
  getLedgerEquity,
  getLedgerSummary,
  getLedgerHealth,
} from '../services/api';
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

const ENGINE_COLORS = { engine_1: '#3b82f6', engine_2: '#10b981' };

/**
 * PaperTradingLedger — the dashboard for measuring recommendation quality and
 * A/B-scoring the two engines (audit decision D35).
 *
 * Two modes:
 *   - Dashboard (default, no stockId): account cards, equity curve, the A/B
 *     scorecard, and the /health heartbeat. Mounted at the app level.
 *   - Per-stock (stockId set): that stock's open/closed paper trades across
 *     engines. Mounted as a tab in StockDetailSideBySide.
 *
 * Read-only; everything comes from the Phase-1 ledger endpoints. A refresh
 * button re-fetches (the data updates once per trading day via the Celery beat).
 */
const PaperTradingLedger = ({ stockId = null, symbol = null }) => {
  const [accounts, setAccounts] = useState([]);
  const [equity, setEquity] = useState({ series: {} });
  const [summary, setSummary] = useState({ engines: {} });
  const [health, setHealth] = useState({ engines: [] });
  const [trades, setTrades] = useState([]);
  const [tradeFilter, setTradeFilter] = useState({ engine: '', status: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

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
      setEquity(eq || { series: {} });
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

      {/* Heartbeat */}
      <section className="ptl-section">
        <h4>Heartbeat</h4>
        <div className="ptl-health-row">
          {(health.engines || []).map((h) => (
            <div key={h.engine} className={`ptl-health ptl-health--${h.status}`}>
              <span className="ptl-health-engine">{h.engine.replace('_', ' #')}</span>
              <span className="ptl-health-status">{h.status}</span>
              <span className="ptl-health-detail">
                last snapshot: {h.last_snapshot_date || 'none'}
                {h.days_since_snapshot != null && ` · ${h.days_since_snapshot}d ago`}
              </span>
              <span className="ptl-health-detail">
                {h.open_trades} open · {h.trades_opened_this_week} opened this week
              </span>
            </div>
          ))}
          {(health.engines || []).length === 0 && (
            <div className="ptl-empty">No paper accounts found.</div>
          )}
        </div>
      </section>

      {/* Account cards */}
      <section className="ptl-section">
        <h4>Accounts</h4>
        <div className="ptl-cards">
          {accounts.map((a) => (
            <div key={a.engine} className="ptl-card">
              <div className="ptl-card-head">
                <span style={{ color: ENGINE_COLORS[a.engine] || '#666' }}>●</span>
                {a.engine.replace('_', ' #')}
                {a.config_version && <span className="ptl-cv" title="signal config_version">cfg {a.config_version}</span>}
              </div>
              <div className="ptl-card-grid">
                <Stat label="Equity" value={fmtMoney(a.equity)} strong />
                <Stat label="Cash" value={fmtMoney(a.cash)} />
                <Stat label="Unrealized" value={fmtSigned(a.unrealized_pnl)} />
                <Stat label="Realized" value={fmtSigned(a.realized_pnl)} />
                <Stat label="Open / Closed" value={`${a.open_trades} / ${a.closed_trades}`} />
                <Stat label="Started" value={fmtMoney(a.starting_cash)} />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Equity curve */}
      <section className="ptl-section">
        <h4>Equity Curve (90d)</h4>
        <div className="ptl-equity-grid">
          {engineNames.map((eng) => {
            const series = (equity.series || {})[eng] || [];
            return (
              <div key={eng} className="ptl-equity-card">
                <div className="ptl-equity-title">{eng.replace('_', ' #')}</div>
                {series.length > 1 ? (
                  <ResponsiveContainer width="100%" height={180}>
                    <LineChart data={series}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e2e2" />
                      <XAxis dataKey="date" tick={{ fill: '#666', fontSize: 11 }} />
                      <YAxis tick={{ fill: '#666', fontSize: 11 }} domain={['auto', 'auto']} width={70} />
                      <Tooltip contentStyle={{ background: '#fff', border: '1px solid #ccc', borderRadius: 4 }} />
                      <Line type="monotone" dataKey="equity" stroke={ENGINE_COLORS[eng] || '#888'} dot={false} strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="ptl-empty">No snapshots yet — the first cycle will write the curve.</div>
                )}
              </div>
            );
          })}
          {engineNames.length === 0 && <div className="ptl-empty">No accounts to chart.</div>}
        </div>
      </section>

      {/* A/B scorecard */}
      <section className="ptl-section">
        <h4>A/B Scorecard</h4>
        {engineNames.length > 0 ? (
          <table className="ptl-scorecard">
            <thead>
              <tr>
                <th>Metric</th>
                {engineNames.map((eng) => <th key={eng}>{eng.replace('_', ' #')}</th>)}
              </tr>
            </thead>
            <tbody>
              <ScoreRow label="Closed trades" engines={engineNames} get={(s) => s.closed_trades} />
              <ScoreRow label="Open trades" engines={engineNames} get={(s) => s.open_trades} />
              <ScoreRow label="Win rate" engines={engineNames} get={(s) => fmtPct(s.win_rate)} />
              <ScoreRow label="Avg planned R:R" engines={engineNames} get={(s) => fmtNum(s.avg_rr_planned)} />
              <ScoreRow label="Avg realized R" engines={engineNames} get={(s) => fmtNum(s.avg_realized_r)} />
              <ScoreRow label="Avg hold (days)" engines={engineNames} get={(s) => fmtNum(s.avg_hold_days, 1)} />
              <ScoreRow label="Total realized P&L" engines={engineNames} get={(s) => fmtSigned(s.total_realized_pnl)} strong />
            </tbody>
          </table>
        ) : (
          <div className="ptl-empty">No engine data yet.</div>
        )}
      </section>
    </div>
  );
};

// ── small presentational helpers ─────────────────────────────────────────────
const Stat = ({ label, value, strong }) => (
  <div className="ptl-stat">
    <span className="ptl-stat-label">{label}</span>
    <span className={`ptl-stat-value ${strong ? 'ptl-stat-value--strong' : ''}`}>{value}</span>
  </div>
);

const ScoreRow = ({ label, engines, get, strong }) => (
  <tr>
    <td className="ptl-score-label">{label}</td>
    {engines.map((eng) => <td key={eng} className={strong ? 'ptl-strong' : ''}>{get(eng)}</td>)}
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
