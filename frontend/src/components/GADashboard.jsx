import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import {
  listGARuns, getGARun, createGARun,
  listBacktests, getBacktest, createBacktest,
  getLedgerConfig,
} from '../services/api';
import './GADashboard.css';

// ── number formatting helpers (mirror PaperTradingLedger) ────────────────────
const fmtNum = (n, d = 3) => (n == null || n === '' ? '—' : Number(n).toFixed(d));
const fmtPct = (n, d = 1) => (n == null ? '—' : `${(Number(n) * 100).toFixed(d)}%`);
const fmtMoney = (n) =>
  n == null ? '—' : Number(n).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
const fmtDateShort = (iso) =>
  iso ? new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—';
// fitness values are typically in the tens/hundreds; gap > 3 signals overfit
const OVERFIT_GAP_THRESHOLD = 3;
const gapClass = (g) => {
  if (g == null) return '';
  return Math.abs(Number(g)) > OVERFIT_GAP_THRESHOLD ? 'ga-gap-bad' : 'ga-gap-ok';
};

// Format an elapsed duration (ms) as e.g. "2m 14s".
const fmtElapsed = (startIso, now) => {
  if (!startIso) return '—';
  const ms = Math.max(0, now - new Date(startIso).getTime());
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const rs = s % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m`;
  }
  return m > 0 ? `${m}m ${rs}s` : `${rs}s`;
};

// Human-readable phase label for a run. While running, derives the LIVE phase from
// config._progress (written by run_ga_task each step): "Precomputing inputs (X/N
// stocks)" then "Optimizing — generation X/Y" — so the 3s poll shows real progress
// instead of a bare "running".
const phaseLabel = (run) => {
  const status = run?.status;
  if (status === 'pending') return 'Queued — waiting for a worker…';
  if (status === 'completed') return 'Completed';
  if (status === 'failed') return 'Failed';
  if (status === 'running') {
    const p = run?.config?._progress;
    if (p?.phase === 'precompute') {
      const w = p.window ? `${p.window} ` : '';
      return `Precomputing ${w}inputs (${p.done || 0}/${p.total || '?'} stocks)`;
    }
    if (p?.phase === 'optimize') {
      return `Optimizing — generation ${p.generation || 0}/${p.total_generations || '?'}`;
    }
    return 'Starting…'; // between worker pickup and the first progress callback
  }
  return status || '';
};

/**
 * Compute a plain-language verdict from train/val fitness + the gap.
 * The gap is the primary overfit signal ("gap says everything").
 *   healthy: val positive AND gap small
 *   overfit: gap large (train >> val — doesn't generalize)
 *   noedge:  val fitness absent/negative, or vastly under-traded
 */
const VERDICTS = {
  healthy: { cls: 'ga-verdict--healthy', icon: '✅', title: 'Healthy — held up out-of-sample' },
  overfit: { cls: 'ga-verdict--overfit', icon: '⚠️', title: 'Likely overfit — do not promote' },
  noedge:  { cls: 'ga-verdict--noedge',  icon: '❌', title: 'No edge — under-traded / negative' },
  unknown: { cls: 'ga-verdict--unknown', icon: '⏳', title: 'Awaiting results' },
};
const computeVerdict = (run) => {
  if (!run || (run.status !== 'completed')) return { ...VERDICTS.unknown, detail: 'Results appear when the optimization completes.' };
  const val = run.best_val_fitness == null ? null : Number(run.best_val_fitness);
  const train = run.best_train_fitness == null ? null : Number(run.best_train_fitness);
  const gap = run.train_val_gap == null ? null : Number(run.train_val_gap);
  const tc = run.best_val_metrics?.trade_count;
  const floor = run.config?.trade_count_floor ?? 5;

  // No edge: validation is negative (loses money out-of-sample) or under-traded.
  if ((val != null && val < 0) || (tc != null && tc < floor)) {
    return { ...VERDICTS.noedge, detail: `Validation fitness is ${fmtNum(val, 2)}${tc != null ? ` with only ${tc} trades (floor ${floor})` : ''}. The strategy doesn't generalize.` };
  }
  // Overfit: large gap between train and val.
  if (gap != null && Math.abs(gap) > OVERFIT_GAP_THRESHOLD) {
    return { ...VERDICTS.overfit, detail: `Train fit ${fmtNum(train, 2)} vs val fit ${fmtNum(val, 2)} — a gap of ${fmtNum(gap, 2)} means the weights fit the training window too closely.` };
  }
  // Healthy.
  return { ...VERDICTS.healthy, detail: `Val fit ${fmtNum(val, 2)} holds up near train fit ${fmtNum(train, 2)} (gap ${fmtNum(gap, 2)}). Safe to consider promoting.` };
};

