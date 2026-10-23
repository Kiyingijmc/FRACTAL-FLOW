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

## D-047 — Stage D.1 Forensic Remediation, Telemetry Hardening, CI Activation, and Focus Trap Management
* **Context:** Forensic remediation and hostile audit (FF-D-01 through FF-D-08) of Stage D identified residual vulnerabilities: disconnected feeds could accept timestamp refreshes without an advancing epoch; cross-source migrations could occur without explicit authority; client idempotency scope lacked explicit non-authoritative boundary documentation; state rejection lacked a bit-for-bit immutable proof; GUI CI remained inactive as a template; and mobile sheets lacked strict WCAG 2.2 focus trap and trigger focus restoration.
* **Decision:**
  1. **Disconnected Telemetry Timestamp Freeze (FF-D-01):** In `telemetry.ts`, strictly freeze `freshnessTimestamp` when state is `DISCONNECTED`. Forbid timestamp refresh or reconnection unless an explicit reconnect request advances the epoch (`incoming.epoch > current.epoch`) for that source.
  2. **Unauthorized Source Migration Protection (FF-D-02):** In `telemetry.ts`, validate source identifiers against known sources and reject any telemetry update attempting to migrate the active source without explicit authorization (`allowSourceMigration: true`).
  3. **Non-Authoritative Client Idempotency Scope (FF-D-03):** In `idempotency.ts`, export `IDEMPOTENCY_AUTHORITY_BOUNDARY` metadata formally declaring the in-memory registry as `CLIENT_GUI_SESSION` and `EPHEMERAL_IN_MEMORY`, with durable multi-session distributed deduplication explicitly documented as `UNRESOLVED_CONTROL_SERVICE_STORE`.
  4. **Bit-for-Bit Protected Trading State Immutability (FF-D-04):** In `SimulationProvider.ts`, export `ProtectedTradingStateSnapshot` and implement `getProtectedTradingStateSnapshot()`, proving zero mutation on positions, orders, candidates, and closed trades during command rejection.
  5. **Active GUI CI Workflow Activation (FF-D-05):** Create `.github/workflows/gui-ci.yml` with least-privilege `permissions: contents: read`, `npm ci` with lockfile caching, `npm run lint`, `npm test`, and `npm run build`.
  6. **Modal Focus Trap & Trigger Focus Restoration (FF-D-08 / WCAG 2.2):** In `FooterLog.tsx` and `MobileBottomNav.tsx`, implement Tab focus trapping, Escape key dismissal, outside click dismissal, and explicit focus restoration to the invoking trigger button (`triggerRef.current?.focus()`).
  7. **Automated Test Expansion:** Author 7 behavioral modal focus tests in `modal_focus_behavior.test.ts` and add 8 hostile assertions to `safety_invariants.test.ts`, expanding the automated test suite to 66 passing tests across safety, layout, sorting, and accessibility.
* **Rationale:** Governed by `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY`. Eliminates silent partition masking, guarantees trading state immutability on command rejection, activates continuous integration quality gates, and ensures full keyboard accessibility compliance.

## D-048 — Stage D.2 Independent Counterexample Remediation, Telemetry Atomicity, and Real DOM Component Verification

* **Context:** Independent hostile review of Stage D.1 revealed four residual risks in telemetry handling: (1) malformed epochs or invalid thresholds could result in `DEGRADED` status while still mutating freshness timestamps or other snapshot fields; (2) caller-controlled `allowSourceMigration: true` boolean was a permission bypass rather than proof of authorization; (3) initial state creation synthesized `Date.now()` when a valid observation timestamp was absent; (4) reconnect and source migration could be forged by epoch advancement alone. Furthermore, prior modal accessibility tests relied on mock element simulations rather than rendered React components, and responsive tests relied on static source-string searches rather than viewport-dependent behavioral layout checks. Authoritative durable idempotency was also prematurely labeled closed despite an unresolved backend store dependency.

