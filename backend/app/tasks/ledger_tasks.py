"""
Celery task for the paper-trading ledger (Phase 1, step 5).

One task per engine, each with its own ``SessionLocal`` (H4: isolated + replayable
— one engine's failure never blocks the other, and either engine can be re-run
independently). The task is a thin wrapper around ``LedgerService.run_cycle``:
it owns the DB session lifecycle and the transaction (commit on success, rollback
on failure); all signal + position math lives in the service. ``run_cycle`` only
``flush()``es, so the commit boundary is here.

The cycle is idempotent on ``cycle_id`` (signal-log UNIQUE(account,stock,cycle) +
ON CONFLICT DO NOTHING; equity snapshot upsert on (account,date); one-open-per-
(account,stock) partial unique index), so an ``acks_late`` redelivery or a retry
is a safe no-op.

Beat: ``engine_1`` daily at 19:00 ET (7pm — after the analysis batches have run on
the day's settled daily bars), queue ``maintenance``. ``engine_2``'s beat is added
in step 8 once it is seeded + validated.
"""
import logging
from datetime import date

from app.celery_app import celery_app
from app.db.database import SessionLocal
from app.models.ledger import PaperAccount
from app.utils.market_hours import get_current_et_time, is_market_holiday, is_weekend

logger = logging.getLogger(__name__)

# engine_2 is dispatch-ready (the adapter raises NotImplementedError until step 8),
# so manual/programmatic triggering won't hit a silent wrong path — but the beat
# only schedules engine_1 until step 8.
VALID_ENGINES = ("engine_1", "engine_2")


def _today_et_date() -> date:
    """The logical trading date for this cycle = today's calendar date in ET.

    The beat fires at 19:00 ET, after the regular close, so 'today' in ET is the
    trading day whose daily bar just settled and is what signals are evaluated on.
    """
    return get_current_et_time().date()


@celery_app.task(bind=True, max_retries=3)
def run_paper_trading_cycle(self, engine: str = "engine_1"):
    """Run one paper-trading cycle for ``engine``.

    Owns its own ``SessionLocal`` (H4 isolation) and the transaction. Per-stock
    errors are already contained inside ``LedgerService`` (C4), so a single bad row
    can't abort the cycle — only structural failures (DB down, account unseeded,
    unexpected orchestration error) bubble up here.

    Non-trading days (weekend / market holiday) are skipped: there is no fresh
    daily bar to evaluate, and logging a signal + flat snapshot under a non-trading
    date would only pollute the audit trail. ``is_market_holiday`` degrades to
    "not a holiday" if Polygon is unreachable, so this guard can never block a
    real trading day on an external-API hiccup.

    Returns a small summary dict (for the Celery result / health checks).
    """
    if engine not in VALID_ENGINES:
        # Config error — don't retry (retrying can't fix a bad engine name).
        logger.error("[ledger] refusing unknown engine %r", engine)
        return {"status": "error", "engine": engine, "error": f"unknown engine {engine!r}"}

    cycle_id = _today_et_date()

    # Skip non-trading days — no fresh bar, and a flat snapshot under a non-trading
    # date is pure noise on the equity curve + signal log.
    if is_weekend() or is_market_holiday():
        logger.info("[ledger %s] skipping non-trading day %s (weekend/holiday)", engine, cycle_id)
        return {
            "status": "skipped",
            "engine": engine,
            "cycle_id": str(cycle_id),
            "reason": "non-trading day",
        }

    logger.info("[ledger %s] starting cycle for %s", engine, cycle_id)
    db = SessionLocal()
    try:
        from app.services.ledger_service import LedgerService

        service = LedgerService(db, engine)
        summary = service.run_cycle(cycle_id=cycle_id)
        db.commit()
        logger.info("[ledger %s] cycle %s complete: %s", engine, cycle_id, summary)
        return summary

    except ValueError as e:
        # Config error (e.g. no paper_account seeded for this engine) — retrying
        # won't help. Roll back and fail this invocation cleanly, no retry.
        db.rollback()
        logger.error("[ledger %s] config error, not retrying: %s", engine, e)
        return {
            "status": "error",
            "engine": engine,
            "cycle_id": str(cycle_id),
            "error": str(e),
        }

    except Exception as e:
        # Transient/structural failure (DB connection, etc.). Idempotent on
        # cycle_id, so a retry is a safe no-op for the rows already written.
        db.rollback()
        logger.error("[ledger %s] cycle failed for %s: %s", engine, cycle_id, e)
        raise self.retry(exc=e, countdown=300)

    finally:
        db.close()


