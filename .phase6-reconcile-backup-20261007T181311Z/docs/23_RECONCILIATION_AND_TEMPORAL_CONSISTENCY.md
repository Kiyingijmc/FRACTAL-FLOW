# FRACTAL FLOW — DOC 23: RECONCILIATION & TEMPORAL CONSISTENCY SPECIFICATION
Version: 1.0
Status: Pass 4.2 Complete Specification

---

## 1. Executive Summary & Temporal Consistency Rules

Reconciliation and Temporal Consistency form the execution safety boundary for FRACTAL FLOW.

Temporal Invariants Enforced:
- `created_at <= updated_at`
- `occurred_at <= recorded_at`
- `source_timestamp <= event_timestamp <= processing_timestamp`
- `last_seen >= source_timestamp`
- `valid_until >= last_seen`

---

## 2. Recovery State Machine & Strategic Execution Gating

System Recovery Lifecycle:
`NORMAL -> RECOVERY_REQUIRED -> RECOVERING -> RECONCILING -> RECOVERY_COMPLETE / SAFE`

During `RECOVERY_REQUIRED`, `RECOVERING`, and `RECONCILING`, strategic authorization is strictly disabled (`can_authorize_strategic_action() == False`).

---

## 3. Reconciliation Mismatch Classifications

- `MATCH`: Local intent and broker state match completely.
- `LOCAL_ONLY`: Execution intent exists locally but no corresponding order or position exists on the broker. Resolves safely to `EXEC_REJECTED`.
- `BROKER_ONLY`: Position or order exists on the broker without local intent records. Enters `ORPHANED_BROKER` quarantine.
- `STATE_MISMATCH`: Execution state differs between local tracking and broker truth. Broker state overrides local tracking.
- `VOLUME_MISMATCH`: Local volume differs from broker deal/position volume.
