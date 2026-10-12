# TRADE TTL / DECAY ENGINE
Version 1.0

## 1. Purpose

Prevent positions from remaining open indefinitely after their expected structural thesis has decayed.

## 2. States

FRESH
AGING
DECAYING
STALE
EXPIRING
EXPIRED

## 3. Decay model

TradeDecay =
f(TimeDecay,
  ProgressShortfall,
  MomentumDecay,
  StructuralDamage,
  VolatilityCollapse,
  OpportunityDecay)

The system should track whether the expected structural progression is occurring.

## 4. Fresh

FRESH means the trade is within its expected resolution window and thesis is behaving normally.

## 5. Aging

AGING means time is passing faster than expected progress.

It is not automatically a close.

## 6. Decaying

DECAYING means multiple evidence streams indicate deteriorating expected value:
- poor progression
- weakening momentum
- structural damage
- reduced opportunity
- abnormal stagnation

## 7. Stale

STALE means the trade is no longer behaving like the setup that justified entry.

Management may:
- tighten
- reduce
- close

## 8. Expiry

At EXPIRING:
evaluate whether a controlled rescue is possible.

Research hypothesis:
- winning/protected: 1.5× adaptive volatility unit
- inadequate: 1×
- still inadequate: close

These values are calibration hypotheses, not constitutional truths.

## 9. Hard invalidation

Never rescue through hard structural invalidation.

If the thesis's protected structure is broken, structural invalidation takes precedence over TTL rescue.

## 10. Updateable TTL

TTL may be updated per:
- trade
- batch
- mode
- setup
- session
- market regime

Every update is versioned and logged.

## 11. Disconnect/restart

TTL state must persist.

A restart must not reset a trade to FRESH.

## 12. News interaction

News can temporarily change expected resolution and protection, but must not erase historical decay.

Post-news revalidation may create a new opportunity lineage; it should not silently revive a dead trade.
