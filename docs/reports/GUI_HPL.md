# FRACTAL-FLOW GUI — HOSTILE PROOF LIST (HPL)
**Document Version:** 1.0 (Stage B Closure)  
**Governing Standard:** Universal Forensic Engineering Protocol  
**Priority:** SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY  
**Scope:** Operator Control Surface (`control_surface/`)  

---

## 1. Executive Summary & Disposition Matrix

| Finding ID | Title | Severity | Stage B Disposition | Evidence Reference |
|---|---|---|---|---|
| **GUI-HPL-001** | Missing Authoritative Backend Integration | CRITICAL (P0) | **BLOCKED (BY DESIGN)** | `control_surface/src/providers/LiveCommandAdapter.ts` |
| **GUI-HPL-002** | Simulated Lifecycle Imitating Execution | HIGH (P0) | **REMEDIATED & VERIFIED** | `control_surface/src/providers/SimulationProvider.ts` |
| **GUI-HPL-003** | Misleading Hardcoded Operational Health | MEDIUM (P1) | **REMEDIATED & VERIFIED** | `control_surface/src/components/Header.tsx` |
| **GUI-HPL-004** | Missing Active GUI CI Workflow | HIGH (P1) | **PARTIALLY REMEDIATED** | `control_surface/ci/gui-ci.yml.template`, `package.json` |
| **GUI-HPL-005** | Server Auth & RBAC Unimplemented | CRITICAL (P0) | **BLOCKED (INFRASTRUCTURE)** | `spec/control_surface_v1.yaml` |
| **GUI-HPL-006** | Idempotency Not Authoritative / Retry-Safe | HIGH (P0) | **REMEDIATED & VERIFIED (CLIENT)** | `control_surface/src/utils/idempotency.ts` |
| **GUI-HPL-007** | Command Recovery & Reconciliation Absent | HIGH (P1) | **BLOCKED (INFRASTRUCTURE)** | `src/fractal_flow/persistence/` |
| **GUI-HPL-008** | Command Scope Exceeds Backend Contracts | MEDIUM (P1) | **MITIGATED & SCOPED** | `control_surface/src/App.tsx` |
| **GUI-HPL-009** | Simulation/Live Provider Isolation | CRITICAL (P0) | **CLOSED & TESTED** | `control_surface/src/providers/interfaces.ts` |
| **GUI-HPL-010** | Specification & Implementation Drift | LOW (P2) | **DOCUMENTED** | `spec/control_surface_v1.yaml` |
| **GUI-HPL-011** | Dependency Installation Reproducibility | MEDIUM (P1) | **REMEDIATED** | `control_surface/package.json` |
| **GUI-HPL-012** | Client-Derived Statistics Provenance | MEDIUM (P1) | **REMEDIATED & LABELED** | `control_surface/src/components/ContextPanel.tsx` |
| **GUI-HPL-013** | Hotkeys Trigger While User Is Typing | HIGH (P1) | **CLOSED & TESTED** | `control_surface/src/utils/keyboard.ts` |
| **GUI-HPL-014** | Automated Adversarial Tests Missing | HIGH (P1) | **CLOSED & TESTED (13 TESTS)**| `control_surface/src/tests/safety_invariants.test.ts`|
| **GUI-HPL-015** | Browser Persistence Stale State Risk | MEDIUM (P1) | **PREVENTED BY DESIGN** | `control_surface/src/App.tsx` |

---

## 2. Forensic Item Analysis

### GUI-HPL-001: Missing Authoritative Backend Integration
- **Threat Scenario:** Operator assumes actions dispatched in the GUI execute on live broker terminals.
- **Evidence:** `src/fractal_flow` contains zero HTTP, WebSocket, or gRPC daemon processes (`NO_API_IN_SRC`).
- **Required Invariant:** In the absence of an authoritative backend, all live mutation attempts must fail closed.
- **Mitigation:** Implemented `LiveCommandAdapter` which unconditionally throws `LiveExecutionBlockedError`.
- **Test Evidence:** `safety_invariants.test.ts` Test 1: `LiveCommandAdapter.submitCommand` confirmed throwing `LiveExecutionBlockedError`.
- **Residual Risk:** Live execution remains unavailable until the backend Control Service is provisioned.
- **Disposition:** BLOCKED (EXPECTED & SAFE).

