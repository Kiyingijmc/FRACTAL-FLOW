# FRACTAL FLOW — PHASE 1 INVARIANT MATRIX

| ID | STATUS | ACTUAL ENFORCEMENT | TEST | LIMITATION |
| :--- | :--- | :--- | :--- | :--- |
| 1 | INTEGRATION_VERIFIED | Market -> DataQuality -> Volatility -> Structure pipeline | `tests/phase1d/test_future_mutations.py::test_1_future_price_spike` | Evaluates multi-engine pipeline across M1 boundaries |
| 2 | ENFORCED | Phase 4 authority boundary | `tests/test_phase4_foundation.py::test_confidence_cannot_authorize_failed_gate` | Strategy analysis cannot authorize a failed mandatory gate |
| 3 | ENFORCED | Phase 4 authority boundary | `tests/test_phase4_foundation.py::test_confidence_cannot_authorize_failed_gate` | PDE has no execution authorization path |
| 4 | ENFORCED | Phase 4 authority boundary | `tests/test_phase4_foundation.py::test_confidence_cannot_authorize_failed_gate` | Flow has no execution authorization path |
| 5 | SPECIFIED_ONLY | Layer 4 Risk engine specification | None | Requires Layer 4 Risk implementation |
| 6 | SPECIFIED_ONLY | Layer 4 Portfolio arbitration specification | None | Requires Layer 4 Portfolio implementation |
| 7 | ENFORCED | TradeDecision authorization fail-closed strategy check | `tests/test_invariant_enforcement.py::test_invariant_7_execution_cannot_reinterpret_strategy` | Execution cannot reinterpret strategy parameters |
| 8 | SPECIFIED_ONLY | Layer 5 News Shield specification | None | Requires Layer 5 News Shield implementation |
| 9 | ENFORCED | StateEnvelope constructor and TradeDecision.is_authorized check | `tests/test_invariant_enforcement.py::test_invariant_9_confidence_cannot_override_validity` | High score cannot bypass boolean validity |
| 10 | ENFORCED | TradeDecision.is_authorized mandatory checks | `tests/test_invariant_enforcement.py::test_invariant_10_mandatory_validity_gates_unbypassable` | Fail-closed evaluation |
| 11 | ENFORCED | Lineage.validate_child_action check | `tests/test_lineage.py::test_lineage_exact_version_accepted` | Structural lineage graph verification |
| 12 | ENFORCED | Lineage constructor fields | `tests/test_lineage.py::test_child_carries_lineage_ids` | Mandatory root/parent fields |
| 13 | ENFORCED | Lineage.validate_child_action strict version check | `tests/test_lineage.py::test_stale_parent_version_rejected` | Fail-closed parent version check |
| 14 | ENFORCED | Lineage.validate_child_action root_id/parent_id check | `tests/test_lineage.py::test_illegal_lineage_edge_skipped_parent_rejected` | Orphaned signals rejected |
| 15 | INTEGRATION_VERIFIED | ReconciliationEngine.reconcile_broker_wide multi-directional discovery | `tests/test_persistence_adversarial.py::test_reconciliation_and_recovery_idempotency_stability` | Broker reconciliation gate |
| 16 | INTEGRATION_VERIFIED | ReconciliationEngine.reconcile_broker_wide multi-directional discovery | `tests/test_persistence_adversarial.py::test_reconciliation_and_recovery_idempotency_stability` | Protective position management |
| 17 | ENFORCED | TradeDecision.is_authorized checks | `tests/test_provenance_authorization.py::test_news_lockdown_blocks_trade_decision_authorization` | Exposure forbidden on uncertain state |
| 18 | INTEGRATION_VERIFIED | DeterministicBrokerSimulator.modify_stop_loss independent of strategy | `tests/test_simulator.py::test_broker_simulator_stop_loss_tighten_ratchet` | Independent simulator ratchet |
| 19 | ENFORCED | DeterministicBrokerSimulator.modify_stop_loss ratchet validation | `tests/test_simulator.py::test_broker_simulator_stop_loss_tighten_ratchet` | Stops cannot be loosened |
| 20 | ENFORCED | TradeDecision.is_authorized checks news_state == 'NEWS_LOCKDOWN' | `tests/test_invariants.py::test_invariant_news_lockdown_blocks_strategic_exposure` | News lockdown veto |
| 21 | SPECIFIED_ONLY | Layer 5 News Engine specification | None | Requires Layer 5 implementation |
| 22 | SPECIFIED_ONLY | Layer 5 News Engine specification | None | Requires Layer 5 implementation |
| 23 | INTEGRATION_VERIFIED | CausalTestFramework no-lookahead future mutation assertions | `tests/phase1d/test_future_mutations.py::test_1_future_price_spike` | Tested across 12 future mutations |
| 24 | INTEGRATION_VERIFIED | TradeDecision quote_timestamp snapshot | `tests/test_provenance_authorization.py::test_provenance_snapshots_preserved` | Quote timestamp audit |
| 25 | ENFORCED | Lineage directed graph verifies legal hierarchy | `tests/test_lineage.py::test_legal_lineage_edges_all_valid` | M1 micro pullbacks non-primary |
| 26 | ENFORCED | Explicit Phase 4 timeframe mapping and migration | `tests/test_phase4_foundation.py::test_timeframe_migration_is_explicit_and_bounded` | Primary is above execution normally; M1 is an explicit migration floor |
| 27 | ENFORCED | Lineage directed graph verifies legal hierarchy | `tests/test_lineage.py::test_legal_lineage_edges_all_valid` | Explicit micro/subordinate classification |
| 28 | SPECIFIED_ONLY | Layer 4 Portfolio Arbitration specification | None | Requires Layer 4 implementation |
| 29 | ENFORCED | LiquiditySweepModifier | `tests/test_phase4_foundation.py::test_opportunity_identity_is_deterministic_and_sweep_is_modifier` | Sweeps cannot form standalone strategy families |
| 30 | ENFORCED | VolatilityState enum and StateEnvelope validation | `tests/test_spec_parity.py::test_states_exact_parity` | Compression is state |
| 31 | ENFORCED | StructureEngine adaptive swing reversal magnitude evaluation | `tests/phase1f/test_structure_transitions.py::test_adaptive_swing_reversal_magnitude_transitions` | Reversal magnitude displacement |
| 32 | ENFORCED | StructureEngine volatility-normalized displacement evaluation | `tests/phase1h/test_invariant_failure_modes.py::test_invariant_32_fixed_three_candle_fractals_not_used_in_structure` | No fixed N-candle fractals |
| 33 | ENFORCED | PDE source-level semantic guard excludes fixed Fibonacci thresholds | tests/phase2v3/test_phase2_substrate_stabilization.py::test_pde_pullback_rules_exclude_fibonacci_and_fixed_candle_thresholds | Non-constitutional Fibonacci semantics are rejected |
| 34 | ENFORCED | PDE source-level semantic guard excludes fixed candle-count pullback rules | tests/phase2v3/test_phase2_substrate_stabilization.py::test_pde_pullback_rules_exclude_fibonacci_and_fixed_candle_thresholds | Bar count remains lifetime-only, not pullback semantics |
| 35 | ENFORCED | StructureEngine.get_structural_stop_candidate protected level anchoring | `tests/phase1h/test_invariant_failure_modes.py::test_invariant_35_structural_stops_are_primary` | Primary protected level anchor |
| 36 | INTEGRATION_VERIFIED | TradeDecision.ttl_ns positive validation | `tests/test_provenance_authorization.py::test_news_lockdown_blocks_trade_decision_authorization` | Positive TTL requirement |
| 37 | SPECIFIED_ONLY | Layer 4 Portfolio Arbitration Engine specification | None | Requires Layer 4 implementation |
| 38 | SPECIFIED_ONLY | Layer 4 Risk Engine account feasibility contract | None | Requires Layer 4 Risk implementation |
| 39 | ENFORCED | EffectiveConfiguration SHA256 identity calculation | `tests/test_units_broker.py::test_effective_configuration_reproducible_identity` | Reproducible configuration identity |
| 40 | ENFORCED | RecoveryEngine.complete_recovery_with_evidence evidence gate validation | `tests/test_persistence_adversarial.py::test_reconciliation_and_recovery_idempotency_stability` | Reconciliation before auth |
| 41 | SPECIFIED_ONLY | Layer 8 Research Engine specification | None | Requires Layer 8 implementation |
| 42 | ENFORCED | AuthorityMatrix fail-closed checks | `tests/test_invariants.py::test_invariant_42_constitutional_rules_never_optimized` | Fail-closed authority enforcement |
