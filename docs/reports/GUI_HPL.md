# FRACTAL-FLOW Control Surface — Hostile Proof List (HPL)

**Status:** RECONCILED POST-STAGE D FORENSIC REMEDIATION & EXTENSION
**Governing Standard:** Universal Forensic Engineering Protocol
**Priority Order:** `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY > SECURITY > RECOVERY > RECONCILIATION > OPERATIONAL ROBUSTNESS > SPEED > PnL`

---

## 1. Canonical Matrix & Dispositions

| Entry ID | Vulnerability / Threat Surface | Severity | Current Disposition | Production Artifact | Test Evidence |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **GUI-HPL-001** | Missing Authoritative Backend Integration | CRITICAL (P0) | **BLOCKED (FAIL-CLOSED)** | `control_surface/src/providers/LiveCommandAdapter.ts` | SC-05.2: `LiveExecutionBlockedError` thrown unconditionally |
| **GUI-HPL-002** | Simulation Lifecycle Authority | HIGH (P1) | **REMEDIATED — TESTED** | `control_surface/src/providers/SimulationProvider.ts` | SC-04.3 & SC-05.1: Provider owns progression; zero mutations on rejection |
| **GUI-HPL-003** | Telemetry Provenance & Freshness | HIGH (P1) | **CLOSED — VERIFIED** | `control_surface/src/utils/telemetry.ts` | SC-01.1–SC-01.6: Provenance isolation, boundary, expiration, skew handling |
| **GUI-HPL-004** | Missing Active GUI CI Workflow | HIGH (P1) | **PARTIAL** | `control_surface/ci/gui-ci.yml.template` | Local quality gates pass clean; remote workflow activation requires repo maintainer |
| **GUI-HPL-005** | Server Authentication & RBAC Unimplemented | CRITICAL (P0) | **BLOCKED (INFRASTRUCTURE)** | Backend Control Service (Deferred) | Live mode fails closed; zero unauthenticated live mutations possible |
| **GUI-HPL-006** | Intent Identity & Payload Fingerprinting | CRITICAL (P0) | **CLOSED — VERIFIED** | `control_surface/src/utils/idempotency.ts` | SC-02.1–SC-02.5: WebCrypto `getRandomValues`, intentId/fingerprint separation |
| **GUI-HPL-007** | Command Recovery & Reconciliation Absent | HIGH (P1) | **BLOCKED (REQUIRES BACKEND)**| Backend Journal & Gateway (Deferred) | Frontend state remains strictly ephemeral and non-authoritative |
| **GUI-HPL-008** | Command Scope Exceeds Backend Contracts | HIGH (P1) | **REMEDIATED — TESTED** | `control_surface/src/types/contracts.ts` | Restricted strictly to `CLOSE`, `TIGHTEN_STOP`, `MOVE_TO_BREAKEVEN`, `KILL_SWITCH` |
| **GUI-HPL-009** | Simulation/Live Provider Isolation | CRITICAL (P0) | **CLOSED — VERIFIED** | `control_surface/src/providers/` | SC-05.2: Strict interface isolation; zero live network calls; fail-closed live gate |
| **GUI-HPL-010** | Specification & Implementation Drift | MEDIUM (P2) | **CLOSED — VERIFIED** | `spec/control_surface_v1.yaml` | Documented as off-broker operator surface with explicit non-authoritative boundaries |
| **GUI-HPL-011** | Dependency Installation Reproducibility | HIGH (P1) | **REMEDIATED — TESTED** | `control_surface/package-lock.json` | Tracked lockfile verified on Node v20/v22 & npm 10/11 clean installs |
| **GUI-HPL-012** | Client-Derived Statistics Provenance | MEDIUM (P1) | **REMEDIATED — TESTED** | `control_surface/src/components/SecondaryViews.tsx` | Visual disclaimers flag client statistics as non-authoritative simulation math |
| **GUI-HPL-013** | Keyboard Safety & Operator Interaction | HIGH (P1) | **CLOSED — VERIFIED** | `control_surface/src/utils/keyboard.ts` | Keyboard guard rejects all inputs, textareas, comboboxes, IME composition, chatter |
| **GUI-HPL-014** | Automated Adversarial Tests Missing | HIGH (P1) | **CLOSED — VERIFIED (51 TESTS)**| `control_surface/src/tests/` | 26 safety invariant + 10 responsive structural + 15 sort invariant tests pass |
| **GUI-HPL-015** | Browser Persistence Stale State Risk | MEDIUM (P1) | **CLOSED — VERIFIED** | `control_surface/src/App.tsx` | Ephemeral state only; zero unauthenticated localStorage persistence of positions |
| **GUI-HPL-016** | Cross-Source Telemetry Overwrite Integrity | HIGH (P1) | **CLOSED — VERIFIED** | `control_surface/src/utils/telemetry.ts` | SC-01.1–SC-01.3: Simulation ticks cannot overwrite or heal external telemetry |
| **GUI-HPL-017** | Intent Replay Alteration & Strict Canonicalization | CRITICAL (P0) | **CLOSED — VERIFIED** | `control_surface/src/utils/idempotency.ts` | SC-02.4 & SC-03.1–SC-03.7: Replay mismatch strictly rejected; -0 normalized |
| **GUI-HPL-018** | Truthful Simulation Reconciliation & Full Rejection | HIGH (P1) | **CLOSED — VERIFIED** | `control_surface/src/providers/SimulationProvider.ts` | SC-04.1–SC-04.2 & SC-05.1: Unknown intents rejected; rejected commands preserve state |
| **GUI-HPL-019** | Audit-Event Persistence Labeling Integrity | MEDIUM (P1) | **CLOSED — VERIFIED** | `control_surface/src/components/FooterLog.tsx` | SC-06.1: In-memory events labeled SESSION/SIMULATED; no false persistence claims |
| **GUI-HPL-020** | PositionsTable Sorting & Active View Retention | MEDIUM (P1) | **CLOSED — VERIFIED** | `control_surface/src/components/PositionsTable.tsx` | SORT-01–SORT-06: Interactive sort by PnL, Symbol, Size with scrollIntoView tracking |

