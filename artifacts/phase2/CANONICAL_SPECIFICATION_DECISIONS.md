# Phase 2 — Canonical Specification Decisions Register

This document records the formal specification reconciliation decisions resolved prior to Phase 2 behavioral-state implementation.

---

## C-001 — Flow State Vocabulary Reconciliation

### Problem
`spec/states.yaml` previously defined FlowState as `[FLOW_NEUTRAL, FLOW_BULLISH_DOMINANT, FLOW_BEARISH_DOMINANT, FLOW_BULLISH_EMERGING, FLOW_BEARISH_EMERGING, FLOW_BALANCED]`, whereas `docs/05_FLOW_ENGINE.md` defined the canonical behavioral state vocabulary.

### Evidence
- `spec/states.yaml:46-52`
- `docs/05_FLOW_ENGINE.md:12-23`

### Canonical authority
`docs/05_FLOW_ENGINE.md §3`

### Decision
Standardize `FlowState` vocabulary to:
`UNKNOWN`, `LONG_EMERGING`, `LONG_DOMINANT`, `LONG_WEAKENING`, `BALANCED`, `CONTESTED`, `SHORT_EMERGING`, `SHORT_DOMINANT`, `SHORT_WEAKENING`, `TRANSITIONING`.

### Required implementation consequence
Phase 2 Flow Engine implementation must emit StateEnvelopes using canonical state names loaded from `spec/states.yaml`.

### Compatibility impact
None. Canonical persisted state and migration boundaries will use canonical state names.

### Historical artifact handling
Historical Phase 1 forensic reports retain their historical terminology.

### Status
RECONCILED

---

## C-002 — PDE Primary State Vocabulary Standard

### Problem
`docs/02_ENGINE_CONTRACTS.md §5` and `spec/states.yaml` had minor string representation differences for primary PDE states.

### Evidence
- `spec/states.yaml:54-66`
- `docs/02_ENGINE_CONTRACTS.md:103-116`
- `docs/DECISION_LOG.md:115` (D-034)

### Canonical authority
Decision D-034 (`docs/DECISION_LOG.md:115`)

### Decision
Standardize primary PDE state (`PDEState`) to:
`PDE_NONE`, `PDE_IMPULSE`, `PDE_PULLBACK_CANDIDATE`, `PDE_PULLBACK_ACTIVE`, `PDE_WEAKENING`, `PDE_STRENGTHENING`, `PDE_DEEPENING`, `PDE_RESUMPTION_IN_PROGRESS`, `PDE_FOLLOW_THROUGH`, `PDE_RESUMPTION_FAILED`, `PDE_INVALIDATED`.

### Required implementation consequence
Phase 2 PDE Engine must use `PDEState` as primary state enum and validate all state transitions through `StateRegistry`.

### Compatibility impact
None.

### Historical artifact handling
Historical reports remain unchanged.

### Status
RECONCILED

---

## C-003 — PDE Resumption Sub-Lifecycle State Vocabulary

### Problem
Resumption states were previously merged into primary PDE states or declared with inconsistent names.

### Evidence
- `spec/states.yaml:67-73`
- `docs/02_ENGINE_CONTRACTS.md:118-125`
- `docs/DECISION_LOG.md:115` (D-034)

### Canonical authority
Decision D-034 (`docs/DECISION_LOG.md:115`)

### Decision
Establish `PDEResumptionState` as the distinct sub-lifecycle resumption state:
`RESUMPTION_NONE`, `RECOVERY_CANDIDATE`, `RECOVERY_CONFIRMED`, `DISPLACEMENT_CANDIDATE`, `RESUMPTION_CONFIRMED`, `FOLLOW_THROUGH`, `RESUMPTION_FAILED`.

### Required implementation consequence
PDE Engine will maintain `state` as `PDEState` and `sub_state` as `PDEResumptionState` in `PullbackObject` and `StateEnvelope`.

### Compatibility impact
None.

### Historical artifact handling
Historical reports remain unchanged.

