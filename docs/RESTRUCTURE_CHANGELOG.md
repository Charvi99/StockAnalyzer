# Restructure Changelog (Phase 0)

> Tracks every directory/file change made during the 2026-07-20 restructure so the
> "before" state is recoverable and reviewable. Branch: `chore/audit-restructure`.
> All moves use `git mv` (history preserved); untracks use `git rm --cached` /
> `git update-index --force-remove` (files stay on disk).

## BEFORE — top-level layout (tracked files, ~617)
```
backend/  frontend/  database/          # swing-trading app
ml-training/  ml_training/              # ML (hyphen=live, underscore=legacy-LIVE)
old_ml_pattern_recognizion/  oldTools/  backups/   # dead duplicates
docs/  (40 stale .md)  +  9 root-level .md
strategiesDocs/  outputs/  .serena/  .claude/
+ root scratch: test_market_hours.py, heart_message.py, fix_windows_ports.ps1,
  start.bat, start-debug.bat, current_stocks_backup.json, claude_code_zai_env.sh
+ tracked build artifacts: ml-training/mlruns/, ml-training/catboost_info/,
  backend/celerybeat-schedule
+ backend/ root: 13 check_*/test_*/fix_*/trigger_* scratch scripts
+ backend/app/services: chart_patterns_old.py, chart_patterns_extended.py
+ frontend/src/components/obsolite/
+ corrupted name: backend/scripts/CWork…check_pattern_timeframes.py
```

## AFTER — top-level layout (tracked files, 593)
```
backend/  frontend/  database/          # swing-trading app   (UNCHANGED)
ml-training/  ml_training/              # ML                  (UNCHANGED)
archive/                                # NEW — all dead code moved here
  ├── backend-dead/        chart_patterns_old.py, chart_patterns_extended.py,
  │                        corrupted_check_pattern_timeframes.py
  ├── backend-scratch/     13 check_*/test_*/fix_*/trigger_* scripts
  ├── frontend-dead/obsolite/  StockDetail.jsx
  ├── old_ml_pattern_recognizion/  oldTools/  backups/
docs/
  ├── AUDIT_PLAN.md        # NEW canonical
  ├── ARCHITECTURE.md      # NEW canonical
  └── RESTRUCTURE_CHANGELOG.md  # this file
logs/   (planned — gitignored ML/runtime scratch redirected here in future)
.gitignore  (+ mlruns/, catboost_info/, lightning_logs/, celerybeat-schedule*)
```

## Steps performed

### Phase 0a — archive verified-dead code  (commit 5663b1d)
Moved (history-preserving `git mv`, **no code edited**, zero live importers verified):
- `backend/app/services/chart_patterns_old.py` → `archive/backend-dead/`
- `backend/app/services/chart_patterns_extended.py` → `archive/backend-dead/`
- `frontend/src/components/obsolite/` → `archive/frontend-dead/obsolite/`
- `old_ml_pattern_recognizion/` → `archive/`
- `oldTools/` → `archive/`
- `backups/` → `archive/`
- 13 backend-root scratch scripts → `archive/backend-scratch/`
  (`check_aapl.py`, `check_aapl_fetch_log.py`, `check_timeframes.py`,
   `fix_indentation.py`, `test_celery_update.py`, `test_manual_fetch.py`,
   `test_phase1.py`, `test_phase2_api.py`, `test_phase4_endpoints.py`,
   `test_timestamp_update.py`, `test_trigger_simple.py`,
   `trigger_hourly_fetch.py`, `trigger_priority_calc.py`)
- corrupted-name `backend/scripts/*StockAnalyzercheck*.py`
  → `archive/backend-dead/corrupted_check_pattern_timeframes.py`

**Verification:** `grep -rn "chart_patterns_old\|chart_patterns_extended" backend/app`
→ no references. Entry points (`start.sh`, `migrate.py`, `migrate.sh`, Dockerfile)
left in place — scratch scripts were confirmed not referenced by them.

### Phase 0b — untrack build artifacts  (commit 29a2096)
Untracked from git (files remain on disk, now gitignored):
- `ml-training/mlruns/` (96 MLflow tracking files)
- `ml-training/catboost_info/` (6 CatBoost scratch)
- `backend/celerybeat-schedule` (Celery Beat runtime state, regenerated on run)

Added to `.gitignore`: `mlruns/`, `catboost_info/`, `lightning_logs/`,
`celerybeat-schedule`, `celerybeat-schedule.*`, `celerybeat.pid`.

**Kept tracked (intentional):** `ml-training/outputs/models/*.yaml` configs,
`ml_training/outputs/models/{lstm,gru}.{h5,keras}` legacy models (used live by
`ml_predictor.py:24`).

## Deferred — needs a decision (NOT done — see AUDIT_PLAN.md §5)
| Item | Why deferred | Action |
|---|---|---|
| `ml_training/` (underscore) | **Live** — holds LSTM/GRU models loaded by `ml_predictor.py:24` | Decide canonical ML lineage first |
| `ml.py` route (501 stub) | Mounted in `main.py:6,58`; archiving needs a paired code edit | Remove stub + edit `main.py` |
| `quiverquant_fetcher.py` (v1) | Not imported, but v1/v2 wiring unclear | Confirm v2 is sole user, then archive v1 |
| `ml-training/saved_models/*.ckpt` | Large checkpoints; deployed artifacts? | Untrack or keep — your call |
| Stale `.md` (root + docs/) | Phase-8/FinBERT contradictions | Move to `archive/docs/` (Phase 0c, pending) |
| Root scratch (test_market_hours.py, heart_message.py, .bat, .ps1) | May be used on Windows / manual ops | Confirm before moving |

## Rollback
Any step is reversible: `git revert <commit>` on branch `chore/audit-restructure`,
or `git checkout main` to ignore the branch entirely. No file content was destroyed
(untracks kept files on disk; moves are `git mv`).
