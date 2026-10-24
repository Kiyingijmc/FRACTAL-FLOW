# FRACTAL-FLOW Control Surface — Hostile Proof List (HPL)

**Status:** RECONCILED POST-STAGE D.2 FORENSIC REMEDIATION & COUNTEREXAMPLE ELIMINATION  
**Governing Standard:** Universal Forensic Engineering Protocol  
**Priority Order:** `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY > SECURITY > RECOVERY > RECONCILIATION > OPERATIONAL ROBUSTNESS > SPEED > PnL`

---

## 1. Canonical Matrix & Dispositions

| Entry ID | Vulnerability / Threat Surface | Severity | Current Disposition | Production Artifact | Test Evidence |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **GUI-HPL-001** | Missing Authoritative Backend Integration | CRITICAL (P0) | **BLOCKED (FAIL-CLOSED)** | `control_surface/src/providers/LiveCommandAdapter.ts` | SC-05.2: `LiveExecutionBlockedError` thrown unconditionally |
| **GUI-HPL-002** | Simulation Lifecycle Authority | HIGH (P1) | **REAL COMPONENT BEHAVIOR VERIFIED** | `control_surface/src/providers/SimulationProvider.ts` | SC-04.3 & SC-05.1: Provider owns progression; zero mutations on rejection |
| **GUI-HPL-003** | Telemetry Provenance, Atomicity & Freshness (D2.3-F01 / C1-C6) | HIGH (P1) | **REAL COMPONENT BEHAVIOR VERIFIED** | `control_surface/src/utils/telemetry.ts` | SC-01.1–SC-01.27: All-or-nothing atomicity, typed rejection diagnostics, strict initial validation (empty/whitespace/null/undefined source -> MISSING_SOURCE; unrecognized/malformed -> UNRECOGNIZED_SOURCE; strict diagnostic precedence), boundary staleness, clock skew degradation, object anti-poisoning, exact sourceEventTimeMs provenance preservation (no implicit fallback to freshnessTimestamp), unstated status defaulting to UNKNOWN, absence-based threshold defaulting |
| **GUI-HPL-004** | Missing Active GUI CI Workflow | HIGH (P1) | **CI PASSED (ACTIVATED)** | `.github/workflows/gui-ci.yml` | Workflow active with least-privilege permissions, npm ci, lint, test, build |
| **GUI-HPL-005** | Server Authentication & RBAC Unimplemented | CRITICAL (P0) | **BLOCKED (UNRESOLVED BACKEND DEPENDENCY)** | Backend Control Service (Deferred) | Live mode fails closed; zero unauthenticated live mutations possible |
| **GUI-HPL-006** | Intent Identity & Payload Fingerprinting | CRITICAL (P0) | **CLIENT-SIDE VERIFIED (BACKEND UNRESOLVED)** | `control_surface/src/utils/idempotency.ts` | SC-02.1–SC-02.5: WebCrypto `getRandomValues`, fingerprint separation; distributed store unresolved |
| **GUI-HPL-007** | Command Recovery & Reconciliation Absent | HIGH (P1) | **BLOCKED (UNRESOLVED BACKEND DEPENDENCY)** | Backend Journal & Gateway (Deferred) | Frontend state remains strictly ephemeral and non-authoritative |
| **GUI-HPL-008** | Command Scope Exceeds Backend Contracts | HIGH (P1) | **IMPLEMENTATION PRESENT & UNIT TEST EXECUTED** | `control_surface/src/types/contracts.ts` | Restricted strictly to `CLOSE`, `TIGHTEN_STOP`, `MOVE_TO_BREAKEVEN`, `KILL_SWITCH` |
| **GUI-HPL-009** | Simulation/Live Provider Isolation | CRITICAL (P0) | **REAL COMPONENT BEHAVIOR VERIFIED** | `control_surface/src/providers/` | SC-05.2: Strict interface isolation; zero live network calls; fail-closed live gate |
| **GUI-HPL-010** | Specification & Implementation Drift | MEDIUM (P2) | **IMPLEMENTATION PRESENT** | `spec/control_surface_v1.yaml` | Documented as off-broker operator surface with explicit non-authoritative boundaries |
| **GUI-HPL-011** | Dependency Installation Reproducibility | HIGH (P1) | **CI PASSED (REPRODUCIBLE LOCKFILE)** | `control_surface/package-lock.json` | Tracked lockfile verified with `npm ci` on Node 20/22 |
| **GUI-HPL-012** | Client-Derived Statistics Provenance | MEDIUM (P1) | **REAL COMPONENT BEHAVIOR VERIFIED** | `control_surface/src/components/SecondaryViews.tsx` | Visual disclaimers flag client statistics as non-authoritative simulation math |
| **GUI-HPL-013** | Keyboard Safety & Operator Interaction | HIGH (P1) | **UNIT TEST EXECUTED** | `control_surface/src/utils/keyboard.ts` | Keyboard guard rejects all inputs, textareas, comboboxes, IME composition, chatter |
| **GUI-HPL-014** | Automated Adversarial Tests Missing | HIGH (P1) | **AUTOMATED TEST SUITE PASSING (84 TESTS)** | `control_surface/src/tests/` | 49 safety invariant + 20 responsive viewport behavioral + 6 positions sort + 9 modal accessibility |
| **GUI-HPL-015** | Browser Persistence Stale State Risk | MEDIUM (P1) | **REAL COMPONENT BEHAVIOR VERIFIED** | `control_surface/src/App.tsx` | Ephemeral state only; zero unauthenticated localStorage persistence of positions |
| **GUI-HPL-016** | Cross-Source Telemetry Overwrite Integrity | HIGH (P1) | **REAL COMPONENT BEHAVIOR VERIFIED** | `control_surface/src/utils/telemetry.ts` | SC-01.1–SC-01.3: Simulation ticks cannot overwrite or heal external telemetry |
| **GUI-HPL-017** | Intent Replay Alteration & Strict Canonicalization | CRITICAL (P0) | **UNIT TEST EXECUTED** | `control_surface/src/utils/idempotency.ts` | SC-02.4 & SC-03.1–SC-03.7: Replay mismatch strictly rejected; -0 normalized |
| **GUI-HPL-018** | Truthful Simulation Reconciliation & Full Rejection | HIGH (P1) | **REAL COMPONENT BEHAVIOR VERIFIED** | `control_surface/src/providers/SimulationProvider.ts` | SC-04.1–SC-04.2 & SC-05.1: Unknown intents rejected; rejected commands preserve state |
| **GUI-HPL-019** | Audit-Event Persistence Labeling Integrity | MEDIUM (P1) | **REAL COMPONENT BEHAVIOR VERIFIED** | `control_surface/src/components/FooterLog.tsx` | SC-06.1: In-memory events labeled SESSION/SIMULATED; no false persistence claims |
| **GUI-HPL-020** | PositionsTable Sorting & Active View Retention | MEDIUM (P1) | **REAL COMPONENT BEHAVIOR VERIFIED (JSDOM)** | `control_surface/src/components/PositionsTable.tsx` | SORT-01–SORT-06: Interactive sort by PnL, Symbol, Size with scrollIntoView tracking |
| **GUI-HPL-021** | Disconnected Telemetry Refresh & Reconnection Authority (FF-D-01 / D.2.1 / D.2.2) | HIGH (P1) | **FAIL-CLOSED VERIFIED (AUTHENTICATED RECONNECTION UNVERIFIED)** | `control_surface/src/utils/telemetry.ts` | SC-01.7, SC-01.8, SC-01.14, SC-01.15, SC-01.21, SC-01.22: Disconnected freeze; caller booleans, tokens, and callbacks rejected as untrusted bypasses; reconnection fails closed under RECONNECT_AUTHORITY_BOUNDARY |
| **GUI-HPL-022** | Unauthorized Source Migration Fail-Closed (FF-D-02 / D2-A / D.2.1) | HIGH (P1) | **REAL COMPONENT BEHAVIOR VERIFIED** | `control_surface/src/utils/telemetry.ts` | SC-01.11, SC-01.14: Caller-controlled migration/reconnect flags rejected fail-closed; RECONNECT_AUTHORITY_BOUNDARY and MIGRATION_AUTHORITY_BOUNDARY declared |
| **GUI-HPL-023** | Non-Authoritative Client Idempotency Scoping (FF-D-03) | HIGH (P1) | **CLIENT-SIDE VERIFIED (BACKEND UNRESOLVED)** | `control_surface/src/utils/idempotency.ts` | SC-02.6: `IDEMPOTENCY_AUTHORITY_BOUNDARY` explicitly documents ephemeral scope; durable store unresolved |
| **GUI-HPL-024** | Protected Trading State Rejection Immutability (FF-D-04) | CRITICAL (P0) | **REAL COMPONENT BEHAVIOR VERIFIED** | `control_surface/src/providers/SimulationProvider.ts` | SC-05.3: Bit-for-bit snapshot equality of positions, orders, candidates on rejection |
| **GUI-HPL-025** | Reproducible GUI CI with Least Privilege (FF-D-05) | HIGH (P1) | **CI PASSED (ACTIVATED)** | `.github/workflows/gui-ci.yml` | permissions: contents: read; npm ci; npm run lint; npm test; npm run build |
| **GUI-HPL-026** | Behavioral Responsive Viewport Layout & Reachability (FF-D-06 / D2-C) | MEDIUM (P2) | **BEHAVIORAL VIEWPORT VERIFIED (JSDOM)** | `control_surface/src/tests/responsive_structural.test.ts` | Real React `<App />` tested across 7 viewports (320, 360, 390, 430, 768, 1024, 1280px); all 8 destinations reachable |
| **GUI-HPL-027** | PositionsTable Multi-Column Sorting & Active Row Focus Retention (FF-D-07 / D2-C) | MEDIUM (P1) | **REAL COMPONENT BEHAVIOR VERIFIED (JSDOM)** | `control_surface/src/tests/positions_table_sort.test.ts` | SORT-01–SORT-06: Real React `<PositionsTable />` rendered in JSDOM; PnL, Symbol, Size, Closed tabs tested |
| **GUI-HPL-028** | Modal Accessibility, Focus Trap & Trigger Focus Restoration (FF-D-08 / D2-B) | HIGH (P1) | **REAL COMPONENT ACCESSIBILITY BEHAVIOR VERIFIED (JSDOM)** | `control_surface/src/components/FooterLog.tsx`, `MobileBottomNav.tsx` | D2-B.01–D2-B.09: Production components tested with native DOM events; Tab wrap, Shift+Tab wrap, Escape, backdrop click |
| **GUI-HPL-029** | Operational Risk Configuration Validation & Fail-Closed Boundary (EXP-01) | HIGH (P1) | **REAL COMPONENT BEHAVIOR VERIFIED** | `src/components/SettingsModal.tsx` | EXP-01.1 & EXP-01.2: Cross-field validation (Lane Risk <= Account Exposure); non-positive and NaN rejection; simulation-scoped writes |
| **GUI-HPL-030** | 5-Class Notification Taxonomy & Non-Resolving Acknowledgement (EXP-02) | HIGH (P1) | **REAL COMPONENT BEHAVIOR VERIFIED** | `src/components/CriticalBanner.tsx`, `NotificationDrawer.tsx` | EXP-02.1 & EXP-02.2: Safety-critical locked ON; operator ack records timestamp without resolving system condition |
| **GUI-HPL-031** | Quant Model Advisory Intent Restriction (Strictly NO CREATE) (EXP-03) | CRITICAL (P0) | **REAL COMPONENT BEHAVIOR VERIFIED** | `src/components/SecondaryViews.tsx` (QUANT) | EXP-03.1 & EXP-03.2: Model intents restricted strictly to VETO, REDUCE, NONE; order creation prohibited; risk gates remain sovereign |
| **GUI-HPL-032** | Lab & Backtesting Read-Only Integrity & Statistical Robustness (EXP-04) | MEDIUM (P2) | **REAL COMPONENT BEHAVIOR VERIFIED** | `src/components/SecondaryViews.tsx` (LAB) | EXP-04.1: Read-only execution barrier; null-world shuffle check, planted-edge recovery, OOS degradation <= 20% |
| **GUI-HPL-033** | Remediation Blockers & Cryptographic Audit Trail Verification (EXP-05) | HIGH (P1) | **REAL COMPONENT BEHAVIOR VERIFIED** | `src/components/SecondaryViews.tsx` (OPS & AUDIT) | EXP-05.1 & EXP-05.2: Blocker evidence retention; audit trail entries carry correlation ID and 64-char SHA-256 digest |

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
- **Disposition:** REAL COMPONENT BEHAVIOR VERIFIED.

