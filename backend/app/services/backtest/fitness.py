"""
Fitness metrics + composite scalar for a backtest (Phase 2).

Pure: operates on the equity-curve list + closed-trade list (and an optional SPY
total return over the same window). Produces the metric dict stored on
``BacktestRun.metrics`` and the composite ``fitness`` scalar the Phase-3 GA
maximizes.

Composite (default): ``Sharpe − dd_penalty·|max_drawdown|``, with a strong
penalty when the run traded fewer than ``trade_count_floor`` times (disqualifies
never-trade / under-traded edge cases that would otherwise score well on a flat,
zero-drawdown curve). All knobs are pass-through so Phase-3 can re-tune the
objective without editing this module.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

TRADING_DAYS = 252


def _daily_returns(equity: List[float]) -> List[float]:
    out = []
    for i in range(1, len(equity)):
        prev = equity[i - 1]
        if prev:
            out.append(equity[i] / prev - 1.0)
    return out


def compute_metrics(
    equity_curve: List[Dict],
    closed_trades: List,
    starting_cash: float,
    spy_return: Optional[float] = None,
    trading_days_per_year: int = TRADING_DAYS,
) -> Dict:
    """Compute the full metric set from a replay account's equity curve.

    ``closed_trades`` items expose ``realized_pnl`` (the BTTrade/PaperTrade attr).
    """
    equity = [float(r["equity"]) for r in equity_curve]
    n_days = len(equity)
    if n_days == 0 or not starting_cash:
        return _empty_metrics()

    final = equity[-1]
    total_return = (final - starting_cash) / starting_cash
    cagr = (final / starting_cash) ** (trading_days_per_year / n_days) - 1.0 if n_days else 0.0

    rets = _daily_returns(equity)
    if rets:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        std = math.sqrt(var)
        sharpe = (mean / std) * math.sqrt(trading_days_per_year) if std > 0 else 0.0
    else:
        sharpe = 0.0

    peak = equity[0]
    mdd = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak:
            mdd = min(mdd, (v - peak) / peak)
    calmar = (cagr / abs(mdd)) if mdd < 0 else 0.0

    pnls = [float(getattr(t, "realized_pnl", None) or 0.0) for t in closed_trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    win_rate = (len(wins) / len(pnls)) if pnls else None
    profit_factor = (sum(wins) / abs(sum(losses))) if losses else None  # None = no losing trades
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0

    in_market = sum(1 for r in equity_curve if (r.get("open_trades_count") or 0) > 0)
    pct_time = in_market / len(equity_curve) if equity_curve else 0.0

    alpha = (total_return - spy_return) if spy_return is not None else None

    return {
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": mdd,
        "calmar": calmar,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "trade_count": len(pnls),
        "pct_time_in_market": pct_time,
        "alpha_vs_spy": alpha,
        "n_days": n_days,
        "final_equity": final,
    }


def _empty_metrics() -> Dict:
    return {
        "total_return": 0.0, "cagr": 0.0, "sharpe": 0.0, "max_drawdown": 0.0,
        "calmar": 0.0, "win_rate": None, "profit_factor": None,
        "avg_win": 0.0, "avg_loss": 0.0, "trade_count": 0,
        "pct_time_in_market": 0.0, "alpha_vs_spy": None, "n_days": 0, "final_equity": 0.0,
    }


def fitness(
    metrics: Dict,
    dd_penalty: float = 0.5,
    trade_count_floor: int = 5,
    no_trade_penalty: float = 10.0,
) -> float:
    """Composite GA objective: risk-adjusted return minus drawdown cost, with a
    steep penalty for under-traded runs (a flat curve scores Sharpe 0 / 0 DD but
    isn't a real strategy)."""
    sharpe = metrics.get("sharpe") or 0.0
    mdd = metrics.get("max_drawdown") or 0.0
    base = sharpe - dd_penalty * abs(mdd)
    if (metrics.get("trade_count") or 0) < trade_count_floor:
        base -= no_trade_penalty
    return base
