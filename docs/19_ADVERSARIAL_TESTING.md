# ADVERSARIAL TESTING & FAILURE MATRIX
Version 1.0

## 1. Purpose

FRACTAL FLOW must be tested against hostile market conditions and hostile software conditions.

Expected statuses:
PASS
FAIL
BLOCKED
RECOVERED
QUARANTINED
CRITICAL_FAIL

## 2. Market stress tests

FF-001 M1 chop
FF-002 M5 chop
FF-003 HTF trend / LTF reversal
FF-004 V-reversal
FF-005 false breakout
FF-006 failed reclaim
FF-007 deep healthy pullback
FF-008 deep destructive pullback
FF-009 slow pullback
FF-010 fast pullback
FF-011 news spike
FF-012 news with no spike
FF-013 unexpected news
FF-014 spread explosion
FF-015 spread normalization failure
FF-016 session rollover
FF-017 weekend/gap
FF-018 symbol trading halt
FF-019 stale data
FF-020 missing bars
FF-021 clock/timezone mismatch
FF-022 DST transition

## 3. Execution/system stress

FF-023 broker disconnect
FF-024 duplicate order response
FF-025 unknown execution state
FF-026 partial fill
FF-027 position mismatch
FF-028 orphaned signal
FF-029 orphaned order
FF-030 orphaned position
FF-031 correlated opportunities
FF-032 simultaneous symbols
FF-033 Smart Overtrading loop
FF-034 flip whipsaw
FF-035 configuration change during trade
FF-036 configuration change during news
FF-037 restart during news
FF-038 restart during open trade
FF-039 restart between order/deal
FF-040 TP modification race
FF-041 SL modification race
FF-042 TTL expiry during disconnect
FF-043 news during runner
FF-044 news immediately after entry
FF-045 news immediately before entry
FF-046 simultaneous news cluster

## 4. Account stress

FF-047 $3 account
FF-048 minimum-lot account
FF-049 high-leverage account
FF-050 large account

Expected behavior:
- infeasible sizing must reject
- hard caps must hold
- minimum lot must not force oversized risk
- high leverage must not create permission to violate risk
- large account must still obey concentration and execution constraints

## 5. Data integrity

FF-051 stale tick
FF-052 stale bar
FF-053 missing bar
FF-054 duplicate tick
FF-055 timestamp regression
FF-056 timestamp jump
FF-057 corrupt OHLC
FF-058 spread unavailable
FF-059 quote unavailable
FF-060 market-closed data

## 6. Lineage tests

FF-061 child references stale parent version
FF-062 parent invalidates while child validates
FF-063 parent invalidates between validation and submit
FF-064 orphan signal attempts execution
FF-065 orphan order attempts cancellation without reconciliation
FF-066 orphan position attempts strategic re-entry
FF-067 duplicate opportunity identity
FF-068 repeated M1 trigger on same parent
FF-069 new structural leg creates new opportunity
FF-070 child survives parent deletion incorrectly

## 7. News tests

FF-071 scheduled high-impact event
FF-072 very-high-impact event
FF-073 event with abnormal spread but small price move
FF-074 event with large price move but normal spread
FF-075 unscheduled shock
FF-076 calendar unavailable + normal market
FF-077 calendar unavailable + abnormal shock
FF-078 strategic pending order during lockdown
FF-079 protective order during lockdown
FF-080 profitable position protection
FF-081 losing position during news
FF-082 news while runner active
FF-083 news cluster
FF-084 base configuration changed during news
FF-085 restart during news
FF-086 post-news validation fails
FF-087 post-news validation recovers
FF-088 pre-news opportunity becomes invalid

## 8. Risk/portfolio tests

FF-089 correlated USD concentration
FF-090 total open risk cap
FF-091 daily risk cap
FF-092 max trades
FF-093 max entries per opportunity
FF-094 mode budget conflict
FF-095 symbol budget conflict
FF-096 drawdown throttle
FF-097 risk halted state
FF-098 merge equivalent opportunities
FF-099 defer lower-quality valid opportunity
FF-100 reject due to opportunity congestion

## 9. Race-condition tests

Test state changes between:
- opportunity validation
- tradeability check
- risk check
- portfolio check
- authorization
- order submission

Any incompatible state change must result in:
ABORT → REVALIDATE

Never:
validated state → stale order submission

## 10. Protection tests

Verify:
- stop never loosens
- protection survives strategy shutdown
- protection survives restart
- news cannot reduce protection
- TTL cannot rescue through hard invalidation
- unknown broker state cannot disable protection

## 11. Execution idempotency

Send duplicate execution requests with:
- same decision_id
- same idempotency key
- different network timing
- delayed broker response

Expected:
at most one intended exposure.

## 12. Reconciliation tests

Simulate:
- internal says no position / broker says position
- internal says position / broker says none
- internal says pending / broker says filled
- broker says multiple deals
- partial fill
- unknown order state
- restart during transaction

Expected:
quarantine/reconstruct/protect, never blindly create another trade.

## 13. Smart Overtrading adversarial tests

Feed:
- repeated M1 triggers
- repeated false recoveries
- rapid parent-child transitions
- same opportunity across several minutes

Expected:
opportunity budget/cooldown/lineage prevents uncontrolled churn.

## 14. Flipping adversarial tests

Sequence:
LONG
→ small loss
→ bearish candle
→ bearish candle
→ bullish recovery
→ bearish break

Expected:
no immediate short on loss.
Short only after independent structural reversal/opportunity validation.

## 15. Research integrity tests

Verify:
- no future bars
- no future spread
- no future event actual
- no OOS contamination
- no parameter optimization on OOS
- no hidden future confirmation
- no survivorship bias
- no accidental label leakage

## 16. Critical failure conditions

Any of these should be CRITICAL_FAIL:
- unintended exposure
- trade without lineage
- trade through news lockdown
- loosened protective SL
- stale signal execution
- unknown execution treated as rejected/final
- correlation/risk limit violation
- lookahead
- loss of protection after restart
- stale config overwrites latest config
- orphaned position becomes a new strategic opportunity without validation

## 17. Test philosophy

Adversarial tests are not optional polish.

They are part of the architecture because the system operates at the intersection of:
- uncertain markets
- asynchronous broker state
- mutable configuration
- distributed/event-driven software
- partial information
- real financial risk.