### GUI-HPL-003: Telemetry Provenance, Atomicity, Initial Validation & Freshness (D2.3-F01)
- **Threat Scenario:** Partial state mutations on malformed epochs, invalid thresholds, or malformed initial inputs leave telemetry corrupted in `DEGRADED` status while updating freshness timestamps; initial state creation fabricates synthetic `SIM_ENGINE` provenance, epoch 1, or unearned `HEALTHY` status; missing `sourceEventTimeMs` is implicitly fabricated from `freshnessTimestamp`; or empty/whitespace-only/null source strings are misclassified as `UNRECOGNIZED_SOURCE` rather than `MISSING_SOURCE` (Defect D2.3-F01).
- **Original Evidence (D2.3-F01):** At baseline `44d6a43`, `evaluateInitialTelemetry` checked `if (incoming.source === undefined)` for `MISSING_SOURCE` and fell through to `!VALID_SOURCES.has(incoming.source)` for all other values, returning `UNRECOGNIZED_SOURCE` for `""`, `"   "`, and `null`.
- **Root Cause:** Absence check failed to detect empty strings, whitespace-only strings, or runtime `null`.
- **Required Invariant:** All telemetry state transitions must execute under all-or-nothing atomicity. If an update is invalid, the existing accepted snapshot must be preserved 100% bit-for-bit without field pollution. Initial telemetry evaluation (`evaluateInitialTelemetry` / `createInitialTelemetry`) must validate source: `undefined`, `null`, `""`, and whitespace-only evaluate to `MISSING_SOURCE`; non-empty unlisted strings and malformed runtime values evaluate to `UNRECOGNIZED_SOURCE` without silent whitespace trimming or coercion; diagnostic precedence is strictly enforced (`MISSING_SOURCE` > `UNRECOGNIZED_SOURCE` > `MISSING_EPOCH` > `MALFORMED_EPOCH` > `MISSING_TIMESTAMP` > `INVALID_TIMESTAMP` > `INVALID_STALE_THRESHOLD` > `INVALID_STATUS` > `INVALID_SOURCE_EVENT_TIME`); invalid inputs fail safely to `DOCUMENTED_UNKNOWN_TELEMETRY` rather than fabricating healthy state; stale threshold defaults to 5000ms strictly when undefined; unstated status defaults safely to `UNKNOWN`; and `sourceEventTimeMs` remains strictly `undefined` when absent (no synthetic timestamp substitution occurs; an explicitly supplied zero timestamp is accepted and preserved as a valid non-negative event timestamp).
- **Mitigation:** Refactored `evaluateInitialTelemetry` in `control_surface/src/utils/telemetry.ts` with explicit string type and whitespace trimming check (`rawSource === undefined || rawSource === null || (typeof rawSource === 'string' && rawSource.trim() === '')` -> `MISSING_SOURCE`), exact allowlist validation without trimming, and comprehensive diagnostic precedence.
- **Test Evidence:** `safety_invariants.test.ts` SC-01.1 through SC-01.27 (49 safety invariants).
- **Residual Risk:** Live authenticated reconnection, server-side RBAC, and distributed durable idempotency remain unresolved backend dependencies and fail closed.
- **Disposition:** REAL COMPONENT BEHAVIOR VERIFIED.

