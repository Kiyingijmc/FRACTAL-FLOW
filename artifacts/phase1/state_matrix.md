# FRACTAL FLOW — PHASE 1 CANONICAL STATE MATRIX

| State Machine | Spec Location | Implementation | Transition Owner | Transition Test | Persistence | Recovery |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DataQualityState** | `spec/states.yaml` | `src/fractal_flow/domain/data_quality.py` | `DataQualityEngine` | `tests/phase1b/test_state_envelope_transitions.py::test_data_quality_state_envelope_creation_and_transition` | `DurableEventJournal` | `SnapshotEngine.replay_journal` |
| **VolatilityState** | `spec/states.yaml` | `src/fractal_flow/domain/volatility.py` | `VolatilityEngine` | `tests/phase1e/test_volatility_formulas.py::test_volatility_state_machine_extreme_and_expansion` | `DurableEventJournal` | `SnapshotEngine.replay_journal` |
| **SwingState** | `spec/states.yaml` | `src/fractal_flow/domain/structure.py` | `StructureEngine` | `tests/phase1f/test_structure_transitions.py::test_adaptive_swing_reversal_magnitude_transitions` | `DurableEventJournal` | `SnapshotEngine.replay_journal` |
| **BreakState** | `spec/states.yaml` | `src/fractal_flow/domain/structure.py` | `StructureEngine` | `tests/phase1f/test_structure_transitions.py::test_structural_break_requires_cross_displacement_and_persistence` | `DurableEventJournal` | `SnapshotEngine.replay_journal` |
| **StructuralDamageState** | `spec/states.yaml` | `src/fractal_flow/domain/structure.py` | `StructureEngine` | `tests/phase1f/test_structure_transitions.py::test_structural_break_requires_cross_displacement_and_persistence` | `DurableEventJournal` | `SnapshotEngine.replay_journal` |
