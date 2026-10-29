# FRACTAL-FLOW — GUI Expansion Design Specification

**Mission:** Unified GUI Expansion, Branch Reconciliation, Implementation, and Forensic Hardening
**Document:** `GUI_EXPANSION_DESIGN_SPEC.md`
**Scope:** Extended Operator Control Surface Frontend Capabilities
**Governing Standard:** Universal Forensic Engineering Protocol
**Protocol Hierarchy:** SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY > SECURITY > RECOVERY > RECONCILIATION > OPERATIONAL ROBUSTNESS > SPEED > PnL OPTIMIZATION
**Date:** 2026-10-29T04:47:00Z
**Status:** `APPROVED SPECIFICATION & CONTRACT MATRIX`

---

## 1. Architectural Philosophy & Safety Boundaries

The GUI expansion strictly adheres to core system principles:
1. **One Backend (Control Service)**: The GUI is an observational and gated command client. It never acts as an independent execution authority.
2. **Fail-Closed Broker Execution**: Live broker execution remains hard-blocked via `LiveExecutionBlockedError`.
3. **Prototype Honesty**: When running against simulated providers, all fixtures and outcomes are explicitly labeled `SIMULATED` or `NON-AUTHORITATIVE`. Browser state is never masqueraded as durable server persistence.
4. **No LLM/Model Order Creation**: Quantitative and machine learning models are strictly advisory. Permitted model intents are limited to `VETO`, `REDUCE`, and `NONE`. `CREATE` is architecturally prohibited.
5. **Acknowledgement $\neq$ Resolution**: Acknowledging a critical notification records operator awareness but does not clear the underlying condition, bypass risk gates, or authorize execution.
6. **Lab is Strictly Read-Only**: The backtesting/lab view provides artifact inspection, robustness metrics, and null-world verification. It provides no run triggers or live model promotion buttons.

---

## 2. Capability Specifications

### 2.1 Settings & Operational Risk Configuration
- **Entry Point**: Header gear button (`[data-testid="settings-trigger"]`), opening an accessible modal dialog.
- **Section 1: Local Presentation Preferences (Local-Only)**:
  - Layout Density: `Compact` (24px table rows), `Default` (28px table rows), `Spacious` (32px table rows).
  - Audio Cues: Muted / Enabled.
  - Theme: High-density Obsidian `#0A0E14` (zero-gradient, 1px `#232A35` hairline borders).
  - Storage: Browser local storage (explicitly flagged `LOCAL-ONLY`).
- **Section 2: Operational Risk Configuration (Server-Authoritative)**:
  - Provenance Display: Active `effective_config_id` (`cfg_live_418_f89c02`), Configuration Version (`v4.1.8`), Source (`SIM_ENGINE` / `CONTROL_SERVICE`).
  - Fields: Max Lane Risk $R$ (e.g. `2.5R`), Max Account Open Exposure (e.g. `5.0R`), Daily Loss Limit Drawdown (`-$1,500.00`).
  - Validation: Cross-field invariant checking (Max Lane Risk $\le$ Max Account Exposure; strictly positive finite numbers; 4-decimal precision).
  - Concurrency & Mutation Guard: Requires explicit before/after diff preview, version matching, and confirmation dialog.
  - Fail-Closed Notice: When no live Control Service write adapter exists, modifications remain isolated to simulation state with an auditable warning banner.
- **Section 3: Calibration-Owned Parameters**:
  - Displays exit and trailing parameters tagged `READ-ONLY (CONTROLLED BY EVIDENCE-BACKED PROMOTION WORKFLOW)`.

### 2.2 Notifications & Persistent Critical Banner
- **5-Class Taxonomy**:
  1. `safety_critical`: Kill-switch, fence epoch breach, bridge drop, unexpected excursion. **Permanently active, cannot be muted**.
  2. `trade_lifecycle`: Order open, partial take-profit, breakeven, close.
  3. `risk_limit`: Lane risk capacity warning, account margin limit threshold.
  4. `calibration_rollout`: Stage progression, regime-confidence alerts.
  5. `informational_daily`: Daily settlement, clock drift check.
- **Critical Banner**:
  - Always rendered directly below the Header when an active safety-critical alert exists.
  - High-contrast crimson `#B23B3B` border, monospace alert ID, full error description.
  - Interactive `ACK` button which idempotently sets acknowledgement timestamp without clearing the underlying trigger.
- **Notification Drawer / Center**:
  - Header bell icon with unread count badge.
  - Tab filters by class, event timeline, stable event IDs, and simulated Telegram delivery statuses.

### 2.3 QUANT (Expanded CALIB) Subviews
- **Tab Identity**: Maintains `CALIB` identifier in navigation for test stability, titled `CALIB / QUANT` in the UI.
- **4 Dedicated Subviews**:
  1. **Parameters & Rollout**: Matrix of parameter keys, active stage (`SHADOW`, `PAPER`, `CANARY`, `ACTIVE`), traffic %, and last rollout evidence hash.
  2. **Model Registry**: Inventory of quantitative models with Model ID, Version, SHA-256 artifact digest, permitted intents (`VETO`, `REDUCE`, `NONE`), lane eligibility, and health status.
  3. **Model Advice & Telemetry**: Live stream of model evaluation records with prediction confidence, rationale, and gate arbitration disposition (`ACCEPTED_AS_ADVICE`, `VETO_OVERRIDDEN_BY_RISK_GATE`).
  4. **Promotion History**: Linear audit trail of stage promotions with evidence checksums and operator approvals.