### GUI-HPL-004: Missing Active GUI CI Workflow
- **Threat Scenario:** Control Surface regressions pass undetected into git history because GUI CI only existed as an inactive template file.
- **Required Invariant:** Active CI workflow in `.github/workflows/gui-ci.yml` triggered on `control_surface/**` paths, running under least-privilege `permissions: contents: read`, using `npm ci` with lockfile caching, and executing lint, tests, and build.
- **Mitigation:** Created `.github/workflows/gui-ci.yml` and synchronized `control_surface/ci/gui-ci.yml.template`.
- **Test Evidence:** Local execution of `npm ci`, `npm run lint`, `npm test`, and `npm run build` succeeds with exit code 0.
- **Disposition:** CI PASSED (ACTIVATED).

### GUI-HPL-005: Server Authentication & RBAC Unimplemented
- **Threat Scenario:** Unauthenticated or unauthorized actors dispatch trading commands over the wire.
- **Required Invariant:** In the absence of server authentication and RBAC, live command execution must fail closed unconditionally.
- **Mitigation:** Frontend live gate remains strictly closed; zero network requests are dispatched to broker endpoints.
- **Disposition:** BLOCKED (UNRESOLVED BACKEND DEPENDENCY).

### GUI-HPL-006 & GUI-HPL-023: Intent Identity, Payload Fingerprinting & Client Idempotency Boundary
- **Threat Scenario:** Operator assumes client-side in-memory idempotency cache provides durable cluster-wide deduplication across restarts.
- **Required Invariant:** Client-side idempotency must be formally documented as ephemeral and non-authoritative (`IDEMPOTENCY_AUTHORITY_BOUNDARY = 'CLIENT_EPHEMERAL_NON_AUTHORITATIVE'`). Durable deduplication must be explicitly documented as an unresolved external backend dependency.
- **Mitigation:** Exported `IDEMPOTENCY_AUTHORITY_BOUNDARY` constant in `idempotency.ts` declaring `CLIENT_GUI_SESSION` and `backendDependency: UNRESOLVED_CONTROL_SERVICE_STORE`.
- **Test Evidence:** `safety_invariants.test.ts` SC-02.1 through SC-02.6.
- **Disposition:** CLIENT-SIDE VERIFIED (AUTHORITATIVE BACKEND STORE UNRESOLVED).

