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
def send_daily_digest(window: str = "PM"):
    """Twice-daily status digest (Phase 1.11b) — the "no need to open the frontend" email.

    Morning (AM, 08:30 ET) + evening (PM, 20:30 ET). ALWAYS sends a full digest:
    system status, both engines' A/B standing, high-conviction BUY watchlist
    (≥70%), vs S&P, top open movers, portfolio heat/cash, and warnings on top.
    Subject is ``[StockAnalyzer] Alert — …`` when something's wrong, else
    ``[StockAnalyzer] Digest — <date> <window>`` (so Gmail can filter on the tag).

    The digest arriving every day IS the system-up heartbeat: if it ever stops,
    the beat/worker is down (an in-stack task can't detect its own scheduler
    dying). **Never raises** — a failing digest best-effort fires an alert + swallows.
    """
    from app.services.alert_service import notify_alert
    from app.services.digest_service import compose_daily_digest

    logger.info("[ledger-digest] composing %s digest", window)
    db = SessionLocal()
    try:
        msg = compose_daily_digest(db, window)
        notify_alert(subject=msg["subject"], body=msg["body"], severity=msg["severity"])
        return {"status": "sent", "window": window, "had_issues": msg["has_issues"]}

    except Exception as e:
        logger.exception("[ledger-digest] %s digest failed: %s", window, e)
        try:
            notify_alert(
                subject="[StockAnalyzer] Alert — digest itself failed",
                body=f"The {window} send_daily_digest task errored:\n\n{e}",
                severity="error",
            )
        except Exception:
            logger.exception("[ledger-digest] meta-alert also failed")
        return {"status": "error", "window": window, "error": str(e)}

    finally:
        db.close()
