# FRACTAL FLOW — PHASE 1 LINEAGE MATRIX

| Object Type | Lineage Fields | Parent Type | Parent Version Validation | Seal Requirement | Test Reference |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Bar** | `open_timestamp`, `sequence`, `data_version` | Tick / Lower-TF Bar | Strict timestamp ordering | Implicit boundary | `tests/phase1a/test_tick_bar_equivalence.py` |
| **DataQualityAssessment** | `root_id`, `parent_id`, `parent_version`, `version` | MarketObservation / Bar | Exact version match | `StateEnvelope` validation | `tests/phase1b/test_state_envelope_transitions.py` |
| **VolatilityMetrics** | `symbol`, `timestamp`, `version` | Bar | Sequential version increment | `StateEnvelope` validation | `tests/phase1e/test_volatility_numerical_policy.py` |
| **StructureTransitionRecord** | `root_id`, `parent_id`, `parent_version`, `state_version` | Bar / Parent Structure | Strict version match | `StateEnvelope` validation | `tests/phase1f/test_structure_lineage.py` |
| **TradeDecision** | `root_id`, `opportunity_id`, `pullback_id`, `lineage_version` | Opportunity / Parent Seal | `AuthoritativeParentSeal` mandatory | `AuthoritativeParentSeal` verified by `GLOBAL_PARENT_RESOLVER` | `tests/test_provenance_authorization.py` |
