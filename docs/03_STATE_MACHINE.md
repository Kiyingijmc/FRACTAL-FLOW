# STATE MACHINE
Version 1.0

## 1. Universal state envelope

StateEnvelope:
- state_id
- object_id
- object_type
- symbol
- timeframe
- root_id
- parent_id
- parent_version
- state
- previous_state
- version
- timestamp
- valid_until
- last_seen
- confidence
- confidence_class
- reason_codes[]
- configuration_version
- data_version
- feature_version
- created_at
- updated_at
- authority

## 2. Canonical high-level lifecycle

DATA_BOOT
→ DATA_VALIDATING
→ DATA_NORMAL

MARKET STATES
→ SETUP DISCOVERY
→ PULLBACK
→ OPPORTUNITY
→ VALIDATION
→ TRADEABILITY
→ RISK
→ PORTFOLIO
→ AUTHORIZATION
→ EXECUTION
→ POSITION
→ MANAGEMENT
→ CLOSED

## 3. Pullback lifecycle

NONE
→ IMPULSE
→ PULLBACK_CANDIDATE
→ PULLBACK_ACTIVE

Then:
WEAKENING
→ STRUCTURAL_RECOVERY
→ RESUMPTION_CANDIDATE
→ RESUMPTION_CONFIRMED
→ FOLLOW_THROUGH

Or:
STRENGTHENING
→ DEEPENING
→ FAILURE_RISK
→ INVALIDATED

Failed resumption:
FAILED_RESUMPTION

## 4. Structure lifecycle

SWING_CANDIDATE
→ SWING_CONFIRMED
→ SWING_PROTECTED
→ SWING_BROKEN

Break:
BREAK_CANDIDATE
→ BREAK_CONFIRMED
→ BREAK_ESTABLISHED

Or:
FAILED_BREAK

## 5. Opportunity lifecycle

DISCOVERED
→ VALIDATING
→ VALID
→ TRIGGER_READY
→ AUTHORIZED
→ EXECUTED

Degradation:
VALID
→ DEGRADED
→ INVALIDATED

Temporal:
VALID
→ STALE
→ EXPIRED

## 6. News lifecycle

NORMAL
→ NEWS_WATCH
→ NEWS_PREP
→ NEWS_LOCKDOWN
→ INITIAL_SHOCK
→ PRICE_DISCOVERY
→ POST_NEWS_VALIDATION
→ RESTRICTED_REENTRY
→ NORMAL_REENTRY
→ NORMAL

Extreme events may enter:
EXTENDED_PROTECTION

## 7. Trade lifecycle

CANDIDATE
→ VALIDATING
→ TRADEABILITY_CHECK
→ RISK_CHECK
→ PORTFOLIO_CHECK
→ ARBITRATION
→ AUTHORIZED
→ SUBMITTING
→ SUBMITTED
→ ACCEPTED
→ PARTIAL
→ FILLED

Execution failures:
REJECTED / CANCELLED / UNKNOWN / RECONCILING

## 8. Position lifecycle

OPENING
→ ACTIVE
→ PROTECTED
→ RUNNER
→ DECAYING
→ EXPIRING
→ CLOSING
→ CLOSED

Health overlay:
HEALTHY
STALLED
DAMAGED
INVALID
CRITICAL

## 9. TTL lifecycle

FRESH
→ AGING
→ DECAYING
→ STALE
→ EXPIRING
→ EXPIRED

## 10. Orphan lifecycle

ACTIVE
→ SUSPECTED_ORPHAN
→ RECONCILING

Outcomes:
REATTACHED
RECOVERED
EXPIRED
QUARANTINED

## 11. Data lifecycle

DATA_BOOT
→ DATA_VALIDATING
→ DATA_NORMAL

Failure branches:
DATA_DEGRADED
DATA_STALE
DATA_CORRUPTED
DATA_UNAVAILABLE

Any non-valid data state blocks new exposure.

## 12. Risk lifecycle

RISK_NORMAL
→ RISK_REDUCED
→ RISK_RESTRICTED
→ RISK_HALTED

Risk can recover only when the underlying condition recovers.

## 13. Arbitration

ALLOW
DEFER
MERGE
REJECT

MERGE is used when opportunities are economically/structurally equivalent and can be represented as one managed exposure rather than duplicated churn.

## 14. State transition requirements

Every transition records:
- previous state
- new state
- timestamp
- reason codes
- parent/root
- version
- configuration version
- feature/data version
- authority

Invalid transitions must fail closed.

## 15. Parent/version invalidation

A child that requires parent version N cannot execute if current parent version != N or required state is no longer satisfied.

At execution:
READ CURRENT STATE → VERIFY LINEAGE → VERIFY VERSION → VERIFY ALL GATES → SUBMIT

## 16. Strategy/protection separation

STRATEGY_OFFLINE may coexist with PROTECTION_ACTIVE.

Protection must remain capable of:
- maintaining SL
- reducing exposure
- closing unsafe positions
- enforcing TTL
- handling emergency conditions

## 17. Unknown execution

UNKNOWN is not equivalent to rejected.

Unknown execution state requires broker reconciliation before a new strategic action can assume the order did not happen.

## 18. Idempotency

Every execution intent requires a stable idempotency key. Duplicate requests must not create duplicate exposure.

## 19. Event sourcing

State transitions should be reconstructable from durable events plus snapshots.

Events include strategy, execution, position, news, risk, configuration and reconciliation events.