/**
 * Rough runtime estimate for a GA launch.
 * Runtime scales ~linearly with stocks × days (cache build is the wall, ~0.7s
 * per stock-day) plus a per-generation cost. Returns a descriptor + minutes.
 */
const estimateRun = ({ max_stocks, start_date, end_date, pop_size, generations }) => {
  const ms = Number(max_stocks) || 0;
  if (!ms || !start_date || !end_date) return null;
  const days = Math.max(1, Math.round((new Date(end_date) - new Date(start_date)) / 86400000));
  const stockDays = ms * days;
  // cache: ~0.7s/stock-day; GA evals: pop_size × generations × (cache-build-ish backtest) ~ crude
  const cacheMin = (stockDays * 0.7) / 60;
  const gaMin = ((Number(pop_size) || 20) * (Number(generations) || 15) * 0.05); // heuristic
  const totalMin = Math.max(1, Math.round(cacheMin + gaMin));
  const bundles = Math.round(stockDays / 250); // ~1 trading-year per bundle
  let cls = 'ga-estimate';
  if (totalMin > 60) cls += ' ga-estimate--heavy';
  else if (totalMin > 15) cls += ' ga-estimate--warn';
  return { totalMin, bundles, cls, stockDays, days };
};

/**
 * GADashboard — the Phase 3.1 backtest + GA dashboard.
 *
 * Card-based layout (NOT tabs), mirroring PaperTradingLedger:
 *   - A top-level view toggle switches the whole panel between "GA Lab" and
 *     "Backtests".
 *   - In GA Lab: a two-column layout. Left column = launcher form + the runs
 *     list. Right column = the selected run's persistent detail card (it stays
 *     mounted across navigation — clicking a row just changes which run shows).
 *   - The most-recently-launched run id is held at the TOP LEVEL so its live
 *     status survives navigation; it appears as a status card above the list.
 *
 * Polling cadence mirrors PaperTradingLedger (3s while pending/running).
 */