### Status
RECONCILED

---

## C-004 — Regime State Vocabulary Standard

### Problem
`spec/states.yaml` prefixed regime states (`REGIME_TREND_UP`), whereas `docs/07_REGIME_ENGINE.md` defined target behavioral states.

### Evidence
- `spec/states.yaml:74-78`
- `docs/07_REGIME_ENGINE.md:5-11`

### Canonical authority
`docs/07_REGIME_ENGINE.md §1`

### Decision
Standardize `RegimeState` vocabulary to:
`UNKNOWN`, `TREND_UP`, `TREND_DOWN`, `RANGE`, `TRANSITION`, `CHAOTIC`.

### Required implementation consequence
Phase 2 Regime Engine must emit state envelopes with canonical RegimeState vocabulary.

### Compatibility impact
None.

### Historical artifact handling
Historical reports remain unchanged.

### Status
RECONCILED

---

## C-005 — Market Role Vocabulary Standard

### Problem
`spec/states.yaml` prefixed role states (`ROLE_CONTINUATION`), whereas `docs/07_REGIME_ENGINE.md` defined canonical market roles.

### Evidence
- `spec/states.yaml:80-90`
- `docs/07_REGIME_ENGINE.md:46-58`

### Canonical authority
`docs/07_REGIME_ENGINE.md §6`

### Decision
Standardize `RoleState` vocabulary to:
`UNKNOWN`, `CONTINUATION`, `PULLBACK`, `COUNTERFLOW`, `RANGE_ROTATION`, `BREAKOUT`, `RECLAIM`, `TRANSITION`, `EXHAUSTION`, `NOISE`, `AMBIGUOUS`.

### Required implementation consequence
Phase 2 Role Engine must emit state envelopes using canonical RoleState vocabulary.

### Compatibility impact
None.

### Historical artifact handling
Historical reports remain unchanged.

### Status
RECONCILED

---

## C-006 — Location State Vocabulary Standard

### Problem
`spec/states.yaml` prefixed location states (`LOC_OPEN`), whereas `docs/07_REGIME_ENGINE.md` defined target location states.

### Evidence
- `spec/states.yaml:92-96`
- `docs/07_REGIME_ENGINE.md:59-66`

### Canonical authority
`docs/07_REGIME_ENGINE.md §7`

### Decision
Standardize `LocationState` vocabulary to:
`OPEN`, `FAVORABLE`, `NEUTRAL`, `CONGESTED`, `BLOCKED`, `EXTREME`.

### Required implementation consequence
Phase 2 Location Engine must emit state envelopes using canonical LocationState vocabulary.

### Compatibility impact
None.

### Historical artifact handling
Historical reports remain unchanged.

### Status
RECONCILED

---

## C-007 — Flow State Transition Graph Specification

### Problem
`spec/transitions.yaml` lacked a transition graph entry for `FlowState`.

### Evidence
- `spec/transitions.yaml` (missing FlowState)
- `docs/05_FLOW_ENGINE.md:20`

### Canonical authority
`docs/05_FLOW_ENGINE.md §5` & `AGENTS.md` (Fail-Closed Machine Validation)

### Decision
Explicitly define legal transition graph for `FlowState` in `spec/transitions.yaml`.

### Required implementation consequence
`StateRegistry.validate_transition` enforces legal flow state transitions at runtime.

### Compatibility impact
None.

### Historical artifact handling
Historical reports remain unchanged.

### Status
RECONCILED

---

## C-008 — Regime State Transition Graph Specification

### Problem
`spec/transitions.yaml` lacked a transition graph entry for `RegimeState`.

### Evidence
- `spec/transitions.yaml` (missing RegimeState)
- `docs/07_REGIME_ENGINE.md:30`

### Canonical authority
`docs/07_REGIME_ENGINE.md §4` & `AGENTS.md`

### Decision
Explicitly define legal transition graph for `RegimeState` in `spec/transitions.yaml`.

