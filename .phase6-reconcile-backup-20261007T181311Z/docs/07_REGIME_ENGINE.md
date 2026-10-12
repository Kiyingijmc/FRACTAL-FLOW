# REGIME / ROLE / LOCATION ENGINE
Version 1.0

## 1. Regime

States:
UNKNOWN
TREND_UP
TREND_DOWN
RANGE
TRANSITION
CHAOTIC

Regime is not equivalent to direction.

## 2. Regime dimensions

Separate:
- direction
- trend strength
- structure
- momentum
- volatility
- compression/expansion
- pullback state
- trend age
- structural integrity
- ambiguity

Avoid simplistic EMA crossover classification.

## 3. Trend age

Trend age is descriptive:
- early
- developing
- mature
- aging/exhausting

It must not automatically imply reversal.

## 4. Transition

A transition is a structural process, not a single candle.

Example:
4H UP
→ protected structure damage
→ break confirmation
→ transition
→ new bearish ownership if independently established

## 5. Range

Range requires meaningful boundaries and rotation evidence.

Range Rotation strategy:
- requires validated range context
- requires usable location
- requires acceptable opportunity space
- must avoid trading during unresolved breakout shock

## 6. Market Role

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

Role tells what price is doing within its environment.

## 7. Location

States:
OPEN
FAVORABLE
NEUTRAL
CONGESTED
BLOCKED
EXTREME

Location incorporates:
- nearby HTF structure
- M15 swings
- liquidity boundaries
- session extremes
- expected path
- congestion

## 8. Role + location

A continuation signal at blocked location is not equivalent to a continuation signal with open space.

A counterflow signal at an extreme may have different context from one in the middle of a trend.

## 9. Ambiguity

AMBIGUITY_SCORE should increase with:
- multi-TF conflict
- structure conflict
- flow conflict
- location uncertainty
- compression
- failed breaks

High ambiguity may:
- block
- defer
- reduce risk
- reduce entry aggressiveness

It cannot manufacture validity.

## 10. Outputs

Regime engine:
- regime state
- direction
- strength
- age
- structural integrity
- volatility context
- ambiguity

Role engine:
- market role
- role confidence
- reason codes

Location engine:
- location
- obstacle map
- opportunity corridor

None directly place orders.
