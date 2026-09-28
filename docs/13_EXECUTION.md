# MT5 EXECUTION
Version 1.0

## 1. Authority

MT5 is authoritative for live execution.

The execution layer must not reinterpret the strategy.

## 2. Unified TradeDecision

Fields:
decision_id
opportunity_id
direction
symbol
environment
role
setup
pullback
resumption
location
opportunity_space
tradeability
news_state
risk_state
portfolio_state
entry_price
structural_sl
tp_plan
ttl
requested_risk
approved_risk
position_size
arbitration_result
configuration_version
lineage_version

## 3. Decision Lifecycle (DecisionLifecycleState) & Order Execution (ExecutionState)

Decision Lifecycle States (DecisionLifecycleState):
DECISION_CANDIDATE
→ DECISION_VALIDATING
→ DECISION_TRADEABILITY_CHECK
→ DECISION_RISK_CHECK
→ DECISION_PORTFOLIO_CHECK
→ DECISION_ARBITRATION
→ DECISION_AUTHORIZED
→ DECISION_EXECUTED

Decision Failure / Rejection:
DECISION_REJECTED + reason

Order & Execution Gateway States (ExecutionState):
EXEC_READY
→ EXEC_SUBMITTING
→ EXEC_SUBMITTED
→ EXEC_ACCEPTED
→ EXEC_PARTIAL
→ EXEC_FILLED

Execution outcomes/failures:
EXEC_REJECTED / EXEC_CANCELLED / EXEC_UNKNOWN / EXEC_RECONCILING

## 4. Pre-submit race checks

Immediately before submission:
1. read current state
2. verify opportunity exists
3. verify parent version
4. verify parent required state
5. verify data quality
6. verify tradeability
7. verify news
8. verify risk
9. verify portfolio
10. verify broker symbol/trading status
11. submit

Any incompatible state change:
ABORT → REVALIDATE

## 5. Order classes

STRATEGIC_PENDING
PROTECTIVE_PENDING
BROKER_REQUIRED_PENDING

During news lockdown:
- strategic pending should be canceled/invalidated
- protective/broker-required orders handled according to safety rules

## 6. Idempotency

Every execution intent requires:
- stable decision_id
- stable idempotency key
- request version
- broker-side correlation where available

Duplicate responses must not create duplicate exposure.

## 7. MT5 object distinction

MT5 distinguishes:
- orders
- deals
- positions

The system must maintain these separately.

A filled order can produce one or multiple deals depending on execution conditions.

## 8. Unknown execution

If broker response is uncertain:
EXEC_UNKNOWN
→ EXEC_RECONCILING

Never assume rejection merely because response is missing.

## 9. Partial fill

PARTIAL requires:
- remaining quantity
- average fill price
- risk recalculation
- TP/SL adjustment if necessary
- lineage preserved

Do not accidentally create an oversized risk position through retries.

## 10. Protection

Protective actions have priority over new strategic exposure.

Emergency rules must survive:
- strategy crash
- network loss
- data loss
- restart
- news event
- unknown execution

## 11. Execution readiness

Broker checks:
- symbol available
- market open
- volume valid
- volume step valid
- stop levels valid
- freeze levels valid
- order type allowed
- margin sufficient
- price fresh

## 12. Execution audit

Record:
- decision
- request
- broker response
- order id
- deal id
- position id
- timestamps
- slippage
- rejection reason
- configuration version
- lineage version

## 13. Execution must not

- create a strategy signal
- change strategy direction
- bypass news
- bypass risk
- bypass arbitration
- assume unknown response is rejection
