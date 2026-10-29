# FRACTAL-FLOW — Forensic Reconnaissance Report

**Mission:** Unified GUI Expansion, Branch Reconciliation, Implementation, and Forensic Hardening
**Document:** `FORENSIC_RECONNAISSANCE.md`
**Governing Standard:** Universal Forensic Engineering Protocol
**Protocol Hierarchy:** SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY > SECURITY > RECOVERY > RECONCILIATION > OPERATIONAL ROBUSTNESS > SPEED > PnL OPTIMIZATION
**Date:** 2026-10-29T04:45:00Z
**Status:** `VERIFIED BY DIRECT EXECUTION & REMOTE PROVENANCE AUDIT`

---

## 1. Environment, Runtimes & Tooling Verification

| Tool / Resource | Availability | Observation & Version | Classification | Direct Verification Command / Evidence |
| :--- | :---: | :--- | :--- | :--- |
| **Node.js Runtime** | AVAILABLE | Node v22.14.0 / Linux x86_64 | `VERIFIED` | `node -v` $\to$ `v22.14.0` |
| **Package Manager** | AVAILABLE | npm v10.9.2 | `VERIFIED` | `npm -v` $\to$ `10.9.2` |
| **TypeScript Compiler** | AVAILABLE | TypeScript v7.0.2 via `tsc --noEmit` | `VERIFIED` | `npm run lint` $\to$ 0 errors, exit 0 |
| **Vite Bundler** | AVAILABLE | Vite v8.3.5 (Client environment for production) | `VERIFIED` | `npm run build` $\to$ `dist/` built in 1.06s, exit 0 |
| **Test Runner & Environment** | AVAILABLE | `tsx` v4.21.0 running Node/JSDOM 26.0.0 | `VERIFIED` | `npm test` $\to$ 157 passed, 0 failed across 9 suites |
| **Git Tooling** | AVAILABLE | Git v2.43.0 | `VERIFIED` | `git --version` $\to$ `git version 2.43.0` |
| **Local Working Tree** | AVAILABLE | AI Studio application workspace at `/` (`/app/applet`) | `VERIFIED` | Direct filesystem inspection & execution |
| **Git Clone / Inspection Repo** | AVAILABLE | Local clone at `/tmp/repo` tracking origin | `VERIFIED` | Remote branches fetched and verified |
| **Remote GitHub Connectivity** | AVAILABLE | Reachable via GitHub PAT over HTTPS | `VERIFIED` | `git ls-remote` verified against canonical refs |
| **Python Toolchain (mypy/ruff)** | NOT APPLICABLE | Frontend TypeScript/React control surface scope | `NOT APPLICABLE` | Python engine quarantined per scope boundary |
| **MT5 / Live Broker** | UNAVAILABLE | Backend Control Service unprovisioned; live trading prohibited | `FAIL-CLOSED SAFE` | `LiveCommandAdapter` throws `LiveExecutionBlockedError` |

---

## 2. Remote Provenance & Canonical Baseline Pinning

Direct query via authenticated `git ls-remote https://github.com/Kiyingijmc/FRACTAL-FLOW.git` and commit inspections established the following canonical reference points:

