# FRACTAL FLOW — PRE-IMPLEMENTATION ARCHITECTURE AUDIT REPORT
Version: 1.0
Status: Complete Architecture Audit
Scope: All 21 specification files (`AGENTS.md`, `CODEX_HANDOFF.md`, `README.md`, `docs/00_CONSTITUTION.md` through `docs/19_ADVERSARIAL_TESTING.md`, `docs/DECISION_LOG.md`)

---

## 1. Executive Summary & Audit Methodology

This audit was conducted as a pre-mortem architectural review of the FRACTAL FLOW specification before Phase 1 implementation. Every specification document was systematically cross-referenced against related specifications, the 42 non-negotiable architectural invariants in `AGENTS.md`, and the Authority Matrix in `docs/02_ENGINE_CONTRACTS.md §18`.

The audit identified:
- **6 Priority Known Issues** explicitly verified and reconciled.
- **8 Additional Cross-Document Contradictions & Gaps** across state machines, authority matrices, lineage chains, formulas, and orphan recovery pathways.
- **Operationalization Assessment of all 42 Invariants**, highlighting areas where invariant assertions lack complete concrete specification mechanisms.

No trading logic or implementation code was modified or added. Where ambiguities presented competing design trade-offs without explicit canonical resolution, they have been formally framed as `OPEN DECISION` entries per `CODEX_HANDOFF.md §2`.

---

## 2. Verification and Reconciliation of Known Priority Issues

### Issue 1: Three Incompatible State-Machine Vocabularies for Pullback/Resumption Lifecycle
* **Locations:**
  - `docs/02_ENGINE_CONTRACTS.md §5`
  - `docs/03_STATE_MACHINE.md §3`
  - `docs/06_PULLBACK_ENGINE.md §8`
* **Defect Description:**
  `docs/02_ENGINE_CONTRACTS.md §5` defines PDE states as: `NONE`, `IMPULSE`, `PULLBACK_CANDIDATE`, `PULLBACK_ACTIVE`, `WEAKENING`, `DEEPENING`, `STRUCTURAL_RECOVERY`, `RESUMPTION_CANDIDATE`, `RESUMPTION_CONFIRMED`, `FOLLOW_THROUGH`, `FAILED_RESUMPTION`, `INVALIDATED`.
  `docs/03_STATE_MACHINE.md §3` introduces `STRENGTHENING` and `FAILURE_RISK` which do not exist in Doc 02.
  `docs/06_PULLBACK_ENGINE.md §8` introduces a third divergent vocabulary for resumption: `RESUMPTION_NONE`, `RECOVERY_CANDIDATE`, `RECOVERY_CONFIRMED`, `DISPLACEMENT_CANDIDATE`, `RESUMPTION_CONFIRMED`, `FOLLOW_THROUGH`, `RESUMPTION_FAILED` (reversing `FAILED_RESUMPTION` naming).
* **Impact if Uncoded:**
  An implementation attempting to map PDE state transitions will fail type checks or misinterpret resumption events. For example, a downstream Opportunity Engine expecting `STRUCTURAL_RECOVERY` would ignore `RECOVERY_CONFIRMED`, blocking trade authorization.
* **Reconciled Resolution:**
  Establish a single canonical two-level state structure for the Pullback Detection Engine:
  1. Primary PDE State (`PDEState`):
     `PDE_NONE`, `PDE_IMPULSE`, `PDE_PULLBACK_CANDIDATE`, `PDE_PULLBACK_ACTIVE`, `PDE_WEAKENING`, `PDE_STRENGTHENING`, `PDE_DEEPENING`, `PDE_RESUMPTION_IN_PROGRESS`, `PDE_FOLLOW_THROUGH`, `PDE_RESUMPTION_FAILED`, `PDE_INVALIDATED`.
  2. Resumption Sub-State (`PDEResumptionState`):
     `RESUMPTION_NONE`, `RECOVERY_CANDIDATE`, `RECOVERY_CONFIRMED`, `DISPLACEMENT_CANDIDATE`, `RESUMPTION_CONFIRMED`.
  Naming convention standardized to `PDE_RESUMPTION_FAILED` across all contracts.

