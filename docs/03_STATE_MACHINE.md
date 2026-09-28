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

Primary PDE States (PDEState):
PDE_NONE
→ PDE_IMPULSE
→ PDE_PULLBACK_CANDIDATE
→ PDE_PULLBACK_ACTIVE

Then:
PDE_WEAKENING
→ PDE_RESUMPTION_IN_PROGRESS
→ PDE_FOLLOW_THROUGH

Or:
PDE_STRENGTHENING
→ PDE_DEEPENING
→ PDE_INVALIDATED

Failed resumption:
PDE_RESUMPTION_FAILED

Resumption Sub-Lifecycle States (PDEResumptionState):
RESUMPTION_NONE
→ RECOVERY_CANDIDATE
→ RECOVERY_CONFIRMED
→ DISPLACEMENT_CANDIDATE
→ RESUMPTION_CONFIRMED

## 4. Structure lifecycle

SwingState:
SWING_NONE
→ SWING_CANDIDATE
→ SWING_CONFIRMED
→ SWING_PROTECTED
→ SWING_BROKEN

BreakState:
BREAK_NONE
→ BREAK_CANDIDATE
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

NewsState:
NEWS_NORMAL
→ NEWS_WATCH
→ NEWS_PREP
→ NEWS_LOCKDOWN
→ INITIAL_SHOCK
→ VOLATILITY_DISCOVERY
→ POST_NEWS_VALIDATION
→ RESTRICTED_REENTRY
→ NORMAL_REENTRY
→ NEWS_NORMAL

Extreme events may enter:
EXTENDED_PROTECTION

## 7. Trade lifecycle

ExecutionState:
EXEC_READY
→ EXEC_SUBMITTING
→ EXEC_SUBMITTED
→ EXEC_ACCEPTED
→ EXEC_PARTIAL
→ EXEC_FILLED

Execution failures/outcomes:
EXEC_REJECTED / EXEC_CANCELLED / EXEC_UNKNOWN / EXEC_RECONCILING

## 8. Position lifecycle

PositionLifecycleState:
POS_OPENING
→ POS_ACTIVE
→ POS_PROTECTED
→ POS_RUNNER
→ POS_DECAYING
→ POS_EXPIRING
→ POS_CLOSING
→ POS_CLOSED

PositionHealthState:
HEALTH_HEALTHY
HEALTH_STALLED
HEALTH_DAMAGED
HEALTH_INVALID
HEALTH_CRITICAL

## 9. TTL lifecycle

FRESH
→ AGING
→ DECAYING
→ STALE
→ EXPIRING
→ EXPIRED

## 10. Orphan lifecycle

ReconciliationState:
RECON_NORMAL
→ RECON_SUSPECTED_ORPHAN
→ RECON_RECONCILING

Outcomes:
RECON_RECOVERED
RECON_QUARANTINED

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
