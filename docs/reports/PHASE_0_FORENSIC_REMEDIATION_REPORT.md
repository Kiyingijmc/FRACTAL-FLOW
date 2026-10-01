# FRACTAL-FLOW Phase-0 Forensic Remediation Status Report

**Date:** 2026-10-01
**Remediation Branch:** `phase-0-forensic-remediation-20261001-c23ceeb4-15105238367861304661`
**Base Commit SHA:** `c23ceeb4be1ca67a72dfaee4e2a0d035e6af2ca1`

---

## 1. Context & Scope

Following the Phase-0 main branch closure merge (`c23ceeb4`), an independent forensic audit identified findings across numerical precision, persistence compatibility, risk authority, lineage verification, market context authority, entry contracts, invariant evidence integrity, simulator alignment, state machine verification, documentation reconciliation, event deep immutability, and CI policy hardening.

This report records the complete forensic remediation pass executed on branch `phase-0-forensic-remediation-20261001-c23ceeb4-15105238367861304661` without altering historical reports or modifying the frozen Pass-4.2 authority and persistence surface.

---

## 2. Document & Spec Parity Reconciliation

- **Authority Matrix Alignment (D-038)**: Reconciled Opportunity Engine authority in `docs/02_ENGINE_CONTRACTS.md` to specify `Opportunity: Invalidates parent = No`, matching `docs/08_OPPORTUNITY_ENGINE.md` and `docs/DECISION_LOG.md`.
- **Lineage Terminology (D-035)**: Confirmed lineage chain hierarchy expansion including `MICRO_PULLBACK` and `OPPORTUNITY` across `spec/lineage.yaml`, `src/fractal_flow/domain/lineage.py`, and `tests/test_lineage.py`.
- **Entry Model Specifications**: Reconciled entry model documentation with active implementation in `src/fractal_flow/domain/entry.py` and `spec/entry_models.yaml`.
- **Historical Report Integrity**: Maintained all previous audit reports in `docs/reports/` as immutable historical records. This report serves as the living current status report for Phase-0 remediation.

---

## 3. Work Package Summary

- **WP 1 & 2 (Decimal Domain Closure & Guard Expansion)**: Converted financial units (`Price`, `PricePips`, `PriceDistance`, `Points`, `Volume`, `PositiveCurrencyAmount`, `SignedCurrencyAmount`) in `units.py` and `BrokerConstraints` in `broker.py` to exact `Decimal` types. Expanded `test_decimal_guard.py` AST guard to check all domain, simulation, and config files for unauthorized floats in financial fields.
- **WP 3, 4 & 5 (Risk Authority Unification & Reservation Lifecycle)**: Enhanced `OpportunityRiskLedger` in `risk_ledger.py` with active reference-tracked reservation lifecycle (`RESERVE`, `ALLOCATE`, `CONSUME`, `COMMIT`, `RELEASE`, `ROLLBACK`, `EXPIRE`, `CANCEL`). Consolidated risk decisions onto `OpportunityRiskLedger` as the single authoritative source of truth.
- **WP 6, 7 & 8 (Central Authorization & MURG Authority)**: Closed `TradeDecision.is_authorized()` in `models.py` with fail-closed checks across news lockdown, risk state, portfolio state, arbitration result, TTL expiration, tradeability, and positive risk/size constraints.
- **WP 9 & 10 (Lineage Authority & Entry Orchestration)**: Enhanced `Lineage` in `lineage.py` with independent parent object state and version verification (`authoritative_parent`), blocking self-asserted parent validity. Verified MURG `ActiveMarketContext` entry analysis boundaries in `entry.py` and added adversarial tests proving fabricated market context or lineage fails closed.
- **WP 11, 12 & 13 (Decimal ↔ Persistence Compatibility & Immutability)**: Implemented canonical persistence adapter in `src/fractal_flow/persistence/adapter.py` providing lossless Decimal conversion, key sorting, canonical JSON formatting, and SHA-256 fingerprinting for Decimal-bearing domain dataclasses without modifying frozen Pass-4.2 persistence files.
- **WP 14 (Event Payload Deep Immutability)**: Enforced deep payload immutability for `Event` objects in `src/fractal_flow/domain/event.py` using `ImmutablePayloadDict` to prevent post-issuance modification of nested event payloads or reason codes.
- **WP 15 & 16 (Invariant Evidence Integrity & State-Machine Evidence)**: Enhanced `test_42_invariants.py` with mechanical AST evidence validation that parses referenced test files, resolves function symbols, and verifies pytest-collectible test functions exist. Verified state machine parity and fail-closed transitions in `test_states.py` and `test_spec_parity.py`.
- **WP 17 & 18 (Simulator Parity & Documentation Reconciliation)**: Aligned `DeterministicBrokerSimulator` (`arm_entry_plan`, `process_price_tick`) with production authorization invariants in `simulator.py`, ensuring plans with news lockdown, risk halt, tradeability failures, or portfolio rejects cannot be armed or executed.
- **WP 19 & 20 (CI Policy & Frozen Surface Verification)**: Reconciled documentation contradictions, updated `pyproject.toml` to explicitly list protected Pass-4.2 files rather than broad wildcards, and verified strict linting, mypy typing, and byte-for-byte identity of all 12 frozen Pass-4.2 files.