---

### Issue 2: Omission of MICRO Pullback Tier in Canonical Lineage Chain
* **Locations:**
  - `docs/00_CONSTITUTION.md §1, Lineage section`
  - `docs/06_PULLBACK_ENGINE.md §1`
  - `docs/14_RECONCILIATION.md §3`
* **Defect Description:**
  `docs/00_CONSTITUTION.md` defines the canonical lineage chain as:
  `ROOT → REGIME → SETUP → PRIMARY PULLBACK → SECONDARY PULLBACK → SIGNAL → ORDER → POSITION → TRADE → MANAGEMENT`
  However, `docs/06_PULLBACK_ENGINE.md §1` establishes a three-tier pullback hierarchy: `PRIMARY → SECONDARY → MICRO` (e.g. 15M Primary → 5M Secondary → 1M Micro). `docs/14_RECONCILIATION.md §3` also omits `MICRO PULLBACK` and `OPPORTUNITY`.
* **Impact if Uncoded:**
  Signals originating from M1 micro pullbacks will fail parent-child lineage verification (AGENTS.md Invariants #11, #12, #25, #27) because `MICRO PULLBACK` is not recognized in the root-to-leaf lineage validation schema.
* **Reconciled Resolution:**
  Update the canonical lineage definition across all docs to:
  `ROOT → REGIME → SETUP → PRIMARY_PULLBACK → [SECONDARY_PULLBACK →] [MICRO_PULLBACK →] OPPORTUNITY → SIGNAL → ORDER → POSITION → TRADE → MANAGEMENT`
  Optional tiers in brackets `[...]` are populated based on the setup's execution timeframe.

---

### Issue 3: Ambiguous Boolean Precedence in Pullback Candidate Rule
* **Locations:**
  - `docs/06_PULLBACK_ENGINE.md §4`
* **Defect Description:**
  The pullback candidate rule is specified as:
  `CounterMoveNorm > θ_counter AND CounterEfficiency > θ_efficiency OR CounterStructuralEvidence = TRUE`
  Without parentheses, boolean operator precedence is ambiguous.
* **Impact if Uncoded:**
  Two conflicting interpretations produce radically different trading behavior:
  - Interpretation A: `(CounterMoveNorm > θ_counter AND CounterEfficiency > θ_efficiency) OR CounterStructuralEvidence = TRUE`
    Allows strong structural evidence (e.g., a structural swing break) to qualify a pullback candidate even if normalized distance or efficiency fall below numerical thresholds.
  - Interpretation B: `CounterMoveNorm > θ_counter AND (CounterEfficiency > θ_efficiency OR CounterStructuralEvidence = TRUE)`
    Mandates a minimum normalized counter-move distance regardless of structural evidence.
* **Status: OPEN DECISION (D-032)**
  - *Option A Argument:* Consistent with AGENTS.md Invariant #35 ("Structural stops/evidence are primary"). If market structure explicitly confirms a counter-swing, rigid fixed thresholds should not block candidate identification.
  - *Option B Argument:* Prevents noisy micro-fluctuations from creating pullback objects before a minimal price displacement has occurred.
  - *Recommendation:* Option A with a baseline safety floor (`CounterMoveNorm > θ_min_floor`).

---

### Issue 4: Orphaned "Policy" Fields on Pullback Object
* **Locations:**
  - `docs/06_PULLBACK_ENGINE.md §2`
  - `docs/08_OPPORTUNITY_ENGINE.md §13`
  - `docs/15_POSITION_MANAGEMENT.md §6`
* **Defect Description:**
  `docs/06_PULLBACK_ENGINE.md §2` declares four policy fields on the pullback object:
  `primary_entry_allowed`, `micro_entry_allowed`, `reentry_allowed`, `runner_management_allowed`.
  These fields are never referenced, read, or evaluated by any downstream engine in `docs/08_OPPORTUNITY_ENGINE.md`, `docs/09_TRADEABILITY.md`, or `docs/15_POSITION_MANAGEMENT.md`.
* **Impact if Uncoded:**
  PDE computes state policies that downstream execution and position management layers ignore, creating dead fields and un-enforced policy intent.
* **Reconciled Resolution:**
  Formally integrate these fields into downstream validity gates:
  1. `docs/08_OPPORTUNITY_ENGINE.md §13` (Entry Authorization Gate) must check `Pullback.primary_entry_allowed == TRUE` (or `micro_entry_allowed` for micro setups).
  2. `docs/12_PORTFOLIO_ARBITRATION.md §8` (Smart Overtrading) must evaluate `Pullback.reentry_allowed == TRUE` before authorizing re-entry into an existing opportunity.
  3. `docs/15_POSITION_MANAGEMENT.md §6` (Runner Management) must verify `Pullback.runner_management_allowed == TRUE` before transitioning a position to `RUNNER` state.

---

### Issue 5: Layering Violation in EvidenceConfidence Formula
* **Locations:**
  - `docs/06_PULLBACK_ENGINE.md §14`
  - `AGENTS.md` Invariant #1
* **Defect Description:**
  `docs/06_PULLBACK_ENGINE.md §14` defines:
  `EvidenceConfidence = f(DataQuality, StructureConfidence, ImpulseConfidence, PullbackConfidence, WeakeningConfidence, ResumptionConfidence, ExecutionConfidence)`
  PDE resides in Layer 2 (State Engines). `ExecutionConfidence` belongs to Layer 6 (Execution Engine). This violates AGENTS.md Invariant #1 ("Raw data flows strictly Layer 0 → 1 → 2 → 3 → 4 → 5 → 6"). PDE cannot read downstream execution states to determine its own confidence.
* **Impact if Uncoded:**
  Creates a circular dependency between Layer 2 (PDE) and Layer 6 (Execution), breaking pipeline isolation and backtesting causal purity (Invariant #23, #24).
* **Reconciled Resolution:**
  Remove `ExecutionConfidence` from PDE's `EvidenceConfidence` formula. PDE `EvidenceConfidence` is strictly calculated as:
  `EvidenceConfidence = f(DataQualityConfidence, StructureConfidence, ImpulseConfidence, PullbackConfidence, WeakeningConfidence, ResumptionConfidence)`
  Execution quality metrics (slippage, fill rate, latency) are evaluated downstream in `docs/09_TRADEABILITY.md` (`ExecutionQualityConfidence`) and Layer 5/6 decision authorization.

---

### Issue 6: Absence of Concrete Types, Units, and Ranges across All Engine Contracts
* **Locations:**
  - All engine contract files (`docs/02_ENGINE_CONTRACTS.md`, `docs/04_STRUCTURE_ENGINE.md` through `docs/16_TTL.md`).
* **Defect Description:**
  No engine contract in the repository specifies concrete data types (e.g., `float64`, `int64`, `uint64`, `enum`, `string`, `bool`, `timestamp_ns`), units (e.g., `price_pips`, `price_quote_currency`, `ratio_0_1`, `seconds`, `nanoseconds`), or valid numerical ranges (e.g., `[0.0, 1.0]`, `[-1.0, 1.0]`, `> 0`).
* **Impact if Uncoded:**
  Implementation teams will invent inconsistent types and unit representations across modules (e.g., mixing pips vs raw price points, seconds vs milliseconds timestamping, floating point vs integer state enums).
* **Reconciled Resolution:**
  A comprehensive schema contract specification has been produced in `SCHEMA_TYPES.md`, establishing explicit data types, physical units, and validation ranges for every field in all canonical objects.

---

## 3. Full Scope Cross-Document Discrepancy Matrix

### Audit Finding 7: News Engine State Enum Mismatch
* **File References:** `docs/02_ENGINE_CONTRACTS.md §11` vs `docs/10_NEWS_SHIELD.md §3`
* **Discrepancy:**
  Doc 02 §11 lists states: `NORMAL`, `WATCH`, `PREP`, `LOCKDOWN`, `SHOCK`, `DISCOVERY`, `VALIDATION`, `RESTRICTED_REENTRY`, `NORMAL_REENTRY`, `EXTENDED_PROTECTION`.
  Doc 10 §3 defines states: `NORMAL`, `NEWS_WATCH`, `NEWS_PREP`, `NEWS_LOCKDOWN`, `INITIAL_SHOCK`, `VOLATILITY_DISCOVERY`, `POST_NEWS_VALIDATION`, `RESTRICTED_REENTRY`, `NORMAL_REENTRY`, `EXTENDED_PROTECTION`.
* **Impact:** State transition routing in News Shield will throw unhandled state exceptions.
* **Resolution:** Reconcile to Doc 10's full descriptive enum (`NEWS_WATCH`, `NEWS_PREP`, `NEWS_LOCKDOWN`, `INITIAL_SHOCK`, `VOLATILITY_DISCOVERY`, `POST_NEWS_VALIDATION`, `RESTRICTED_REENTRY`, `NORMAL_REENTRY`, `EXTENDED_PROTECTION`, `NORMAL`).

---

### Audit Finding 8: Structure Engine States Incompleteness
* **File References:** `docs/02_ENGINE_CONTRACTS.md §3` vs `docs/04_STRUCTURE_ENGINE.md §5`
* **Discrepancy:**
  Doc 02 §3 lists only swing states (`SWING_CANDIDATE`, `SWING_CONFIRMED`, `SWING_PROTECTED`, `SWING_BROKEN`).
  Doc 04 §5 defines structural break states (`BREAK_CANDIDATE`, `BREAK_CONFIRMED`, `BREAK_ESTABLISHED`, `FAILED_BREAK`).
* **Impact:** Downstream engines listening for structural break events cannot process them via contract interfaces.
* **Resolution:** Doc 02 contract must explicitly publish two distinct state fields: `SwingState` and `BreakState`.

---

### Audit Finding 9: Authority Matrix Contradiction on Opportunity Engine
* **File References:** `docs/02_ENGINE_CONTRACTS.md §18` vs `docs/08_OPPORTUNITY_ENGINE.md §7`
* **Discrepancy:**
  Doc 02 §18 (Authority Matrix) states: `Opportunity: Invalidates parent = Yes`.
  Doc 08 §7 explicitly states: "An opportunity cannot invalidate its parent regime/setup state; it expires or fails tradeability."
* **Impact:** Violates parent-child hierarchy invariants (AGENTS.md Invariant #13). A child opportunity expiring should not collapse the parent 1H trend regime.
* **Resolution:** Reconcile Doc 02 §18: `Opportunity: Invalidates parent = No`. An opportunity can invalidate subordinate child signals or child opportunities, but never its parent regime or setup.

---

### Audit Finding 10: Stop-Loss Formula Sign & Direction Ambiguity for Short Positions During News
* **File References:** `docs/10_NEWS_SHIELD.md §10`
* **Discrepancy:**
  Doc 10 §10 specifies stop tightening rules:
  - Long: `SL_final = max(SL_existing, SL_news)`
  - Short: `SL_final = min(SL_existing, SL_news)`
  While `min` for a short position numerically moves the stop lower (closer to current price, which tightens the stop), if price coordinates are represented relative to entry distance or pips, `min` vs `max` sign conventions reverse.
* **Impact:** Incorrect sign handling could move short stops higher (loosening the stop), explicitly violating AGENTS.md Invariant #19 ("Existing protective stops must never be loosened").
* **Resolution:** Standardize formula definitions to explicit price direction logic:
  - Long Stop (tighten = move price UP): `SL_final = max(SL_existing, SL_news_candidate)`
  - Short Stop (tighten = move price DOWN): `SL_final = min(SL_existing, SL_news_candidate)`
  Add mandatory assertion: `Assert(Distance(Entry, SL_final) <= Distance(Entry, SL_existing))`.

---

### Audit Finding 11: Missing Parent State Recovery Paths in Reconciliation Engine
* **File References:** `docs/14_RECONCILIATION.md §4` vs `docs/03_STATE_MACHINE.md §10`
* **Discrepancy:**
  Doc 14 §4 defines orphan states: `NORMAL`, `SUSPECTED_ORPHAN`, `RECONCILING`, `RECOVERED`, `QUARANTINED`.
  However, neither Doc 14 nor Doc 03 defines state transition rules for exiting `QUARANTINED` or reconstructing parent lineage when parent state objects were lost during a system crash.
* **Impact:** Position remains frozen in `QUARANTINED` indefinitely with active market exposure and no defined exit pathway.
* **Status: OPEN DECISION (D-033)**
  - *Option A:* Un-reconcilable positions are handed over to a dedicated Protective Manager that trails a tight structural/time stop until flat, while blocking new strategic exposure.
  - *Option B:* Emergency manual/broker intervention alert raised; position held at current hard stop.
  - *Recommendation:* Option A (Automated protective trailing management to zero exposure).

---

### Audit Finding 12: Undefined Calibration Parameters in Formulas
* **File References:** `docs/06_PULLBACK_ENGINE.md §4, §7`, `docs/16_TTL.md §3`
* **Discrepancy:**
  Formulas in docs contain uncalibrated weights and undefined functional forms:
  - `IQ = wD * D + wE * E + wS * S + wP * P + wR * R` (`wD, wE, wS, wP, wR` unspecified).
  - `TradeDecay = f(TimeDecay, ProgressShortfall, MomentumDecay, StructuralDamage, VolatilityCollapse, OpportunityDecay)` (`f(...)` functional form unspecified).
* **Impact:** Developers might hardcode arbitrary weights or linear sums, bypassing proper research calibration.
* **Resolution:** Confirm that weights and function implementations are marked as Layer 8 Research Calibration Parameters (`docs/18_RESEARCH.md §8`), loaded dynamically from versioned configuration files (`docs/01_ARCHITECTURE.md §10`). Code interfaces must accept configuration structs rather than hardcoded constants.

---

## 4. AGENTS.md Invariants Compliance Audit

| Invariant # | Summary | Operationalized in Docs? | Status / Gap Analysis |
|---|---|---|---|
| #1 | Raw data flows strictly Layer 0 → 6 | Yes | Fully specified in `docs/01_ARCHITECTURE.md §1`. Resolved PDE layering violation in Issue 5. |
| #2 | Strategy engines do not directly place MT5 orders | Yes | `docs/02_ENGINE_CONTRACTS.md`, `docs/13_EXECUTION.md §1`. |
| #3 | PDE cannot call OrderSend | Yes | `docs/06_PULLBACK_ENGINE.md §15`. |
| #4 | Flow cannot open position | Yes | `docs/05_FLOW_ENGINE.md §1`. |
| #5 | Risk cannot manufacture signal | Yes | `docs/11_RISK_ENGINE.md §1`. |
| #6 | Portfolio arbitration cannot manufacture direction | Yes | `docs/12_PORTFOLIO_ARBITRATION.md §1`. |
| #7 | Execution cannot reinterpret strategy | Yes | `docs/13_EXECUTION.md §1`. |
| #8 | News Shield cannot manufacture trades | Yes | `docs/10_NEWS_SHIELD.md §2`. |
| #9 | Confidence cannot make invalid object valid | Yes | `docs/02_ENGINE_CONTRACTS.md §19`. |
| #10 | Mandatory gates not bypassed by high score | Yes | `docs/00_CONSTITUTION.md §2`. |
| #11 | Valid lineage required for executable object | Yes | Reconciled lineage chain in Issue 2. |
| #12 | Child carries parent_id, parent_version, root_id | Yes | `docs/03_STATE_MACHINE.md §1`. |
| #13 | Child cannot act when parent state invalid | Yes | `docs/03_STATE_MACHINE.md §15`. |
| #14 | Orphaned signals never execute | Yes | `docs/14_RECONCILIATION.md §4`. |
| #15 | Orphaned orders reconciled before cancellation | Yes | `docs/14_RECONCILIATION.md §9`. |
| #16 | Orphaned positions protectively managed | Partially | Added transition rules for `QUARANTINED` in Finding 11 (D-033). |
| #17 | Uncertain state cannot create new exposure | Yes | `docs/09_TRADEABILITY.md`, `docs/10_NEWS_SHIELD.md`. |
| #18 | Strategy offline while protection active | Yes | `docs/01_ARCHITECTURE.md §5`. |
| #19 | Protective stops never loosened | Yes | Standardized sign logic in Finding 10. |
| #20 | No new exposure during NEWS_LOCKDOWN | Yes | `docs/10_NEWS_SHIELD.md §7`. |
| #21 | Scheduled news vs observed shock separate | Yes | `docs/10_NEWS_SHIELD.md §5`. |
| #22 | 10-min post-news is checkpoint, not auto restart | Yes | `docs/10_NEWS_SHIELD.md §12`. |
| #23 | No future data / lookahead | Yes | `docs/18_RESEARCH.md §4`. |
| #24 | Decisions use data available at/before t | Yes | `docs/18_RESEARCH.md §9`. |
| #25 | Pullbacks hierarchical (M1 micro ≠ primary) | Yes | `docs/06_PULLBACK_ENGINE.md §1`. |
| #26 | Primary pullback higher TF than execution | Yes | `docs/06_PULLBACK_ENGINE.md §1`. |
| #27 | Lower-TF pullback explicit micro exception | Yes | `docs/06_PULLBACK_ENGINE.md §11`. |
| #28 | Flipping requires structural reversal | Yes | `docs/12_PORTFOLIO_ARBITRATION.md §9`. |
| #29 | Sweeps are trigger modifiers | Yes | `docs/08_OPPORTUNITY_ENGINE.md §8`. |
| #30 | Compression is state, not automatic signal | Yes | `docs/08_OPPORTUNITY_ENGINE.md §9`. |
| #31 | Static EMA crossover not core strategy | Yes | `docs/07_REGIME_ENGINE.md §2`. |
| #32 | Fixed 3-candle fractals not structure model | Yes | `docs/04_STRUCTURE_ENGINE.md §1`. |
| #33 | No fixed Fibonacci pullback rules | Yes | `docs/06_PULLBACK_ENGINE.md §4`. |
| #34 | No fixed candle-count pullback rules | Yes | `docs/06_PULLBACK_ENGINE.md §4`. |
| #35 | Structural stops primary; ATR buffer only | Yes | `docs/11_RISK_ENGINE.md §9`. |
| #36 | Finite lifetime through TTL | Yes | `docs/16_TTL.md §1`. |
| #37 | Exposure currency-aware & correlation-aware | Yes | `docs/12_PORTFOLIO_ARBITRATION.md §4, §5`. |
| #38 | Account feasibility checked before sizing | Yes | `docs/11_RISK_ENGINE.md §6`. |
| #39 | Configuration versioned | Partially | Addressed in `HARDENING_RECOMMENDATIONS.md`. |
| #40 | Reconciliation completes before strategy auth | Yes | `docs/14_RECONCILIATION.md §7`. |
| #41 | Research tests incremental information value | Yes | `docs/18_RESEARCH.md §2`. |
| #42 | Constitutional rules never optimized away | Yes | `docs/00_CONSTITUTION.md §3`. |

---

## 5. Summary of Open Decisions vs Reconciled Resolutions

1. **Reconciled Resolutions:**
   - **Resumption Vocabulary:** Standardized to `PDE_RESUMPTION_FAILED` and unified state structure (D-034).
   - **Lineage Chain:** Expanded to include `MICRO_PULLBACK` and `OPPORTUNITY` (D-035).
   - **Orphaned Policy Fields:** Integrated into Opportunity Gate, Smart Overtrading, and Runner Management (D-036).
   - **PDE Layering Violation:** Removed downstream `ExecutionConfidence` from PDE formula (D-037).
   - **Authority Matrix:** Corrected Opportunity Engine row in Authority Matrix (`Invalidates parent = No`) (D-038).

2. **Open Decisions (Pushed to `DECISION_LOG_ADDENDUM.md`):**
   - **D-032 (Boolean Precedence in Pullback Candidate Rule):** Framing Option A vs Option B for research calibration.
   - **D-033 (Quarantined Position Resolution Pathway):** Automated structural trailing termination vs manual intervention freeze.
