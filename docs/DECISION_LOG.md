# FRACTAL FLOW DECISION LOG
Version 1.0

This file records major architectural decisions and rejected shortcuts so future agents do not accidentally resurrect abandoned designs.

## D-001 — Scalping, not HFT
FRACTAL FLOW is intended for Forex scalping. It is not an HFT system.

## D-002 — MT5 authority
MT5 is authoritative for live execution, risk enforcement, position management and reconciliation.

## D-003 — TradingView role
TradingView is visualization/research/state display, not a competing execution brain.

## D-004 — Hierarchical timeframe model
4H → 1H → 30M → 15M → 5M → 1M.

## D-005 — Primary pullback hierarchy
Primary pullback normally exists above execution timeframe. Secondary and micro pullbacks are children.

## D-006 — Adaptive structure
Do not use fixed three-candle fractals.

## D-007 — No fixed Fibonacci constitutional rule
Pullback depth is a feature, not a fixed Fibonacci law.

## D-008 — No fixed candle-count constitutional rule
Duration is measured adaptively.

## D-009 — Flow is descriptive
Flow does not directly issue orders.

## D-010 — Weakening is not resumption
Weakening only identifies changing counter-pressure. Resumption requires structural recovery and directional displacement.

## D-011 — Liquidity sweep
A sweep is a trigger modifier, not a standalone strategy.

## D-012 — Compression
Compression is a state. It can precede breakout or false-break rotation depending on subsequent acceptance/rejection.

## D-013 — Strategy families
Initial families:
FLOW_CONTINUATION
COUNTERFLOW
RANGE_ROTATION
TRANSITION_BREAK

## D-014 — Opportunity identity
Repeated triggers from one primary pullback are one opportunity unless a new structural leg/setup is created.

## D-015 — Smart Overtrading
The name remains user-facing. Internally it is an opportunity-budget mechanism.

## D-016 — Flipping
No immediate opposite trade after a loss. Structural reversal and independent validation required.

## D-017 — Tradeability
Signal validity and economic tradeability are separate.

## D-018 — Dynamic TP
TP should be adaptive rather than permanently static.

## D-019 — Structural trailing
Trailing follows protected structure, not a blind percentage or raw ATR trail.

## D-020 — TTL
Every trade has a finite lifetime. Decay is multidimensional.

## D-021 — News Shield
News is an overlay, not a separate strategy.

## D-022 — 75% news profit protection
Approximately 75% of current realizable profit is a research/default hypothesis, not an immutable law.

## D-023 — 10-minute post-news rule
Ten minutes is a validation checkpoint, not automatic restart.

## D-024 — Unscheduled shock
Abnormal price/spread/velocity shock without known news can trigger protective lockdown.

## D-025 — Configuration versioning
News overlays must not overwrite or later restore stale base configurations.

## D-026 — Orphan lifecycle
Objects are reconciled, not immediately deleted.

## D-027 — Strategy/protection separation
Strategy may be offline while protection remains active.

## D-028 — Confidence
Confidence cannot bypass validity.

## D-029 — Portfolio currency exposure
Currency vectors are required because multiple symbols can represent one concentrated macro/currency position.

## D-030 — Research philosophy
Research architectural layers incrementally rather than maximizing backtest PnL alone.

## D-031 — Safety-first
Survival/correctness/lineage/protection precede speed and PnL.

## Open calibration areas

These remain research questions:
- exact swing thresholds
- feature weights
- flow thresholds
- hysteresis/dwell
- pullback thresholds
- news windows
- news protection target
- post-news risk multipliers
- TP profile allocations
- TTL rescue multipliers
- spread/cost thresholds
- session-specific behavior
- symbol-specific behavior
- correlation thresholds
- Smart Overtrading budgets

Constitutional architecture must not be optimized away to solve these questions.
