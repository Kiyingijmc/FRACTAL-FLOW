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

## D-043 — Operator Control Surface GUI Architecture and Safety Boundary
* **Context:** The FRACTAL-FLOW systematic engine requires a dedicated, low-latency operator instrument panel to observe multi-timeframe regime alignment, gate-chain candidate evaluations, and manage live positions without compromising backend safety authority.
* **Decision:** Implement `spec/control_surface_v1.yaml` and `control_surface/` as a high-density React/TypeScript instrument panel governed strictly by `docs/24_CONTROL_SURFACE_DESIGN_SYSTEM.md`. Enforce explicit operational mode badges (`SIMULATION` vs `CONNECTED`), a formal command lifecycle (`REQUESTED` -> `ACCEPTED` -> `DISPATCHED` -> `CONFIRMED` / `REJECTED`), client-side idempotency keys, and mandatory operator confirmation dialogs.
* **Rationale:** Adheres to the constitutional invariant that the frontend is an observation and dispatch surface, never a rogue authority. Ensures simulation states cannot dispatch live broker orders and guarantees zero-pill, tabular-numeral typographic discipline across trading operations.

## D-044 — Stage B GUI Safe Simulation Boundary & Provider Isolation Architecture
* **Context:** Remediation of initial GUI findings (GUI-HPL-001 through GUI-HPL-015) identified that client-side simulation state and timer progressions could be conflated with real broker authority, idempotency keys lacked deterministic intent hashing, telemetry chips were hardcoded, and hotkeys lacked text-input focus guards.
* **Decision:**
  1. Implement explicit provider boundaries (`IDataProvider`, `ICommandProvider`) separating `SimulationProvider` from `LiveCommandAdapter`.
  2. Enforce fail-closed live execution: `LiveCommandAdapter` throws `LiveExecutionBlockedError` unconditionally until backend Control Service and ExecutionGateway are provisioned.
  3. Require `SimulationProvider` to tag all telemetry and execution outcomes with `isAuthoritative: false` and `source: 'SIM_ENGINE'`.
  4. Implement deterministic intent fingerprinting (`generateIntentFingerprint`) via canonicalized parameter hashing, guaranteeing identical idempotency keys across retries.
  5. Refactor Header to render dynamic `TelemetryProvenance` with status transitions (`HEALTHY`, `STALE`, `DISCONNECTED`).
  6. Harden keyboard shortcuts via `isSafeKeyboardShortcutTarget` to prevent accidental triggers while typing in inputs, textareas, or selects.
  7. Implement 13 automated adversarial invariant tests in `safety_invariants.test.ts`.
* **Rationale:** Preserves the core constitutional hierarchy (`SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY`). Prevents simulation state from masquerading as broker receipts, eliminates accidental operator dispatch, and provides an auditable foundation for future backend integration.

## D-045 — PR #29 Stage B Forensic Remediation & Closure Reconciliation
* **Context:** An adversarial source review of PR #29 identified residual discrepancies: `App.tsx` owned simulated tick and command timers bypassing the provider boundary; `idempotency.ts` used a non-standard 32-bit hash without deep recursive canonicalization and conflated logical intent IDs with payload fingerprints; keyboard checks omitted IME composition and repeat chatter; telemetry freshness was calculated in-line without testing edge cases; and tests included self-comparisons and mock calculations.
* **Decision:**
  1. Relocate all simulated tick generation, internal position updates, and asynchronous command progression into `SimulationProvider.ts`. `App.tsx` subscribes cleanly to provider events without nested `setTimeout` loops.
  2. Separate logical intent identity (`intentId`) from semantic payload fingerprinting (`payloadFingerprint`). Distinct operator actions generate distinct `intentId`s; retries reuse the existing `intentId`.
  3. Implement deterministic recursive canonicalization rejecting `undefined`, `NaN`, `Infinity`, functions, and cyclic structures, backed by standard FIPS 180-4 SHA-256 and verified with NIST/RFC 6234 KAT vectors.
  4. Author production `evaluateTelemetryFreshness()` in `telemetry.ts` handling fresh, threshold boundary, expired, missing, and disconnected telemetry.
  5. Harden keyboard safety with IME composition suppression (`isComposing`, `keyCode === 229`), key chatter repeat guards (`event.repeat`), modifier enforcement, and modal/in-flight context gates.
  6. Generate and track `control_surface/package-lock.json` for reproducible clean installs.
  7. Expand automated safety test suite to 17 adversarial assertions exercising actual production code.
