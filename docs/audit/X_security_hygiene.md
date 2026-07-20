# X — Cross-cutting: Security, Config & Repo Hygiene (audit report, X1 + X2)

Verified 2026-07-20 against `backend/app/main.py`, `app/db/database.py`, fetchers,
`backend/requirements.txt`, `.gitignore`, and the `archive/` layout. Tag legend: ✅ confirmed · ⛔ false positive.

## Headline
Secrets are handled well (env vars, `.env` gitignored), but the **CORS config is the #1
security risk for a 24/7 internet-exposed run**: wildcard origins + credentials + all methods,
on an API with **no authentication**. Dependencies are ~18 months stale and one
(`python-jose`) carries known advisories — though it's installed but unused. No code changed.

## X1 — Security & Config

### X1.1 ✅ CONFIRMED (critical, 24/7) — permissive CORS + no auth
`main.py:46-49`:
```python
CORSMiddleware,
allow_origins=["*"],      # "In production, replace with specific origins"
allow_credentials=True,
allow_methods=["*"],
```
Combined with **no authentication on any endpoint** (A3 — POST/PATCH/DELETE on stocks,
patterns, ML ops are all open), any web origin can drive the API: create/delete stocks,
trigger fetches, delete patterns/models, train ML. `allow_origins=["*"]` + `allow_credentials=True`
is also invalid under the CORS spec (browsers reject the combo), so the *intent* (credentialed
cross-origin) silently fails while the wildcard still allows uncredentialed cross-origin writes.
**Fix:** set `allow_origins` to an explicit allow-list from env, drop `allow_credentials` (or pair
it with a real origin list), and add auth (a token header at minimum; `python-jose` is already
installed for JWT). This is the gating item before exposing the app.

### X1.2 ✅ CONFIRMED (config footgun) — hardcoded DB password in the fallback
`app/db/database.py:7`:
```python
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://stockuser:stockpass123@localhost:5432/stock_analyzer")
```
Not a leaked secret (it's a dev default), but a weak default credential baked into source — and a
silent footgun: if `DATABASE_URL` is unset in a deploy, the app connects with `stockpass123`
instead of failing loudly. **Fix:** no default for `DATABASE_URL` in prod (raise if unset), and a
separate, stronger dev credential in `.env.example` only.

### X1.3 ✅ CONFIRMED (deps, 24/7) — stale dependencies + known advisories
Pinned versions are ~early-2024 (fastapi 0.109.0, pydantic 2.5.3, sqlalchemy 2.0.25,
tensorflow 2.15.0, ~18 months old). Specifically:
- **`python-jose==3.3.0`** — carries published advisories (alg-confusion / DoS family). It is
  installed but **not wired to any auth** (A3), so currently unexploitable — but the moment JWT
  auth is added (X1.1 fix), this version must be upgraded first.
- **`tensorflow==2.15.0`** — legacy ML path only; older TF has many advisories.
- I did **not** run a CVE scan against a live database — calibrated claim, not an exhaustive list.
**Fix:** run `pip-audit` (and `npm audit` for the frontend) in CI, then upgrade/replace flagged
packages. Treat the pinned set as overdue for a refresh.

### X1.4 ✅ CONFIRMED (config) — no central Settings despite pydantic-settings installed
Config is ad-hoc `os.getenv` scattered across `celery_app.py`, `database.py`, and each fetcher
(every one re-reads `POLYGON_API_KEY` / `QUIVERQUANT_API_KEY` independently). `pydantic-settings==2.1.0`
is in requirements but **unused**. This is the "config not magic numbers" theme (§7 of the summary)
applied to infra: no single validated config object, no fail-fast on missing required env.
**Fix:** one `Settings(BaseSettings)` class (DB url, API keys, CORS allow-list, thresholds,
rate limits) — also unblocks D13 (tunable pattern thresholds) and D24.

### X1.5 ✅ CONFIRMED (minor, 24/7) — `/docs` (Swagger UI) exposed by default
No `docs_url`/`openapi_url` override in `main.py` → the interactive API explorer is public. For an
internet-exposed 24/7 run that's a free attack-surface map. **Fix:** `docs_url=None,
openapi_url=None` when `ENV=prod` (or behind auth).

## X1 — Positives (verified)
- ⛔ **API keys via env, not hardcoded** — `POLYGON_API_KEY`, `QUIVERQUANT_API_KEY`,
  `CELERY_BROKER_URL` all `os.getenv(...)`. No secrets in source.
- ⛔ **`.env` is gitignored**; only `.env.example` is tracked (correct). No tracked `.env` leak.
- `python-jose` + `cryptography` present — the tooling for auth is already there, just unused.

## X2 — Repo Hygiene (mostly resolved by Phase 0)
Phase 0 (commits `5663b1d` archive + `29a2096` untrack) already handled the bulk:
- dead code → `archive/` (chart_patterns_old/extended, old_ml_pattern_recognizion, oldTools,
  backups, 13 scratch scripts, the corrupted-name file).
- build artifacts untracked + `.gitignore` (`mlruns/`, `catboost_info/`, `celerybeat-schedule*`).

**Residuals still open (decisions, not bugs):**
- `database/init.sql` is stale vs alembic (S5 / D22).
- Root-level scratch files (`.bat`, `.ps1`, `test_market_hours.py`, `heart_message.py`) —
  deferred pending confirmation they're not used on Windows/manual ops (RESTRUCTURE_CHANGELOG).
- Two stale-`.md` contradictions (Phase-8/FinBERT) — Phase 0c curate-to-`archive/docs/` deferred.
- `backend/celerybeat-schedule` shows as modified in git status (runtime state; gitignored now).

## Status
- **Audit-only — no code changed.**
- **Gating items for a 24/7 internet-exposed run:** X1.1 (CORS + auth), X1.3 (pip-audit + jose
  upgrade before wiring auth), X1.5 (hide /docs). X1.2/X1.4 are config-hardening.
- Test: `python3 backend/tests/test_X_security.py` → locks in the positives (`.env` gitignored,
  no tracked secrets, keys via env) and flags the known issues (CORS wildcard, DB default pw).

## Open decisions added (feed into AUDIT_PLAN §5)
- **D31:** CORS allow-list from env + drop wildcard credentials + add auth (X1.1) — **gating.**
- **D32:** `pip-audit` / `npm audit` in CI; upgrade `python-jose` before wiring JWT (X1.3).
- **D33:** Central `Settings(BaseSettings)`; fail-fast on missing prod env (X1.2/X1.4).
- **D34:** Disable `/docs` in prod (X1.5).
- X2 residuals fold into D22 (init.sql) + a Phase 0c curate pass.
