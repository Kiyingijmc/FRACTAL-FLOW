# ENGINE CONTRACTS
Version 1.0

Every engine contract is:

ENGINE → Inputs → Derived Features → State → Transition Rules → Outputs → Parent Dependencies → Invalidations → Expiry → Authority → Events

## 1. Data Quality Engine

Inputs:
ticks, bars, timestamps, quote metadata, market-open state.

States:
DATA_BOOT
DATA_VALIDATING
DATA_NORMAL
DATA_DEGRADED
DATA_STALE
DATA_CORRUPTED
DATA_UNAVAILABLE

Outputs:
data confidence, tick age, bar age, missing bars, timestamp integrity, sequence integrity, spread/quote availability.

Invariant:
DATA != VALID → NEW_EXPOSURE FORBIDDEN.

## 2. Volatility Engine

States:
VOL_UNKNOWN
VOL_COMPRESSION
VOL_NORMAL
VOL_EXPANSION
VOL_EXTREME
VOL_COLLAPSE

Measurements:
local_vol
short_vol
session_vol
regime_vol
volatility_percentile
range_percentile
expansion_rate
contraction_rate
shock_score

It measures; it does not trade.

## 3. Structure Engine

Responsibilities:
adaptive swings, protected levels, structural breaks, failed breaks, reclaim.

States:
SWING_NONE
SWING_CANDIDATE
SWING_CONFIRMED
SWING_PROTECTED
SWING_BROKEN

Break:
BREAK_NONE
BREAK_CANDIDATE
BREAK_CONFIRMED
BREAK_ESTABLISHED
FAILED_BREAK

Structural integrity:
INTACT
DAMAGE_CANDIDATE
DAMAGE_CONFIRMED
STRUCTURE_BROKEN
RECLAIM_CANDIDATE
RECLAIM_CONFIRMED

Can invalidate parent state but cannot place orders.

## 4. Flow Ownership Engine

States:
UNKNOWN
LONG_EMERGING
LONG_DOMINANT
LONG_WEAKENING
BALANCED
CONTESTED
SHORT_EMERGING
SHORT_DOMINANT
SHORT_WEAKENING
TRANSITIONING

Measurements:
long strength
short strength
imbalance
momentum
efficiency
structural progression
persistence
confidence

Uses hysteresis to avoid noisy ownership flipping.

## 5. PDE

States (PDEState):
PDE_NONE
PDE_IMPULSE
PDE_PULLBACK_CANDIDATE
PDE_PULLBACK_ACTIVE
PDE_WEAKENING
PDE_STRENGTHENING
PDE_DEEPENING
PDE_RESUMPTION_IN_PROGRESS
PDE_FOLLOW_THROUGH
PDE_RESUMPTION_FAILED
PDE_INVALIDATED

Resumption States (PDEResumptionState):
RESUMPTION_NONE
RECOVERY_CANDIDATE
RECOVERY_CONFIRMED
DISPLACEMENT_CANDIDATE
RESUMPTION_CONFIRMED

PDE describes market behavior. It never directly emits a broker order.

## 6. Regime Engine

States:
UNKNOWN
TREND_UP
TREND_DOWN
RANGE
TRANSITION
CHAOTIC

Separate:
direction
trend strength
structure
momentum
volatility
compression/expansion
pullback
trend age
structural integrity

## 7. Market Role Engine

States:
UNKNOWN
CONTINUATION
PULLBACK
COUNTERFLOW
RANGE_ROTATION
BREAKOUT
RECLAIM
TRANSITION
EXHAUSTION
NOISE
AMBIGUOUS

Direction and role remain independent.

## 8. Location Engine

States:
OPEN
FAVORABLE
NEUTRAL
CONGESTED
BLOCKED
EXTREME

Inputs include nearby structure, liquidity boundaries, session extremes and HTF obstacles.

## 9. Opportunity Engine

Lifecycle:
DISCOVERED
VALIDATING
VALID
TRIGGER_READY
AUTHORIZED
EXECUTED

