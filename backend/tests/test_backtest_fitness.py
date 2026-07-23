"""
Fitness-module test (Phase 2). Pure-Python, no DB:
``python3 backend/tests/test_backtest_fitness.py``.

Checks compute_metrics + the composite fitness on synthetic equity curves with
hand-computed expected values (return, max drawdown, Sharpe sign, win rate,
profit factor, SPY alpha) and the under-trade-floor penalty.
"""
import math
import sys
from dataclasses import dataclass
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.backtest.fitness import compute_metrics, fitness  # noqa: E402

FAILURES = []
START = 100_000.0


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if (detail and not cond) else ""))
    if not cond:
        FAILURES.append(name)


@dataclass
class FT:
    realized_pnl: float


def curve(equity_values, in_market_days=None):
    in_market_days = in_market_days if in_market_days is not None else len(equity_values)
    return [
        {"equity": v, "cash": v, "open_positions_value": 0.0,
         "open_trades_count": 1 if i < in_market_days else 0}
        for i, v in enumerate(equity_values)
    ]


def noisy_uptrend():
    rs = [0.003, -0.001, 0.004, 0.002, -0.002, 0.005, 0.001, 0.003, -0.001, 0.004] * 6
    eq = [START]
    for r in rs:
        eq.append(eq[-1] * (1 + r))
    return eq


def main():
    print("[1] noisy uptrend -> positive return, positive Sharpe, small drawdown")
    eq = noisy_uptrend()
    m = compute_metrics(curve(eq), [], START)
    check("total_return > 0", m["total_return"] > 0, m["total_return"])
    check("sharpe > 0", m["sharpe"] > 0, m["sharpe"])
    check("max_drawdown <= 0", m["max_drawdown"] <= 1e-9, m["max_drawdown"])

    print("[2] flat curve -> zero return, zero Sharpe, zero drawdown")
    m = compute_metrics(curve([START] * 30), [], START)
    check("total_return == 0", abs(m["total_return"]) < 1e-9)
    check("sharpe == 0", abs(m["sharpe"]) < 1e-9)
    check("max_drawdown == 0", abs(m["max_drawdown"]) < 1e-9)

    print("[3] constructed drawdown 120k->90k = -25%")
    eq = [START, 120_000.0, 90_000.0, 100_000.0]
    m = compute_metrics(curve(eq), [], START)
    check("max_drawdown == -0.25", abs(m["max_drawdown"] - (-0.25)) < 1e-9, m["max_drawdown"])

    print("[4] win rate + profit factor")
    trades = [FT(100.0), FT(-50.0), FT(200.0)]
    m = compute_metrics(curve(noisy_uptrend()), trades, START)
    check("win_rate == 2/3", abs((m["win_rate"] or 0) - 2 / 3) < 1e-9, m["win_rate"])
    check("profit_factor == 6.0", abs((m["profit_factor"] or 0) - 6.0) < 1e-9, m["profit_factor"])
    check("trade_count == 3", m["trade_count"] == 3)

    print("[5] alpha vs SPY")
    m = compute_metrics(curve(noisy_uptrend()), [], START, spy_return=0.10)
    check("alpha_vs_spy == total_return - 0.10",
          abs((m["alpha_vs_spy"] or 0) - (m["total_return"] - 0.10)) < 1e-9, m["alpha_vs_spy"])

    print("[6] under-trade-floor penalty")
    m_few = {"sharpe": 1.5, "max_drawdown": -0.1, "trade_count": 2}
    m_many = {"sharpe": 1.5, "max_drawdown": -0.1, "trade_count": 20}
    f_few = fitness(m_few)
    f_many = fitness(m_many)
    check("under-traded penalized below well-traded", f_few < f_many, f"{f_few} vs {f_many}")
    check("well-traded fitness == sharpe - dd_penalty*|mdd|",
          abs(f_many - (1.5 - 0.5 * 0.1)) < 1e-9, f_many)

    print("[7] empty curve -> empty metrics (no crash)")
    m = compute_metrics([], [], START)
    check("empty -> total_return 0 / trade_count 0", m["total_return"] == 0.0 and m["trade_count"] == 0)


if __name__ == "__main__":
    print("=" * 60)
    print("test_backtest_fitness")
    print("=" * 60)
    main()
    print("=" * 60)
    if FAILURES:
        print(f"FAILED {len(FAILURES)} check(s): {FAILURES}")
        sys.exit(1)
    print("ALL CHECKS PASSED")
    sys.exit(0)