---

## 2. Forensic Item Analysis & Evidence

### GUI-HPL-001: Missing Authoritative Backend Integration
- **Threat Scenario:** Operator assumes actions dispatched in the GUI execute on live broker terminals.
- **Evidence:** `src/fractal_flow` contains zero HTTP, WebSocket, or gRPC daemon processes (`NO_API_IN_SRC`).
- **Required Invariant:** In the absence of an authoritative backend, all live mutation attempts must fail closed.
- **Mitigation:** Implemented `LiveCommandAdapter` which unconditionally throws `LiveExecutionBlockedError`.
- **Test Evidence:** `safety_invariants.test.ts` SC-05.2: `LiveCommandAdapter.submitCommand` confirmed throwing `LiveExecutionBlockedError`.
- **Residual Risk:** Live execution remains unavailable until the backend Control Service is provisioned.
- **Disposition:** BLOCKED (FAIL-CLOSED & EXPECTED).

### GUI-HPL-002: Simulation Lifecycle Authority
- **Threat Scenario:** Operator observes synthetic timers advancing lifecycle states and believes an external broker executed the fill.
- **Evidence:** Prior implementation in `App.tsx` owned nested `setTimeout`s and randomized tick loops.
- **Required Invariant:** Simulation ticks and lifecycle progression must be owned strictly within the simulation boundary, tagged with `authoritative: false`.
- **Mitigation:** Moved tick generation, position pricing, and asynchronous lifecycle progression into `SimulationProvider.ts`. `App.tsx` subscribes to the provider and eliminates nested `setTimeout` loops. Rejections in simulation cause zero state mutations.
- **Test Evidence:** `safety_invariants.test.ts` SC-04.3 & SC-05.1.
- **Disposition:** REMEDIATED — TESTED.