const GADashboard = () => {
  const [view, setView] = useState('ga'); // 'ga' | 'backtests'
  // Lifted, persistent state (survives navigation):
  const [activeRunId, setActiveRunId] = useState(null);   // most-recently-launched (live status card)
  const [selectedRunId, setSelectedRunId] = useState(null); // which run's detail is open
  const [activeRun, setActiveRun] = useState(null);       // the launched run's latest data (polled here)

  // Poll the launched run at the top level so its status survives navigation.
  const activePollRef = useRef(null);
  const stopActivePoll = useCallback(() => {
    if (activePollRef.current) { clearInterval(activePollRef.current); activePollRef.current = null; }
  }, []);
  useEffect(() => () => stopActivePoll(), [stopActivePoll]);

  const startActivePoll = useCallback((id) => {
    stopActivePoll();
    const tick = async () => {
      try {
        const r = await getGARun(id);
        setActiveRun(r);
        if (r.status === 'completed' || r.status === 'failed') {
          stopActivePoll();
          // Auto-select the completed run so the user lands on its detail.
          setSelectedRunId(id);
        }
      } catch { /* keep polling; transient */ }
    };
    tick();
    activePollRef.current = setInterval(tick, 3000);
  }, [stopActivePoll]);

  const handleLaunched = useCallback((id) => {
    setActiveRunId(id);
    setActiveRun(null);
    setSelectedRunId(id); // open detail immediately so the running state is visible
    startActivePoll(id);
  }, [startActivePoll]);

  const handleOpen = useCallback((id) => {
    setSelectedRunId(id);
  }, []);

  return (
    <div className="ga">
      <div className="ga-toolbar">
        <h2>🧬 GA / Backtest Lab</h2>
        <div className="ga-viewtoggle">
          <button className={`ga-viewtoggle-btn ${view === 'ga' ? 'active' : ''}`} onClick={() => setView('ga')}>GA Lab</button>
          <button className={`ga-viewtoggle-btn ${view === 'backtests' ? 'active' : ''}`} onClick={() => setView('backtests')}>Backtests</button>
        </div>
      </div>

      {view === 'ga' ? (
        <div className="ga-layout">
          <div className="ga-layout-col">
            <GALauncher onLaunched={handleLaunched} estimate={estimateRun} />
            {activeRunId && (
              <ActiveRunCard run={activeRun} runId={activeRunId} onOpen={() => setSelectedRunId(activeRunId)} />
            )}
            <GARunsList onOpen={handleOpen} selectedRunId={selectedRunId} />
          </div>
          <div className="ga-layout-col">
            {selectedRunId ? (
              <GARunDetail runId={selectedRunId} />
            ) : (
              <div className="ga-detail-empty">
                <div className="ga-detail-empty-icon">🧬</div>
                <div>Select a run from the list — or launch one — to see its detail here.</div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <BacktestsView />
      )}
    </div>
  );
};

// ── Active Run status card (lifted: survives navigation) ─────────────────────
const ActiveRunCard = ({ run, runId, onOpen }) => {
  if (!run) {
    return (
      <div className="ga-active-run">
        <div className="ga-active-run-row">
          <span className="ga-spinner" style={{ width: 18, height: 18, borderWidth: 3 }} />
          <span className="ga-active-run-title">Run #{runId} launching…</span>
        </div>
      </div>
    );
  }
  const terminal = run.status === 'completed' || run.status === 'failed';
  return (
    <div className="ga-active-run">
      <div className="ga-active-run-row">
        <span className={`ga-status ga-status--${run.status}`}>{run.status}</span>
        <span className="ga-active-run-title">Run #{runId} — {run.engine}</span>
        {terminal && run.status === 'completed' && (
          <span>Val fit <strong>{fmtNum(run.best_val_fitness, 2)}</strong> · Gap <strong className={gapClass(run.train_val_gap)}>{fmtNum(run.train_val_gap, 2)}</strong></span>
        )}
        <button className="ga-refresh" style={{ marginLeft: 'auto', padding: '4px 12px' }} onClick={onOpen}>
          View detail →
        </button>
      </div>
    </div>
  );
};

// ── GA Launcher ──────────────────────────────────────────────────────────────
const DEFAULT_FORM = {
  engine: 'engine_2',
  start_date: '2024-01-01',
  end_date: '2025-01-01',
  max_stocks: 10,
  pop_size: 20,
  generations: 15,
  seed: 0,
  train_split: 0.7,
  dd_penalty: 0.5,
  trade_count_floor: 5,
  starting_cash: 100000.0,
};

const GALauncher = ({ onLaunched, estimate }) => {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const est = estimate(form);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        ...form,
        max_stocks: Number(form.max_stocks),
        pop_size: Number(form.pop_size),
        generations: Number(form.generations),
        seed: Number(form.seed),
        train_split: Number(form.train_split),
        dd_penalty: Number(form.dd_penalty),
        trade_count_floor: Number(form.trade_count_floor),
        starting_cash: Number(form.starting_cash),
      };
      const run = await createGARun(payload);
      onLaunched(run.id);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to launch GA run');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="ga-section" onSubmit={submit}>
      <h4>Launch a Genetic-Algorithm weight search</h4>
      <div className="ga-form">
        <div className="ga-field">
          <label>Engine</label>
          <select value={form.engine} onChange={(e) => setField('engine', e.target.value)}>
            <option value="engine_1">engine_1</option>
            <option value="engine_2">engine_2</option>
          </select>
        </div>
        <div className="ga-field">
          <label>Start date</label>
          <input type="date" value={form.start_date} onChange={(e) => setField('start_date', e.target.value)} />
        </div>
        <div className="ga-field">
          <label>End date</label>
          <input type="date" value={form.end_date} onChange={(e) => setField('end_date', e.target.value)} />
        </div>
        <div className="ga-field">
          <label>Max stocks (universe size)</label>
          <input type="number" min="1" max="200" value={form.max_stocks} onChange={(e) => setField('max_stocks', e.target.value)} />
          <span className="ga-field-help">Runtime scales ~linearly with stocks × days. Cache build is the wall (~0.7s/stock-day). Keep ≤ ~10 stocks for fast iteration.</span>
        </div>
        <div className="ga-field">
          <label>Population size</label>
          <input type="number" min="2" value={form.pop_size} onChange={(e) => setField('pop_size', e.target.value)} />
        </div>
        <div className="ga-field">
          <label>Generations</label>
          <input type="number" min="1" value={form.generations} onChange={(e) => setField('generations', e.target.value)} />
        </div>
        <div className="ga-field">
          <label>Seed (0 = random)</label>
          <input type="number" min="0" value={form.seed} onChange={(e) => setField('seed', e.target.value)} />
        </div>
        <div className="ga-field">
          <label>Train split (overfit guard)</label>
          <input type="number" min="0.01" max="0.99" step="0.01" value={form.train_split} onChange={(e) => setField('train_split', e.target.value)} />
        </div>
        <div className="ga-field">
          <label>Drawdown penalty</label>
          <input type="number" min="0" step="0.1" value={form.dd_penalty} onChange={(e) => setField('dd_penalty', e.target.value)} />
        </div>
        <div className="ga-field">
          <label>Trade-count floor</label>
          <input type="number" min="0" value={form.trade_count_floor} onChange={(e) => setField('trade_count_floor', e.target.value)} />
        </div>
        <div className="ga-field">
          <label>Starting cash ($)</label>
          <input type="number" min="0" step="1000" value={form.starting_cash} onChange={(e) => setField('starting_cash', e.target.value)} />
        </div>
        <div className="ga-form-actions">
          <button type="submit" className="ga-submit" disabled={submitting}>
            {submitting ? 'Launching…' : '🚀 Launch GA run'}
          </button>
          {est && (
            <span className={est.cls}>
              ≈ {est.bundles} bundle{est.bundles === 1 ? '' : 's'} · {est.stockDays.toLocaleString()} stock-days · est. ~{est.totalMin} min
              {est.totalMin > 60 ? ' (heavy — consider fewer stocks/shorter window)' : est.totalMin > 15 ? ' (moderate)' : ''}
            </span>
          )}
        </div>
      </div>
      <div style={{ marginTop: 10, fontSize: 12, color: '#888' }}>
        Recommendation: ≤ ~10 stocks and ≤ ~1.5 years for iteration. The per-(stock, T) input cache is held in memory for the whole run.
      </div>
    </form>
  );
};