* **Decision:**
  1. **Telemetry All-or-Nothing Atomicity & Fail-Closed Migration (D2-A):**
     - In `control_surface/src/utils/telemetry.ts`, enforce strict pre-validation of all incoming update fields. Any malformed epoch (non-integer, non-positive, or non-finite), invalid threshold (non-finite or non-positive), missing/invalid timestamp, unauthorized source migration, or unverified reconnect rejects the entire update atomically, returning `current` untouched without partial field mutation.
     - Eliminate the caller-controlled `allowSourceMigration: true` flag. Cross-source telemetry migration is fail-closed rejected and scoped to `MIGRATION_AUTHORITY_BOUNDARY = 'UNRESOLVED_CONTROL_SERVICE_AUTHORITY'`.
     - In `createInitialTelemetry()`, set `freshnessTimestamp: 0` and status `UNKNOWN` when an observation timestamp is absent; never synthesize `Date.now()`.
     - Reconnection requires explicit `reconnectAuthorized: true`, strictly advancing epoch (`incoming.epoch > current.epoch`), valid positive finite timestamp, and active bridge status (`SIM_VIRTUAL_OK` or `CONNECTED`). Dual timestamp tracking preserves distinct `sourceEventTime` and `localReceiveTime`.
     - Author 13 adversarial assertions in `safety_invariants.test.ts` (SC-01.1 through SC-01.13) verifying all-or-nothing atomicity and fail-closed migrations.

  2. **Real Component Modal Accessibility Verification (D2-B):**
     - Completely rewrite `modal_focus_behavior.test.ts` to mount genuine React production components (`<FooterLog />`, `<MobileBottomNav />`) in a JSDOM environment under React 19 synthetic and native event loops.
     - Eliminate all mock-function focus traps. Exercise real DOM events: initial focus entry into close buttons, Tab key wrap-around from last to first element, Shift+Tab reverse wrap-around from first to last element, Escape keydown dismissal, Close button click, backdrop click, tab selection focus return, and defensive trigger unmount handling (D2-B.01 through D2-B.09).

  3. **Behavioral Viewport Layout & Interactive Table Sorting (D2-C):**
     - Upgrade `positions_table_sort.test.ts` to mount real React `<PositionsTable />` in JSDOM: verify default descending PnL sort, ascending PnL toggle, alphabetical Symbol (A-Z / Z-A) sort, numerical Size lot sort, active row `data-selected="true"` preservation during re-sorting, and Closed Trades Realized R and Realized P&L ($) multi-directional sorting (SORT-01 through SORT-06).
     - Upgrade `responsive_structural.test.ts` to mount real React `<App />` in JSDOM across all 7 target viewports: 320px, 360px, 390px, 430px, 768px, 1024px, and 1280px CSS pixels.
     - Verify document-level overflow prevention (`w-full max-w-full overflow-hidden`), dual-deck mobile vs single-deck desktop header, mobile bottom nav docking (<768px), nav rail docking (>=768px), safe-area bottom clearance (`pb-14`/`pb-16`), critical status visibility (`SIM: OFF-BROKER`, `HEALTHY`), touch target height invariants (>=44px), and full reachability of all 8 navigation destinations (`POS`, `DEC`, `RISK`, `MODE`, `NEWS`, `CALIB`, `HEALTH`, `STATS`) on both mobile and desktop (20 passing tests).

  4. **HPL Evidence Distinction & Truthfulness Audit (D2-D):**
     - Reconcile `docs/reports/GUI_HPL.md` to strictly distinguish evidence tiers: `REAL COMPONENT BEHAVIOR VERIFIED (JSDOM)`, `BEHAVIORAL VIEWPORT VERIFIED (JSDOM)`, `UNIT TEST EXECUTED`, `CI PASSED`, and `UNRESOLVED BACKEND DEPENDENCY`.
     - Correct disposition of `GUI-HPL-006` and `GUI-HPL-023` to `CLIENT-SIDE VERIFIED (AUTHORITATIVE BACKEND STORE UNRESOLVED)`, formally documenting that durable cluster idempotency requires the unresolved Control Service store.
     - Update `GUI-HPL-014` to document the full 70-test automated verification suite.

