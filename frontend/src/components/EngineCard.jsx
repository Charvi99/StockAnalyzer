import React from 'react';
import { LineChart, Line, ResponsiveContainer } from 'recharts';

const fmtMoney = (n) =>
  n == null ? '—' : Number(n).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const fmtPct = (n, d = 1) =>
  n == null ? '—' : `${(Number(n) * 100).toFixed(d)}%`;

const ENGINE_COLOR = { engine_1: '#3b82f6', engine_2: '#10b981' };

/**
 * EngineCard — one card per paper-trading engine on the ledger dashboard.
 * Mirrors StockCard (clickable, hover lift). Clicking opens EngineDetail.
 *
 * Props: engine (name), account, summary, series (equity pts for the sparkline),
 *        healthEntry, onClick.
 */
const EngineCard = ({ engine, account, summary, series, healthEntry, onClick }) => {
  const equity = account?.equity ?? 0;
  const start = account?.starting_cash ?? equity;
  const totalReturn = start ? (equity - start) / start : null;
  const spark = (series || []).map((p, i) => ({ i, v: p.equity }));
  const health = healthEntry?.status || 'no_data';

  return (
    <div className="ec-card" onClick={onClick} role="button" tabIndex={0}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onClick()}>
      <div className="ec-top-bar" style={{ background: ENGINE_COLOR[engine] || '#888' }} />
      <div className="ec-body">
        <div className="ec-head">
          <span className="ec-title">{(engine || '').replace('_', ' #')}</span>
          <span className={`ec-health ec-health--${health}`} title={`beat ${health}`}>●</span>
        </div>

        <div className="ec-equity">{fmtMoney(equity)}</div>
        <div className={`ec-return ${totalReturn == null ? '' : totalReturn >= 0 ? 'ec-pos' : 'ec-neg'}`}>
          {totalReturn == null ? '—' : `${totalReturn >= 0 ? '+' : ''}${(totalReturn * 100).toFixed(2)}%`} all-time
        </div>

        <div className="ec-spark">
          {spark.length > 1 ? (
            <ResponsiveContainer width="100%" height={44}>
              <LineChart data={spark}>
                <Line type="monotone" dataKey="v" stroke={ENGINE_COLOR[engine] || '#888'} dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="ec-spark-empty">no equity history yet</div>
          )}
        </div>

        <div className="ec-stats">
          <div><span className="ec-stat-label">Win rate</span><span className="ec-stat-val">{fmtPct(summary?.win_rate, 0)}</span></div>
          <div><span className="ec-stat-label">Realized R</span><span className="ec-stat-val">{summary?.avg_realized_r == null ? '—' : Number(summary.avg_realized_r).toFixed(2)}</span></div>
          <div><span className="ec-stat-label">Open</span><span className="ec-stat-val">{account?.open_trades ?? 0}</span></div>
          <div><span className="ec-stat-label">Closed</span><span className="ec-stat-val">{account?.closed_trades ?? 0}</span></div>
        </div>

        {account?.config_version && (
          <div className="ec-cv" title="signal config_version">cfg {account.config_version}</div>
        )}
      </div>
    </div>
  );
};

export default EngineCard;