### GUI-HPL-003: Telemetry Provenance & Freshness
- **Threat Scenario:** Stale market data or frozen broker connection masquerades as real-time state.
- **Evidence:** Prior UI displayed a static green pill without timestamp delta evaluation.
- **Required Invariant:** Health indicators must be evaluated by a production evaluator handling fresh, threshold boundary, expired, missing, and disconnected states.
- **Mitigation:** Authored `evaluateTelemetryFreshness()` in `control_surface/src/utils/telemetry.ts`. Disconnected sources cannot be promoted to healthy; threshold boundary is strictly `STALE`.
- **Test Evidence:** `safety_invariants.test.ts` SC-01.4, SC-01.5, SC-01.6: Evaluated all freshness boundaries, clock skew, and disconnected states.
- **Disposition:** CLOSED — VERIFIED.

### GUI-HPL-004: Missing Active GUI CI Workflow
- **Threat Scenario:** Regressions introduced without automated PR verification on GitHub.
- **Evidence:** Workflow template exists in `control_surface/ci/gui-ci.yml.template`, but `.github/workflows/` contains only Python backend CI.
- **Required Invariant:** Deterministic CI pipeline verifying build, lint, and invariant tests.
- **Mitigation:** Workflow template retained. `npm test` script integrated into `package.json` covering all 51 tests. Local gates run clean.
- **Residual Risk:** GitHub Actions workflow activation in `.github/workflows/` requires repository maintainer authorization.
- **Disposition:** PARTIAL.

### GUI-HPL-005: Server Authentication & RBAC Unimplemented
- **Threat Scenario:** Unauthenticated users trigger privileged commands.
- **Evidence:** No auth headers, JWT tokens, or session validation exist in the frontend.
- **Required Invariant:** Server-enforced deny-by-default access control.
- **Mitigation:** Live mode is hard-blocked (fails closed). Simulation mode modifies only ephemeral local memory.
- **Residual Risk:** Real RBAC requires backend implementation.
- **Disposition:** BLOCKED (INFRASTRUCTURE).

### GUI-HPL-006: Intent Identity & Payload Fingerprinting
- **Threat Scenario:** Conflating intent identity with payload fingerprint causes distinct commands to reuse intent IDs or retries to alter fingerprints.
- **Evidence:** Prior dual 32-bit mix sorted only top-level keys and derived intentId directly from the hash.
- **Required Invariant:** Separate logical intent ID (operator action identity) from payload fingerprint (semantic payload hash). Implement recursive canonicalization and cryptographic SHA-256.
- **Mitigation:** Authored `control_surface/src/utils/idempotency.ts`:
  1. Cryptographically secure `crypto.getRandomValues()` intent ID generation.
  2. Standard FIPS 180-4 SHA-256 implementation.
  3. Recursive deep object-key sorting, null preservation, array order retention, and strict rejection of `undefined`, `NaN`, `Infinity`, functions, and cyclic structures.
  4. Retries preserve `intentId` and `idempotencyKey`; new commands generate distinct `intentId`s.
  5. Active registry rejecting reuse of an existing intentId with modified semantic payload.
- **Test Evidence:** `safety_invariants.test.ts` SC-02.1–SC-02.5 and SC-03.1–SC-03.7.
- **Disposition:** CLOSED — VERIFIED.

### GUI-HPL-007: Command Recovery & Reconciliation Absent
- **Threat Scenario:** Browser refresh drops in-flight command state, leaving operator blind to unconfirmed orders.
- **Evidence:** React state is purely in-memory.
- **Required Invariant:** Durable event-sourcing and backend orphan reconciliation.
- **Disposition:** BLOCKED (REQUIRES BACKEND JOURNAL & RECONCILIATION ENGINE).