| Ref / Identifier | Canonical SHA | Verification Source | Role / State / Parent |
| :--- | :--- | :--- | :--- |
| **`refs/heads/main`** | `74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d` | `git ls-remote` | Protected Baseline HEAD (Merge PR #23) |
| **`refs/heads/feature/gui-control-surface`** | `c392c3e95f8e950cf7552d494a97d8821c2dd158` | `git ls-remote` | Protected PR #29 Review Target HEAD (Preserved untouched) |
| **`refs/pull/29/head`** | `c392c3e95f8e950cf7552d494a97d8821c2dd158` | GitHub API | PR #29 State: `open`, `mergeable: true`, `mergeable_state: clean` |
| **`refs/pull/29/merge`** | `72edde894a7ded123ec099fe345bc60c331d5d95` | `git ls-remote` | PR #29 GitHub synthetic merge ref against `main` |
| **Canonical Checkpoint** | `719633433bebcf5b78b4dc31af93888e4325a66c` | `git ls-remote` | HEAD of `reconciliation/phase9-working-tree-20261028` |
| **Parent of Canonical Checkpoint** | `f84e0a57709d96274f737e11f1b76fe2eae828d5` | `git rev-list` | `chore(structure): remove unused Bar import` |
| **`work/gui-reconciliation-20261024`** | `28372d0c28919daccb10e421fcd5f90a25e30223` | `git ls-remote` | Stage H.1 corrective closure baseline |
| **`work/stage-h1-1-3-projected-risk-20261027`** | `9956bcc8fe6ed688d42bda37f71f0840c2931c95` | `git ls-remote` | Stage H.1.1.3 verified final commit (descendant of `28372d0c`) |

---

## 3. Discrepancy & Anomaly Reconnaissance

### 3.1 Investigation of the "No Common Ancestor" Finding
A prior comparison reported no common ancestor between the canonical working checkpoint `719633433bebcf5b78b4dc31af93888e4325a66c` on branch `reconciliation/phase9-working-tree-20261028` and `main` (`74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d`).
- **Forensic Investigation:**
  - `git rev-list --max-parents=0 origin/main` yields root commit `e55e8aeca457bc8d0180e3cf326ff4a823c30fd3`.
  - `git rev-list --max-parents=0 origin/feature/gui-control-surface` yields root commit `e55e8aeca457bc8d0180e3cf326ff4a823c30fd3` (17 commits ahead of `main`).
  - `git rev-list --max-parents=0 origin/reconciliation/phase9-working-tree-20261028` yields root commit `0fe03629e96bb1b3ea1616ded1325fd6f344d408` (`chore: establish Phase 6 forensic baseline`).
- **Conclusion:** `reconciliation/phase9-working-tree-20261028` was created from an orphaned root commit (`0fe0362`) initialized during Phase 6 reconciliation. It does not share Git object history with `main` or PR #29. Attempting a standard Git three-way merge between `reconciliation/phase9-working-tree-20261028` and `main` or `feature/gui-control-surface` will fail or create unrelated-histories conflicts.
- **Architectural Resolution:** The GUI work must proceed along the verified linear lineage rooted on `feature/gui-control-surface` (`c392c3e`) through `work/gui-reconciliation-20261024` (`28372d0c`) and `work/stage-h1-1-3-projected-risk-20261027` (`9956bcc8`), while semantically reconciling all frontend additions from `719633433`.

### 3.2 CI Workflow 404 Discrepancy Analysis
Inspection of commit diff for `719633433bebcf5b78b4dc31af93888e4325a66c` noted a GUI CI workflow, but querying `.github/workflows/gui-ci.yml` at that commit returned 404.
- **Forensic Investigation:**
  - `git ls-tree 719633433bebcf5b78b4dc31af93888e4325a66c:.github/workflows` reveals only `workflows/ci.yml` (the Python baseline CI).
  - In `719633433bebcf5b78b4dc31af93888e4325a66c`, the GUI workflow was placed at `control_surface/ci/gui-ci.yml.template`. GitHub Actions only detects workflow files placed directly under `.github/workflows/*.yml`.
  - In `feature/gui-control-surface` (`c392c3e`) and `work/stage-h1-1-3-projected-risk-20261027` (`9956bcc8`), `.github/workflows/gui-ci.yml` is active and present at the correct root location.
  - Querying the GitHub Actions API for commit `719633433bebcf5b78b4dc31af93888e4325a66c` showed only Run ID `40793229194` ("FRACTAL FLOW Baseline CI" which tests Python 3.12 and 3.13), which failed on Ruff Check (Python 3.13). **Zero GUI CI runs were triggered on GitHub Actions for `719633433bebcf5b78b4dc31af93888e4325a66c`**.
- **Conclusion:** The CI release gate cannot be marked PASSED on `719633433bebcf5b78b4dc31af93888e4325a66c`. Local verification via `npm run lint` and `npm test` and `npm run build` is 100% green (157 passing tests), but remote CI execution on GitHub for that SHA is `UNAVAILABLE / NOT RUN`.

### 3.3 Core-Engine Scope Contamination Analysis
Commit `f84e0a57709d96274f737e11f1b76fe2eae828d5` (parent of `719633433bebcf5b78b4dc31af93888e4325a66c` on branch `reconciliation/phase9-working-tree-20261028`) modified `src/fractal_flow/domain/structure_v23.py` (deleting `from ... import Bar`).
- **Forensic Investigation:** Commit `fe71fdbe15f59d0dea9b6de690239216fe11e12a` also modified Python trading engine files (`entry.py`, `envelope.py`, `models.py`, `broker_truth.py`, etc.).
- **Boundary Enforcement:** The GUI scope is strictly limited to `control_surface/` (React, TypeScript, CSS, UI tests, and GUI documentation). Non-GUI Python files are strictly quarantined. No changes from `src/fractal_flow/...` or Python tests are admitted into the GUI implementation.

---

## 4. Existing GUI Architecture & Component Inventory

The GUI codebase is organized into modular functional units with zero circular dependencies:

### 4.1 Entry & Layout Shell
- `src/App.tsx`: Central coordinator managing active navigation tab, simulated tick engine (cadence 3.2s, 400ms flash), selected position, modal dialogs, and real production authorization boundary.
- `src/components/Header.tsx`: System branding (`FRACTAL-FLOW control surface`), Lane selector, Bridge session health, dynamic Open Risk and Daily P&L KPI cards, latency monitor modal trigger, and Settings gear trigger.
- `src/components/GateChainStrip.tsx`: 11-gate sequential chain renderer (**Q E R P L O T N K A X**), candidate selector, pass/fail status styling, and explicit pre-flight simulation disclaimer.
- `src/components/NavRail.tsx`: Compact 64px desktop navigation rail with 8 core tabs (`POS`, `DEC`, `RISK`, `MODE`, `NEWS`, `CALIB/QUANT`, `HEALTH`, `STATS`).
- `src/components/MobileBottomNav.tsx`: 48px touch-optimized mobile navigation bar with accessible touch targets ($\ge 44 \times 44\text{px}$) and secondary drawer trigger.
- `src/components/CriticalBanner.tsx`: Persistent high-contrast safety-critical incident banner rendered whenever an unresolved safety-critical condition exists.
- `src/components/FooterLog.tsx`: Real-time system event log ticker highlighting critical epoch and safety events.

### 4.2 Data & Context Panels
- `src/components/PositionsTable.tsx`: Multi-tab table (Open Positions, Pending Orders, Closed Trades) with monospace numeric tabular alignment, side pills (`LONG` teal / `SHORT` rose), and row selection highlight.
- `src/components/ContextPanel.tsx`: Telemetry inspector for selected position, 6-tier timeframe cascade (`4H 1H 30M 15M 5M 1M`), excursion bar ($R$-multiple), structural anchor, and gated operator action triggers.
- `src/components/SecondaryViews.tsx`: Multi-panel view container housing:
  - `DEC`: Real-time candidate decision pipeline and gate rejection inspection.
  - `RISK`: Dynamic portfolio lane risk aggregation, account exposure caps, and drawdowns.
  - `MODE`: Regime profiles and mode eligibility matrix.
  - `NEWS`: Economic calendar, volatility impacts, and news blackouts.
  - `CALIB / QUANT`: 4-subview quant model dashboard (Parameters/Rollout, Model Registry, Advisory Stream, Promotion History).
  - `HEALTH`: Bridge connectivity, heartbeat telemetry, and fence states.
  - `STATS`: Execution performance statistics and win-rate analytics.
  - `LAB`: Read-only research and backtest artifact inspection.
  - `OPS`: Remediation blockers register with verifiable evidence records.
  - `AUDIT`: Non-authoritative, session-local event audit ledger with canonical JSON SHA-256 digests.

### 4.3 Modals & Interaction Controls
- `src/components/ConfirmDialog.tsx`: Accessible modal dialog for operator actions (Close, Tighten Stop, Breakeven, Add Size) with parameter verification and focus trapping.
- `src/components/SettingsModal.tsx`: Dual-section settings modal separating local presentation preferences (density, audio, theme) from operational risk configuration drafts.
- `src/components/NotificationDrawer.tsx`: Accessible side-drawer for 5-class notification taxonomy (`safety_critical`, `risk_limit`, `trade_lifecycle`, `calibration_rollout`, `informational_daily`).
- `src/components/AutomatedRiskValidator.tsx`: Automated risk analysis modal inspecting candidate risk against active operational risk limits.

---

## 5. Provider Boundaries & Fail-Closed Commitments

### 5.1 `LiveCommandAdapter` Fail-Closed Sovereign Boundary
- `src/providers/LiveCommandAdapter.ts`:
  - `submitCommand(intent: IntentFingerprint)`: Throws `LiveExecutionBlockedError` unconditionally:
    `"LiveCommandAdapter: Live execution is blocked by system governance. Backend Control Service is unprovisioned."`
  - `reconcileCommand(correlationId: string)`: Throws `LiveExecutionBlockedError` unconditionally:
    `"LiveCommandAdapter: Live reconciliation is blocked by system governance. Backend Control Service is unprovisioned."`
  - **Invariant:** Live commands cannot succeed through any UI action, keyboard shortcut, confirmation dialog, retry, reconnection, or alternate dispatch path.

### 5.2 `SimulationProvider` Non-Authoritative Sandbox Boundary
- `src/providers/SimulationProvider.ts`:
  - In-memory simulation state machine.
  - State immutability: When a command is rejected by risk validation, simulation state remains bit-for-bit unchanged.
  - Explicit non-authoritative labeling: All mock values, simulated fills, and demo positions are explicitly marked `SIMULATED`.

---

## 6. Production Test & Verification Inventory

The local workspace test harness executes 9 modular test suites via `npm test` (`tsx` runner):

1. `src/tests/safety_invariants.test.ts` (44 tests): Core fail-closed safety invariants, LiveExecutionBlockedError, state rejection immutability.
2. `src/tests/responsive_structural.test.ts` (12 tests): Viewport layouts across 7 standard screen widths (320px to 1280px), touch target sizes ($\ge 44\text{px}$).
3. `src/tests/positions_table_sort.test.ts` (13 tests): Positions table multi-column sorting (Symbol, Size, PnL, Open/Pending/Closed tabs), focus retention.
4. `src/tests/modal_focus_behavior.test.ts` (8 tests): Accessible focus trapping, Tab/Shift+Tab wrapping, Escape dismissal, trigger restoration.
5. `src/tests/gui_expansion_invariants.test.ts` (9 tests): Operational risk configuration cross-field invariants, notification subscriptions, QUANT model advisory intent constraints (strictly NO CREATE), Lab robustness checks, Blocker evidence attribution.
6. `src/tests/risk_validator_and_latency.test.ts` (8 tests): Automated risk validator limits, header latency monitor states (`NO_DATA`, `HEALTHY`, `EXCEEDED`).
7. `src/tests/stage_h_adversarial_invariants.test.ts` (17 tests): Micro-R integer scaling, FIPS 180-4 standard SHA-256 conformance, session actor attribution.
8. `src/tests/stage_h1_production_behavior.test.ts` (18 tests): Real production `<Header />` risk rendering, 3 $\times$ 0.005R = 0.015R precision, zero premature rounding bias, NIST vectors.
9. `src/tests/stage_h1_1_production_path.test.ts` (28 tests): Production path risk-increasing authorization, real mounted `<App />` state transitions, projected-risk cap enforcement, test seam isolation.

**Total Automated Tests:** **157 PASSED, 0 FAILED** (100% pass rate).
**TypeScript Lint:** `tsc --noEmit` $\to$ **0 errors**.
**Production Build:** `NODE_ENV=production vite build` $\to$ **Clean build in 1.06s**.