### 2.4 Lab & Backtesting Analytical Viewer
- **Access**: Header `LAB` quick-action and navigation drawer.
- **Analytical Dimensions**:
  - Multi-run comparison: Baseline vs Candidate.
  - Fidelity levels: `F0` (Tick level), `F1` (Bar level), `F2` (Synthetic Monte Carlo), `F3` (Fast vectorized); `Lab-0` to `Lab-3`.
  - Statistical Robustness: Null-world shuffle verification, planted-edge recovery, OOS degradation %, and parameter perturbation sensitivity.
  - Guardrail: Fully read-only, no execution or deployment actions.

### 2.5 Blockers / Ops (Remediation Register)
- **Data Source**: Derived directly from `remediation_register.yaml` / HPL defect ledger.
- **Attributes**: Blocker ID, Category, Severity (`P0`, `P1`, `P2`), Resolution Status, Owner, Evidence Artifact.

### 2.6 Audit Trail Viewer
- **Attributes**: Event ID, Timestamp (UTC), Actor, Action, Target, Outcome, Correlation ID, SHA-256 Intent Digest.
- **Integrity**: Read-only, session-local non-authoritative representation with canonical JSON SHA-256 digest.

---

## 3. Shared Frontend Contracts & Authority Boundaries

### 3.1 Field-Level Source-of-Truth Contracts
| Field / Metric | Units / Type | Source & Provenance | Authority Level | Freshness Semantics | Missing / Malformed Behavior | Mutation Supported? |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **Open Risk ($R$)** | Floating-point $R$ scaled to $10^6$ micro-R | Positions aggregate via `evaluatePortfolioRisk` | Authoritative over client view | Updated on every position mutation / tick | Fails closed to `null`; Header renders `INVALID` | Yes (via order de-risking) |
| **Daily P&L** | USD currency formatted to 2 decimals | `SessionDailyPnL` from portfolio ledger | Non-authoritative client display | Updated on position exit / tick | Fallback to `$0.00` with warning | No (derived metric) |
| **Account Equity** | USD currency | `AccountState` from simulation engine | Simulated account balance | Updated on session tick | Retains last known with `STALE` badge | No (derived metric) |
| **Timeframe Cascade** | 6 tiers (`4H` to `1M`) | Active position setup anchor | Observed structural analysis | Static per open position | Displays default inactive tiers | No (read-only structural) |
| **Gate Strip Status** | 11 gates (**Q E R P L O T N K A X**) | Pre-flight candidate evaluation | Non-authoritative candidate analysis | Evaluated on candidate arrival | Shows `FAILED` with explicit reason | No (pipeline evaluation) |
| **Operational Risk Draft** | Risk limits ($R$, USD) | Modal draft state | Draft (client memory) | Live during editing | Rejection blocks save; preserves active config | Yes (subject to confirmation) |
| **QUANT Model Advice** | Intent (`VETO`, `REDUCE`, `NONE`) | Model inference stream | Advisory only (strictly NO CREATE) | Real-time candidate feed | Ignored if malformed; fails closed to `NONE` | No (read-only advisory) |
| **Audit Trail Log** | Append-only event list | Local session dispatcher | Session-only non-durable | Immediate on action | Renders sanitized text; no HTML injection | Append-only |

### 3.2 Action-Level Contracts & Failure Boundaries
| Action Intent | Preconditions | UI Confirmation | Provider Boundary | Failure Mode & Recovery |
| :--- | :--- | :---: | :--- | :--- |
| **Close Position** | Position exists in state | Yes (`ConfirmDialog`) | `SimulationProvider.submitCommand` | If provider fails, position remains open; error logged |
| **Tighten Stop** | Stop distance $\ge 0.5\sigma$ | Yes (`ConfirmDialog`) | `SimulationProvider.submitCommand` | If rejected, stop level unchanged; audit event recorded |
| **Move to Breakeven** | Current profit $> 1.0R$ | Yes (`ConfirmDialog`) | `SimulationProvider.submitCommand` | If rejected, breakeven flag false; audit event recorded |
| **Add Size (Scale In)** | Portfolio risk valid; projected risk $\le$ caps | Yes (`ConfirmDialog`) | `SimulationProvider.submitCommand` | If projected risk $>$ cap, action BLOCKED fail-closed |
| **Live Order Dispatch** | None (blocked) | N/A (hard-blocked) | `LiveCommandAdapter.submitCommand` | Throws `LiveExecutionBlockedError` unconditionally |
| **Update Risk Draft** | Valid inputs; Lane $\le$ Account | Yes (diff preview + confirm) | Simulation config state | Rejection preserves previous config bit-for-bit |

---

## 4. Design System & Accessibility Compliance

- **Visuals**: Flat `#0A0E14` dark surface, `#10151D` panel background, `#232A35` 1px borders, `IBM Plex Sans` for labels, `IBM Plex Mono` tabular numerals for numbers/hashes.
- **WCAG 2.2**: Minimum 44px touch targets on mobile (`min-h-[44px]`), Tab/Shift+Tab focus wrapping in all dialogs, Escape key dismissal with focus restoration to invoking trigger, high-contrast text (`#E7EAEE` on `#10151D`).