### Required implementation consequence
`StateRegistry.validate_transition` enforces legal regime transitions at runtime.

### Compatibility impact
None.

### Historical artifact handling
Historical reports remain unchanged.

### Status
RECONCILED

---

## C-009 — Role State Transition Graph Specification

### Problem
`spec/transitions.yaml` lacked a transition graph entry for `RoleState`.

### Evidence
- `spec/transitions.yaml` (missing RoleState)
- `docs/07_REGIME_ENGINE.md:46`

### Canonical authority
`docs/07_REGIME_ENGINE.md §6` & `AGENTS.md`

### Decision
Explicitly define legal transition graph for `RoleState` in `spec/transitions.yaml`.

### Required implementation consequence
`StateRegistry.validate_transition` enforces legal role transitions at runtime.

### Compatibility impact
None.

### Historical artifact handling
Historical reports remain unchanged.

### Status
RECONCILED

---

## C-010 — Location State Transition Graph Specification

### Problem
`spec/transitions.yaml` lacked a transition graph entry for `LocationState`.

### Evidence
- `spec/transitions.yaml` (missing LocationState)
- `docs/07_REGIME_ENGINE.md:59`

### Canonical authority
`docs/07_REGIME_ENGINE.md §7` & `AGENTS.md`

### Decision
Explicitly define legal transition graph for `LocationState` in `spec/transitions.yaml`.

### Required implementation consequence
`StateRegistry.validate_transition` enforces legal location transitions at runtime.

### Compatibility impact
None.

### Historical artifact handling
Historical reports remain unchanged.

### Status
RECONCILED

---

## C-011 — PDE Transition Ownership & Sub-State Transition Graph

### Problem
`spec/transitions.yaml` defined PDEState transitions but omitted PDEResumptionState sub-transitions.

### Evidence
- `spec/transitions.yaml:42-54`
- `docs/06_PULLBACK_ENGINE.md:8`

### Canonical authority
Decision D-034 & `docs/06_PULLBACK_ENGINE.md §8`

### Decision
Add explicit transition graph for `PDEResumptionState` in `spec/transitions.yaml`.

### Required implementation consequence
`StateRegistry.validate_transition` validates resumption sub-state transitions fail-closed.

### Compatibility impact
None.

### Historical artifact handling
Historical reports remain unchanged.

### Status
RECONCILED

---

## C-012 — Lineage Chain Reconciliation (D-035)

### Problem
`docs/00_CONSTITUTION.md` and `docs/14_RECONCILIATION.md` contained outdated lineage chains omitting `MICRO_PULLBACK` and `OPPORTUNITY`.

### Evidence
- `docs/00_CONSTITUTION.md:348`
- `docs/14_RECONCILIATION.md:35`
- `docs/DECISION_LOG.md:120` (D-035)
- `spec/lineage.yaml:2`

### Canonical authority
Decision D-035 (`docs/DECISION_LOG.md:120`)

### Decision
Reconcile active canonical documentation to D-035 lineage:
`ROOT → REGIME → SETUP → PRIMARY_PULLBACK → [SECONDARY_PULLBACK →] [MICRO_PULLBACK →] OPPORTUNITY → SIGNAL → ORDER → POSITION → TRADE → MANAGEMENT`.

### Required implementation consequence
Lineage validation and specification parity checks strictly enforce D-035 hierarchy.

### Compatibility impact
None.

### Historical artifact handling
Historical forensic reports retain historical terminology.

### Status
RECONCILED

---

## C-013 — Primary Pullback Timeframe Rule Specification

### Problem
Invariant 26 (`primary_pullback_higher_tf`) was `SPECIFIED_ONLY` without explicit fail-closed boundary rules.

### Evidence
- `spec/invariants.yaml:250`
- `docs/06_PULLBACK_ENGINE.md:4`

### Canonical authority
AGENTS.md Invariant #26 & `docs/06_PULLBACK_ENGINE.md §1`

