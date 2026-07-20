# FU — Frontend (audit report, consolidated FU1–3)

Verified 2026-07-20 against `frontend/src/` (~14K LOC, 23 components, React 18 / CRA).
Stack: `axios`, `lightweight-charts`, `recharts`. **No state-management lib** (no
Redux/Zustand/React Query), **no router** (no react-router). Tag legend: ✅ confirmed · ⛔ false positive.

## Headline
The frontend has a **clean, centralized API layer** (`services/api.js`, env-configurable,
with an incremental-polling design already in place) — better discipline than expected. The
core weakness is the absence of a **data layer**: every component hand-rolls loading/error/
refetch state, so the good polling design is fragile for unattended use. For the 24/7
paper-trading goal the frontend is the *viewing* layer (the backend is the engine), so these
are lower-priority than the backend findings — except polling robustness and the 51 dev
markers. No code changed.

## Findings

### FU1 ✅ CONFIRMED (architecture) — no data layer; loading/error logic duplicated per component
- 8 components import `services/api` directly; **42** hand-rolled loading `useState` sites and
  **108** error-handling sites (`try/catch`, `console.error`, `setError`) scattered across them.
- No React Query / SWR / context store → no shared cache, no request dedup, no global retry or
  stale-while-revalidate. Selecting the same stock in two places fires two fetches.
- `api.js` has **no axios interceptors** → no centralized error normalization (500/429/network
  all surface differently) and no auth-token injection point (consistent with backend A3, but
  blocks adding auth later without touching every call).
- **Fix:** introduce React Query (or SWR) as the data layer — it gives caching, dedup, retry,
  and refetch-on-focus for ~free, and collapses those 42+108 sites into a few hooks. Add an
  axios response interceptor for uniform error handling.

### FU2 ✅ CONFIRMED (reliability, 24/7-relevant) — polling is well-intentioned but not robust
`StockList.jsx:307` polls every 30s using the incremental `getRecentUpdates` /
`getAnalysisByIds` pair (good design — only refetches changed stocks). Cleanup IS present
(`return () => clearInterval(...)` at `:309`) — ⛔ the "missing cleanup / leak" hypothesis was a
**false positive**. Real gaps for unattended operation:
- **No overlap guard** — `checkForUpdates` is async; if a cycle takes >30s (slow API under
  load), the next interval fires concurrently → overlapping `getAnalysisByIds` calls and
  `setState` races on stale data. Needs an `isFetching` flag or `setTimeout`-rearm pattern.
- **No tab-visibility pause** — keeps polling every 30s when the tab is hidden (wasted
  requests; matters for a dashboard left open 24/7).
- **No error backoff** — on repeated failure it keeps hammering every 30s.
- `FetchCountdown` and `MarketStatus` poll every **1s** (`setInterval(..., 1000)`) — aggressive
  re-render cadence; fine if cheap, worth confirming the work per tick.

### FU3 ✅ CONFIRMED (visualization / supporting) — large components + dev noise
- Several 1000–2000 LOC components (`ChartPatterns.jsx` 2064, `TechnicalAnalysis.jsx` 1440,
  `IndicatorInfo.jsx` 1394, `StockList.jsx` 1297) — hard to maintain; natural split targets.
- **51 dev markers** (`console.log` / `TODO` / `FIXME` / `HACK`) across components — production
  noise and unfinished-work signals. E.g. `StockList.jsx:295-299` logs emoji poll traces.
- `App.jsx` "Project Team" section has literal template placeholders (`[Jakub Charvat]`,
  `[https://github.com/Charvi99]`) — unfinished, ships to users.

### FU4 ✅ CONFIRMED (minor, 24/7) — health check is one-shot
`App.jsx:10-22` checks API health **once on mount**. If the API drops after load, the header
still reads "ok". For a dashboard meant to stay open, health should poll (slowly) or ride on
the existing data-poll failure signal.

## Positives (verified)
- ⛔ **Centralized, env-configured API layer** — `api.js` with `REACT_APP_API_URL || localhost`,
  one axios instance, clean endpoint functions. Good.
- ⛔ **Incremental polling design exists** (`getRecentUpdates`/`getAnalysisByIds`) — the right
  idea for efficient 24/7 refresh; just needs hardening (FU2).
- ⛔ **Polling cleanup is present** — no memory leak (corrected hypothesis).
- Consistent symbol/param conventions across endpoints.

## Status
- **Audit-only — no frontend code changed.**
- **For the 24/7 goal:** the only frontend items that matter before a paper-trading run are
  FU2 (polling robustness, so the dashboard reflects state accurately) and stripping the 51
  dev markers. FU1 (data layer) is the right refactor but can wait until after the run.
- Test: `python3 backend/tests/test_fu_frontend.py` → source-inspects the frontend: locks in
  the centralized-api + cleanup-present positives and counts the dev markers (FU3). (Note:
  proper component tests should use the CRA `jest` setup; this is a static guard.)

## Open decisions added (feed into AUDIT_PLAN §5)
- **D26:** Adopt React Query/SWR as the data layer + an axios error interceptor (FU1).
- **D27:** Harden polling — overlap guard, visibility pause, error backoff (FU2, 24/7-relevant).
- **D28:** Strip the 51 dev markers + fix `App.jsx` template placeholders (FU3).
- **D29:** Poll health in the header (or surface data-poll failure) instead of one-shot (FU4).
- **D30:** Split the 1000–2000 LOC components (FU3, maintainability).