### GUI-HPL-021: Disconnected-State Telemetry Timestamp Refresh & Reconnect Authority (FF-D-01 / D.2.1 / D.2.2)
- **Threat Scenario:** When external broker feed is in DISCONNECTED state, incoming messages artificially refresh timestamps, or callers attempt to manufacture reconnection authority using caller-controlled booleans (`reconnectAuthorized: true`), caller-constructed proof objects, or callbacks returning `true`.
- **Required Invariant:** In DISCONNECTED state, `freshnessTimestamp` must remain strictly frozen. Caller-controlled booleans, tokens, and callbacks are NOT proof of Control Service authentication and must be strictly rejected. In the absence of genuine authenticated Control Service infrastructure, reconnection from DISCONNECTED must fail closed unconditionally, preserving the accepted snapshot 100% bit-for-bit. Active bridge allowlist (`VALID_ACTIVE_BRIDGE_STATUSES`) must reject `'UNKNOWN'` and `'DISCONNECTED'`.
- **Mitigation:** Refactored `updateTelemetryState` and `tryUpdateTelemetryState` in `control_surface/src/utils/telemetry.ts`: eliminated caller authorization bypasses, enforced `RECONNECT_AUTHORITY_BOUNDARY = { isSupported: false, status: 'BLOCKED — TRUSTED CONTROL SERVICE AUTHORITY NOT INTEGRATED', callerAuthorityAccepted: false }`, and guaranteed exact bit-for-bit snapshot preservation on all rejected reconnection attempts.
- **Test Evidence:** `safety_invariants.test.ts` SC-01.7, SC-01.8, SC-01.14, SC-01.15, SC-01.20, SC-01.21, SC-01.22.
- **Disposition:** FAIL-CLOSED VERIFIED (AUTHENTICATED RECONNECTION UNVERIFIED / BLOCKED — BACKEND AUTHORITY NOT INTEGRATED).