### Decision
`PRIMARY_PULLBACK.timeframe > execution_timeframe` using repository timeframe ordering (`4H > 1H > 30M > 15M > 5M > 1M`). If `primary_timeframe <= execution_timeframe`, object is rejected/quarantined with no downstream execution authorization.

### Required implementation consequence
Layer 2 PDE construction will validate timeframe ordering prior to setting `primary_entry_allowed`.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-014 — Fibonacci Constitutional Independence Specification

### Problem
Invariant 33 (`fixed_fibonacci_not_constitutional`) status was `SPECIFIED_ONLY`.

### Evidence
- `spec/invariants.yaml:259`
- `docs/DECISION_LOG.md:24` (D-007)
- `docs/06_PULLBACK_ENGINE.md:53`

### Canonical authority
Decision D-007 & AGENTS.md Invariant #33

### Decision
Fibonacci levels are descriptive, contextual, research and diagnostic features ONLY. Crossing or altering a Fibonacci threshold cannot invalidate constitutional state validity.

### Required implementation consequence
Phase 2 behavioral engines will not treat fixed Fibonacci thresholds as constitutional laws.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-015 — Fixed Candle-Count Constitutional Independence Specification

### Problem
Invariant 34 (`fixed_candle_count_not_constitutional`) status was `SPECIFIED_ONLY`.

### Evidence
- `spec/invariants.yaml:267`
- `docs/DECISION_LOG.md:26` (D-008)
- `docs/06_PULLBACK_ENGINE.md:53`

### Canonical authority
Decision D-008 & AGENTS.md Invariant #34

### Decision
Fixed candle counts and duration ratios are descriptive context ONLY. They must not act as unconditional constitutional requirements.

### Required implementation consequence
Phase 2 engines will measure adaptive structure rather than hard-coded candle-count thresholds.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-016 — Flow Engine Authority Boundary

### Problem
`spec/engines.yaml` had an incomplete entry for `Flow`.

### Evidence
- `spec/engines.yaml`
- `src/fractal_flow/domain/authority.py:60`
- `docs/05_FLOW_ENGINE.md:44`

### Canonical authority
`docs/05_FLOW_ENGINE.md §9` & `src/fractal_flow/domain/authority.py`

### Decision
Flow engine permissions in `spec/engines.yaml`:
Allowed: `READ_MARKET_STATE`, `READ_FEATURES`, `WRITE_FLOW_STATE`.
Forbidden: `CREATE_EXECUTION_INTENT`, `SUBMIT_ORDER`, `MODIFY_POSITION`, `CLOSE_POSITION_STRATEGICALLY`.

### Required implementation consequence
Flow engine cannot claim execution authority at runtime.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-017 — PDE Engine Authority Boundary

### Problem
`spec/engines.yaml` lacked full explicit alignment with `src/fractal_flow/domain/authority.py`.

### Evidence
- `spec/engines.yaml:2`
- `src/fractal_flow/domain/authority.py:44`

### Canonical authority
`docs/06_PULLBACK_ENGINE.md §15` & `src/fractal_flow/domain/authority.py`

### Decision
PDE engine permissions in `spec/engines.yaml`:
Allowed: `READ_MARKET_STATE`, `READ_FEATURES`, `WRITE_PDE_STATE`, `CREATE_PULLBACK_OBJECT`, `INVALIDATE_SUBORDINATE_CHILDREN`.
Forbidden: `CREATE_EXECUTION_INTENT`, `SUBMIT_ORDER`, `MODIFY_POSITION`, `CLOSE_POSITION_STRATEGICALLY`.

### Required implementation consequence
PDE engine cannot claim execution authority at runtime.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-018 — Regime Engine Authority Boundary Specification

### Problem
`spec/engines.yaml` and `src/fractal_flow/domain/authority.py` lacked explicit capability definitions for `Regime`.

### Evidence
- `spec/engines.yaml`
- `src/fractal_flow/domain/authority.py`
- `docs/07_REGIME_ENGINE.md:70`

