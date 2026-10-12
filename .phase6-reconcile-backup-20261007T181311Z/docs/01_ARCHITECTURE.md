# SYSTEM ARCHITECTURE
Version 1.0

## 1. Layered architecture

### Layer 0 — Market/Data
Quotes, ticks, bars, spreads, session clock, calendar/news inputs, broker metadata.

### Layer 1 — Feature extraction
Volatility, displacement, efficiency, velocity, acceleration, structure measurements, spread/cost metrics.

### Layer 2 — State engines
Data Quality, Volatility, Structure, Flow Ownership, PDE, Regime, Role, Location, News, Risk.

### Layer 3 — Opportunity
Opportunity discovery, setup identity, opportunity space, tradeability.

### Layer 4 — Allocation
Portfolio arbitration, exposure limits, mode budgets, account feasibility.

### Layer 5 — Decision authorization
Unified TradeDecision and final gate verification.

### Layer 6 — Execution
MT5 order gateway, idempotency, broker response handling.

### Layer 7 — Position management
SL/TP, partials, runner, structural trailing, TTL, news protection.

### Layer 8 — Persistence/reconciliation
Event sourcing, snapshots, broker reconciliation, orphan lifecycle.

### Layer 9 — Research/visualization
Replay, feature store, labeling, calibration, walk-forward, TradingView.

## 2. Logical directory

/fractal_flow
├── core/
│   ├── state/
│   ├── events/
│   ├── lineage/
│   ├── configuration/
│   └── invariants/
├── strategy/
│   ├── data_quality/
│   ├── volatility/
│   ├── structure/
│   ├── flow/
│   ├── pde/
│   ├── regime/
│   ├── role/
│   ├── location/
│   ├── opportunity/
│   ├── tradeability/
│   ├── news/
│   ├── risk/
│   └── arbitration/
├── execution/
│   ├── mt5_gateway/
│   ├── execution/
│   ├── positions/
│   ├── reconciliation/
│   └── protection/
└── research/
    ├── replay/
    ├── feature_store/
    ├── labeling/
    ├── walk_forward/
    ├── calibration/
    └── adversarial/

## 3. Canonical timeframe mapping

4H: market environment
1H: directional state
30M: structural context
15M: primary opportunity/pullback
5M: confirmation
1M: execution

The mapping engine must be setup-aware and support migration of the active opportunity to lower timeframes after structural transition.

## 4. Parent-child graph

Every important object:
object_id
parent_id
root_id
version
state
timestamp
valid_until
owner
symbol
timeframe
status

Lineage must be persistent and reconstructable.

## 5. Strategic/protective separation

Strategic control:
- create opportunity
- open exposure
- add exposure
- re-enter
- flip

Protective control:
- preserve/ratchet SL
- reduce exposure
- enforce TTL
- emergency close
- news protection
- shutdown protection

Strategy may be disabled while protective management remains active.

## 6. Event-driven architecture

Canonical event types include:
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

News and reconciliation events extend the same event model.

## 7. State envelope

All state objects use a common envelope:
state_id
object_id
object_type
symbol
timeframe
root_id
parent_id
parent_version
state
previous_state
version
timestamp
valid_until
last_seen
confidence
confidence_class
reason_codes[]
configuration_version
data_version
feature_version
created_at
updated_at
authority

## 8. Decision lifecycle

CANDIDATE
→ VALIDATING
→ TRADEABILITY_CHECK
→ RISK_CHECK
→ PORTFOLIO_CHECK
→ ARBITRATION
→ AUTHORIZED
→ EXECUTION

Failure:
REJECTED + reason codes

## 9. Race safety

Immediately before execution:
1. read current state
2. verify parent version
3. verify required parent state
4. verify risk
5. verify portfolio
6. verify news
7. verify tradeability
8. verify broker readiness
9. submit

Any incompatible state change aborts/revalidates.

## 10. Configuration overlays

Effective configuration:
BASE CONFIG
→ SYMBOL PROFILE
→ SESSION PROFILE
→ MODE PROFILE
→ NEWS OVERLAY
→ EFFECTIVE CONFIGURATION

Version every layer. News overlay must be reversible without restoring stale configuration.

## 11. Failure containment

Uncertainty must propagate toward:
DEFER / REJECT / QUARANTINE

Never:
uncertainty → guessed direction → order.

## 12. Simplicity boundary

Complexity belongs inside engines and state machines. User-facing controls should remain understandable:
- mode
- symbol/session profile
- risk
- protection
- execution status
- opportunity status

Avoid cockpit-like exposure of every internal feature.
