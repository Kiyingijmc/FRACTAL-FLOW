# FRACTAL-FLOW Phase-0 Forensic Remediation Status Report

**Date:** 2026-10-01
**Remediation Branch:** `phase-0-forensic-remediation-20261001-c23ceeb4`
**Base Commit SHA:** `c23ceeb4be1ca67a72dfaee4e2a0d035e6af2ca1`

---

## 1. Context & Scope

Following the Phase-0 main branch closure merge (`c23ceeb4`), an independent forensic audit identified findings across numerical precision, persistence compatibility, risk authority, lineage verification, market context authority, entry contracts, invariant evidence integrity, simulator alignment, state machine verification, documentation reconciliation, and CI policy hardening.

This report records the complete forensic remediation pass executed on branch `phase-0-forensic-remediation-20261001-c23ceeb4` without altering historical reports or modifying the frozen Pass-4.2 authority and persistence surface.

---

## 2. Document & Spec Parity Reconciliation

- **Authority Matrix Alignment (D-038)**: Reconciled Opportunity Engine authority in `docs/02_ENGINE_CONTRACTS.md` to specify `Opportunity: Invalidates parent = No`, matching `docs/08_OPPORTUNITY_ENGINE.md` and `docs/DECISION_LOG.md`.
- **Lineage Terminology (D-035)**: Confirmed lineage chain hierarchy expansion including `MICRO_PULLBACK` and `OPPORTUNITY` across `spec/lineage.yaml`, `src/fractal_flow/domain/lineage.py`, and `tests/test_lineage.py`.
- **Entry Model Specifications**: Reconciled entry model documentation with active implementation in `src/fractal_flow/domain/entry.py` and `spec/entry_models.yaml`.
- **Historical Report Integrity**: Maintained all previous audit reports in `docs/reports/` as immutable historical records. This report serves as the living current status report for Phase-0 remediation.

---

## 3. Work Package Summary

- **WP 1 & 2 (Decimal Domain Closure & Guard Expansion)**: Converted financial units (`Price`, `PricePips`, `PriceDistance`, `Points`, `Volume`, `PositiveCurrencyAmount`, `SignedCurrencyAmount`) in `units.py` and `BrokerConstraints` in `broker.py` to exact `Decimal` types. Expanded `test_decimal_guard.py` AST guard to check all domain, simulation, and config files for unauthorized floats in financial fields.
- **WP 3 & 4 (Risk Ledger & Single Risk Authority)**: Enhanced `OpportunityRiskLedger` in `risk_ledger.py` with active reference-tracked reservation lifecycle (`RESERVE`, `ALLOCATE`, `CONSUME`, `COMMIT`, `RELEASE`, `ROLLBACK`, `EXPIRE`, `CANCEL`). Consolidated risk decisions onto `OpportunityRiskLedger` as the single authoritative source of truth.
- **WP 5 & 8 (Authorization Gate & Entry Contract)**: Closed `TradeDecision.is_authorized()` in `models.py` with fail-closed checks across news lockdown, risk state, portfolio state, arbitration result, TTL expiration, tradeability, and positive risk/size constraints.
- **WP 6 & 7 (Lineage & MURG Authority Closure)**: Enhanced `Lineage` in `lineage.py` with independent parent object state and version verification (`authoritative_parent`), blocking self-asserted parent validity. Verified MURG `ActiveMarketContext` boundaries and added adversarial tests proving fabricated market context fails closed.
- **WP 9 & 10 (Decimal ↔ Persistence Compatibility & Immutability)**: Implemented canonical persistence adapter in `src/fractal_flow/persistence/adapter.py` providing lossless Decimal conversion, key sorting, canonical JSON formatting, and SHA-256 fingerprinting for Decimal-bearing domain dataclasses without modifying frozen Pass-4.2 persistence files.
- **WP 11 & 13 (Invariant Evidence Integrity & State-Machine Evidence)**: Enhanced `test_42_invariants.py` with mechanical AST evidence validation that parses referenced test files, resolves function symbols, and verifies pytest-collectible test functions exist. Verified state machine parity and fail-closed transitions in `test_states.py` and `test_spec_parity.py`.
- **WP 12 (Simulator Contract Alignment)**: Aligned `DeterministicBrokerSimulator` (`arm_entry_plan`, `process_price_tick`) with production authorization invariants in `simulator.py`, ensuring plans with news lockdown, risk halt, tradeability failures, or portfolio rejects cannot be armed or executed.
- **WP 14 & 15 (Documentation Reconciliation & CI / Ruff Hardening)**: Reconciled documentation contradictions, updated `pyproject.toml` to explicitly list protected Pass-4.2 files rather than broad wildcards, and verified strict linting and mypy typing across active code.