### GUI-HPL-022: Unauthorized Source Migration Fail-Closed Protection (FF-D-02 / D2-A)
- **Threat Scenario:** Callers or telemetry payloads bypass source identity checks via a boolean flag (`allowSourceMigration: true`), migrating the active source identifier without proof of authorization.
- **Required Invariant:** Cross-source migration must be rejected fail-closed. Caller-controlled boolean flags must not authorize migration.
- **Mitigation:** Removed caller-controlled `allowSourceMigration: true` bypass in `control_surface/src/utils/telemetry.ts`. Documented `MIGRATION_AUTHORITY_BOUNDARY = 'UNRESOLVED_CONTROL_SERVICE_AUTHORITY'`.
- **Test Evidence:** `safety_invariants.test.ts` SC-01.11 (unauthorized migration rejected fail-closed in both directions, forged flags rejected).
- **Disposition:** REAL COMPONENT BEHAVIOR VERIFIED.

### GUI-HPL-024: Bit-for-Bit Protected Trading State Immutability on Rejection (FF-D-04)
- **Threat Scenario:** A command rejected by risk constraints, invalid parameters, or nonexistent positions partially mutates sandbox state, leaving phantom or corrupt position records.
- **Required Invariant:** Upon command rejection, protected trading state (`positions`, `pendingOrders`, `candidates`, `closedTrades`) must remain 100% bit-for-bit immutable.
- **Mitigation:** Added `getProtectedTradingStateSnapshot()` to `SimulationProvider.ts` and guaranteed zero state mutation on constraint failure or missing target position.
- **Test Evidence:** `safety_invariants.test.ts` SC-05.3: deep snapshot equality confirmed before and after command rejections.
- **Disposition:** REAL COMPONENT BEHAVIOR VERIFIED.

