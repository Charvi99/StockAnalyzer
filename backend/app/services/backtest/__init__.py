"""Phase-2 historical backtester (no-look-ahead, price-technical core).

Modules:
  - backtest_signal_adapter: as-of-T signal assembly (the no-look-ahead invariant)
  - backtest_regime:          pure market-regime label from a price DataFrame
  - backtest_order_calc:      pure stop/target level twin (added in a later step)
  - replay_engine:            in-memory Account+Position loop (added later)
  - fitness:                  metrics + composite scalar (added later)
  - runner:                   load prices -> run -> persist (added later)
"""