---

## 4. Frozen Surface SHA-256 Hashes (12 / 12 Match)

| File Path | SHA-256 Hash | Status |
| :--- | :--- | :--- |
| `src/fractal_flow/execution/recovery.py` | `11bbe931165fbf7aa5c5ee189b41675f971a8c75e905d5dc905a62ef3d3992d3` | **MATCH** |
| `src/fractal_flow/execution/reconciliation.py` | `3fc747460e7918cc74537209d10044c78596c04cb1ec5d79fdee03ac5d27339b` | **MATCH** |
| `src/fractal_flow/persistence/interfaces.py` | `0c07f5011d92d034cff54035eef844b14834679381952a9e45959ad3689fbf95` | **MATCH** |
| `src/fractal_flow/persistence/journal.py` | `e75a81ccfd8614da280801e1b1dc50f387e84ef7aff3175e05eb1801b1585d24` | **MATCH** |
| `src/fractal_flow/persistence/snapshot.py` | `3c2e39a5f9bde0524f90239cfc9debe731266617da8a459e4835314505c95009` | **MATCH** |
| `tests/test_pass_4_2_authority_graph_issuance_closure.py` | `58251fe758901187024b70d6d9bcee72e6c4cf86d438f7387d52d1000aab72ea` | **MATCH** |
| `tests/test_pass_4_2_authority_provenance_hardening.py` | `c247b44165a9f860482d0f4c69d29b07102b646b8a5ea8ba0d46dc9f5ae93ffc` | **MATCH** |
| `tests/test_pass_4_2_authority_root_closure.py` | `f05f8c4e57d6dea67bf0b1a373d2b632373d18070e8044e30739c84947a597e9` | **MATCH** |
| `tests/test_pass_4_2_forensic_authority_closure.py` | `10f131f41d6e3e9bbeaad77e6e2af1670c535ac7b21747217834fc8eed4c5c79` | **MATCH** |
| `tests/test_pass_4_2_production_authority_lifecycle_closure.py` | `ee9a4a963b9712e4694e793736dd84d442f47ea47c497be11b588e713b92cd6d` | **MATCH** |
| `tests/test_pass_4_2_production_bootstrap_boundary_closure.py` | `bc487a8db1ac32a3fd75095d0d3a963654bacc9e7a4597c91b0beae933830b17` | **MATCH** |
| `tests/test_persistence_adversarial.py` | `faca8ef05a7f1bb7f7f8349c616c4210241178447be59e2c1057dc7400d38b74` | **MATCH** |