### GUI-HPL-008: Command Scope Exceeds Backend Contracts
- **Threat Scenario:** Frontend offers actions not supported by the execution gateway.
- **Mitigation:** Mapped actions strictly to supported FRACTAL-FLOW operations (`CLOSE`, `TIGHTEN_STOP`, `MOVE_TO_BREAKEVEN`, `KILL_SWITCH`).
- **Disposition:** REMEDIATED — TESTED.

### GUI-HPL-009: Simulation/Live Provider Isolation
- **Threat Scenario:** Simulation code inadvertently invokes live network APIs, or live code falls back to mock data.
- **Evidence:** Separate `SimulationProvider` and `LiveCommandAdapter` classes implementing `ICommandProvider` and `IDataProvider`.
- **Required Invariant:** Strict interface decoupling; live adapter fails closed without network access.
- **Mitigation:** `LiveCommandAdapter` throws `LiveExecutionBlockedError` immediately; `SimulationProvider` operates solely on in-memory fixtures.
- **Test Evidence:** `safety_invariants.test.ts` SC-05.2.
- **Disposition:** CLOSED — VERIFIED.

### GUI-HPL-010: Specification & Implementation Drift
- **Threat Scenario:** Discrepancy between documentation and code claims.
- **Mitigation:** `spec/control_surface_v1.yaml` explicitly notes `status: design_not_yet_implemented`. GUI README clarifies simulation boundary.
- **Disposition:** CLOSED — VERIFIED.

### GUI-HPL-011: Dependency Installation Reproducibility
- **Threat Scenario:** Non-deterministic package resolution leads to unverified build behavior across environments.
- **Evidence:** Tracked lockfile resolves declared manifest dependencies without external tree leaks.
- **Mitigation:** Verified reproducible clean installation with npm 10/11 on Node v20/v22.
- **Disposition:** REMEDIATED — TESTED.

### GUI-HPL-012: Client-Derived Statistics Provenance
- **Threat Scenario:** Operator relies on client math as authoritative financial risk calculations.
- **Evidence:** Win rate, expectancy, and max drawdown computed locally from closed trade fixtures.
- **Required Invariant:** Clear visual disclaimer that metrics are client-derived and non-authoritative.
- **Mitigation:** Added persistent amber warning badge in Stats tab: `[DEMO CALCULATION] Local client math from simulation fixtures. Non-authoritative.`
- **Disposition:** REMEDIATED — TESTED.

### GUI-HPL-013: Keyboard Safety & Operator Interaction
- **Threat Scenario:** Operator typing in search/filter boxes triggers hotkeys, or key chatter causes double execution.
- **Evidence:** Input targets, IME composition, repeated keys, and open modal conditions required systematic gating.
- **Required Invariant:** Suppress shortcuts on text targets, IME composition, key repeat, open confirmation dialogs, and commands in flight.
- **Mitigation:** Authored `control_surface/src/utils/keyboard.ts` providing `isSafeKeyboardShortcutTarget`, `isValidShortcutEvent`, and `isKeyboardShortcutAllowed`.
- **Test Evidence:** `safety_invariants.test.ts` Keyboard safety assertions.
- **Disposition:** CLOSED — VERIFIED.

### GUI-HPL-014: Automated Adversarial Tests Missing
- **Threat Scenario:** Safety regressions pass undetected due to superficial or circular test assertions.
- **Required Invariant:** Automated adversarial test suite exercising actual production logic across safety, layout, and interaction.
- **Mitigation:** 51 total deterministic automated tests:
  - 26 tests in `safety_invariants.test.ts` (SC-01 through SC-06).
  - 10 tests in `responsive_structural.test.ts` (UX-01 through UX-08).
  - 15 tests in `positions_table_sort.test.ts` (SORT-01 through SORT-06).
- **Test Evidence:** All 51 tests pass with exit code 0 (`npm test`).
- **Disposition:** CLOSED — VERIFIED (51 TESTS).