@celery_app.task
def check_ledger_health():
    """Daily ledger health verification (Phase 1.11 hardening).

    Scheduled ~1h after the 19:00 paper-trading cycles so the day's snapshot
    already exists. For each engine it checks two things and alerts if either fails:

      - **staleness** — no fresh snapshot ⇒ the beat / worker / cycle stalled.
      - **reconciliation** — the latest snapshot's cash/equity/realized P&L must
        match a fresh recomputation from the live tables (catches a crash-mid-cycle
        that debited cash without recording the trade, a mark-to-market bug, etc.).

    Pushes via ``alert_service.notify_alert`` (always logs; webhook/email if
    configured). **Never raises**: a health checker that crashes on its own error
    masks the very problem it's meant to surface, so even a meta-failure best-effort
    fires an alert and swallows.

    Limitation: this task is itself scheduled by the beat, so it catches a stalled
    worker / erroring cycle but NOT the beat container dying (a dead beat schedules
    nothing). Full dead-beat coverage needs an external monitor pinging /health.
    """
    from app.services.alert_service import notify_alert
    from app.services.ledger_health_service import compute_engine_health, reconcile_account

    logger.info("[ledger-health] starting daily check")
    db = SessionLocal()
    try:
        health = compute_engine_health(db)
        stalled = [h for h in health if h["status"] in ("stale", "no_data")]

        recon_problems = []
        for h in health:
            acct = db.query(PaperAccount).filter(PaperAccount.engine == h["engine"]).first()
            if acct is None:
                continue
            r = reconcile_account(db, acct.id)
            if r.get("has_snapshot") and not r.get("ok"):
                recon_problems.append(r)

        if not stalled and not recon_problems:
            logger.info("[ledger-health] all engines healthy + reconciled")
            return {"status": "ok", "engines": len(health)}

        lines = []
        for h in stalled:
            lines.append(
                f"- {h['engine']}: {h['status']} — last snapshot "
                f"{h['last_snapshot_date']} ({h['days_since_snapshot']}d ago); "
                f"equity ${h['equity']:.0f}, {h['open_trades']} open positions"
            )
        for r in recon_problems:
            d = r["deltas"]
            lines.append(
                f"- {r['engine']}: books don't reconcile (snapshot @ {r['snapshot_date']}) — "
                f"cash Δ${d['cash']:.2f}, equity Δ${d['equity']:.2f}, realized Δ${d['realized']:.2f}"
            )
        notify_alert(
            subject=(
                f"Paper-trading ledger needs attention "
                f"({len(stalled)} stalled, {len(recon_problems)} not reconciling)"
            ),
            body="\n".join(lines),
            severity="error" if stalled else "warning",
        )
        return {
            "status": "alerted",
            "stalled": len(stalled),
            "recon_problems": len(recon_problems),
        }

    except Exception as e:
        # The checker itself failed (e.g. DB unreachable) — exactly when an alert is
        # most valuable. Best-effort fire one, then swallow. Never raise (see docstring).
        logger.exception("[ledger-health] check itself failed: %s", e)
        try:
            notify_alert(
                subject="Ledger health check ITSELF failed",
                body=f"The daily check_ledger_health task errored:\n\n{e}",
                severity="error",
            )
        except Exception:
            logger.exception("[ledger-health] failed to send the meta-alert too")
        return {"status": "error", "error": str(e)}

    finally:
        db.close()
