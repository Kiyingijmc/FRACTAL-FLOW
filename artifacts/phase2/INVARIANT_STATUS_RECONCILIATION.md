# Phase 2 Invariant Status Reconciliation

This document provides an explicit forensic comparison between the Phase 1 evidence baseline, the previously claimed Phase 2 reconciliation counts, and the verified Phase 2 forensic closure state across all 42 non-negotiable architectural invariants.

---

## Invariant Evidence Comparison Table

| ID | Title / Rule Name | Phase 1 Baseline | Phase 2 Claimed | Phase 2 Verified | Production Path / Evidence Summary |
|---|---|---|---|---|---|
| 1 | pipeline_data_flow_layers | INTEGRATION_VERIFIED | INTEGRATION_VERIFIED | INTEGRATION_VERIFIED | `BarAggregator.process_tick`, `DataQualityEngine.evaluate_tick`, `VolatilityEngine.update_bar`, `StructureEngine.process_bar` |
| 2 | strategy_engines_no_direct_orders | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/engines.yaml`, `AuthorityMatrix` (Deferred to Layer 2) |
| 3 | pde_cannot_call_ordersend | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/engines.yaml`, `AuthorityMatrix` (Deferred to Layer 2) |
| 4 | flow_cannot_open_position | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/engines.yaml`, `AuthorityMatrix` (Deferred to Layer 2) |
| 5 | risk_cannot_manufacture_signal | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/invariants.yaml` (Deferred to Layer 4) |
| 6 | portfolio_cannot_manufacture_direction | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/invariants.yaml` (Deferred to Layer 4) |
| 7 | execution_cannot_reinterpret_strategy | ENFORCED | ENFORCED | ENFORCED | `TradeDecision.is_authorized`, `test_invariant_7_execution_cannot_reinterpret_strategy` |
| 8 | news_shield_cannot_manufacture_trades | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/invariants.yaml` (Deferred to Layer 5) |
| 9 | confidence_cannot_override_validity | ENFORCED | ENFORCED | ENFORCED | `StateEnvelope.__post_init__`, `TradeDecision.is_authorized` |
| 10 | mandatory_validity_gates_unbypassable | ENFORCED | ENFORCED | ENFORCED | `TradeDecision.is_authorized` mandatory failure gates |
| 11 | valid_lineage_required | ENFORCED | ENFORCED | ENFORCED | `Lineage.validate_child_action`, `test_lineage_exact_version_accepted` |
| 12 | child_carries_lineage_ids | ENFORCED | ENFORCED | ENFORCED | `Lineage` dataclass fields |
| 13 | child_blocked_on_invalid_parent | ENFORCED | ENFORCED | ENFORCED | `Lineage.validate_child_action` strict version check |
| 14 | orphaned_signals_never_execute | ENFORCED | ENFORCED | ENFORCED | `Lineage.validate_child_action` parent/root check |
| 15 | orphaned_orders_reconciled | INTEGRATION_VERIFIED | INTEGRATION_VERIFIED | INTEGRATION_VERIFIED | `ReconciliationEngine.reconcile_broker_wide` |
| 16 | orphaned_positions_protectively_managed | INTEGRATION_VERIFIED | INTEGRATION_VERIFIED | INTEGRATION_VERIFIED | `ReconciliationEngine.reconcile_broker_wide` |
| 17 | uncertain_state_no_new_exposure | ENFORCED | ENFORCED | ENFORCED | `TradeDecision.is_authorized` news/risk/lineage check |
| 18 | strategy_offline_protection_active | INTEGRATION_VERIFIED | INTEGRATION_VERIFIED | INTEGRATION_VERIFIED | `DeterministicBrokerSimulator.modify_stop_loss` |
| 19 | protective_stops_never_loosened | ENFORCED | ENFORCED | ENFORCED | `DeterministicBrokerSimulator.modify_stop_loss` ratchet check |
| 20 | no_strategic_exposure_in_news_lockdown | ENFORCED | ENFORCED | ENFORCED | `TradeDecision.is_authorized` news state check |
| 21 | scheduled_news_vs_observed_shock_separate | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/invariants.yaml` (Deferred to Layer 5) |
| 22 | ten_min_post_news_checkpoint | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/invariants.yaml` (Deferred to Layer 5) |
| 23 | no_future_data_lookahead | INTEGRATION_VERIFIED | INTEGRATION_VERIFIED | INTEGRATION_VERIFIED | `CausalTestFramework.verify_causality` |
| 24 | decisions_use_past_data | INTEGRATION_VERIFIED | INTEGRATION_VERIFIED | INTEGRATION_VERIFIED | `TradeDecision` quote timestamp snapshot |
| 25 | pullbacks_hierarchical_m1_micro | ENFORCED | ENFORCED | ENFORCED | `Lineage.verify_legal_edge` graph hierarchy |
| 26 | primary_pullback_higher_tf | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/invariants.yaml` (Deferred to Layer 2 PDE strategy) |
| 27 | lower_tf_pullback_explicit_micro | ENFORCED | ENFORCED | ENFORCED | `Lineage.verify_legal_edge` micro tier check |
| 28 | flipping_requires_structural_reversal | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/invariants.yaml` (Deferred to Layer 4 Portfolio) |
| 29 | liquidity_sweeps_trigger_modifiers | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/invariants.yaml` (Deferred to Layer 3 Opportunity) |
| 30 | compression_is_state | ENFORCED | ENFORCED | ENFORCED | `VolatilityEngine.update_bar`, `VolatilityState` enum |
| 31 | static_ema_crossover_not_core | ENFORCED | ENFORCED | ENFORCED | `StructureEngine.process_bar` V_local displacement |
| 32 | fixed_fractals_not_core_structure | ENFORCED | ENFORCED | ENFORCED | `StructureEngine.process_bar` adaptive swing magnitude |
| 33 | fixed_fibonacci_not_constitutional | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/invariants.yaml`, `test_fibonacci_independence_principle` (Deferred to Layer 2) |
| 34 | fixed_candle_count_not_constitutional | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/invariants.yaml`, `test_candle_count_independence_principle` (Deferred to Layer 2) |
| 35 | structural_stops_primary | ENFORCED | ENFORCED | ENFORCED | `StructureEngine.get_structural_stop_candidate` |
| 36 | finite_lifetime_ttl | INTEGRATION_VERIFIED | INTEGRATION_VERIFIED | INTEGRATION_VERIFIED | `TradeDecision.is_authorized` TTL validation |
| 37 | portfolio_currency_and_correlation_aware | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/invariants.yaml` (Deferred to Layer 4 Portfolio) |
| 38 | account_feasibility_checked | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/invariants.yaml` (Deferred to Layer 4 Risk) |
| 39 | configuration_versioned_and_reproducible | ENFORCED | ENFORCED | ENFORCED | `EffectiveConfiguration` SHA256 canonical identity |
| 40 | reconciliation_completes_before_auth | ENFORCED | ENFORCED | ENFORCED | `RecoveryEngine.complete_recovery_with_evidence` |
| 41 | research_tests_information_value | SPECIFIED_ONLY | SPECIFIED_ONLY | SPECIFIED_ONLY | `spec/invariants.yaml` (Deferred to Layer 8 Research) |
| 42 | constitutional_rules_never_optimized | ENFORCED | ENFORCED | ENFORCED | `AuthorityMatrix.verify_capability` fail-closed check |

---

## Status Totals Summary

| Category | Phase 1 Baseline | Phase 2 Claimed | Phase 2 Verified |
|---|---|---|---|
| **ENFORCED** | 19 | 19 | 19 |
| **INTEGRATION_VERIFIED** | 7 | 7 | 7 |
| **SPECIFIED_ONLY** | 16 | 16 | 16 |
| **TOTAL** | 42 | 42 | 42 |

---

## Status Promotions

None. No invariant was prematurely promoted from SPECIFIED_ONLY to ENFORCED or INTEGRATION_VERIFIED without executable production-path implementation code.

---

## Status Downgrades / False Claim Corrections

### False Claim Correction 1: Invariant Specification Tests vs Production Path Enforcement
- **Invariants Affected:** 2 (`strategy_engines_no_direct_orders`), 3 (`pde_cannot_call_ordersend`), 4 (`flow_cannot_open_position`), 33 (`fixed_fibonacci_not_constitutional`), 34 (`fixed_candle_count_not_constitutional`).
- **Correction:** Clarified that adding specification consistency tests in `tests/test_phase2_spec_reconciliation.py` proves specification parity, but does NOT constitute production-path runtime enforcement. These invariants remain correctly classified as `SPECIFIED_ONLY` with `production_path: []` until Phase 2 Layer 2 production behavioral engines are implemented.