### GUI-HPL-015: Browser Persistence Stale State Risk
- **Threat Scenario:** Stale position versions stored in `localStorage` corrupt live execution state across sessions.
- **Required Invariant:** Zero unauthenticated persistent storage of position versions in the client.
- **Mitigation:** Component state is strictly ephemeral and re-queried from provider on mount.
- **Disposition:** CLOSED — VERIFIED.

### GUI-HPL-016: Cross-Source Telemetry Overwrite Integrity
- **Threat Scenario:** Internal simulation ticks inadvertently promote a disconnected external broker feed to healthy.
- **Required Invariant:** `updateTelemetryState` must guarantee that events from `SIM_ENGINE` cannot overwrite or alter timestamps of external sources (`BROKER_FEED` / `CONTROL_SERVICE`). Out-of-order stale events must be discarded.
- **Mitigation:** Implemented cross-source protection gates in `control_surface/src/utils/telemetry.ts`.
- **Test Evidence:** `safety_invariants.test.ts` SC-01.1, SC-01.2, SC-01.3.
- **Disposition:** CLOSED — VERIFIED.

### GUI-HPL-017: Intent Replay Semantic Alteration & Strict Canonicalization
- **Threat Scenario:** Replaying an existing intent ID with modified parameters bypasses validation or causes duplicate execution with altered parameters.
- **Required Invariant:** Existing intent IDs re-submitted with altered semantic payloads must throw `IntentReplayMismatchError`. Numeric canonicalization must normalize `-0` to `0` and reject non-finite, sparse, or exotic object structures.
- **Mitigation:** Implemented active intent registry in `control_surface/src/utils/idempotency.ts` and enhanced canonicalizer.
- **Test Evidence:** `safety_invariants.test.ts` SC-02.4 and SC-03.1–SC-03.7.
- **Disposition:** CLOSED — VERIFIED.

### GUI-HPL-018: Truthful Simulation Reconciliation & Full Rejection
- **Threat Scenario:** Reconciling unknown or malformed intent IDs returns false confirmations, or rejected commands mutate local state.
- **Required Invariant:** `reconcileCommand` must reject unrecorded or malformed intent IDs. Rejected commands must leave deep simulation state completely unmodified.
- **Mitigation:** Implemented validation gates and pre-mutation rollback snapshots in `SimulationProvider.ts`.
- **Test Evidence:** `safety_invariants.test.ts` SC-04.1, SC-04.2, SC-05.1.
- **Disposition:** CLOSED — VERIFIED.

### GUI-HPL-019: Audit-Event Persistence Labeling Integrity
- **Threat Scenario:** UI falsely displays session-only in-memory events as durably persisted to disk or server.
- **Required Invariant:** Event log must visibly distinguish ephemeral in-memory records with `SESSION` or `SIMULATED` chips.
- **Mitigation:** Updated `FooterLog.tsx` with accurate provenance chips and persistence status badges.
- **Test Evidence:** `safety_invariants.test.ts` SC-06.1.
- **Disposition:** CLOSED — VERIFIED.

### GUI-HPL-020: PositionsTable Sorting & Active View Retention
- **Threat Scenario:** Sorting trades by PnL, Symbol, or Size causes the active monitored position to jump out of the viewport, disorienting the operator during rapid market conditions.
- **Required Invariant:** Column headers must support interactive sorting with clear directional indicators (`▲` / `▼`), visible sortable affordances, and accessible `aria-sort`. The currently selected position must remain highlighted and automatically scrolled into view (`selectedRowRef.scrollIntoView`).
- **Mitigation:** Implemented interactive sorting across Open, Pending, and Closed tabs in `PositionsTable.tsx` with automatic scroll tracking.
- **Test Evidence:** `positions_table_sort.test.ts` SORT-01 through SORT-06 (15 tests passing).
- **Disposition:** CLOSED — VERIFIED.