### GUI-HPL-002: Simulated Lifecycle Imitating Execution
- **Threat Scenario:** Operator observes synthetic timers (`setTimeout`) advancing `ACCEPTED` → `DISPATCHED` → `CONFIRMED` and believes broker executed the fill.
- **Evidence:** Prior implementation in `App.tsx` mutated positions locally on timers.
- **Required Invariant:** Simulation must clearly declare non-authoritative status and never mimic broker confirmations.
- **Mitigation:** Quarantined simulation logic to `SimulationProvider`. Results explicitly carry `authoritative: false` and are tagged with `[SANDBOX] (NON-BROKER)`.
- **Test Evidence:** `safety_invariants.test.ts` Test 4: Confirmed `authoritative === false` on all simulation outcomes.
- **Disposition:** REMEDIATED & VERIFIED.

### GUI-HPL-003: Misleading Hardcoded Operational Health
- **Threat Scenario:** Header displayed static green text "bridge live · fence OK · epoch 418", giving a false sense of broker connectivity.
- **Evidence:** Hardcoded string in `Header.tsx`.
- **Required Invariant:** Health chips must derive from typed `TelemetryProvenance` with source, status, and freshness timestamp.
- **Mitigation:** Refactored `Header.tsx` to consume dynamic `TelemetryProvenance`. Status evaluates to `STALE` if no heartbeat is received within `staleThresholdMs` (5000ms). Source is displayed as `SRC: SIM_ENGINE` and `AUTH: NO (SIM)`.
- **Test Evidence:** `safety_invariants.test.ts` Test 13: Stale evaluation verified.
- **Disposition:** REMEDIATED & VERIFIED.

### GUI-HPL-004: Missing Active GUI CI Workflow
- **Threat Scenario:** Regressions introduced without automated PR verification.
- **Evidence:** Fine-grained PAT without `workflow` scope prevented direct push to `.github/workflows/`.
- **Required Invariant:** Deterministic CI pipeline verifying build and invariant tests.
- **Mitigation:** CI workflow authored as template `control_surface/ci/gui-ci.yml.template`. Added `npm test` script to `package.json` for deterministic execution in any CI environment.
- **Residual Risk:** GitHub Actions workflow requires repo owner activation.
- **Disposition:** PARTIALLY REMEDIATED.

### GUI-HPL-005: Server Authentication & RBAC Unimplemented
- **Threat Scenario:** Unauthenticated users trigger privileged commands (e.g. kill switches).
- **Evidence:** No auth headers, JWT tokens, or session validation exist.
- **Required Invariant:** Server-enforced deny-by-default access control.
- **Mitigation:** Live mode is hard-blocked. Simulation mode is non-destructive.
- **Residual Risk:** Real RBAC requires backend implementation.
- **Disposition:** BLOCKED (INFRASTRUCTURE).

### GUI-HPL-006: Idempotency Not Authoritative / Retry-Safe
- **Threat Scenario:** Network retry generates a fresh timestamp/random key, causing double executions at the broker.
- **Evidence:** `App.tsx` previously used `Date.now() + Math.random()`.
- **Required Invariant:** Identical logical intent must yield the identical idempotency key across all retransmissions.
- **Mitigation:** Implemented deterministic intent fingerprinting (`generateIntentFingerprint`) via Fowler-Noll-Vo / Murmur hash over `(operatorId, targetPositionId, symbol, actionType, canonicalParameters)`.
- **Test Evidence:** `safety_invariants.test.ts` Tests 6, 7, 8: Verified identical keys on retries, parameter order invariance, and key divergence on parameter changes.
- **Disposition:** REMEDIATED & VERIFIED (CLIENT).

