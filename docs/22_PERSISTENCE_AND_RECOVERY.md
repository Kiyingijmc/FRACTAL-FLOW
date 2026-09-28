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