### Canonical authority
`docs/07_REGIME_ENGINE.md §10` & `docs/02_ENGINE_CONTRACTS.md §18`

### Decision
Define `Regime` permissions in `spec/engines.yaml` and `src/fractal_flow/domain/authority.py`:
Allowed: `READ_MARKET_STATE`, `READ_FEATURES`, `WRITE_REGIME_STATE`.
Forbidden: `CREATE_EXECUTION_INTENT`, `SUBMIT_ORDER`, `MODIFY_POSITION`, `CLOSE_POSITION_STRATEGICALLY`.

### Required implementation consequence
Regime engine is strictly limited to state writing and forbidden from execution actions.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-019 — Role Engine Authority Boundary Specification

### Problem
`spec/engines.yaml` and `src/fractal_flow/domain/authority.py` lacked explicit capability definitions for `Role`.

### Evidence
- `spec/engines.yaml`
- `src/fractal_flow/domain/authority.py`
- `docs/07_REGIME_ENGINE.md:70`

### Canonical authority
`docs/07_REGIME_ENGINE.md §10` & `docs/02_ENGINE_CONTRACTS.md §18`

### Decision
Define `Role` permissions in `spec/engines.yaml` and `src/fractal_flow/domain/authority.py`:
Allowed: `READ_MARKET_STATE`, `READ_FEATURES`, `WRITE_ROLE_STATE`.
Forbidden: `CREATE_EXECUTION_INTENT`, `SUBMIT_ORDER`, `MODIFY_POSITION`, `CLOSE_POSITION_STRATEGICALLY`.

### Required implementation consequence
Role engine is strictly limited to state writing and forbidden from execution actions.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-020 — Location Engine Authority Boundary Specification

### Problem
`spec/engines.yaml` and `src/fractal_flow/domain/authority.py` lacked explicit capability definitions for `Location`.

### Evidence
- `spec/engines.yaml`
- `src/fractal_flow/domain/authority.py`
- `docs/07_REGIME_ENGINE.md:70`

### Canonical authority
`docs/07_REGIME_ENGINE.md §10` & `docs/02_ENGINE_CONTRACTS.md §18`

### Decision
Define `Location` permissions in `spec/engines.yaml` and `src/fractal_flow/domain/authority.py`:
Allowed: `READ_MARKET_STATE`, `READ_FEATURES`, `WRITE_LOCATION_STATE`.
Forbidden: `CREATE_EXECUTION_INTENT`, `SUBMIT_ORDER`, `MODIFY_POSITION`, `CLOSE_POSITION_STRATEGICALLY`.

### Required implementation consequence
Location engine is strictly limited to state writing and forbidden from execution actions.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-021 — Behavioral Object Metadata Standard

### Problem
Behavioral state objects must consistently support root/parent lineage and versioning metadata fields.

### Evidence
- `src/fractal_flow/domain/envelope.py:87`
- `docs/03_STATE_MACHINE.md:1-20`

### Canonical authority
`AGENTS.md` Invariant #12 & `docs/03_STATE_MACHINE.md §1`

### Decision
All state-bearing behavioral objects wrap or integrate `StateEnvelope` carrying: `root_id`, `parent_id`, `parent_version`, `version`, `configuration_version`, `data_version`, `feature_version`, `timestamp`, `valid_until`, `authority`.

### Required implementation consequence
Enforced via `StateEnvelope.__post_init__` validation.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-022 — Audit Event Metadata Schema Alignment

### Problem
Event telemetry specifications required reconciliation against `StateEnvelope` fields.

### Evidence
- `src/fractal_flow/domain/event.py`
- `spec/events.yaml`
- `docs/01_ARCHITECTURE.md:120`

### Canonical authority
`docs/01_ARCHITECTURE.md §6` & `docs/14_RECONCILIATION.md §10`

### Decision
Behavioral transition events carry: `event_type`, `object_id`, `root_id`, `parent_id`, `parent_version`, `previous_state`, `new_state`, `timestamp`, `reason_codes`, `configuration_version`, `authority`.

