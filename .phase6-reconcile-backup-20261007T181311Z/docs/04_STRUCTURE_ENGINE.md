# STRUCTURE ENGINE
Version 1.0

## 1. Objective

Detect adaptive market structure without reducing structure to a fixed three-candle fractal.

## 2. Normalized event stream

Each bar/tick-derived observation may include:
- OHLC
- true range
- directional body
- wick ratio
- volatility context
- UP/DOWN displacement
- retracement
- expansion
- compression

## 3. Adaptive swing

A swing candidate is a local extreme followed by meaningful rejection/displacement.

SwingReversalMagnitude =
ReversalDisplacement / V_local

V_local is a volatility-normalized reference.

Swing strength considers:
- reversal displacement
- efficiency
- volatility normalization
- persistence
- subsequent structure

States:
SWING_CANDIDATE
SWING_CONFIRMED
SWING_PROTECTED
SWING_BROKEN

## 4. Protected structure

Protected structure is the swing/current level on which directional thesis depends.

Separate:
- internal structure
- external structure

A protected level may transition:
INTACT
→ DAMAGE_CANDIDATE
→ DAMAGE_CONFIRMED
→ STRUCTURE_BROKEN

Or:
RECLAIM_CANDIDATE
→ RECLAIM_CONFIRMED

## 5. Structural break

StructuralBreak =
LevelCross × DisplacementConfirmation × PersistenceConfirmation

Break states:
BREAK_CANDIDATE
BREAK_CONFIRMED
BREAK_ESTABLISHED
FAILED_BREAK

A level touch alone is not a structural break.

## 6. Break quality

Break quality considers:
- penetration
- displacement
- efficiency
- persistence
- momentum
- follow-through
- retest behavior

False breaks must be explicit objects/states.

## 7. Structure ownership

Structure informs directional ownership but does not itself authorize trading.

Example:
4H bullish structure can remain intact while 15M is in a bearish pullback.

Only when protected 15M bullish structure is damaged/broken does the local ownership potentially transition.

## 8. Structural ambiguity

Ambiguity rises when:
- competing protected levels exist
- multiple breaks fail
- internal and external structure disagree
- timeframes conflict
- price compresses around important levels

High ambiguity can block/reduce opportunities.

## 9. No fixed fractal law

Do not use:
- fixed 3-candle fractals
- fixed N-candle swings
- fixed pip thresholds across all volatility regimes

Adaptive thresholds must be normalized to local/session/regime volatility.

## 10. Structure and pullbacks

A pullback can be deep but healthy if protected structure remains intact.

A shallow pullback can be destructive if it breaks the relevant protected level.

Depth alone is never sufficient to classify pullback health.

## 11. Reclaim

A failed break followed by a structurally meaningful reclaim may transition:
BREAK_CONFIRMED → FAILED_BREAK → RECLAIM_CANDIDATE → RECLAIM_CONFIRMED

Reclaim is contextual and must be attached to the parent structure/opportunity.

## 12. Outputs

The engine should expose:
- swings
- protected levels
- break events
- reclaim events
- structural integrity
- internal/external structure
- direction
- confidence
- ambiguity
- reason codes
- parent lineage

It cannot open positions.