* **Rationale:** Governed by `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY`. Eliminates partial state corruption risks in telemetry ingestion, guarantees fail-closed source authority, validates genuine React component accessibility and responsive behavior without mock simulations or string-search heuristics, and maintains strict epistemic truthfulness regarding unresolved backend infrastructure.


## D-049 — Stage D.2.1 Telemetry Counterexample Closure, Reconnection Authority Hardening, and Initial-State Validation

* **Context:** Independent hostile review of Stage D.2 identified residual counterexamples in telemetry handling:
  1. Caller-controlled boolean flags (e.g. `reconnectAuthorized: true` on an incoming update) allowed arbitrary callers to assert reconnection authority without cryptographic or backend-attested proof.
  2. Bridge-status checks on reconnection admitted `'UNKNOWN'` as active because only `'DISCONNECTED'` was rejected.
  3. `createInitialTelemetry()` silently defaulted malformed input (bad sources, non-positive or non-finite epochs, invalid timestamps, malformed statuses) into healthy-looking defaults (`source: 'SIM_ENGINE'`, `epoch: 1`), fabricating provenance and freshness.
  4. Stale threshold defaulting relied on JavaScript truthiness (`incoming.staleThresholdMs || 5000`), which silently coerced `0`, `NaN`, and negative numbers rather than validating numeric properties.
  5. Missing hostile regression tests for forged booleans, `UNKNOWN` bridge status on reconnect, malformed initial telemetry inputs, invalid timestamps, and bit-for-bit snapshot preservation on rejections.

* **Decision:**
  1. **Elimination of Caller-Controlled Reconnection Authority:**
     - Reject caller-asserted booleans (`incoming.reconnectAuthorized: true`) as untrusted authority bypasses.
     - Mandate that reconnection from `DISCONNECTED` requires an independent `ReconnectAuthorizationProof` parameter (`authority: 'CONTROL_SERVICE_HANDSHAKE'` with verified handshake credentials).
     - Because external Control Service handshake infrastructure is unresolved, all reconnection attempts without independent authenticated proof fail closed, strictly preserving the existing disconnected snapshot bit-for-bit.
     - Formally declare `RECONNECT_AUTHORITY_BOUNDARY = 'UNRESOLVED_CONTROL_SERVICE_HANDSHAKE'`.
  2. **Explicit Active Bridge-Status Allowlist:**
     - Define `VALID_ACTIVE_BRIDGE_STATUSES = ['SIM_VIRTUAL_OK', 'CONNECTED', 'OK', 'SIM_SANDBOX_VIRTUAL']` based on actual system contracts.
     - Strictly reject `'UNKNOWN'` and `'DISCONNECTED'` during reconnection; an incoming payload reporting bridgeStatus `'UNKNOWN'` is rejected fail-closed.
  3. **Initial Telemetry Validation & Documented Unknown State:**
     - In `createInitialTelemetry()`, strictly validate source name (non-empty string), epoch (finite positive integer), timestamp (positive finite number), stale threshold (positive finite number), status, and source-event timestamp.
     - When initial input is malformed, never synthesize `SIM_ENGINE` or epoch 1. Fail safely by returning `DOCUMENTED_UNKNOWN_TELEMETRY` (`status: 'UNKNOWN'`, `epoch: 0`, `source: 'FALLBACK_FIXTURE'`, `freshnessTimestamp: 0`), preventing false provenance or unearned healthy display.
  4. **Absence-Only Threshold Defaulting:**
     - Stale threshold defaults to 5000ms strictly when `incoming.staleThresholdMs === undefined`.
     - Zero (`0`), negative values, `NaN`, non-numeric types, and `Infinity` are rejected as invalid threshold counterexamples.
  5. **Adversarial Regression Tests (SC-01.14 – SC-01.21):**
     - Author 8 hostile test cases in `control_surface/src/tests/safety_invariants.test.ts`:
       - `SC-01.14`: Forged `reconnectAuthorized: true` caller boolean rejected; snapshot preserved.
       - `SC-01.15`: Bridge status `'UNKNOWN'` rejected during reconnection.
       - `SC-01.16`: Malformed initial source and epoch produce `DOCUMENTED_UNKNOWN_TELEMETRY`.
       - `SC-01.17`: Negative, zero, NaN, and infinite thresholds rejected; update preserved; initial creation fails safely.
       - `SC-01.18`: Invalid source-event timestamps rejected atomically.
       - `SC-01.19`: Invalid status values rejected atomically.
       - `SC-01.20`: Complete bit-for-bit snapshot preservation on all rejected updates.
       - `SC-01.21`: Valid same-source reconnection succeeds only when independent `ReconnectAuthorizationProof` is established.
     - Expands test suite to 78 passing tests (43 safety invariants, 20 responsive viewport behavioral, 6 positions sort, 9 modal accessibility).
  6. **Retain Unresolved Backend Authority as BLOCKED / FAIL-CLOSED:**
     - Do not simulate or fabricate backend authorization. Mark authoritative reconnection and durable cross-session idempotency explicitly as unresolved Control Service dependencies.

