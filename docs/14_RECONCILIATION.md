# ORPHAN LIFECYCLE & RECONCILIATION ENGINE
Version 1.0

## 1. Purpose

Recover safely from:
- restart
- crash
- disconnect
- duplicate responses
- partial execution
- state loss
- broker/internal divergence

## 2. Object contract

Every important object:
object_id
parent_id
root_id
state
version
created_at
updated_at
owner
symbol
timeframe
status
expiry
last_seen
confidence

## 3. Lineage

ROOT
→ REGIME
→ SETUP
→ PRIMARY PULLBACK
→ SECONDARY PULLBACK
→ SIGNAL
→ ORDER
→ POSITION
→ TRADE
→ PARTIAL/RUNNER/MANAGEMENT

## 4. Orphan lifecycle

ACTIVE
→ SUSPECTED_ORPHAN
→ RECONCILING

Then:
REATTACHED
RECOVERED
EXPIRED
QUARANTINED

No immediate deletion.

## 5. Orphan categories

- orphan trade
- orphan order
- orphan pullback
- orphan signal
- orphan runner
- orphan setup
- orphan regime
- orphan TTL state
- orphan trailing state

## 6. Safety rules

Child cannot act without valid parent.

Orphaned signal:
NEVER EXECUTE

Orphaned order:
reconcile before cancellation/finalization

Orphaned position:
protectively manage while lineage is reconstructed

Uncertain object:
cannot create new exposure

Quarantine:
no strategic decisions
protective management remains active

## 7. Restart sequence

1. load persistent state
2. query broker positions
3. query broker pending orders
4. query recent broker history
5. match broker/internal objects
6. reconstruct lineage
7. mark unmatched objects
8. quarantine uncertain objects
9. restore protection
10. enable strategy only after reconciliation complete

Invariant:
RECONCILIATION_COMPLETE → STRATEGY_ALLOWED

## 8. Confidence of reconstructed state

100% authoritative
90% reconstructed
70% partial
40% uncertain
0% invalid

Uncertain cannot create exposure.

## 9. MT5 reconciliation

Use:
- position identity
- order history
- deal history
- timestamps
- symbols
- volumes
- prices
- magic/comment/correlation identifiers where available
- internal idempotency keys

Do not assume a broker identifier alone is enough for full lineage.

## 10. Event sourcing

Events:
SETUP_CREATED
PULLBACK_CREATED
PULLBACK_UPDATED
SIGNAL_CREATED
SIGNAL_EXPIRED
ORDER_SUBMITTED
ORDER_ACCEPTED
ORDER_REJECTED
ORDER_PARTIALLY_FILLED
ORDER_FILLED
POSITION_OPENED
POSITION_MODIFIED
PARTIAL_CLOSED
RUNNER_CREATED
SL_MOVED
TP_MOVED
TTL_UPDATED
TRADE_DECAY_STARTED
TRADE_EXPIRED
POSITION_CLOSED

Add:
NEWS_STATE_CHANGED
RISK_STATE_CHANGED
CONFIG_CHANGED
RECONCILIATION_STARTED
RECONCILIATION_COMPLETED
ORPHAN_DETECTED
ORPHAN_REATTACHED
QUARANTINE_ENTERED
QUARANTINE_RELEASED

## 11. Protective continuity

Protection must be restored before strategy reactivation.

If protection cannot be confidently restored:
- quarantine
- reduce/close according to emergency policy
- do not resume strategy

## 12. Configuration reconciliation

If configuration changed while offline/news:
- use latest valid version
- do not overwrite with stale snapshots
- preserve per-trade configuration lineage
