"""
Genetic-algorithm weight optimization over the Phase-2 backtester (Phase 3).

Each engine's signal WEIGHTS are the genome. The GA searches the weight simplex
(each weight in [0, w_max], normalized to sum 1) maximizing the Phase-2 composite
fitness (Sharpe - dd_penalty*|max_drawdown|, with an under-trade penalty).

Evaluation reuses the in-memory ``ReplayEngine`` + the per-(stock, T) input cache
(``precompute.precompute_inputs``) so every candidate skips the expensive indicator
assembly and only re-applies weights — that is what makes a GA of hundreds of
evaluations feasible.

Overfitting guard: history is split CHRONOLOGICALLY into train (first ~70%) and
validation (last ~30%). The GA optimizes on train only; the best individual is
then evaluated on the unseen validation window, and the train-vs-val gap is
reported (a large gap = overfit). Survivorship bias (today's universe) stays a
documented caveat.

Pure compute: no DB, no wall-clock. Deterministic given ``seed``. Testable with
synthetic data.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.services.backtest.fitness import compute_metrics, fitness
from app.services.backtest.precompute import precompute_inputs
from app.services.backtest.replay_engine import ReplayEngine, STARTING_CASH

# The genome = components that actually CAST a vote in the price-technical backtest.
# The others are always None / score 0 there (engine_2: ``sentiment``, ``ml``;
# engine_1: ``sentiment``, ``dividend_split_signals``) -> optimizing their weights is
# unconstrained noise (GA #3/#5: sentiment/ml took free weight despite never voting).
# The GA optimizes ONLY the voting components; non-voting ones are held at their
# module default (merged in at eval time via ``_full_weights`` so the pure signal fns
# receive a complete, KeyError-safe weight dict, and the result is live-promotable).
VOTING_WEIGHT_KEYS: Dict[str, List[str]] = {
    "engine_1": ["chart_patterns", "candlestick_patterns", "technical_indicators", "market_regime"],
    "engine_2": ["technical", "chart_pattern", "candlestick", "strategy"],
}

# The full component set each engine's pure signal function consumes (reference +
# used to derive the non-voting defaults held fixed during optimization).
ENGINE_WEIGHT_KEYS: Dict[str, List[str]] = {
    "engine_1": [
        "chart_patterns", "candlestick_patterns", "technical_indicators",
        "sentiment", "market_regime", "dividend_split_signals",
    ],
    "engine_2": [
        "technical", "chart_pattern", "candlestick", "sentiment", "ml", "strategy",
    ],
}


def _module_weights(engine: str) -> Dict[str, float]:
    """The engine's live module WEIGHTS / COMPONENT_WEIGHTS (all components)."""
    if engine == "engine_1":
        from app.services.signal.systematic import WEIGHTS
        return WEIGHTS
    from app.services.signal.swing import COMPONENT_WEIGHTS
    return COMPONENT_WEIGHTS


def default_weights(engine: str) -> Dict[str, float]:
    """The GA's seed / baseline individual: the VOTING components at their live
    module defaults (the genome — non-voting components are NOT optimized)."""
    mw = _module_weights(engine)
    return {k: mw[k] for k in VOTING_WEIGHT_KEYS[engine]}


