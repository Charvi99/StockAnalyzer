"""
In-memory replay engine for the backtester (Phase 2).

Day-by-day historical replay of one engine, mirroring the live
``LedgerService.run_cycle`` exits-first ordering (C1) but writing NO live state —
it keeps an in-memory ``BTAccount`` / ``BTTrade`` ledger and produces an equity
curve + closed-trade list. Reuses the SAME pure decision math the live ledger
uses (``_is_fresh_buy`` / ``_exit_reason`` / ``_exit_fill_price`` /
``_apply_slippage`` / ``_realized_pnl_long`` + ``risk_utils`` sizing/heat), so the
replay is behaviourally faithful to the live paper-trading cycle.

Per cycle date T:
  1. signals as-of T (via ``backtest_signal_adapter.signal_as_of`` on df truncated at T)
  2. exits FIRST on T's OHLC (C1: never exit the birth bar; SL wins a same-day span)
  3. open fresh BUYs (order levels via ``backtest_order_calc`` + risk_utils sizing,
     portfolio-heat + cash guards)
  4. mark-to-market at T's close
  5. snapshot equity (cash + open market value)

``trading_days_held`` = index difference on that stock's bar calendar (entry day = 0),
matching the live ``trading_days_between`` semantics.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from app.services.backtest.backtest_signal_adapter import signal_as_of
from app.services.backtest.backtest_order_calc import calculate_levels
from app.services.ledger_service import (
    LEDGER_COMMISSION_PER_SHARE,
    LEDGER_MAX_HOLD_DAYS,
    LEDGER_MAX_PORTFOLIO_HEAT,
    LEDGER_RISK_PERCENT,
    LEDGER_SLIPPAGE_BPS,
    _apply_slippage,
    _exit_fill_price,
    _exit_reason,
    _is_fresh_buy,
    _realized_pnl_long,
)
from app.services.signal.types import SignalResult
from app.utils.risk_utils import calculate_portfolio_heat, calculate_position_size

logger = logging.getLogger(__name__)

# Default virtual capital for a backtest (matches the live paper-account seed).
STARTING_CASH = 100_000.0


@dataclass
class BTTrade:
    """One virtual trade (open or closed) — mirrors the PaperTrade fields used."""
    stock_id: int
    symbol: str
    entry_price: float
    entry_date: object
    stop_loss: float
    take_profit: float
    position_size: int
    risk_amount: float
    signal_at_entry: str
    config_version: str
    entry_confidence: float
    mark_price: Optional[float] = None
    unrealized_pnl: float = 0.0
    status: str = "open"
    exit_price: Optional[float] = None
    exit_date: Optional[object] = None
    exit_reason: Optional[str] = None
    realized_pnl: Optional[float] = None
    realized_pnl_pct: Optional[float] = None


@dataclass
class BTAccount:
    engine: str
    starting_cash: float
    config_version: str
    cash: float = 0.0
    open: Dict[int, BTTrade] = field(default_factory=dict)
    closed: List[BTTrade] = field(default_factory=list)
    last_signal: Dict[int, str] = field(default_factory=dict)
    equity_curve: List[Dict] = field(default_factory=list)

    def __post_init__(self):
        self.cash = self.starting_cash


class ReplayEngine:
    """Replays one engine over a historical window, fully in-memory."""

    def __init__(
        self,
        engine: str,
        starting_cash: float = STARTING_CASH,
        risk_pct: float = LEDGER_RISK_PERCENT,
        max_heat: float = LEDGER_MAX_PORTFOLIO_HEAT,
        max_hold_days: int = LEDGER_MAX_HOLD_DAYS,
        slippage_bps: int = LEDGER_SLIPPAGE_BPS,
        commission: float = LEDGER_COMMISSION_PER_SHARE,
        weights: Optional[Dict[str, float]] = None,
        input_cache: Optional[Dict] = None,
        overlay_strength: float = 0.0,
    ):
        self.engine = engine
        self.starting_cash = starting_cash
        self.risk_pct = risk_pct
        self.max_heat = max_heat
        self.max_hold_days = max_hold_days
        self.slippage_bps = slippage_bps
        self.commission = commission
        # Phase 3: optional signal-weight override (GA candidates). ``None`` replays
        # the engine's live default weights. Threaded into signal_as_of per bar.
        self.weights = weights
        # Phase 3: optional per-(stock, T) input cache (GA). Maps (stock_id, T) ->
        # a pre-assembled weight-independent bundle, reused across every candidate
        # so only weights are re-applied. None => assemble per bar (Phase-2 path,
        # used by single backtests to avoid holding every bundle in memory).
        self.input_cache = input_cache
        # Phase 2.5: regime de-risk overlay strength in [0,1]. ``0.0`` (default)
        # => overlay OFF, byte-identical replay. Threaded into signal_as_of per
        # bar; the sizing step also reads each signal's ``bear_size_factor``.
        self.overlay_strength = overlay_strength

    def run(self, prices_by_stock: Dict[int, pd.DataFrame], trading_dates: List) -> BTAccount:
        """Run the exits-first replay. ``prices_by_stock`` maps stock_id -> a
        chronological daily OHLCV DataFrame with a ``timestamp`` column."""
        # Per-stock date->row-index map (for trading_days_held + truncation).
        date_pos: Dict[int, Dict] = {
            sid: {pd.Timestamp(t): i for i, t in enumerate(df["timestamp"])}
            for sid, df in prices_by_stock.items()
        }
        account = BTAccount(engine=self.engine, starting_cash=self.starting_cash, config_version=self._config_version())

        for T in trading_dates:
            T = pd.Timestamp(T)
            self._cycle(account, prices_by_stock, date_pos, T)

        return account

    def _config_version(self) -> str:
        try:
            if self.engine == "engine_1":
                from app.services.signal.systematic import config_version_for as cv_for
                return cv_for(self.weights, self.overlay_strength)
            from app.services.signal.swing import config_version_for as cv_for
            return cv_for(self.weights, self.overlay_strength)
        except Exception:
            return "unknown"

    def _cycle(self, account: BTAccount, prices_by_stock, date_pos, T) -> None:
        # 1. signals as-of T (truncated); fresh-BUY detection.
        current_signals: Dict[int, Optional[SignalResult]] = {}
        fresh_buys = set()
        for sid, df in prices_by_stock.items():
            df_T = df[df["timestamp"] <= T]
            if len(df_T) < 2:
                continue
            try:
                bundle = self.input_cache.get((sid, T)) if self.input_cache else None
                sr = signal_as_of(self.engine, df_T, self.weights, bundle, self.overlay_strength)
            except Exception as e:  # C4: per-stock fault tolerance
                logger.warning("[backtest %s] signal failed for stock %s at %s: %s", self.engine, sid, T, e)
                current_signals[sid] = None
                continue
            current_signals[sid] = sr
            if _is_fresh_buy(account.last_signal.get(sid), sr.signal):
                fresh_buys.add(sid)
            account.last_signal[sid] = sr.signal

        # 2. exits FIRST (C1: entry_date < T). Evaluate against T's OHLC.
        for sid, pos in list(account.open.items()):
            if pos.entry_date is not None and pd.Timestamp(pos.entry_date) >= T:
                continue  # never exit the birth bar
            df = prices_by_stock.get(sid)
            if df is None:
                continue
            df_T = df[df["timestamp"] <= T]
            if len(df_T) == 0:
                continue
            bar = df_T.iloc[-1]
            day_high, day_low, market_close = float(bar["high"]), float(bar["low"]), float(bar["close"])
            sr = current_signals.get(sid)
            days_held = self._days_held(date_pos, sid, pos.entry_date, T)
            reason = _exit_reason(
                day_high=day_high, day_low=day_low,
                stop_loss=pos.stop_loss, take_profit=pos.take_profit,
                trading_days_held=days_held,
                current_signal=(sr.signal if sr else None),
                max_hold_days=self.max_hold_days,
            )
            if reason is None:
                continue
            fill = _exit_fill_price(reason, pos.stop_loss, pos.take_profit, market_close)
            self._close(account, pos, reason, fill, T)

        # 3. open fresh BUYs (after exits freed cash).
        for sid in fresh_buys:
            if sid in account.open:
                continue
            df = prices_by_stock.get(sid)
            if df is None:
                continue
            df_T = df[df["timestamp"] <= T]
            if len(df_T) == 0:
                continue
            bar = df_T.iloc[-1]
            entry = _apply_slippage(float(bar["close"]), self.slippage_bps)
            # Reuse the bundle's pre-detected pattern levels (Phase 3) so a fresh
            # BUY skips the ~1.2s chart re-detection inside calculate_levels.
            bundle = self.input_cache.get((sid, T)) if self.input_cache else None
            levels = calculate_levels(
                df_T, entry,
                pattern_levels=(bundle.get("pattern_levels") if bundle else None),
            )
            size_info = calculate_position_size(
                account_capital=account.cash,
                risk_per_trade_percent=self.risk_pct,
                entry_price=entry,
                stop_loss=levels["stop_loss"],
            )
            sr = current_signals.get(sid)
            size = int(size_info.get("position_size") or 0)
            if size <= 0:
                continue
            # Phase 2.5 regime overlay: shrink a weekly-bear BUY's size (engine_2).
            # engine_1 signals carry no bear_size_factor -> 1.0 (no change). Done
            # before the heat/cash guards so the smaller size's risk is honest.
            if self.overlay_strength > 0.0 and sr is not None:
                bear_f = float((sr.extras or {}).get("bear_size_factor", 1.0))
                if bear_f < 1.0:
                    size = max(0, int(size * bear_f))
                    size_info = {**size_info,
                                 "position_size": size,
                                 "risk_amount": float(size_info.get("risk_amount") or 0.0) * bear_f}
                    if size <= 0:
                        continue
            if not self._within_heat(account, entry, levels["stop_loss"], size):
                continue
            cost = entry * size + self.commission * size
            if cost > account.cash:
                continue
            self._open(account, sid, sr, entry, T, levels, size, size_info)

        # 4. mark to market at T's close.
        for sid, pos in account.open.items():
            df = prices_by_stock.get(sid)
            if df is None:
                continue
            df_T = df[df["timestamp"] <= T]
            if len(df_T) == 0:
                continue
            close = float(df_T.iloc[-1]["close"])
            pos.mark_price = close
            pos.unrealized_pnl = (close - pos.entry_price) * pos.position_size

        # 5. snapshot equity.
        open_value = sum(
            (p.mark_price if p.mark_price is not None else p.entry_price) * p.position_size
            for p in account.open.values()
        )
        realized_cum = sum((t.realized_pnl or 0.0) for t in account.closed)
        account.equity_curve.append({
            "date": T.date() if hasattr(T, "date") else T,
            "cash": account.cash,
            "open_positions_value": open_value,
            "equity": account.cash + open_value,
            "realized_pnl_cumulative": realized_cum,
            "open_trades_count": len(account.open),
        })

    def _days_held(self, date_pos, sid, entry_date, T) -> int:
        pos_map = date_pos.get(sid, {})
        i_entry = pos_map.get(pd.Timestamp(entry_date))
        i_T = pos_map.get(T)
        if i_entry is None or i_T is None:
            return 0
        return max(0, i_T - i_entry)

    def _within_heat(self, account: BTAccount, entry: float, stop: float, size: int) -> bool:
        positions = [
            {"entry_price": p.entry_price, "stop_loss": p.stop_loss, "position_size": p.position_size}
            for p in account.open.values()
        ]
        positions.append({"entry_price": entry, "stop_loss": stop, "position_size": size})
        heat = calculate_portfolio_heat(positions, account.starting_cash, self.max_heat)
        return bool(heat.get("can_add_position", False))

    def _open(self, account, sid, sr: Optional[SignalResult], entry, T, levels, size, size_info) -> None:
        cost = entry * size + self.commission * size
        account.cash -= cost
        account.open[sid] = BTTrade(
            stock_id=sid,
            symbol=str(sid),
            entry_price=entry,
            entry_date=T,
            stop_loss=levels["stop_loss"],
            take_profit=levels["take_profit"],
            position_size=size,
            risk_amount=float(size_info.get("risk_amount") or 0.0),
            signal_at_entry=(sr.signal if sr else "BUY"),
            config_version=(sr.config_version if sr else account.config_version),
            entry_confidence=(sr.confidence if sr else 0.5),
        )

    def _close(self, account, pos: BTTrade, reason, fill, T) -> None:
        pnl, pct = _realized_pnl_long(pos.entry_price, fill, pos.position_size, self.commission)
        proceeds = fill * pos.position_size - self.commission * pos.position_size
        account.cash += proceeds
        pos.exit_price = fill
        pos.exit_date = T
        pos.exit_reason = reason
        pos.realized_pnl = pnl
        pos.realized_pnl_pct = pct
        pos.mark_price = fill
        pos.unrealized_pnl = 0.0
        pos.status = "closed"
        account.closed.append(pos)
        account.open.pop(pos.stock_id, None)
