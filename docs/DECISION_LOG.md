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

## D-032 — Pullback Candidate Boolean Precedence
* **Status:** OPEN — pending research validation
* **Context:** `docs/06_PULLBACK_ENGINE.md §4` specified candidate rules as `CounterMoveNorm > θ_counter AND CounterEfficiency > θ_efficiency OR CounterStructuralEvidence = TRUE` without parentheses.
* **Decision:** Reconcile as `(CounterMoveNorm > θ_counter AND CounterEfficiency > θ_efficiency) OR (CounterMoveNorm > θ_min_floor AND CounterStructuralEvidence = TRUE)`.
* **Rationale:** Structural evidence (e.g. key swing break) is primary (AGENTS.md Invariant #35) and can qualify a pullback candidate even if normalized move or efficiency metrics fall below standard threshold, provided a baseline distance floor `θ_min_floor` is satisfied.

## D-033 — Quarantined Position Exit Pathway
* **Status:** OPEN — pending research validation
* **Context:** `docs/14_RECONCILIATION.md §4` defined orphan state `QUARANTINED` when parent lineage cannot be reconstructed after a crash. Inventing a structural trailing stop without valid lineage creates a circular dependency.
* **Decision:** Distinguish two quarantine sub-states:
  1. `QUARANTINED_WITH_VALID_PROTECTION`: Structure intact; Protective Manager trails tight stop until flat.
  2. `QUARANTINED_WITHOUT_VALID_THESIS`: Lineage/structure damaged; broker hard stop remains authoritative + emergency alert. No structural thesis is invented.
* **Rationale:** Prevents inventing unverified trailing theses while maintaining active risk containment.

## D-034 — Canonical Pullback Resumption Vocabulary Standard
* **Context:** `docs/02_ENGINE_CONTRACTS.md §5`, `docs/03_STATE_MACHINE.md §3`, and `docs/06_PULLBACK_ENGINE.md §8` defined three incompatible state enums for PDE and resumption.
* **Decision:** Standardize to a primary state `PDEState` (`PDE_RESUMPTION_FAILED`, `PDE_RESUMPTION_IN_PROGRESS`, etc.) and a sub-lifecycle state `PDEResumptionState` (`RECOVERY_CANDIDATE`, `RECOVERY_CONFIRMED`, `DISPLACEMENT_CANDIDATE`, `RESUMPTION_CONFIRMED`).
* **Rationale:** Establishes type-safe state interfaces across Layer 2 (PDE) and downstream consumers without string ambiguity or naming reversals.

## D-035 — Lineage Chain Hierarchy Expansion
* **Context:** `docs/00_CONSTITUTION.md` lineage omitted `MICRO PULLBACK` and `OPPORTUNITY` tiers.
* **Decision:** Canonical lineage is updated to: `ROOT → REGIME → SETUP → PRIMARY_PULLBACK → [SECONDARY_PULLBACK →] [MICRO_PULLBACK →] OPPORTUNITY → SIGNAL → ORDER → POSITION → TRADE → MANAGEMENT`.
* **Rationale:** Ensures M1 micro pullbacks and multi-timeframe opportunities satisfy root-to-leaf lineage validation invariants (AGENTS.md Invariants #11, #12, #25, #27).

## D-036 — PDE Policy Fields Consumer Authorization Integration
* **Context:** Policy fields on pullback objects (`primary_entry_allowed`, `micro_entry_allowed`, `reentry_allowed`, `runner_management_allowed`) were declared in Doc 06 but never read downstream.
* **Decision:** downstream validity gates (Opportunity Entry Authorization, Smart Overtrading, Runner Management) MUST evaluate these policy flags as mandatory entry/management prerequisites.
* **Rationale:** Eliminates orphaned fields and operationalizes PDE state policy decisions across allocation and position management layers.

## D-037 — PDE Layering Isolation & EvidenceConfidence Calibration
* **Context:** `docs/06_PULLBACK_ENGINE.md §14` included `ExecutionConfidence` in PDE's `EvidenceConfidence` formula, violating Layer 2 -> Layer 6 pipeline isolation.
* **Decision:** `ExecutionConfidence` is removed from PDE `EvidenceConfidence` and evaluated strictly downstream in Layer 5/6 decision authorization.
* **Rationale:** Upholds AGENTS.md Invariant #1 (strict layer data flow) and backtesting causal purity (Invariants #23, #24).

## D-038 — Opportunity Engine Parent Invalidation Authority Correction
* **Context:** `docs/02_ENGINE_CONTRACTS.md §18` Authority Matrix stated `Opportunity: Invalidates parent = Yes`, contradicting `docs/08_OPPORTUNITY_ENGINE.md §7`.
* **Decision:** Reconcile Authority Matrix: `Opportunity: Invalidates parent = No`.
* **Rationale:** An expiring or untradeable child opportunity must never invalidate its parent regime or setup state (AGENTS.md Invariant #13).

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
- pullback candidate boolean precedence (θ_min_floor)
- quarantine exit strategy choice

Constitutional architecture must not be optimized away to solve these questions.
