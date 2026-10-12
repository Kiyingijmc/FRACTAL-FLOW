# FRACTAL FLOW — PHASE 1F EVIDENCE REPORT

**Phase**: 1F — Structure Engine
**Status**: COMPLETE

---

## 1. Test Commands & Exit Statuses

| Command | Exit Code | Test Count | Status / Notes |
| :--- | :--- | :--- | :--- |
| `poetry run pytest --no-cov -q tests/phase1f` | 0 | 5 | All Phase 1F structure tests passed |
| `poetry run pytest --no-cov -q tests/phase1f/test_structure_transitions.py` | 0 | 2 | Adaptive swings & structural break logic passed |
| `poetry run pytest --no-cov -q tests/phase1f/test_structure_lineage.py` | 0 | 1 | Lineage & version propagation passed |
| `poetry run pytest --no-cov -q tests/phase1f/test_structure_authority.py` | 0 | 1 | Capability boundary & stop candidate output passed |
| `poetry run pytest --no-cov -q tests/phase1f/test_structure_confirmation_causality.py` | 0 | 1 | Confirmation causality & no-lookahead passed |
| `poetry run pytest` | 0 | 332 | Full test suite passed (Coverage: 87.92%, exceeds 85% requirement) |

---

## 2. Artifact Paths

- **Implementation**:
  - `src/fractal_flow/domain/structure.py` — `StructureEngine`, `StructuralBreak`, `StructuralStopCandidate`, `StructureTransitionRecord`, `SwingState`, `BreakState`, `StructuralDamageState`
  - `src/fractal_flow/domain/__init__.py` — Module exports
  - `spec/states.yaml` & `spec/transitions.yaml` — Structure state declarations and transitions
- **Test Suite**:
  - `tests/phase1f/test_structure_transitions.py`
  - `tests/phase1f/test_structure_lineage.py`
  - `tests/phase1f/test_structure_authority.py`
  - `tests/phase1f/test_structure_confirmation_causality.py`
- **Evidence Record**:
  - `artifacts/phase1/phase1f_evidence.md`

---

## 3. Executable Definitions & Invariants

1. **Local Volatility Reference ($V_{local}$)**: Executably defined as $V_{local} = \max(ATR_{14}, 0.0001)$. Adaptive swing reversal magnitude is evaluated as $\text{SwingReversalMagnitude} = \frac{\text{ReversalDisplacement}}{V_{local}}$.
2. **Structural Break Invariant**:
   $$\text{StructuralBreak} = \text{LevelCross} \times \text{DisplacementConfirmation} \times \text{PersistenceConfirmation}$$
   - `LevelCross`: $Close_t > High_{protected}$ or $Close_t < Low_{protected}$. A level touch alone strictly evaluates `LevelCross = False` and yields `BREAK_NONE`.
   - `DisplacementConfirmation`: Reversal displacement $\ge 0.5 \times V_{local}$.
   - `PersistenceConfirmation`: Price stays beyond level for $\ge 2$ consecutive closed bars.
3. **Authority & Capability Boundaries**: Structure outputs `StructuralStopCandidate` references. Tests prove that `StructureEngine` possesses zero methods or attributes to size trades, authorize trades, manufacture execution intent, or submit orders.