class GeneticOptimizer:
    """Tournament-selection GA over an engine's signal weights.

    The input cache is built ONCE (over train + val dates) in ``__init__`` and
    reused for every candidate, so each evaluation is a cheap weight re-application.
    """

    def __init__(
        self,
        engine: str,
        prices_by_stock: Dict[int, pd.DataFrame],
        trading_dates: List,
        *,
        pop_size: int = 20,
        generations: int = 15,
        elitism: int = 2,
        tournament_k: int = 3,
        mutation_rate: float = 0.2,
        mutation_sigma: float = 0.10,
        w_max: float = 0.60,
        train_split: float = 0.7,
        dd_penalty: float = 0.5,
        trade_count_floor: int = 5,
        starting_cash: float = STARTING_CASH,
        seed: int = 0,
        progress_cb=None,
    ):
        if engine not in VOTING_WEIGHT_KEYS:
            raise ValueError(f"Unknown engine {engine!r}")
        if not trading_dates:
            raise ValueError("trading_dates is empty — cannot optimize")
        self.engine = engine
        self.prices_by_stock = prices_by_stock
        self.keys = VOTING_WEIGHT_KEYS[engine]
        # Non-voting components are held at their module default (not optimized) so the
        # weight dict passed to the signal fns is always complete (KeyError-safe).
        self._non_voting_defaults = {
            k: _module_weights(engine)[k] for k in ENGINE_WEIGHT_KEYS[engine] if k not in self.keys
        }
        self.pop_size = pop_size
        self.generations = generations
        self.elitism = min(elitism, pop_size)
        self.tournament_k = tournament_k
        self.mutation_rate = mutation_rate
        self.mutation_sigma = mutation_sigma
        self.w_max = w_max
        self.dd_penalty = dd_penalty
        self.trade_count_floor = trade_count_floor
        self.starting_cash = starting_cash
        self.seed = seed

        # Chronological train/validation split (train on older, validate on newer).
        n_train = max(1, int(round(len(trading_dates) * train_split)))
        self.train_dates: List = list(trading_dates[:n_train])
        self.val_dates: List = list(trading_dates[n_train:])

        # Live progress callback (Phase 3 UI). None => no reporting (tests / direct
        # callers unchanged). Threaded into the precompute build (per stock) below and
        # into the generation loop in optimize().
        self.progress_cb = progress_cb

        # Build the per-(stock, T) input caches ONCE; reused across every candidate.
        self.cache_train = precompute_inputs(
            engine, prices_by_stock, self.train_dates, on_progress=self._pre_progress("train"))
        self.cache_val = (
            precompute_inputs(engine, prices_by_stock, self.val_dates,
                              on_progress=self._pre_progress("val")) if self.val_dates else None
        )

    def _pre_progress(self, window: str):
        """Wrap precompute's per-stock ``(done, total)`` callback into a phased
        ``progress_cb`` signal so the dashboard can show the precompute phase."""
        def _cb(done, total):
            if self.progress_cb:
                self.progress_cb("precompute", window=window, done=done, total=total)
        return _cb

    # ── genome helpers ──────────────────────────────────────────────────────────
    def _renormalize(self, d: Dict[str, float]) -> Dict[str, float]:
        clipped = {k: min(self.w_max, max(0.0, v)) for k, v in d.items()}
        s = sum(clipped.values()) or 1.0
        return {k: v / s for k, v in clipped.items()}

    def _random_individual(self, rng: random.Random) -> Dict[str, float]:
        raw = [rng.uniform(0.0, self.w_max) for _ in self.keys]
        s = sum(raw) or 1.0
        return {k: raw[i] / s for i, k in enumerate(self.keys)}

    def _tournament(self, scored: List[Tuple], rng: random.Random) -> Dict[str, float]:
        k = min(self.tournament_k, len(scored))
        contenders = rng.sample(scored, k)
        return max(contenders, key=lambda x: x[1])[0]

    def _crossover(self, p1: Dict[str, float], p2: Dict[str, float], rng: random.Random) -> Dict[str, float]:
        alpha = rng.uniform(0.3, 0.7)
        child = {k: alpha * p1[k] + (1 - alpha) * p2[k] for k in self.keys}
        return self._renormalize(child)

    def _mutate(self, ind: Dict[str, float], rng: random.Random) -> Dict[str, float]:
        out = dict(ind)
        for k in self.keys:
            if rng.random() < self.mutation_rate:
                out[k] = max(0.0, out[k] + rng.gauss(0.0, self.mutation_sigma))
        return self._renormalize(out)

    def _full_weights(self, candidate: Dict[str, float]) -> Dict[str, float]:
        """Merge the candidate (voting) with the fixed non-voting defaults -> a
        complete weight dict. The signal fns get every key (KeyError-safe, esp. for
        engine_1 whose ``_decide_systematic`` sums over all score keys); non-voting
        components stay at their module default so the result is live-promotable."""
        return {**self._non_voting_defaults, **candidate}

    # ── evaluation ──────────────────────────────────────────────────────────────
    def _fitness(self, weights: Dict[str, float], dates: List, cache: Dict) -> Tuple[float, Dict]:
        account = ReplayEngine(
            engine=self.engine, weights=self._full_weights(weights), starting_cash=self.starting_cash,
            input_cache=cache,
        ).run(self.prices_by_stock, dates)
        metrics = compute_metrics(account.equity_curve, account.closed, self.starting_cash, None)
        return fitness(metrics, dd_penalty=self.dd_penalty, trade_count_floor=self.trade_count_floor), metrics

    def _run_for_account(self, weights, dates, cache):
        account = ReplayEngine(
            engine=self.engine, weights=self._full_weights(weights), starting_cash=self.starting_cash,
            input_cache=cache,
        ).run(self.prices_by_stock, dates)
        return account

    # ── main loop ───────────────────────────────────────────────────────────────
    def optimize(self) -> Dict:
        """Run the GA. Returns the best individual + train/val fitness + history."""
        rng = random.Random(self.seed)
        # Seed the population with the live defaults + random individuals (the
        # default-weight individual anchors the search so the GA can't do worse
        # than the baseline by generation 0).
        population: List[Dict[str, float]] = [self._renormalize(default_weights(self.engine))]
        population += [self._random_individual(rng) for _ in range(self.pop_size - 1)]

        history: List[Dict] = []
        best: Optional[Tuple[Dict[str, float], float, Dict]] = None  # (weights, fit, metrics)

        for gen in range(self.generations):
            scored = [(ind, *self._fitness(ind, self.train_dates, self.cache_train)) for ind in population]
            scored.sort(key=lambda x: x[1], reverse=True)
            gen_best_w, gen_best_fit, gen_best_metrics = scored[0]
            if best is None or gen_best_fit > best[1]:
                best = (gen_best_w, gen_best_fit, gen_best_metrics)
            fits = [s[1] for s in scored]
            history.append({
                "generation": gen,
                "best": gen_best_fit,
                "mean": sum(fits) / len(fits),
                "worst": min(fits),
                "best_weights": gen_best_w,
            })

            # Live progress: report the completed generation + the partial history so
            # the dashboard can render gen X/Y + the per-generation fitness chart live.
            if self.progress_cb:
                self.progress_cb(
                    "optimize",
                    generation=len(history),
                    total_generations=self.generations,
                    best=gen_best_fit,
                    mean=sum(fits) / len(fits),
                    history=list(history),
                )

            elites = [s[0] for s in scored[: self.elitism]]
            next_pop: List[Dict[str, float]] = list(elites)
            while len(next_pop) < self.pop_size:
                p1 = self._tournament(scored, rng)
                p2 = self._tournament(scored, rng)
                next_pop.append(self._mutate(self._crossover(p1, p2, rng), rng))
            population = next_pop

        best_weights, train_fit, train_metrics = best  # type: ignore[misc]

        # Overfitting guard: evaluate the best on the UNSEEN validation window.
        if self.cache_val is not None and self.val_dates:
            val_fit, val_metrics = self._fitness(best_weights, self.val_dates, self.cache_val)
        else:
            val_fit, val_metrics = None, None

        # Re-run the best on train to recover its account (for the equity curve).
        best_account = self._run_for_account(best_weights, self.train_dates, self.cache_train)

        return {
            "engine": self.engine,
            "best_weights": best_weights,
            "train_fitness": train_fit,
            "train_metrics": train_metrics,
            "val_fitness": val_fit,
            "val_metrics": val_metrics,
            "train_val_gap": (train_fit - val_fit) if val_fit is not None else None,
            "generations": history,
            "n_train_dates": len(self.train_dates),
            "n_val_dates": len(self.val_dates),
            "best_train_account": best_account,
        }
