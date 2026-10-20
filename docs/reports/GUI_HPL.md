# FRACTAL-FLOW Control Surface — Hostile Proof List (HPL)
**Status:** RECONCILED POST-STAGE B FORENSIC REMEDIATION  
**Governing Standard:** Universal Forensic Engineering Protocol  
**Priority Order:** `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY > SECURITY > RECOVERY > RECONCILIATION > OPERATIONAL ROBUSTNESS > SPEED > PnL`

---

## 1. Canonical Matrix & Dispositions

| Entry ID | Vulnerability / Threat Surface | Severity | Current Disposition | Production Artifact | Test Evidence |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **GUI-HPL-001** | Missing Authoritative Backend Integration | CRITICAL (P0) | **BLOCKED (FAIL-CLOSED)** | `control_surface/src/providers/LiveCommandAdapter.ts` | Test 1 & 2: `LiveExecutionBlockedError` thrown on submit & reconcile |
| **GUI-HPL-002** | Simulation Lifecycle Authority | HIGH (P1) | **REMEDIATED — TESTED** | `control_surface/src/providers/SimulationProvider.ts` | Test 4 & 5: Provider owns progression & tick updates; zero mutations on rejection |
| **GUI-HPL-003** | Telemetry Provenance & Freshness | HIGH (P1) | **REMEDIATED — TESTED** | `control_surface/src/utils/telemetry.ts` | Test 15 & 16: Evaluates fresh, threshold boundary, expired, invalid, disconnected |
| **GUI-HPL-004** | Missing Active GUI CI Workflow | HIGH (P1) | **PARTIAL** | `control_surface/ci/gui-ci.yml.template` | Local quality gates pass; workflow activation requires maintainer auth |
| **GUI-HPL-005** | Server Authentication & RBAC Unimplemented | CRITICAL (P0) | **BLOCKED (INFRASTRUCTURE)** | Backend Control Service (Deferred) | Live mode fails closed; no unauthenticated live mutations possible |
| **GUI-HPL-006** | Intent Identity & Payload Fingerprinting | CRITICAL (P0) | **REMEDIATED — TESTED** | `control_surface/src/utils/idempotency.ts` | Tests 6–11: Standard SHA-256 KAT, recursive canonicalization, intentId/fingerprint separation |
| **GUI-HPL-007** | Command Recovery & Reconciliation Absent | HIGH (P1) | **BLOCKED (REQUIRES BACKEND)**| Backend Journal & Gateway (Deferred) | Frontend state remains strictly ephemeral; non-authoritative |
| **GUI-HPL-008** | Command Scope Exceeds Backend Contracts | HIGH (P1) | **REMEDIATED — TESTED** | `control_surface/src/types/contracts.ts` | Restricted strictly to `CLOSE`, `TIGHTEN_STOP`, `MOVE_TO_BREAKEVEN`, `KILL_SWITCH` |
| **GUI-HPL-009** | Simulation/Live Provider Isolation | CRITICAL (P0) | **CLOSED — VERIFIED** | `control_surface/src/providers/` | Tests 1–5: Strict interface isolation; zero live network calls; fail-closed live gate |
| **GUI-HPL-010** | Specification & Implementation Drift | MEDIUM (P2) | **CLOSED — VERIFIED** | `spec/control_surface_v1.yaml` | Documented as off-broker operator surface with explicit non-authoritative boundaries |
| **GUI-HPL-011** | Dependency Installation Reproducibility | HIGH (P1) | **REMEDIATED — TESTED** | `control_surface/package-lock.json` | Tracked lockfile generated; verified on Node v22.23.3 & npm 10.9.9 |
| **GUI-HPL-012** | Client-Derived Statistics Provenance | MEDIUM (P1) | **REMEDIATED — TESTED** | `control_surface/src/components/SecondaryViews.tsx` | Visual disclaimers flag client statistics as non-authoritative simulation math |
| **GUI-HPL-013** | Keyboard Safety & Operator Interaction | HIGH (P1) | **CLOSED — VERIFIED** | `control_surface/src/utils/keyboard.ts` | Tests 12–14: Input target, IME composition, repeat chatter, modifier, modal, in-flight guards |
| **GUI-HPL-014** | Automated Adversarial Tests Missing | HIGH (P1) | **CLOSED — VERIFIED (17 TESTS)**| `control_surface/src/tests/safety_invariants.test.ts` | 17/17 deterministic tests exercising actual production logic pass |
| **GUI-HPL-015** | Browser Persistence Stale State Risk | MEDIUM (P1) | **CLOSED — VERIFIED** | `control_surface/src/App.tsx` | Ephemeral state only; zero unauthenticated localStorage persistence of positions |

---

## 2. Forensic Item Analysis & Evidence

### GUI-HPL-001: Missing Authoritative Backend Integration
- **Threat Scenario:** Operator assumes actions dispatched in the GUI execute on live broker terminals.
- **Evidence:** `src/fractal_flow` contains zero HTTP, WebSocket, or gRPC daemon processes (`NO_API_IN_SRC`).
- **Required Invariant:** In the absence of an authoritative backend, all live mutation attempts must fail closed.
- **Mitigation:** Implemented `LiveCommandAdapter` which unconditionally throws `LiveExecutionBlockedError`.
- **Test Evidence:** `safety_invariants.test.ts` Test 1: `LiveCommandAdapter.submitCommand` confirmed throwing `LiveExecutionBlockedError`.
- **Residual Risk:** Live execution remains unavailable until the backend Control Service is provisioned.
- **Disposition:** BLOCKED (EXPECTED & SAFE).

