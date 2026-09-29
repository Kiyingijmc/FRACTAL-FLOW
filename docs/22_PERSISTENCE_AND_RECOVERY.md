# FRACTAL FLOW — DOC 22: PERSISTENCE, RECOVERY & CRASH SAFETY SPECIFICATION
Version: 1.0
Status: Pass 4.2 Complete Specification

---

## 1. Executive Summary & Persistence Architecture

The FRACTAL FLOW Persistence Engine provides crash-safe, durable, and auditable storage for state-changing events, execution intents, risk ledgers, and aggregate snapshots.

Persistence Architecture:
```
EVENT JOURNAL (Append-only)
    ↓
DURABLE EXECUTION INTENTS & IDEMPOTENCY FINGERPRINTS
    ↓
RISK LEDGER (Exact Decimal accounting)
    ↓
SNAPSHOT ENGINE (Checksum verification & deterministic replay)
    ↓
RECOVERY & RECONCILIATION ENGINE
    ↓
RUNTIME STATE
```

---

## 2. Event Journal & Monotonic Aggregate Versioning

- **Append-only Journal:** Every state-changing event is recorded with a global sequence number, UTC timestamps, and SHA-256 record checksum.
- **Monotonic Sequence Enforcement:** Aggregate events enforce strictly sequential versions (`incoming == current + 1`). Version gaps or duplicates raise `InvalidEventVersionException`.
- **Integrity Validation:** Corrupted records raise `JournalCorruptionException` upon startup loading.

---

## 3. Durable Execution Intents & Idempotency Fingerprints

- **Request Fingerprinting:** `DurableExecutionIntentRepository` generates SHA-256 fingerprints across `symbol`, `side`, `requested_volume`, `entry_price`, `sl`, `decision_id`, `effective_config_id`, and `lineage_version`.
- **Idempotency Protection:** Re-submitting an intent with the same key returns the existing state without creating duplicate orders. Submitting conflicting request parameters under the same idempotency key raises `IdempotencyConflictException`.

---

## 4. Opportunity Risk Ledger

- **Exact Decimal Accounting:** `OpportunityRiskLedger` maintains exact Decimal balances for `total_risk`, `reserved_risk`, `allocated_risk`, and `consumed_risk`.
- **Fail-Closed Protection:** Accounting violations or negative remaining balances raise `AccountingInvariantException` rather than silently clamping numbers.

---

## 5. Crash Recovery & Broker Reconciliation Engine

- **Recovery State Machine:** Manages `NORMAL -> RECOVERY_REQUIRED -> RECOVERING -> RECONCILING -> RECOVERY_COMPLETE / SAFE`.
- **Strategic Execution Gating:** `RecoveryEngine.can_authorize_strategic_action()` returns `False` during system restart until broker reconciliation is complete.
- **Authoritative Reconciliation:** `ReconciliationEngine` queries authoritative broker orders/positions to resolve `EXEC_UNKNOWN` states cleanly (`MATCH`, `LOCAL_ONLY`, `BROKER_ONLY`, `STATE_MISMATCH`).

---

## 6. Pass 4.2 Authority Provenance & Authority Root Hardening Architecture

- **Singular Production Authority Root Anchor:** Production authority is anchored strictly via `TrustedRuntimeBootstrap.bootstrap_production_runtime()`. Public constructors (`AuthorityBootstrap()`, `AuthorityDomain()`, `TrustedRuntimeAuthority()`) construct non-production domains (`is_production=False`) that fail closed at the `RecoveryEngine` strategic recovery gate.
- **Domain-Scoped Capabilities & Object Serialization Lock:** `ProducerCapability`, `ValidatorCapability`, `AuthorityDomain`, `TrustedRuntimeBootstrap`, `SealedObservation`, `_AuthorityToken`, and `_ReconciliationAuthorityStamp` carry immutable `authority_domain_id` attributes. Direct instantiation, copy/deepcopy, or pickling/unpickling serialization attempts are prohibited and fail closed with `AuthorityError`.
- **Producer Domain Registration Enforcement:** Subsystem validators (`JournalRecoveryValidator`, `SnapshotRecoveryValidator`, `RiskLedgerRecoveryValidator`, `IntentRecoveryValidator`, `ConfigurationValidator`, `ProtectiveMonitoringValidator`) verify that the live producer instance is explicitly registered within the domain (`is_registered_producer`), rejecting unregistered live subsystem objects.
- **Unforgeable Capability Issuance:** `ProducerCapability` and `ValidatorCapability` objects require internal issuance verification (`_issuance_key`). Direct instantiation, copy/deepcopy, or serialization forgery is blocked fail-closed.
- **Exact Validator Role Binding:** Validator capabilities are bound to exact subsystem validator roles (`JOURNAL_RECOVERY_VALIDATOR`, `SNAPSHOT_RECOVERY_VALIDATOR`, `RISK_LEDGER_RECOVERY_VALIDATOR`, `INTENT_RECOVERY_VALIDATOR`, `BROKER_RECONCILIATION_VALIDATOR`, `CONFIGURATION_VALIDATOR`, `PROTECTIVE_MONITORING_VALIDATOR`). Capability transplantation across validator identities is rejected.
- **Sealed Subsystem Observations:** All seven recovery subsystems produce `SealedObservation`s signed with role-scoped `ProducerCapability` keys. Raw strings, raw booleans, duck-typed objects, or fake instances cannot establish authority.
- **Broker Query & Stamp Provenance:** `BrokerQueryResult` instantiation claiming `FOUND` or `NOT_FOUND_AUTHORITATIVE` requires a verified `SealedObservation` from `AuthoritativeBrokerAdapter`. `ReconciliationReport` contains a `_ReconciliationAuthorityStamp` cryptographically binding `authority_domain_id`, `engine_id`, `session_id`, `broker_observation_digest`, `query_timestamp`, `temporal_boundary`, and `report_digest`.
- **Deep Immutability & Reversal Accounting:** `OrphanRecord` uses recursive `_deep_freeze()` on nested mappings, tuples, and sets. `ReconciliationEngine` enforces formal `REVERSAL` deal transition accounting (closing prior exposure + opening opposite exposure, over-close detection, and side matching).