* **Rationale:** Governed by `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY`. Eliminates forged client authority, guarantees bit-for-bit snapshot preservation on all rejected updates, establishes strict epistemic truthfulness on initial state, and prevents silent state corruption across broker disconnect cycles.


## D-050 — Stage D.2.2 Reconnection Authority Boundary Closure, Fail-Closed Gating, and Initial-State Validation

* **Context:** Independent forensic review of Stage D.2.1 identified that the telemetry reconnection proof contract accepted a caller-supplied object (`authority: 'CONTROL_SERVICE_HANDSHAKE'` with a caller-provided `verify()` callback). A callback supplied by the caller returning `true` is an untrusted authority bypass rather than genuine proof of Control Service authentication. Furthermore, initial telemetry creation required strict validation to ensure missing sources or epochs fail safely into a documented unknown state rather than synthesizing default identities.

* **Reconnaissance & Trust Boundary Verification:**
  - Full codebase inspection confirmed zero trusted authentication mechanisms, zero cryptographic verification keys or distribution mechanisms, zero trusted server adapters, and zero authenticated Control Service handshake protocols (`NO_API_IN_SRC` in the strategy engine; `LiveCommandAdapter` throws `LiveExecutionBlockedError` unconditionally).
  - Because no genuine backend trust boundary exists in the GUI runtime, caller-asserted credentials cannot be verified. Therefore, the only truthful and safe architecture is a strictly fail-closed implementation where reconnection from `DISCONNECTED` remains blocked until backend authority is provisioned.