### GUI-HPL-026: Responsive Viewport Layout, Document Overflow & Destination Reachability (FF-D-06 / D2-C)
- **Threat Scenario:** Narrow mobile viewports (320px–430px) experience document overflow blowouts, touch targets below 44px, or clipped critical statuses; secondary destinations unreachable.
- **Required Invariant:** Strict viewport container containment (`w-full max-w-full overflow-hidden`), dual-deck mobile header, dedicated table scroll container, 44px+ touch targets, bottom padding clearance (`pb-14`/`pb-16`) for docked navigation, and complete reachability of all 8 navigation destinations (`POS`, `DEC`, `RISK`, `MODE`, `NEWS`, `CALIB`, `HEALTH`, `STATS`).
- **Mitigation:** Responsive layout architecture in `App.tsx`, `Header.tsx`, `PositionsTable.tsx`, and `MobileBottomNav.tsx`. Tested with real rendered React `<App />` component mounting in JSDOM across 7 viewports: 320px, 360px, 390px, 430px, 768px, 1024px, 1280px.
- **Test Evidence:** `responsive_structural.test.ts` UX-01 through UX-08, VIEWPORT-320px through VIEWPORT-1280px, NAV-01, NAV-02, TOUCH-01 (20 passing tests).
- **Disposition:** BEHAVIORAL VIEWPORT VERIFIED (JSDOM).

### GUI-HPL-027: PositionsTable Multi-Column Sorting & Active Row Focus Retention (FF-D-07 / D2-C)
- **Threat Scenario:** Operator sorting by PnL, Symbol, or Size causes the active monitored position to jump off-screen during high-volatility events.
- **Required Invariant:** Multi-column sorting across open, pending, and closed positions with directional icons (`▲`/`▼`), distinct active header highlights, `aria-sort` screen reader contracts, deterministic tie-breaking, and automatic `selectedRowRef.scrollIntoView` tracking.
- **Mitigation:** Implemented sort reducer and row-tracking effects in `PositionsTable.tsx`. Tested real rendered React `<PositionsTable />` in JSDOM.
- **Test Evidence:** `positions_table_sort.test.ts` SORT-01 through SORT-06 (6 real component behavioral tests passing).
- **Disposition:** REAL COMPONENT BEHAVIOR VERIFIED (JSDOM).

### GUI-HPL-028: Modal Accessibility, Focus Trap & Trigger Focus Restoration (FF-D-08 / D2-B)
- **Threat Scenario:** Mobile sheets trap keyboard focus permanently or dump focus to document root upon close, violating WCAG 2.2 accessibility standards and disorienting keyboard operators.
- **Required Invariant:** Modals must implement `role="dialog"`, `aria-modal="true"`, focus trap cycling (Tab wraps to first element, Shift+Tab wraps to last element), Escape key dismissal, outside click dismissal, and explicit focus restoration to the invoking trigger element.
- **Mitigation:** Implemented focus trap event handlers, outside click listeners, and trigger focus return refs in `FooterLog.tsx` and `MobileBottomNav.tsx`. Tested actual production components rendered in JSDOM with real DOM KeyboardEvent and MouseEvent dispatching.
- **Test Evidence:** `modal_focus_behavior.test.ts` D2-B.01 through D2-B.09 (9 real component accessibility tests passing).
- **Disposition:** REAL COMPONENT ACCESSIBILITY BEHAVIOR VERIFIED (JSDOM).
