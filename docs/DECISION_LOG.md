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
* **Context:** `docs/06_PULLBACK_ENGINE.md §4` specified candidate rules as `CounterMoveNorm > θ_counter AND CounterEfficiency > θ_efficiency OR CounterStructuralEvidence = TRUE` without parentheses.
* **Decision:** Reconcile as `(CounterMoveNorm > θ_counter AND CounterEfficiency > θ_efficiency) OR (CounterMoveNorm > θ_min_floor AND CounterStructuralEvidence = TRUE)`.
* **Rationale:** Structural evidence (e.g. key swing break) is primary (AGENTS.md Invariant #35) and can qualify a pullback candidate even if normalized move or efficiency metrics fall below standard threshold, provided a baseline distance floor `θ_min_floor` is satisfied.

## D-033 — Quarantined Position Exit Pathway
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
* **Decision:** Downstream validity gates (Opportunity Entry Authorization, Smart Overtrading, Runner Management) MUST evaluate these policy flags as mandatory entry/management prerequisites.
* **Rationale:** Eliminates orphaned fields and operationalizes PDE state policy decisions across allocation and position management layers.

## D-037 — PDE Layering Isolation & EvidenceConfidence Calibration
* **Context:** `docs/06_PULLBACK_ENGINE.md §14` included `ExecutionConfidence` in PDE's `EvidenceConfidence` formula, violating Layer 2 -> Layer 6 pipeline isolation.
* **Decision:** `ExecutionConfidence` is removed from PDE `EvidenceConfidence` and evaluated strictly downstream in Layer 5/6 decision authorization.
* **Rationale:** Upholds AGENTS.md Invariant #1 (strict layer data flow) and backtesting causal purity (Invariants #23, #24).

## D-038 — Opportunity Engine Parent Invalidation Authority Correction
* **Context:** `docs/02_ENGINE_CONTRACTS.md §18` Authority Matrix stated `Opportunity: Invalidates parent = Yes`, contradicting `docs/08_OPPORTUNITY_ENGINE.md §7`.
* **Decision:** Reconcile Authority Matrix: `Opportunity: Invalidates parent = No`.
* **Rationale:** An expiring or untradeable child opportunity must never invalidate its parent regime or setup state (AGENTS.md Invariant #13).

## D-039 — Authority Provenance Boundary Classification
* **Context:** Pass 4.2 implemented in-process sealing (`SealedObservation`, `ProducerCapability`, `ValidatorCapability`, `_AuthorityToken`) to prevent state forgery.
* **Decision:** Python in-process sealing is classified as defense-in-depth and not a primary operating system or hardware security boundary. Further authority-provenance expansion is frozen.
* **Rationale:** Prevents endless in-process hardening while maintaining deterministic capability checks.

## D-040 — Recovery Master-Key Zeroing Behaviour
* **Context:** `AuthorityDomain.finalize()` executes `self._master_key = b"\x00" * 32` after freezing registries.
* **Decision:** Confirmed intentional zeroing protocol to permanently prevent capability minting post-finalization.
* **Rationale:** Ensures runtime immutability and capability isolation post-bootstrap.

## D-041 — HMAC Production Secret Management
* **Context:** HMAC key generation currently utilizes UUID/random process-scoped byte generation.
* **Decision:** In production environments, HMAC master secrets MUST be provided via an external secret-management service (e.g. KMS/Vault) rather than per-process transient randomness.
* **Rationale:** Supports multi-process/distributed recovery verification while maintaining secret security.

## D-042 — Scoped Ruff Gate Architecture
* **Context:** Phase 0 introduced a repository-wide Ruff lint gate (`poetry run ruff check src/ tests/`) which failed against historical Pass 4.2 artifacts due to pre-existing import findings (103 errors).
* **Decision:** Configure narrow `extend-exclude` in `pyproject.toml` for historical protected Pass 4.2 production and test artifacts while enforcing active quality gates across all Phase 0 code and future files.
* **Rationale:** Preserves historical Pass 4.2 artifacts byte-for-byte without false modifications while maintaining strict, reproducible quality gates for Phase 0 and future development.

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

## Structure v2.2 — Causal Structural Excursion Closure

The Structure Engine remediation now treats an unresolved candidate as a bounded structural excursion rather than a trailing local maximum/minimum. A new extreme may extend the same excursion without resetting its origin or age. Confirmation is a later causal reversal event normalized by `V_local`. The former `pivot_neighborhood_bars` parameter is retained only for backward-compatible configuration/snapshot loading and is no longer an algorithmic authority.

Key decisions:
- `created_from_timestamp` is immutable excursion origin; `candidate_at` identifies the latest excursion extreme.
- Directional continuation is required to extend an excursion; a contrary wick is reversal evidence, not automatic candidate supersession.
- First-observation ambiguity is preserved; exact competing evidence is not arbitrarily ordered.
- Confirmed pivots remain immutable historical records with `confirmed_at == effective_from`.
- Excursion expiry is fail-closed and cannot recreate a new candidate from the same observation.
- `authoritative_state()` is the canonical forensic state surface for causal-prefix and recovery equivalence.
- Snapshot schema is advanced to `structure-engine-v2.2`, while the loader remains compatible with v2.1 snapshots.

The implementation is intentionally deterministic, bounded, auditable, and independent of ML authority.

## Phase 5 Part A — R7/R8/R9 forensic decisions — 2026-10-06

- **R7 account identity:** `ACT_PRIMARY` is not an implicit source default. Account identity is explicit at the Phase3 -> Phase4 decision boundary, resolved only through the strict account registry, and unknown/disabled identities fail closed.
- **R8 invariant relevance:** an invariant may remain ENFORCED / INTEGRATION_VERIFIED only when its executable test reference exists and carries an explicit `covers: [id]` relevance marker. Runtime authority registry and `spec/engines.yaml` are aligned for Phase3Orchestrator and core engines.
- **R9 restart authority:** durable Phase2 restart authority is the journal. Checkpoints are diagnostic/acceleration metadata and cannot override or block journal reconstruction. Snapshot restoration is not a restart authority.
- **R6 evidence discipline:** the pre-R7 100-seed decision campaign is historical only; final R6 closure requires a fresh explicit-account rerun.

### Phase 5 Part B — authority-separated News / Feasibility / Risk / Portfolio boundary — 2026-10-06

Part B implementation is intentionally layered as `Phase3/Phase4 decision -> News Shield -> Account Feasibility -> Risk Allocation -> Portfolio Arbitration -> Lane/Group controls`. News may veto but cannot create trades; feasibility establishes physical account/instrument support before sizing; risk allocates only within constitutional limits and cannot create direction; portfolio arbitrates aggregate exposure and cannot reverse strategy direction; lane/group controls are hard pre-exposure caps. Part-B policy objects carry explicit version/provenance metadata and News Shield state is deterministic/recoverable.

### Phase 5 Part B — persistence and causal hardening — 2026-10-06

The Part-B authority boundary was extended with an append-only `PartBDecisionJournal` over the canonical durable event journal. The journal records deterministic Part-B outcomes, allocation evidence, and News Shield state hashes; duplicate identical outcomes are idempotent while conflicting reuse of the same identity is rejected. Risk/Portfolio remain deterministic/stateless authorities rather than accumulating hidden mutable risk state.

A concrete look-ahead defect in News Shield calendar/observation handling was closed: evidence whose timestamp is later than the decision timestamp now fails closed. Canonical NewsState names were reconciled to `spec/states.yaml`, and backward-compatible enum aliases do not introduce noncanonical state values. Risk cooldown and malformed portfolio numeric input guards were added as protective hardening.

## Phase 5 Part B forensic remediation — authority, freshness, portfolio and persistence — 2026-10-06

The initial Part-B implementation was re-opened after forensic review identified material authority/correctness gaps. The remediation deliberately precedes feature expansion and preserves the authority graph:

`Phase3/Phase4 Strategy Authority -> News Protection -> Account Feasibility -> Risk Allocation -> Portfolio Arbitration -> Lane/Group Controls -> Execution boundary`.

Decisions:
- Phase-4 structural validity is not authority. `TradeDecisionV4` now requires an opaque factory-only authority proof minted by `make_decision()`; direct construction cannot manufacture `phase4_ready`/`authorized` even with a valid fingerprint and opportunity hash.
- Phase-4 authority is content-bound to the current opportunity and, for child opportunities, to the current parent content hash.
- Part B never trusts a stale `decision.authorized` bit. It requires the current authoritative `Opportunity` and revalidates content, identity, lineage, state and time at the Part-B boundary.
- `max_entries_per_opportunity` is a hard pre-exposure cap. The effective cap is the minimum of portfolio policy and the authoritative opportunity's own `max_entries`.
- MERGE is an optimization, not a privileged authorization path. Merged candidates are evaluated against the same currency, correlation, total-risk, trade-count and entry-count constraints as ordinary admission.
- Portfolio correlation now incorporates both candidate and existing-position risk using deterministic shared-risk scaling; portfolio risk throttling can reduce allocation, but final sizing remains exclusively owned by `RiskEngine`.
- Portfolio exposure no longer falls back silently from `notional` to raw `volume`; an explicit standardized exposure unit is mandatory.
- News observations for scheduled events cannot precede the scheduled release timestamp. The observation becomes explicit release evidence at/after the release boundary.
- Part-B durable journal records now carry reconstruction context and a deterministic context fingerprint sufficient to audit the account/spec/policy/request/portfolio/correlation/lane inputs used for the decision.
- The R5 isolated stress harness no longer waits for unrelated thread-pool workers after a failure; cancellation and non-blocking executor shutdown preserve process isolation and termination semantics.

No remediation changes execution authority or permits News/Risk/Portfolio/Lane components to manufacture strategy direction.

## Phase 5 Part B — final forensic hardening — 2026-10-06

- `PortfolioCandidate.notional` is a mandatory domain invariant. Missing exposure is rejected before portfolio arithmetic rather than tolerated until a downstream `TypeError`.
- Every authoritative Part-B outcome is journaled with context envelope version 2. The envelope contains decision, authoritative opportunity, parent opportunity, account, SymbolSpec, portfolio state, requested risk, risk/portfolio configuration, correlations, lane/group, evaluation timestamp, News state hash, outcome and allocation evidence where available.
- Earlier verification figures are historical/superseded. The canonical current baseline is 744 passed / 6 xfailed / 89.51% coverage for the ordinary repository regression excluding explicit R5/R6 stress modules.
- R5 causal census execution is bounded by disposable worker processes. Ordinary pytest uses a small bounded smoke slice; exact 300-trial acceptance remains an explicit partitionable stress gate. A worker timeout is process-group terminated and cannot leave unrelated thread-pool workers draining indefinitely.
