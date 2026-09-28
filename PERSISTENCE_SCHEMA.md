# FRACTAL FLOW — PERSISTENCE SCHEMA & EXECUTION INTENT SPECIFICATION
Version: 1.0
Status: Phase 1 Canonical Storage Specification

This document specifies the relational/key-value database schema, event-sourcing append log, and execution intent mapping required for state integrity, idempotency, restart recovery, and unknown execution handling.

---

## 1. Event Store Schema (`events_log`)

Append-only event store for state reconstruction and causal replay:

```sql
CREATE TABLE events_log (
    event_id TEXT PRIMARY KEY,           -- UUIDv4
    event_type TEXT NOT NULL,            -- e.g. PULLBACK_STATE_CHANGED, DECISION_AUTHORIZED
    aggregate_type TEXT NOT NULL,        -- e.g. PULLBACK, OPPORTUNITY, POSITION
    aggregate_id TEXT NOT NULL,          -- UUIDv4 object_id
    root_id TEXT NOT NULL,               -- UUIDv4 root_id
    parent_id TEXT,                      -- UUIDv4 parent_id
    version INTEGER NOT NULL,            -- Monotonic version counter
    payload JSON NOT NULL,               -- Full event JSON payload
    timestamp INTEGER NOT NULL,          -- Nanoseconds since UTC epoch
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_aggregate ON events_log(aggregate_id, version);
CREATE INDEX idx_events_root ON events_log(root_id);
```

---

## 2. Execution Intent & Idempotency Schema (`execution_intents`)

Guarantees execution idempotency and resolves "unknown execution" states after disconnects:

```sql
CREATE TABLE execution_intents (
    intent_id TEXT PRIMARY KEY,          -- UUIDv4 execution intent ID
    decision_id TEXT UNIQUE NOT NULL,    -- Linked TradeDecision ID
    opportunity_id TEXT NOT NULL,        -- Linked Opportunity ID
    client_order_id TEXT UNIQUE NOT NULL,-- Unique broker submission token
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,                  -- BUY or SELL
    requested_volume REAL NOT NULL,      -- Lot size
    entry_price REAL NOT NULL,
    structural_sl REAL NOT NULL,
    tp_plan JSON NOT NULL,
    decision_lease_until INTEGER NOT NULL, -- Lease expiration timestamp
    status TEXT NOT NULL,                -- CREATED, SUBMITTED, CONFIRMED, UNKNOWN, REJECTED, EXPIRED
    broker_ticket INTEGER,               -- MT5 order ticket if confirmed
    error_code INTEGER,                  -- MT5 return code
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX idx_intents_client_order ON execution_intents(client_order_id);
```

### 2.1 Execution Idempotency Rule
**Invariant**: An execution intent in `UNKNOWN` status MUST NEVER be re-submitted. Reconciliation MUST first query broker history/open orders by `client_order_id` to confirm whether the broker placed or rejected the order.

---

## 3. Position Reconciliation Schema (`broker_positions`)

```sql
CREATE TABLE broker_positions (
    position_ticket INTEGER PRIMARY KEY, -- MT5 Position Ticket ID
    symbol TEXT NOT NULL,
    type TEXT NOT NULL,                  -- BUY or SELL
    volume REAL NOT NULL,
    open_price REAL NOT NULL,
    current_sl REAL NOT NULL,
    current_tp REAL,
    client_order_id TEXT,               -- Reconstructed client order ID
    internal_position_id TEXT,           -- Mapped local Position UUID
    quarantine_status TEXT NOT NULL,     -- RECON_NORMAL, QUARANTINED_WITH_VALID_PROTECTION, QUARANTINED_WITHOUT_VALID_THESIS
    last_reconciled_at INTEGER NOT NULL
);
```

---

## 4. Quarantined Position Exit Architecture (Refined D-033)

When a position is discovered during restart without matching local state lineage:

### Category A: `QUARANTINED_WITH_VALID_PROTECTION`
- **Condition**: Structural high/low swing anchors are verified on market chart and existing stop loss is intact.
- **Action**: Transferred to Protective Manager; trails a tight structural/time stop until flat. New strategic exposure forbidden.

### Category B: `QUARANTINED_WITHOUT_VALID_THESIS`
- **Condition**: Structural lineage cannot be reconstructed or protected swing anchors are damaged/missing.
- **Action**: Broker hard stop remains authoritative. No structural trailing thesis is invented. Emits P0 CRITICAL_EMERGENCY alert for immediate operator review. Zero strategic action permitted.
