import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { getLedgerTrades, getLedgerConfig } from '../services/api';

const fmtMoney = (n) =>
  n == null ? '—' : Number(n).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
const fmtNum = (n, d = 2) => (n == null ? '—' : Number(n).toFixed(d));
const fmtPct = (n, d = 1) => (n == null ? '—' : `${(Number(n) * 100).toFixed(d)}%`);
const fmtSigned = (n) => {
  if (n == null) return '—';
  const v = Number(n);
  const s = v.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
  return v > 0 ? `+${s}` : s;
};
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '');
const pnlClass = (n) => (n == null ? '' : Number(n) > 0 ? 'ptl-pos' : Number(n) < 0 ? 'ptl-neg' : '');
const ENGINE_COLOR = { engine_1: '#3b82f6', engine_2: '#10b981' };

/**
 * EngineDetail — the drill-in for one engine (opened by clicking an EngineCard).
 * Shows the account header, an equity-vs-SPY chart (both scaled to starting_cash),
 * the trade history with expandable per-trade reasoning, and the read-only signal
 * config (weights + thresholds + active tools), locked to config_version.
 *
 * Props: engine, account, summary, healthEntry, equitySeries, benchmark, onBack.
 * Fetches its own trades + config on mount.
 */
const EngineDetail = ({ engine, account, summary, healthEntry, equitySeries, benchmark, onBack }) => {
  const [trades, setTrades] = useState([]);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [sortKey, setSortKey] = useState('entry_date');
  const [sortDir, setSortDir] = useState('desc');

  const toggleSort = (field) => {
    if (sortKey === field) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(field); setSortDir('desc'); }
  };
  const sortedTrades = useMemo(() => {
    const dir = sortDir === 'asc' ? 1 : -1;
    return [...trades].sort((a, b) => {
      const av = a[sortKey]; const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;            // nulls sort last
      if (bv == null) return -1;
      if (typeof av === 'string') return av.localeCompare(bv) * dir;
      return (Number(av) - Number(bv)) * dir;
    });
  }, [trades, sortKey, sortDir]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, c] = await Promise.all([
        getLedgerTrades({ engine, limit: 200 }),
        getLedgerConfig(),
      ]);
      setTrades(t.trades || []);
      setConfig((c.engines || {})[engine] || null);
    } finally {
      setLoading(false);
    }
  }, [engine]);

  useEffect(() => { load(); }, [load]);

  const start = account?.starting_cash ?? 100000;
  const chartData = useMemo(() => {
    const firstBenchmark = benchmark && benchmark[0] ? benchmark[0].close : null;
    const byDate = {};
    (equitySeries || []).forEach((p) => { byDate[p.date] = { date: p.date, equity: p.equity }; });
    (benchmark || []).forEach((p) => {
      if (!byDate[p.date]) byDate[p.date] = { date: p.date };
      if (firstBenchmark) byDate[p.date].spy = start * (p.close / firstBenchmark);
    });
    return Object.values(byDate).sort((a, b) => (a.date < b.date ? -1 : 1));
  }, [equitySeries, benchmark, start]);

  const hasEquity = (equitySeries || []).length > 1;
  const color = ENGINE_COLOR[engine] || '#888';

  return (
    <div className="ed">
      <div className="ed-toolbar">
        <button className="ed-back" onClick={onBack} title="Back to all engines">
          <span className="ed-back-arrow">←</span> All engines
        </button>
        <div className="ed-title-wrap">
          <span className="ed-title-dot" style={{ background: color }} />
          <h2 className="ed-title">{(engine || '').replace('_', ' #')}</h2>
          {account?.config_version && <span className="ed-title-cv">cfg {account.config_version}</span>}
        </div>
        <button className="ptl-refresh ed-refresh" onClick={load} disabled={loading}>
          {loading ? 'Refreshing…' : '↻ Refresh'}
        </button>
      </div>

      {/* Header / account summary */}
      <div className="ed-header">
        <Stat label="Equity" value={fmtMoney(account?.equity)} strong />
        <Stat label="Cash" value={fmtMoney(account?.cash)} />
        <Stat label="Started" value={fmtMoney(account?.starting_cash)} />
        <Stat label="Unrealized" value={fmtSigned(account?.unrealized_pnl)} />
        <Stat label="Realized" value={fmtSigned(account?.realized_pnl)} />
        <Stat label="Open / Closed" value={`${account?.open_trades ?? 0} / ${account?.closed_trades ?? 0}`} />
        <Stat label="Win rate" value={fmtPct(summary?.win_rate, 0)} />
        <Stat label="Avg realized R" value={fmtNum(summary?.avg_realized_r)} />
        <Stat label="Avg hold (d)" value={fmtNum(summary?.avg_hold_days, 1)} />
        <div className="ed-health">
          <span className={`ptl-health-status ptl-health-status--${healthEntry?.status || 'no_data'}`}>{healthEntry?.status || 'no_data'}</span>
          <span className="ed-health-detail">snapshot {healthEntry?.last_snapshot_date || 'none'}</span>
        </div>
      </div>

      {/* Equity vs S&P */}
      <section className="ptl-section">
        <h4>Accumulated Value vs S&amp;P 500</h4>
        {chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e2e2" />
              <XAxis dataKey="date" tick={{ fill: '#666', fontSize: 11 }} />
              <YAxis tick={{ fill: '#666', fontSize: 11 }} domain={['auto', 'auto']} width={75} tickFormatter={(v) => fmtMoney(v)} />
              <Tooltip contentStyle={{ background: '#fff', border: '1px solid #ccc', borderRadius: 4 }} formatter={(v) => fmtMoney(v)} />
              <Legend />
              <Line type="monotone" name={`${engine.replace('_', ' #')} equity`} dataKey="equity" stroke={color} dot={false} strokeWidth={2} connectNulls />
              <Line type="monotone" name="S&P 500 (SPY)" dataKey="spy" stroke="#999" dot={false} strokeWidth={2} strokeDasharray="5 4" connectNulls />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="ptl-empty">
            {hasEquity ? 'Not enough data to chart yet.' : 'No equity history yet — the first live cycle will start this curve. The dashed S&P line aligns once there is at least one point.'}
          </div>
        )}
      </section>

      {/* Trades with expandable reasoning */}
      <section className="ptl-section">
        <h4>Trades ({trades.length}) — click a row for the reasoning</h4>
        {trades.length === 0 ? (
          <div className="ptl-empty">No trades yet for this engine.</div>
        ) : (
          <div className="ptl-table-wrap">
            <table className="ptl-trades">
              <thead>
                <tr>
                  <SortTh label="Symbol" field="symbol" sortKey={sortKey} sortDir={sortDir} onToggle={toggleSort} />
                  <th>Signal</th>
                  <SortTh label="Status" field="status" sortKey={sortKey} sortDir={sortDir} onToggle={toggleSort} />
                  <SortTh label="Entry" field="entry_date" sortKey={sortKey} sortDir={sortDir} onToggle={toggleSort} />
                  <th>SL / TP</th>
                  <SortTh label="Exit" field="exit_date" sortKey={sortKey} sortDir={sortDir} onToggle={toggleSort} />
                  <SortTh label="Realized" field="realized_pnl" sortKey={sortKey} sortDir={sortDir} onToggle={toggleSort} />
                  <SortTh label="Unrealized" field="unrealized_pnl" sortKey={sortKey} sortDir={sortDir} onToggle={toggleSort} />
                </tr>
              </thead>
              <tbody>
                {sortedTrades.map((t) => (
                  <React.Fragment key={t.id}>
                    <tr className={`ptl-trade-row ptl-trade--${t.status}`} onClick={() => setExpandedId(expandedId === t.id ? null : t.id)}>
                      <td><strong>{t.symbol}</strong> <span className="ptl-expand">{expandedId === t.id ? '▾' : '▸'}</span></td>
                      <td>{t.signal_at_entry}{t.entry_confidence != null && ` (${fmtPct(t.entry_confidence)})`}</td>
                      <td><span className={`ptl-badge ptl-badge--${t.status}`}>{t.status}</span></td>
                      <td>{fmtMoney(t.entry_price)}<span className="ptl-date">{fmtDate(t.entry_date)}</span></td>
                      <td>{fmtMoney(t.stop_loss)} / {fmtMoney(t.take_profit)}</td>
                      <td>{t.exit_reason ? `${t.exit_reason}${t.exit_price != null ? ` @ ${fmtMoney(t.exit_price)}` : ''}` : '—'}<span className="ptl-date">{fmtDate(t.exit_date)}</span></td>
                      <td className={pnlClass(t.realized_pnl)}>{fmtSigned(t.realized_pnl)}</td>
                      <td className={pnlClass(t.unrealized_pnl)}>{fmtSigned(t.unrealized_pnl)}</td>
                    </tr>
                    {expandedId === t.id && (
                      <tr className="ptl-reasoning-row">
                        <td colSpan={8}>
                          <Reasoning payload={t.entry_reasoning} title="Why it was opened" />
                          {t.exit_reasoning && <Reasoning payload={t.exit_reasoning} title="Signal at exit" />}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Read-only config */}
      <section className="ptl-section">
        <h4>Signal Config <span className="ed-cv-tag">(read-only · cfg {config?.config_version || '—'} · {config?.schema})</span></h4>
        {config ? (
          <div className="ed-config">
            <div className="ed-config-col">
              <div className="ed-config-sub">Weights</div>
              {Object.entries(config.weights || {}).map(([k, w]) => (
                <div key={k} className="ed-weight">
                  <span className="ed-weight-name">{k}</span>
                  <div className="ed-weight-bar"><div className="ed-weight-fill" style={{ width: `${Math.min(100, Number(w) * 100)}%`, background: color }} /></div>
                  <span className="ed-weight-val">{Number(w).toFixed(2)}</span>
                </div>
              ))}
            </div>
            <div className="ed-config-col">
              <div className="ed-config-sub">Thresholds</div>
              <table className="ed-kv">
                <tbody>
                  {Object.entries(config.thresholds || {}).map(([k, v]) => (
                    <tr key={k}><td>{k}</td><td>{String(v)}</td></tr>
                  ))}
                </tbody>
              </table>
              <div className="ed-config-sub" style={{ marginTop: 12 }}>Active tools</div>
              <div className="ed-tags">{(config.active_components || []).map((c) => <span key={c} className="ed-tag">{c}</span>)}</div>
            </div>
          </div>
        ) : (
          <div className="ptl-empty">Config unavailable.</div>
        )}
      </section>
    </div>
  );
};

const SortTh = ({ label, field, sortKey, sortDir, onToggle }) => {
  const active = sortKey === field;
  return (
    <th className={`ed-sort-th${active ? ' active' : ''}`} onClick={() => onToggle(field)} title={`Sort by ${label}`}>
      {label}<span className="ed-sort-arrow">{active ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ' ⇅'}</span>
    </th>
  );
};

const Stat = ({ label, value, strong }) => (
  <div className="ed-stat">
    <span className="ed-stat-label">{label}</span>
    <span className={`ed-stat-val ${strong ? 'ed-stat-val--strong' : ''}`}>{value}</span>
  </div>
);

const Reasoning = ({ payload, title }) => {
  if (!payload) return null;
  const scores = payload.component_scores || {};
  const scoreEntries = Object.entries(scores);
  return (
    <div className="ed-reasoning">
      <div className="ed-reasoning-title">{title}{payload.regime ? ` · regime: ${payload.regime}` : ''}</div>
      {scoreEntries.length > 0 && (
        <div className="ed-reasoning-scores">
          {scoreEntries.map(([k, v]) => (
            <span key={k} className="ed-score-chip"><strong>{k}</strong>: {Number(v).toFixed(3)}</span>
          ))}
        </div>
      )}
      {(payload.reasoning || []).length > 0 && (
        <ul className="ed-reasoning-lines">
          {payload.reasoning.map((line, i) => <li key={i}>{line}</li>)}
        </ul>
      )}
      {scoreEntries.length === 0 && (payload.reasoning || []).length === 0 && (
        <div className="ptl-empty" style={{ padding: '4px 0' }}>No component detail recorded.</div>
      )}
    </div>
  );
};

export default EngineDetail;