* **Decision:**
  1. **Elimination of Caller-Supplied Authorization API Path:**
     - Removed the ability for callers to authorize reconnection by supplying their own verifier, token object, boolean, or arbitrary callback.
     - Any caller attempting to pass a proof object or callback to `updateTelemetryState()` or `tryUpdateTelemetryState()` is diagnosed with `CALLER_RECONNECT_AUTHORITY_FORGERY` and rejected fail-closed.
     - Forged caller booleans (`reconnectAuthorized: true`) continue to be strictly rejected.
  2. **Fail-Closed Reconnection Gating & Snapshot Preservation:**
     - In `DISCONNECTED` state, all reconnection attempts fail closed.
     - Rejected reconnection attempts preserve the accepted telemetry snapshot 100% bit-for-bit without partial field mutation.
     - Formally declared `RECONNECT_AUTHORITY_BOUNDARY`:
       ```ts
       export const RECONNECT_AUTHORITY_BOUNDARY = {
         isSupported: false,
         status: 'BLOCKED — TRUSTED CONTROL SERVICE AUTHORITY NOT INTEGRATED',
         reason: 'CONTROL_SERVICE_HANDSHAKE_PROTOCOL_UNRESOLVED',
         policy: 'RECONNECTION_FROM_DISCONNECTED_STRICTLY_FAIL_CLOSED_REJECTED',
         callerAuthorityAccepted: false
       } as const;
       ```
  3. **Typed Rejection Diagnostics (`tryUpdateTelemetryState`):**
     - Exported `TelemetryRejectionReason`, `TelemetryUpdateDiagnostic`, and `tryUpdateTelemetryState()`, providing explicit typed diagnostic output while guaranteeing zero mutation of the protected state snapshot.
  4. **Strict Initial-State Contract (`createInitialTelemetry`):**
     - In `createInitialTelemetry()`, missing or malformed source identity, missing or invalid epoch (`<= 0`, non-integer, NaN), or missing/non-positive observation timestamp fails safely to `DOCUMENTED_UNKNOWN_TELEMETRY` (`status: 'UNKNOWN'`, `epoch: 0`, `source: 'FALLBACK_FIXTURE'`, `freshnessTimestamp: 0`).
     - Never silently converts missing inputs into `'SIM_ENGINE'`, epoch `1`, or unearned `'HEALTHY'` status.
     - Stale threshold defaults to 5000ms strictly when genuinely absent (`incoming.staleThresholdMs === undefined`).
  5. **Hostile Regression Test Expansion (SC-01.8, SC-01.21, SC-01.22, SC-01.23):**
     - `SC-01.8`: Updated to verify fail-closed reconnection gating, caller flag forgery rejection, and diagnostic reason assertions.
     - `SC-01.21`: Refactored to verify that caller-manufactured proofs, tokens, and callbacks returning `true` fail closed with `CALLER_RECONNECT_AUTHORITY_FORGERY`.
     - `SC-01.22`: Added hostile test proving reconnection remains fail-closed and preserves snapshot even with advancing epoch and allowlisted active bridge status.
     - `SC-01.23`: Added hostile test verifying strict initial-state validation on missing source, epoch, or timestamp.
     - Total automated test suite expanded to 80 passing tests (45 safety invariant, 20 responsive viewport behavioral, 6 positions sort, 9 modal accessibility).
  6. **Retained Boundary Status:**
     - Retained `AUTHENTICATED RECONNECTION UNVERIFIED` / `BLOCKED — BACKEND AUTHORITY NOT INTEGRATED`.
     - Retained `DURABLE IDEMPOTENCY BLOCKED` (client in-memory deduplication verified, distributed store unresolved).
     - Retained `SERVER AUTHENTICATION & RBAC BLOCKED` (live broker commands throw `LiveExecutionBlockedError`).

* **Rationale:** Governed by `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY`. Eliminates forged caller authorization, prevents synthetic healthy telemetry on malformed initial data, preserves bit-for-bit snapshot immutability on all rejected inputs, and truthfully reflects that external Control Service authority is not integrated.


## D-051 — Stage D.2.3 Telemetry Provenance, Diagnostic Accuracy, and Unstated Status Fail-Safe
* **Context:** Forensic review of Stage D.2.2 identified three precision and provenance counterexamples:
  1. Implicit Fallback in Source-Event Timestamp (`incoming.sourceEventTimeMs ?? freshnessTimestamp`): The contract defines `sourceEventTimeMs` as an optional generation timestamp from the telemetry producer. Fabricating source-event generation time from local receive time / freshness timestamp when absent conflates observation provenance with reception freshness.
  2. Diagnostic Flattening in Initial State Validation: `tryUpdateTelemetryState(undefined, incoming)` previously mapped every initial-state failure uniformly to `INVALID_TIMESTAMP`, masking distinct root causes such as missing source, malformed epoch, invalid threshold, or invalid status.
  3. Silent Initial Status Promotion: When initial telemetry omitted `status` (`incoming.status === undefined`), the initial builder defaulted to `'HEALTHY'`. Without an explicit contract authorizing this assumption, unstated health must not be presumed healthy.
* **Reconnaissance & Contract Verification:**
  - `control_surface/src/types/contracts.ts` declares `sourceEventTimeMs?: number;` on `TelemetryProvenance`. No contract specifies or authorizes defaulting an unstated source-event timestamp to local freshness.
  - Inspection of `control_surface/src/utils/telemetry.ts` revealed that `createInitialTelemetry` and `tryUpdateTelemetryState` handled initial-state validation independently, allowing potential diagnostic divergence.
  - In financial and critical telemetry feeds, unstated health state is epistemic uncertainty (`UNKNOWN`), not proof of health.