* **Rationale:** Adheres strictly to `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY`. Ensures simulation boundaries cannot masquerade as broker receipts, establishes cryptographic intent fingerprinting semantics, prevents keyboard-driven operator errors, and provides verifiable evidence across all safety invariants.

## D-046 — Stage D Forensic Remediation, State Rejection Invariants, and PositionsTable Interactive Sorting
* **Context:** Following Stage C responsive remediation, forensic audit required hardening of telemetry provenance isolation, cryptographically secure intent identity generation, strict canonicalization invariants, truthful simulation reconciliation, full-state rejection guarantees, non-authoritative event persistence labeling, and operator-grade interactive PositionsTable column sorting with active row tracking.
* **Decision:**
  1. **Telemetry Source Isolation (SC-01 / SC-06):** In `telemetry.ts`, enforce that simulation ticks (`SIM_ENGINE`) cannot heal, refresh, or overwrite external broker or control service telemetry state (`BROKER_FEED` / `CONTROL_SERVICE`). Validate runtime timestamps and thresholds (rejecting non-finite, zero, or negative numbers to `UNKNOWN` or `DEGRADED`).
  2. **Secure Intent Identity & Replay Protection (SC-02 / SC-03):** In `idempotency.ts`, generate logical `intentId` using `crypto.getRandomValues()` (eliminating pseudo-randomness). Maintain an active intent registry rejecting any retry of an existing `intentId` with an altered semantic payload (`IntentReplayMismatchError`). Enforce strict canonicalization normalizing `-0` to `0`, rejecting sparse arrays and custom own properties, and rejecting unsupported types.
  3. **Truthful Simulation Reconciliation & Full-State Rejection (SC-04 / SC-05):** In `SimulationProvider.ts`, reject unknown or malformed intent IDs during reconciliation. Ensure rejected commands leave positions, orders, and system events 100% unmutated. `LiveCommandAdapter` remains fail-closed throwing `LiveExecutionBlockedError`.
  4. **Audit-Event Persistence Integrity (SC-06):** In `FooterLog.tsx`, label in-memory and simulated journal events as `SESSION` / `SIMULATED`, eliminating misleading claims of durable server persistence.
  5. **PositionsTable Interactive Column Sorting (SORT-01 / UX-03):** In `PositionsTable.tsx`, implement interactive header sorting for PnL (`unrealizedR` / `realizedR` / `realizedPnl`), Symbol, Size, Entry Price, Current Price, MFE, and Age across Open, Pending, and Closed tabs. Show prominent active directional icons (`▲` / `▼`), distinct header highlights (`text-[#5B8FBF] bg-[#161C26]/90 border-b-2 border-[#5B8FBF]`), and visible hover affordances for unsorted columns. Wire `selectedRowRef` to automatically maintain active position tracking and scroll the active position into view upon sorting.
  6. **Quality Gate Expansion:** Author 26 adversarial safety tests (`safety_invariants.test.ts`), 10 responsive structural tests (`responsive_structural.test.ts`), and 15 PositionsTable sort invariant tests (`positions_table_sort.test.ts`), bringing total automated verification coverage to 51 passing tests.
* **Rationale:** Governed by `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY`. Guarantees mathematical and operational truthfulness, prevents state corruption on command rejection, eliminates false persistence claims, and provides an operator-grade, accessible trading control surface.
