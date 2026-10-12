# OPPORTUNITY ENGINE
Version 1.0

## 1. Purpose

Convert valid market-state information into uniquely identified, time-bounded trading opportunities without conflating market state with execution.

## 2. Opportunity object

Fields:
opportunity_id
parent_opportunity_id
root_id
symbol
session
mode
environment
environment_tf
location
location_tf
dominant_flow
local_flow
market_role
primary_pullback_id
setup_type
direction
structural_edge
opportunity_space
tradeability
execution_quality
entry_profile
risk_class
ttl_class
confidence
state
entry_allowed

## 3. Lifecycle

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

## 4. Opportunity identity

Repeated signals from the same primary pullback are normally the same opportunity.

New opportunity identity requires meaningful new structure, such as:
- new structural leg
- new primary pullback
- independently revalidated setup
- confirmed transition
- new post-news lineage

This prevents Smart Overtrading from becoming random M1 churn.

## 5. Trade quality

TradeQuality =
SignalQuality × OpportunitySpace × Tradeability

Signal quality may include:
- structure
- flow
- pullback state
- resumption
- role
- location

Opportunity space measures the path to structural objectives.

Tradeability accounts for execution costs.

## 6. Trade corridor

ENTRY
→ TP1
→ TP2
→ RUNNER

Obstacles:
- HTF support/resistance
- M15 swing
- liquidity boundary
- session extreme
- congestion

If the corridor is too short/congested, reject or defer.

## 7. Setup families

FF-01 FLOW_CONTINUATION
FF-02 COUNTERFLOW
FF-03 RANGE_ROTATION
FF-04 TRANSITION_BREAK

### FF-01 FLOW_CONTINUATION
Requires aligned environment/flow/structure and valid pullback/resumption or continuation state.

### FF-02 COUNTERFLOW
Requires stronger location/context evidence and independent invalidation risk controls. More restrictive than continuation.

### FF-03 RANGE_ROTATION
Requires validated range, meaningful boundary location, and acceptable post-entry space.

### FF-04 TRANSITION_BREAK
Requires structural ownership transition rather than merely a price spike.

## 8. Liquidity sweep

Liquidity sweep is a trigger modifier:
- sweep + recovery
- sweep + rejection
- sweep + continuation

It is not a standalone strategy family.

## 9. Compression

Compression is a state.

Compression + directional expansion + acceptance can produce breakout context.

Compression + false break + range re-entry can produce rotation/reversal context.

## 10. Parent budgets

A parent opportunity may define:
- maximum entries
- cooldown
- risk budget
- total exposure
- re-entry conditions
- runner allowance

## 11. Mode behavior

Smart Overtrading:
- opportunity-budgeted
- same parent = same opportunity
- new structural leg = new opportunity
- no repeated entry when location/space deteriorates

Small Account / Compounding:
- equity-based risk
- exposure/drawdown throttles
- minimum-lot feasibility

Flipping:
- requires independent opposite opportunity after structural reversal

## 12. Timeframe mapping

A mapping engine determines:
context_tf
primary_tf
secondary_tf
confirmation_tf
execution_tf
micro_tf

The mapping may migrate after structural transition.

## 13. Entry authorization

Opportunity alone does not authorize execution.
It must pass:
tradeability
news
risk
portfolio
arbitration
execution readiness

## 14. Expiry

An opportunity expires when:
- parent invalidates
- structural space disappears
- setup-specific TTL expires
- news invalidates lineage
- data becomes unreliable
- execution context is no longer valid