* **Decision:**
  1. **Source-Event Provenance Integrity (D2.3-A):**
     - Removed the implicit fallback `incoming.sourceEventTimeMs ?? freshnessTimestamp`.
     - In initial state creation (`evaluateInitialTelemetry`), when `incoming.sourceEventTimeMs` is absent/undefined, `sourceEventTimeMs` is set to `undefined`.
     - In `DOCUMENTED_UNKNOWN_TELEMETRY`, `sourceEventTimeMs` is explicitly `undefined`.
     - In state updates (`tryUpdateTelemetryState`), when `incoming.sourceEventTimeMs` is absent/undefined, the accepted state preserves `current.sourceEventTimeMs` unchanged.
     - Strict validation rejects negative, NaN, and non-finite timestamps with typed rejection reason `INVALID_SOURCE_EVENT_TIME`. Valid non-negative finite timestamps (including 0) are accepted.
  2. **Unified Initial-State Diagnostics (D2.3-B):**
     - Implemented `evaluateInitialTelemetry(incoming: Partial<TelemetryState> | undefined): TelemetryUpdateDiagnostic`.
     - Unifies validation and initial state construction between `createInitialTelemetry` and `tryUpdateTelemetryState`, eliminating code divergence.
     - Maps distinct failure conditions to precise typed rejection reasons:
       - `MISSING_INITIAL_TELEMETRY`: incoming input is null or undefined.
       - `MISSING_SOURCE`: incoming source is undefined, empty, or whitespace.
       - `UNRECOGNIZED_SOURCE`: incoming source is an unrecognized string outside `TelemetrySource`.
       - `MISSING_EPOCH`: incoming epoch is undefined.
       - `MALFORMED_EPOCH`: incoming epoch is non-positive, non-integer, NaN, or non-finite.
       - `MISSING_TIMESTAMP`: incoming freshness timestamp is undefined.
       - `INVALID_TIMESTAMP`: incoming freshness timestamp is non-positive, non-finite, or NaN.
       - `INVALID_STALE_THRESHOLD`: incoming stale threshold is <= 0, non-finite, or NaN.
       - `INVALID_STATUS`: incoming status is unrecognized outside `TelemetryStatus`.
       - `INVALID_SOURCE_EVENT_TIME`: incoming sourceEventTimeMs is negative, non-finite, or NaN.
     - `createInitialTelemetry()` delegates directly to `evaluateInitialTelemetry(opts).state`.
  3. **Fail-Safe Initial Status Defaulting to UNKNOWN (D2.3-C):**
     - When `incoming.status` is omitted/undefined, the state defaults safely to `'UNKNOWN'` rather than synthesizing `'HEALTHY'`.
     - Only explicit `'HEALTHY'` status yields healthy telemetry upon initial construction.
  4. **Hostile Regression Test Expansion (SC-01.24 & SC-01.25):**
     - `SC-01.24`: Hostile verification of source-event timestamp provenance, absence preservation without fabrication from freshnessTimestamp, zero/positive acceptance, and rejection of negative/NaN/Infinity values.
     - `SC-01.25`: Hostile verification of precise typed initial-state diagnostics across missing/invalid source, epoch, timestamp, threshold, status, and source-event timestamp, plus verification that unstated initial status defaults to `'UNKNOWN'`.
     - Automated test suite expanded to 82 passing tests (47 safety invariants, 20 responsive viewport behavioral, 6 positions sort, 9 modal accessibility).
  5. **Retained Boundary Status:**
     - Retained `AUTHENTICATED RECONNECTION UNVERIFIED` / `BLOCKED — BACKEND AUTHORITY NOT INTEGRATED`.
     - Retained `DURABLE IDEMPOTENCY BLOCKED` (client in-memory deduplication verified, distributed store unresolved).
     - Retained `SERVER AUTHENTICATION & RBAC BLOCKED` (live broker commands throw `LiveExecutionBlockedError`).
* **Rationale:** Governed by `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY`. Eliminates fabricated observation provenance, guarantees zero diagnostic divergence on initial telemetry ingestion, ensures unstated health is never presumed, and preserves complete snapshot immutability on rejected inputs.