### GUI-HPL-007: Command Recovery & Reconciliation Absent
- **Threat Scenario:** Browser refresh drops in-flight command state, leaving operator blind to unconfirmed orders.
- **Evidence:** React state is purely in-memory.
- **Required Invariant:** Durable event-sourcing and backend orphan reconciliation.
- **Disposition:** BLOCKED (REQUIRES BACKEND JOURNAL & RECONCILIATION ENGINE).

### GUI-HPL-008: Command Scope Exceeds Backend Contracts
- **Threat Scenario:** Frontend offers actions not supported by the execution gateway.
- **Mitigation:** Mapped actions strictly to supported FRACTAL-FLOW operations (`CLOSE`, `TIGHTEN_STOP`, `MOVE_TO_BREAKEVEN`).
- **Disposition:** MITIGATED & SCOPED.

### GUI-HPL-009: Simulation/Live Provider Isolation
- **Threat Scenario:** Simulation code inadvertently invokes live network APIs, or live code falls back to mock data.
- **Evidence:** Initial prototype coupled mock data directly into component state.
- **Required Invariant:** Strict interface decoupling (`IDataProvider`, `ICommandProvider`) with separate classes.
- **Mitigation:** Created `SimulationProvider` and `LiveCommandAdapter` under `src/providers/`.
- **Test Evidence:** `safety_invariants.test.ts` Tests 1, 2, 3, 4.
- **Disposition:** CLOSED & TESTED.

### GUI-HPL-010: Specification & Implementation Drift
- **Threat Scenario:** Discrepancy between documentation and code claims.
- **Mitigation:** `spec/control_surface_v1.yaml` explicitly notes `status: design_not_yet_implemented`. GUI README clarifies simulation boundary.
- **Disposition:** DOCUMENTED.

### GUI-HPL-011: Dependency Installation Reproducibility
- **Threat Scenario:** Non-deterministic package resolution leads to unverified build behavior.
- **Mitigation:** Pinned exact dependency versions in `control_surface/package.json`.
- **Disposition:** REMEDIATED.

### GUI-HPL-012: Client-Derived Statistics Provenance
- **Threat Scenario:** Operator relies on client math as authoritative financial risk calculations.
- **Evidence:** Win rate, expectancy, and max drawdown computed locally from closed trade fixtures.
- **Required Invariant:** Clear visual disclaimer that metrics are client-derived and non-authoritative.
- **Mitigation:** Added persistent amber warning badge in Stats tab: `[DEMO CALCULATION] Local client math from simulation fixtures. Non-authoritative.`
- **Disposition:** REMEDIATED & LABELED.

### GUI-HPL-013: Hotkeys Trigger While User Is Typing
- **Threat Scenario:** Operator typing in a search bar triggers hotkeys `T` (tighten), `B` (breakeven), or `C` (close).
- **Evidence:** Unfiltered global `window.addEventListener('keydown')`.
- **Required Invariant:** All keyboard shortcuts must be strictly suppressed when focus is on text-entry elements.
- **Mitigation:** Authored `isSafeKeyboardShortcutTarget` in `src/utils/keyboard.ts`, guarding against `INPUT`, `TEXTAREA`, `SELECT`, and `contentEditable`.
- **Test Evidence:** `safety_invariants.test.ts` Tests 9, 10, 11, 12: Confirmed suppression on all input types.
- **Disposition:** CLOSED & TESTED.

### GUI-HPL-014: Automated Adversarial Tests Missing
- **Threat Scenario:** Safety regressions pass undetected.
- **Mitigation:** Created `safety_invariants.test.ts` containing 13 deterministic assertions.
- **Test Evidence:** 13/13 passing with zero errors.
- **Disposition:** CLOSED & TESTED.

### GUI-HPL-015: Browser Persistence Stale State Risk
- **Threat Scenario:** Stale position versions stored in `localStorage` corrupt live execution state across sessions.
- **Required Invariant:** Zero unauthenticated persistent storage of position versions in the client.
- **Mitigation:** Component state is strictly ephemeral and re-queried from provider on mount.
- **Disposition:** PREVENTED BY DESIGN.