Degradation:
VALID → DEGRADED → INVALIDATED

Temporal:
VALID → STALE → EXPIRED

Opportunity identity prevents repeated entries from being treated as new independent opportunities.

## 10. Tradeability Engine

States:
UNKNOWN
PASS
MARGINAL
FAIL_SPREAD
FAIL_COST
FAIL_LIQUIDITY
FAIL_EXECUTION
FAIL_OPPORTUNITY_SPACE

Must separately evaluate:
spread
commission
slippage
liquidity
execution quality
opportunity corridor.

## 11. News Engine

States (NewsState):
NEWS_NORMAL
NEWS_WATCH
NEWS_PREP
NEWS_LOCKDOWN
INITIAL_SHOCK
VOLATILITY_DISCOVERY
POST_NEWS_VALIDATION
RESTRICTED_REENTRY
NORMAL_REENTRY
EXTENDED_PROTECTION

Can block/override protection but cannot create strategy signals.

## 12. Risk Engine

States:
RISK_NORMAL
RISK_REDUCED
RISK_RESTRICTED
RISK_HALTED

Responsibilities:
allowed risk
position sizing
drawdown throttle
news throttle
mode throttle
account feasibility
hard caps

Cannot manufacture direction.

## 13. Portfolio Arbitration

Results:
ALLOW
DEFER
MERGE
REJECT

Inputs:
currency exposure vector
symbol exposure
directional exposure
correlation
setup budgets
mode budgets
total open risk
daily risk
trade count
opportunity identity

Cannot manufacture direction.

## 14. Execution Engine

States (ExecutionState):
EXEC_READY
EXEC_SUBMITTING
EXEC_SUBMITTED
EXEC_ACCEPTED
EXEC_PARTIAL
EXEC_FILLED
EXEC_REJECTED
EXEC_CANCELLED
EXEC_UNKNOWN
EXEC_RECONCILING

Cannot reinterpret strategy.

## 15. Position Management

Lifecycle States (PositionLifecycleState):
POS_OPENING
POS_ACTIVE
POS_PROTECTED
POS_RUNNER
POS_DECAYING
POS_EXPIRING
POS_CLOSING
POS_CLOSED

Health States (PositionHealthState):
HEALTH_HEALTHY
HEALTH_STALLED
HEALTH_DAMAGED
HEALTH_INVALID
HEALTH_CRITICAL

## 16. TTL

States:
FRESH
AGING
DECAYING
STALE
EXPIRING
EXPIRED

## 17. Reconciliation

States (ReconciliationState):
RECON_NORMAL
RECON_SUSPECTED_ORPHAN
RECON_RECONCILING
RECON_RECOVERED
RECON_QUARANTINED

## 18. Authority matrix

| Engine | Creates state | Invalidates parent | Opens | Closes/protects |
|---|---|---|---|---|
| Data | Yes | Yes | No | Protective |
| Volatility | Yes | No | No | No |
| Structure | Yes | Yes | No | No |
| Flow | Yes | No | No | No |
| PDE | Yes | Yes | No | No |
| Regime | Yes | Yes | No | No |
| Role | Yes | Yes | No | No |
| Location | Yes | No | No | No |
| Opportunity | Yes | No | No | No |
| Tradeability | Yes | No | No | No |
| News | Yes | Yes | No | Protective |
| Risk | Yes | No | No | Protective |
| Portfolio | Yes | No | Authorize | No |
| Execution | Yes | No | Execute | Execute |
| Position | Yes | No | Only authorized | Yes |
| TTL | Yes | No | No | Yes |
| Reconciliation | Yes | Yes | No | Protective |

## 19. Confidence

Confidence may:
- prioritize valid opportunities
- choose risk class
- choose TP profile
- choose entry aggressiveness
- influence post-news reentry

Confidence may NOT:
- bypass mandatory validity
- bypass news lockdown
- bypass risk caps
- bypass lineage
- turn an invalid signal into a valid one

Only calibrated confidence can be interpreted probabilistically.