// ── GA Runs List ─────────────────────────────────────────────────────────────
const GARunsList = ({ onOpen, selectedRunId }) => {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [engine, setEngine] = useState('');
  const [lastRefresh, setLastRefresh] = useState(null);
  const pollRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      const data = await listGARuns({ engine: engine || undefined, limit: 100 });
      setRuns(data.runs || []);
      setLastRefresh(new Date().toLocaleTimeString());
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load GA runs');
    } finally {
      setLoading(false);
    }
  }, [engine]);

  useEffect(() => { load(); }, [load]);

  // Auto-refresh while any run is still pending/running (so the list stays live).
  useEffect(() => {
    const hasActive = runs.some((r) => r.status === 'pending' || r.status === 'running');
    if (!hasActive) return;
    pollRef.current = setInterval(load, 4000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [runs, load]);

  return (
    <div className="ga-section">
      <div className="ga-toolbar" style={{ marginBottom: 10 }}>
        <h4 style={{ margin: 0 }}>GA Runs</h4>
        <div className="ga-toolbar-right">
          <select value={engine} onChange={(e) => setEngine(e.target.value)} className="ga-viewtoggle-btn" style={{ background: '#fff' }}>
            <option value="">All engines</option>
            <option value="engine_1">engine_1</option>
            <option value="engine_2">engine_2</option>
          </select>
          {lastRefresh && <span className="ga-updated">Updated {lastRefresh}</span>}
          <button onClick={load} disabled={loading} className="ga-refresh">
            {loading ? '…' : '↻'}
          </button>
        </div>
      </div>

      {error && <div className="ga-error">{error}</div>}

      {runs.length === 0 ? (
        <div className="ga-empty">No GA runs yet. Launch one above.</div>
      ) : (
        <div className="ga-table-wrap">
          <table className="ga-runs">
            <thead>
              <tr>
                <th>ID</th><th>Engine</th><th>Status</th>
                <th>Train fit</th>
                <th className="ga-highlight" title="Fitness on unseen validation data — the key metric">Val fit</th>
                <th className="ga-highlight" title="Train−Val. Large gap = overfit.">Gap</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className={`ga-run-row ${selectedRunId === r.id ? 'ga-run-row--active' : ''}`} onClick={() => onOpen(r.id)}>
                  <td className="ga-run-id">#{r.id}</td>
                  <td>{r.engine}</td>
                  <td><span className={`ga-status ga-status--${r.status}`}>{r.status}</span></td>
                  <td>{fmtNum(r.best_train_fitness, 2)}</td>
                  <td className="ga-highlight">{fmtNum(r.best_val_fitness, 2)}</td>
                  <td className={gapClass(r.train_val_gap)}>{fmtNum(r.train_val_gap, 2)}</td>
                  <td>{fmtDate(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

// ── GA Run Detail (persistent card) ──────────────────────────────────────────
const GARunDetail = ({ runId }) => {
  const [run, setRun] = useState(null);
  const [liveDefaults, setLiveDefaults] = useState(null); // engine live weights for comparison
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [now, setNow] = useState(() => Date.now());
  const pollRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      const data = await getGARun(runId);
      setRun(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load GA run');
    } finally {
      setLoading(false);
    }
  }, [runId]);

  // Fetch the engine's live config (weights) for side-by-side comparison.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cfg = await getLedgerConfig();
        if (!cancelled) setLiveDefaults(cfg);
      } catch { /* config is best-effort for comparison */ }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => { load(); }, [load]);

  // If still running, keep polling + tick the elapsed clock.
  useEffect(() => {
    if (!run || (run.status !== 'pending' && run.status !== 'running')) return;
    pollRef.current = setInterval(load, 3000);
    const clock = setInterval(() => setNow(Date.now()), 1000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); clearInterval(clock); };
  }, [run, load]);

  // Merged comparison series + at-a-glance returns. This block (incl. the useMemo)
  // MUST sit before the early returns below — React hooks can't be called
  // conditionally, so guard for run==null inside the hook. Mirrors EngineDetail.jsx.
  const startCash = Number(run?.config?.starting_cash) || 100000;
  const hasBaseline = Array.isArray(run?.baseline_equity_curve) && run.baseline_equity_curve.length > 0;
  const hasSpy = Array.isArray(run?.benchmark) && run.benchmark.length > 0;
  const chartData = useMemo(() => {
    if (!run) return [];
    const byDate = {};
    (run.equity_curve || []).forEach((p) => { byDate[p.date] = { date: p.date, equity: p.equity }; });
    if (hasBaseline) {
      (run.baseline_equity_curve || []).forEach((p) => {
        if (!byDate[p.date]) byDate[p.date] = { date: p.date };
        byDate[p.date].baseline = p.equity;
      });
    }
    if (hasSpy) {
      const firstSpy = run.benchmark[0].close;
      (run.benchmark || []).forEach((p) => {
        if (!byDate[p.date]) byDate[p.date] = { date: p.date };
        byDate[p.date].spy = startCash * (p.close / firstSpy);
      });
    }
    return Object.values(byDate).sort((a, b) => (a.date < b.date ? -1 : 1));
  }, [run, hasBaseline, hasSpy, startCash]);

  const lastOf = (arr) => (Array.isArray(arr) && arr.length ? arr[arr.length - 1] : null);
  const optFinal = lastOf(run?.equity_curve)?.equity;
  const baseFinal = hasBaseline ? lastOf(run?.baseline_equity_curve)?.equity : null;
  const spyReturn = hasSpy ? lastOf(run?.benchmark)?.return_pct : null;
  const optReturn = optFinal != null ? (optFinal - startCash) / startCash : null;
  const baseReturn = baseFinal != null ? (baseFinal - startCash) / startCash : null;

  if (error) return <div className="ga-error">{error}</div>;
  if (!run) return <div className="ga-empty">{loading ? 'Loading…' : 'No data.'}</div>;

  const isRunning = run.status === 'pending' || run.status === 'running';
  const verdict = computeVerdict(run);
  const generations = Array.isArray(run.generations) ? run.generations : [];
  const equityCurve = Array.isArray(run.equity_curve) ? run.equity_curve : [];
  const engineCfg = liveDefaults?.engines?.[run.engine] || liveDefaults?.[run.engine];
  const liveWeights = engineCfg?.weights || engineCfg?.signal_weights || {};
  const genData = generations.map((g) => ({ gen: g.generation, best: g.best, mean: g.mean, worst: g.worst }));

  return (
    <>
      <div className="ga-detail-head">
        <h3 className="ga-detail-title">Run #{run.id} — {run.engine}</h3>
        <span className={`ga-status ga-status--${run.status}`}>{run.status}</span>
        <span className="ga-detail-subtitle">created {fmtDate(run.created_at)}</span>
        <button onClick={load} disabled={loading} className="ga-refresh" style={{ marginLeft: 'auto' }}>
          {loading ? 'Refreshing…' : '↻ Refresh'}
        </button>
      </div>

      {/* RUNNING / PENDING: progress card — live phase + generation, never "nothing" */}
      {isRunning && (
        <div className="ga-section">
          <div className="ga-progress">
            <div className="ga-spinner" />
            <div className="ga-progress-status">{phaseLabel(run)}</div>
            <div className="ga-progress-elapsed">
              elapsed {fmtElapsed(run.started_at || run.created_at, now)}
              {run.started_at == null && <span> (queued, not started)</span>}
            </div>
            {run?.config?._progress?.phase === 'optimize'
              && run?.config?._progress?.best != null && (
              <div className="ga-progress-note">
                best train fitness:{' '}
                <strong>{Number(run.config._progress.best).toFixed(3)}</strong>
                {run.config._progress.mean != null && (
                  <> · this gen&rsquo;s mean {Number(run.config._progress.mean).toFixed(3)}</>
                )}
              </div>
            )}
            <div className="ga-progress-note">
              {run?.config?._progress?.phase === 'precompute'
                ? 'Building the per-(stock, day) input cache — the one-time step before optimization.'
                : 'Live per-generation fitness appears in the chart below as each generation completes.'}
            </div>
          </div>
        </div>
      )}

      {/* FAILED: show the error */}
      {run.status === 'failed' && run.error && (
        <div className="ga-error">Error: {run.error}</div>
      )}

      {/* Verdict badge — the headline (only meaningful once completed) */}
      {run.status === 'completed' && (
        <div className={`ga-verdict ${verdict.cls}`}>
          <span className="ga-verdict-icon">{verdict.icon}</span>
          <div className="ga-verdict-body">
            <span className="ga-verdict-title">{verdict.title}</span>
            <span className="ga-verdict-detail">{verdict.detail}</span>
          </div>
        </div>
      )}

      {/* Fitness summary strip — with plain-language captions */}
      {run.status === 'completed' && (
        <div className="ga-section">
          <h4>Fitness breakdown</h4>
          <div className="ga-fit-strip">
            <div className="ga-fit-stat">
              <span className="ga-fit-label">Train fit</span>
              <span className="ga-fit-val">{fmtNum(run.best_train_fitness, 2)}</span>
              <span className="ga-fit-caption">on the optimization window</span>
            </div>
            <div className="ga-fit-stat">
              <span className="ga-fit-label">Val fit</span>
              <span className="ga-fit-val ga-fit-val--strong">{fmtNum(run.best_val_fitness, 2)}</span>
              <span className="ga-fit-caption">on unseen validation data</span>
            </div>
            <div className="ga-fit-stat">
              <span className="ga-fit-label">Gap (train − val)</span>
              <span className={`ga-fit-val ${gapClass(run.train_val_gap)}`}>{fmtNum(run.train_val_gap, 2)}</span>
              <span className="ga-fit-caption">large gap ⇒ overfit</span>
            </div>
          </div>
        </div>
      )}

      {/* Weight comparison: best vs live defaults (only once completed) */}
      {run.status === 'completed' && (
        <WeightComparison best={run.best_weights || {}} defaults={liveWeights} />
      )}

      {/* Per-generation fitness chart */}
      {genData.length > 0 && (
        <div className="ga-section">
          <h4>Per-generation fitness</h4>
          <div className="ga-chart">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={genData} margin={{ top: 8, right: 20, bottom: 8, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                <XAxis dataKey="gen" tick={{ fontSize: 12 }} label={{ value: 'generation', position: 'insideBottom', offset: -2, fontSize: 11 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="best" stroke="#2ed573" strokeWidth={2} dot={false} name="best" />
                <Line type="monotone" dataKey="mean" stroke="#667eea" strokeWidth={2} dot={false} name="mean" />
                <Line type="monotone" dataKey="worst" stroke="#ff4757" strokeWidth={1.5} dot={false} name="worst" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Optimized vs original engine vs S&P 500 (train window) */}
      {chartData.length > 1 && (
        <div className="ga-section">
          <h4>Optimized vs original engine vs S&amp;P 500 <span className="ga-chart-sub">(train window)</span></h4>
          <div className="ga-chart">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 8, right: 20, bottom: 8, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={fmtDateShort} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => fmtMoney(v)} domain={['auto', 'auto']} />
                <Tooltip labelFormatter={fmtDateShort} formatter={(v) => fmtMoney(v)} />
                <Legend />
                <Line type="monotone" dataKey="equity" stroke="#10b981" strokeWidth={2} dot={false} name="Optimized" connectNulls />
                {hasBaseline && (
                  <Line type="monotone" dataKey="baseline" stroke="#3b82f6" strokeWidth={2} dot={false} strokeDasharray="6 4" name="Original engine" connectNulls />
                )}
                {hasSpy && (
                  <Line type="monotone" dataKey="spy" stroke="#999" strokeWidth={2} dot={false} strokeDasharray="5 4" name="S&P 500 (SPY)" connectNulls />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
          {/* At-a-glance: did optimization beat the original engine AND the market? */}
          <div className="ga-cmp-strip">
            <span className="ga-cmp-stat">Optimized <strong>{fmtPct(optReturn)}</strong></span>
            {hasBaseline && <span className="ga-cmp-stat">Original <strong>{fmtPct(baseReturn)}</strong></span>}
            {hasSpy && <span className="ga-cmp-stat">S&amp;P 500 <strong>{fmtPct(spyReturn)}</strong></span>}
          </div>
        </div>
      )}

      {/* Metrics: train vs val */}
      {run.status === 'completed' && (
        <div className="ga-section">
          <h4>Metrics</h4>
          <div className="ga-metrics-grid">
            <div className="ga-metrics-col">
              <div className="ga-fit-label" style={{ marginBottom: 6 }}>Best train metrics</div>
              <MetricsTable metrics={run.best_train_metrics} />
            </div>
            <div className="ga-metrics-col">
              <div className="ga-fit-label" style={{ marginBottom: 6 }}>Best val metrics</div>
              <MetricsTable metrics={run.best_val_metrics} />
            </div>
          </div>
        </div>
      )}

      {/* Config dump */}
      {run.config && (
        <div className="ga-section">
          <h4>Config</h4>
          <div className="ga-config-list">
            {Object.entries(run.config).map(([k, v]) => (
              <span key={k} className="ga-config-chip">{k}: {String(v)}</span>
            ))}
          </div>
          {run.config_version && <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>config_version: {run.config_version}</div>}
        </div>
      )}
    </>
  );
};

// Side-by-side weight comparison with bar viz per weight.
const WeightComparison = ({ best, defaults }) => {
  const keys = Array.from(new Set([...Object.keys(best || {}), ...Object.keys(defaults || {})]));
  if (keys.length === 0) {
    return <div className="ga-section"><h4>Best weights vs live defaults</h4><div className="ga-empty">No weights available.</div></div>;
  }
  const maxAbs = Math.max(0.0001, ...keys.map((k) => Math.max(Math.abs(best?.[k] ?? 0), Math.abs(defaults?.[k] ?? 0))));

  return (
    <div className="ga-section">
      <h4>Best weights vs live defaults</h4>
      <div className="ga-weights">
        {keys.map((k) => {
          const bv = best?.[k];
          const dv = defaults?.[k];
          return (
            <div key={k} className="ga-weight">
              <span className="ga-weight-name">{k}</span>
              <span className="ga-weight-track">
                {dv != null && (
                  <span className="ga-weight-fill ga-weight-fill--default" style={{ width: `${(Math.abs(Number(dv)) / maxAbs) * 100}%`, position: 'absolute', top: 0, left: 0, opacity: 0.4 }} />
                )}
                {bv != null && (
                  <span className="ga-weight-fill" style={{ width: `${(Math.abs(Number(bv)) / maxAbs) * 100}%`, position: 'absolute', top: 0, left: 0 }} />
                )}
              </span>
              <span className="ga-weight-val">
                {fmtNum(bv, 3)}{dv != null && <span className="ga-weight-val-default"> / {fmtNum(dv, 3)}</span>}
              </span>
            </div>
          );
        })}
      </div>
      <div style={{ marginTop: 8, fontSize: 11, color: '#999' }}>
        Bar = best weight (indigo) over live default (grey). Value column: best / default.
      </div>
    </div>
  );
};

const MetricsTable = ({ metrics }) => {
  const entries = Object.entries(metrics || {});
  if (entries.length === 0) return <div className="ga-empty">No metrics.</div>;
  return (
    <table className="ga-kv">
      <tbody>
        {entries.map(([k, v]) => (
          <tr key={k}>
            <td>{k}</td>
            <td>{typeof v === 'number' ? (k.includes('rate') ? fmtPct(v, 1) : k.includes('return') || k.includes('drawdown') ? fmtPct(v, 2) : fmtNum(v, 3)) : String(v ?? '—')}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};

// ── Backtests (lower priority: launcher + list, full-width) ──────────────────
const BacktestsView = () => {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [engine, setEngine] = useState('');
  const [form, setForm] = useState({
    engine: 'engine_2', start_date: '2024-01-01', end_date: '2025-01-01',
    max_stocks: 30, starting_cash: 100000.0, dd_penalty: 0.5, trade_count_floor: 5,
  });
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState(null);

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      const data = await listBacktests({ engine: engine || undefined, limit: 50 });
      setRuns(data.runs || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load backtests');
    } finally {
      setLoading(false);
    }
  }, [engine]);

  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const payload = {
        ...form,
        max_stocks: Number(form.max_stocks),
        starting_cash: Number(form.starting_cash),
        dd_penalty: Number(form.dd_penalty),
        trade_count_floor: Number(form.trade_count_floor),
      };
      const run = await createBacktest(payload);
      setNotice(`Backtest #${run.id} launched (status: ${run.status}).`);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to launch backtest');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <form className="ga-section" onSubmit={submit}>
        <h4>Launch a backtest (no-look-ahead historical run)</h4>
        <div className="ga-form">
          <div className="ga-field">
            <label>Engine</label>
            <select value={form.engine} onChange={(e) => setField('engine', e.target.value)}>
              <option value="engine_1">engine_1</option>
              <option value="engine_2">engine_2</option>
            </select>
          </div>
          <div className="ga-field">
            <label>Start date</label>
            <input type="date" value={form.start_date} onChange={(e) => setField('start_date', e.target.value)} />
          </div>
          <div className="ga-field">
            <label>End date</label>
            <input type="date" value={form.end_date} onChange={(e) => setField('end_date', e.target.value)} />
          </div>
          <div className="ga-field">
            <label>Max stocks</label>
            <input type="number" min="1" max="200" value={form.max_stocks} onChange={(e) => setField('max_stocks', e.target.value)} />
          </div>
          <div className="ga-field">
            <label>Starting cash ($)</label>
            <input type="number" min="0" step="1000" value={form.starting_cash} onChange={(e) => setField('starting_cash', e.target.value)} />
          </div>
          <div className="ga-field">
            <label>Drawdown penalty</label>
            <input type="number" min="0" step="0.1" value={form.dd_penalty} onChange={(e) => setField('dd_penalty', e.target.value)} />
          </div>
          <div className="ga-field">
            <label>Trade-count floor</label>
            <input type="number" min="0" value={form.trade_count_floor} onChange={(e) => setField('trade_count_floor', e.target.value)} />
          </div>
          <div className="ga-form-actions">
            <button type="submit" className="ga-submit" disabled={submitting}>
              {submitting ? 'Launching…' : '▶ Run backtest'}
            </button>
            <span className="ga-form-hint">Async; refresh the list below to track status.</span>
          </div>
        </div>
      </form>

      {notice && <div className="ga-success">{notice}</div>}
      {error && <div className="ga-error">{error}</div>}

      <div className="ga-toolbar">
        <div className="ga-viewtoggle" style={{ marginBottom: 0 }}>
          <select value={engine} onChange={(e) => setEngine(e.target.value)} className="ga-viewtoggle-btn" style={{ background: '#fff' }}>
            <option value="">All engines</option>
            <option value="engine_1">engine_1</option>
            <option value="engine_2">engine_2</option>
          </select>
        </div>
        <div className="ga-toolbar-right">
          <button onClick={load} disabled={loading} className="ga-refresh">
            {loading ? 'Refreshing…' : '↻ Refresh'}
          </button>
        </div>
      </div>

      <div className="ga-section">
        {runs.length === 0 ? (
          <div className="ga-empty">No backtests yet.</div>
        ) : (
          <div className="ga-table-wrap">
            <table className="ga-runs">
              <thead>
                <tr>
                  <th>ID</th><th>Engine</th><th>Status</th>
                  <th>Fitness</th><th>Total return</th><th>Sharpe</th>
                  <th>Max DD</th><th>Trades</th><th>Created</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => {
                  const m = r.metrics || {};
                  return (
                    <tr key={r.id}>
                      <td className="ga-run-id">#{r.id}</td>
                      <td>{r.engine}</td>
                      <td><span className={`ga-status ga-status--${r.status}`}>{r.status}</span></td>
                      <td className="ga-highlight">{fmtNum(r.fitness, 2)}</td>
                      <td>{fmtPct(m.total_return, 2)}</td>
                      <td>{fmtNum(m.sharpe, 2)}</td>
                      <td>{fmtPct(m.max_drawdown, 2)}</td>
                      <td>{m.trade_count ?? '—'}</td>
                      <td>{fmtDate(r.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
};

export default GADashboard;
