# PULLBACK DETECTION ENGINE (PDE)
Version 1.0

## 1. Constitution

The primary pullback normally occurs on a timeframe strictly higher than the execution timeframe.

Hierarchy:
PRIMARY → SECONDARY → MICRO

Example:
PB-001 15M PRIMARY
→ PB-002 5M SECONDARY
→ PB-003 1M MICRO

This prevents an M1 micro pullback from being mistaken for a primary opportunity.

## 2. Canonical pullback object

Fields:
id
parent_id
root_id
symbol
timeframe
direction
parent_direction
start_time
start_price
impulse_high
impulse_low
impulse_range
current_high
current_low
counter_move
counter_move_norm
retracement_depth
duration
duration_ratio
velocity
acceleration
efficiency
momentum
range
structural_damage
weakening_score
resumption_score
false_resumption_risk
maturity
state
validity
confidence
protected_level

Policy:
primary_entry_allowed
micro_entry_allowed
reentry_allowed
runner_management_allowed

## 3. Impulse

Impulse features:
D = directional displacement
E = efficiency
S = structural progression
P = momentum/persistence
R = range expansion

ImpulseQuality:
IQ = wD D + wE E + wS S + wP P + wR R

Impulse states:
START
DEVELOPING
EXTENDING
MATURING
EXHAUSTING

Impulse ends when:
- opposing pressure dominates
- progression stops
- efficiency collapses
- compression persists
- opposing structure invalidates
- other setup-specific termination condition occurs

## 4. Pullback measurement

Bull:
CounterMove = ImpulseHigh - CurrentPrice

Bear:
CounterMove = CurrentPrice - ImpulseLow

Features:
- counter displacement
- duration
- efficiency
- velocity
- acceleration
- retracement
- structural damage
- momentum
- range

Candidate:
CounterMoveNorm > θ_counter
AND CounterEfficiency > θ_efficiency
OR explicit CounterStructuralEvidence = TRUE

No fixed Fibonacci or candle-count law.

## 5. Pullback maturity

EARLY
DEVELOPING
MATURE
LATE
EXHAUSTED

Maturity is descriptive, not a direct entry trigger.

## 6. Weakening

Track:
ΔM = momentum change
ΔV = velocity change
ΔE = efficiency change
ΔR = range change
ΔX = extension effectiveness change
ΔD = displacement change

Weakening evidence:
- counter momentum decreases
- counter range contracts
- counter displacement weakens
- extension success declines
- candle efficiency declines
- failed continuation attempts increase
- structural damage trend remains controlled

Weakening is not resumption.

If counter pressure falls while structural damage rises:
WEAKENING_WITH_STRUCTURAL_RISK

## 7. Failed extension

ExtensionEffectiveness =
successful_extension / attempted_extension

ExtensionFailureStrength =
1 - ExtensionEffectiveness

This captures repeated attempts that fail to extend the pullback.

## 8. Resumption

Bullish recovery can include:
- pullback lower high
- higher low
- break of internal lower high
- bullish displacement

Bearish recovery is the inverse.

Break quality:
- penetration
- displacement
- efficiency
- persistence
- momentum

States:
RESUMPTION_NONE
RECOVERY_CANDIDATE
RECOVERY_CONFIRMED
DISPLACEMENT_CANDIDATE
RESUMPTION_CONFIRMED
FOLLOW_THROUGH
RESUMPTION_FAILED

## 9. False resumption

FalseResumptionRisk =
f(weak_followthrough, deep_retest, opposing_displacement, rapid_failure)

False resumption should be explicit so that the engine does not convert a weak first break into a permanent ownership reversal.

## 10. Parent-state gating

Every signal references:
Parent Setup ID
Parent Pullback ID
Parent Regime ID

If primary pullback invalidates:
- child continuation signals are ignored
- a new independent setup must establish ownership

## 11. Lower-TF exceptions

Allowed exceptions:
- re-entry while original setup remains valid
- runner continuation
- strong breakout continuation
- established HTF trend continuation
- explicit setup hierarchy exception

Such a pullback remains MICRO_PULLBACK or subordinate; it is not promoted to PRIMARY by convenience.

## 12. Opportunity migration

Initial:
15M primary
5M confirmation
1M execution

After confirmed transition:
5M primary
1M execution

The mapping engine owns this migration; it must not be hard-coded as a permanent timeframe assumption.

## 13. Feature registry

Impulse:
IMPULSE_DISPLACEMENT
IMPULSE_DISPLACEMENT_NORM
IMPULSE_RANGE
IMPULSE_EFFICIENCY
IMPULSE_PERSISTENCE
IMPULSE_STRUCTURE_PROGRESS
IMPULSE_RANGE_EXPANSION
IMPULSE_DURATION

Pullback:
PB_COUNTER_MOVE
PB_COUNTER_MOVE_NORM
PB_RETRACEMENT
PB_VELOCITY
PB_ACCELERATION
PB_EFFICIENCY
PB_DURATION
PB_DURATION_RATIO
PB_STRUCTURAL_DAMAGE
PB_MOMENTUM
PB_RANGE

Weakening:
PB_MOMENTUM_DECAY
PB_RANGE_CONTRACTION
PB_VELOCITY_DECAY
PB_EFFICIENCY_DECAY
PB_FAILED_EXTENSION_RATE
PB_EXTENSION_FAILURE_MAGNITUDE
PB_STRUCTURAL_COMPRESSION
PB_WEAKENING_SCORE

Resumption:
RES_STRUCTURE_RECOVERY
RES_BREAK_DISTANCE
RES_DISPLACEMENT
RES_DISPLACEMENT_NORM
RES_MOMENTUM_RECOVERY
RES_FOLLOW_THROUGH
RES_RETEST_DEPTH
RES_FALSE_BREAK_RISK
RES_RESUMPTION_SCORE

## 14. Evidence confidence

EvidenceConfidence =
f(DataQuality, StructureConfidence, ImpulseConfidence,
  PullbackConfidence, WeakeningConfidence,
  ResumptionConfidence, ExecutionConfidence)

Only calibrated confidence can become probability.

## 15. Contract

PDE:
- reads market/state features
- creates pullback state
- updates lineage
- can invalidate child opportunity state when parent fails
- cannot place orders