### GUI-HPL-002: Simulation Lifecycle Authority
- **Threat Scenario:** Operator observes synthetic timers advancing lifecycle states and believes an external broker executed the fill.
- **Evidence:** Prior implementation in `App.tsx` owned nested `setTimeout`s and randomized tick loops.
- **Required Invariant:** Simulation ticks and lifecycle progression must be owned strictly within the simulation boundary, tagged with `authoritative: false`.
- **Mitigation:** Moved tick generation, position pricing, and asynchronous lifecycle progression into `SimulationProvider.ts`. `App.tsx` subscribes to the provider and eliminates nested `setTimeout` loops. Rejections in simulation cause zero state mutations.
- **Test Evidence:** `safety_invariants.test.ts` Tests 4 & 5: Verified provider emits non-authoritative progress updates and rejected commands leave positions untouched.
- **Disposition:** REMEDIATED — TESTED.

### GUI-HPL-003: Telemetry Provenance and Freshness
- **Threat Scenario:** Hardcoded or synthesized timestamps mask network disconnection or stale feeds.
- **Evidence:** Inline timestamp comparison previously bypassed edge cases (missing timestamps, disconnected source).
- **Required Invariant:** Health indicators must be evaluated by a production evaluator handling fresh, threshold boundary, expired, missing, and disconnected states.
- **Mitigation:** Authored `evaluateTelemetryFreshness()` in `control_surface/src/utils/telemetry.ts`. Disconnected sources cannot be promoted to healthy; threshold boundary is strictly `STALE`.
- **Test Evidence:** `safety_invariants.test.ts` Tests 15 & 16: Evaluated all freshness boundaries and disconnected states.
- **Disposition:** REMEDIATED — TESTED.

### GUI-HPL-004: Missing Active GUI CI Workflow
- **Threat Scenario:** Regressions introduced without automated PR verification on GitHub.
- **Evidence:** Workflow template exists in `control_surface/ci/gui-ci.yml.template`, but `.github/workflows/` contains only Python backend CI.
- **Required Invariant:** Deterministic CI pipeline verifying build, lint, and invariant tests.
- **Mitigation:** Workflow template retained. `npm test` script integrated into `package.json`. Local gates run clean.
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
  1. Standard FIPS 180-4 SHA-256 implementation.
  2. Recursive deep object-key sorting, null preservation, array order retention, and strict rejection of `undefined`, `NaN`, `Infinity`, functions, and cyclic structures.
  3. Retries preserve `intentId` and `idempotencyKey`; new commands generate distinct `intentId`s.
  4. Explicit code and specification notice that client fingerprinting is NOT authoritative server deduplication.
- **Test Evidence:** `safety_invariants.test.ts` Tests 6–11: Standard NIST/RFC KAT vectors pass; recursive canonicalization verified; intent ID separation verified.
- **Disposition:** REMEDIATED — TESTED.

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
- **Test Evidence:** `safety_invariants.test.ts` Tests 1, 2, 3, 4, 5.
- **Disposition:** CLOSED — VERIFIED.

### GUI-HPL-010: Specification & Implementation Drift
- **Threat Scenario:** Discrepancy between documentation and code claims.
- **Mitigation:** `spec/control_surface_v1.yaml` explicitly notes `status: design_not_yet_implemented`. GUI README clarifies simulation boundary.
- **Disposition:** CLOSED — VERIFIED.

### GUI-HPL-011: Dependency Installation Reproducibility
- **Threat Scenario:** Non-deterministic package resolution leads to unverified build behavior across environments.
- **Evidence:** `control_surface/package-lock.json` was missing.
- **Required Invariant:** Tracked lockfile pinned for deterministic clean installs.
- **Mitigation:** Generated and verified `control_surface/package-lock.json` using Node v22.23.3 and npm 10.9.9.
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
- **Test Evidence:** `safety_invariants.test.ts` Tests 12, 13, 14: Confirmed suppression on all input types, IME composition, key repeat, and modal/in-flight states.
- **Disposition:** CLOSED — VERIFIED.

### GUI-HPL-014: Automated Adversarial Tests Missing
- **Threat Scenario:** Safety regressions pass undetected due to superficial or circular test assertions.
- **Evidence:** Prior test suite had 13 tests, including self-comparison of hashes and inline timestamp calculations.
- **Required Invariant:** Automated adversarial test suite exercising actual production logic.
- **Mitigation:** Authored 17 deterministic tests in `safety_invariants.test.ts` exercising FIPS 180-4 SHA-256 KAT vectors, recursive canonicalization, rejection of invalid types, intent identity separation, keyboard safety, and production telemetry evaluation.
- **Test Evidence:** 17/17 passing with 0 errors (`npm test`).
- **Disposition:** CLOSED — VERIFIED (17 TESTS).

### GUI-HPL-015: Browser Persistence Stale State Risk
- **Threat Scenario:** Stale position versions stored in `localStorage` corrupt live execution state across sessions.
- **Required Invariant:** Zero unauthenticated persistent storage of position versions in the client.
- **Mitigation:** Component state is strictly ephemeral and re-queried from provider on mount.
- **Disposition:** CLOSED — VERIFIED.