### Required implementation consequence
State transitions emit events matching this schema.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-023 — StateEnvelope Vocabulary Authority

### Problem
Verification of StateEnvelope runtime fail-closed state validation against canonical `spec/states.yaml`.

### Evidence
- `src/fractal_flow/domain/envelope.py:148`
- `spec/states.yaml`

### Canonical authority
`src/fractal_flow/domain/envelope.py` & `spec/states.yaml`

### Decision
`StateEnvelope.__post_init__` checks object state membership in `GLOBAL_STATE_REGISTRY` loaded directly from `spec/states.yaml`.

### Required implementation consequence
Any unknown state fails closed with `ValueError`.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-024 — StateRegistry Transition Authority

### Problem
Verification of StateRegistry runtime fail-closed transition validation against `spec/transitions.yaml`.

### Evidence
- `src/fractal_flow/domain/envelope.py:53`
- `spec/transitions.yaml`

### Canonical authority
`src/fractal_flow/domain/envelope.py` & `spec/transitions.yaml`

### Decision
`StateRegistry.validate_transition` enforces legal transition lookup from `spec/transitions.yaml`, failing closed on unknown machines, current states, target states, or unauthorized edges.

### Required implementation consequence
Any illegal transition raises `InvalidStateTransitionException`.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-025 — Ambiguity Semantics

### Problem
Explicit distinction between `UNKNOWN`, `AMBIGUOUS`, `TRANSITIONING`, and `CONTESTED` states.

### Evidence
- `docs/07_REGIME_ENGINE.md:65`
- `docs/00_CONSTITUTION.md:83`

### Canonical authority
`docs/07_REGIME_ENGINE.md §9`

### Decision
`AMBIGUOUS` is a first-class state that defers, blocks, or reduces permission, but NEVER manufactures validity or default directional exposure.

### Required implementation consequence
Behavioral engines will set `AMBIGUOUS` when multi-TF or structural conflict exists.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-026 — Pullback Maturity Model Semantics

### Problem
Explicit clarification of pullback maturity state usage.

### Evidence
- `docs/06_PULLBACK_ENGINE.md:45`
- `src/fractal_flow/domain/models.py:88`

### Canonical authority
`docs/06_PULLBACK_ENGINE.md §5`

### Decision
Maturity (`EARLY`, `DEVELOPING`, `MATURE`, `LATE`, `EXHAUSTED`) is descriptive/contextual and must NEVER act as a direct entry trigger or execution authorization flag.

### Required implementation consequence
PDE Engine computes maturity for research and location context only.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-027 — Weakening vs Resumption Semantics

### Problem
Clarification of weakening versus resumption distinction.

### Evidence
- `docs/06_PULLBACK_ENGINE.md:50`
- `docs/DECISION_LOG.md:35` (D-010)

### Canonical authority
Decision D-010 (`docs/DECISION_LOG.md:35`)

### Decision
Weakening measures counter-pressure decay, whereas resumption requires structural recovery and directional displacement. Weakening does NOT equal automatic reversal or resumption.

### Required implementation consequence
PDE Engine maintains separate `weakening_score` and `resumption_score` fields.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED

---

## C-028 — Impulse Quality (IQ) Specification Gap

### Problem
The Impulse Quality formula `IQ = wD*D + wE*E + wS*S + wP*P + wR*R` requires explicit configuration-bound weights.

### Evidence
- `docs/06_PULLBACK_ENGINE.md:30`

### Canonical authority
`docs/06_PULLBACK_ENGINE.md §3`

### Decision
Document the weight model requirement for Phase 2 Layer 2 PDE implementation: weights must be explicit, versioned, reproducible, deterministic, and configuration-bound without hidden ML authority.

### Required implementation consequence
Phase 2 PDE Engine implementation will define explicit configuration classes for impulse weights.

### Compatibility impact
None.

### Historical artifact handling
None.

### Status
RECONCILED
