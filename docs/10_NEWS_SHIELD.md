# NEWS SHIELD ENGINE
Version 1.0

## 1. Purpose

Protect the strategy from scheduled and unscheduled macro shocks without becoming an independent signal generator.

## 2. Core philosophy

Do not trade information arrival.

Trade the structure formed after information has been processed.

## 3. State machine

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

Extreme:
→ EXTENDED_PROTECTION

## 4. News object

Fields:
event_id
timestamp
country
currencies[]
category
importance
forecast
previous
actual
scheduled
released
revised
affected_symbols[]
pre_window
shock_window
validation_window
severity
status
volatility_response
spread_response
liquidity_response
normalization_state

## 5. Scheduled versus observed

ScheduledSeverity is calendar-derived.

ObservedSeverity is derived from actual market response.

EffectiveNewsSeverity =
f(ScheduledSeverity, ObservedSeverity)

An apparently moderate event can become severe if market shock is extreme.

## 6. Initial research hypotheses

Not immutable:
HIGH:
pre 5m
shock ~2m
validation 10–15m

VERY_HIGH:
pre 10m
shock ~5m
validation 20–30m

These values must be tested/calibrated.

## 7. Signal freeze

At NEWS_PREP/LOCKDOWN:
SIGNAL_FREEZE = NO NEW STRATEGIC EXPOSURE

Existing positions remain under protective management.

Unfilled strategic pending orders should be canceled/invalidated or explicitly protected according to order classification.

Never silently allow strategic pending orders to fill through lockdown.

## 8. Exposure mapping

News exposure is symbol/currency-specific.

Example:
USD CPI can strongly affect:
EURUSD
GBPUSD
USDJPY
USDCHF
XAUUSD

EURGBP is more indirect.

Implement:
NewsExposureScore(symbol, event)

## 9. Shock metrics

ShockMagnitude =
PostNewsMove / NormalExpectedMove

SpreadShock =
CurrentSpread / NormalSpread

RangeShock =
CurrentRange / NormalRange

VelocityShock =
CurrentVelocity / NormalVelocity

States:
CALM
ELEVATED
SHOCK
EXTREME

## 10. Profitable positions

A research/default policy may target protection of approximately 75% of current realizable profit during major news.

Modes:
OFF
FIXED_PERCENT
STRUCTURAL
HYBRID
ADAPTIVE

HYBRID is intended as the flexible default research profile.

Protection must account for:
- broker minimum stop distance
- spread
- commission
- slippage
- volatility
- structural levels

For long (tighten = move price UP):
SL_final = max(SL_existing, SL_news_candidate)

For short (tighten = move price DOWN):
SL_final = min(SL_existing, SL_news_candidate)

Add mandatory assertion:
Assert(Distance(Entry, SL_final) <= Distance(Entry, SL_existing))

Never loosen the stop.

If 75% cannot be safely protected, use the maximum feasible protection rather than violating broker/structure constraints.

## 11. Losing positions

Health:
HEALTHY_LOSS
STALLING_LOSS
THESIS_DAMAGE
THESIS_INVALID
CRITICAL_LOSS

Actions:
HOLD
TIGHTEN
REDUCE
CLOSE

The news engine overlays the strategy; it does not invent the thesis.

## 12. Validation

Ten minutes after release is an earliest checkpoint, not automatic restart.

Require evidence such as:
SpreadNormalized
VolatilityNormalized
QuoteStabilityRecovered
PriceDiscoveryCompleted
ExecutionQualityRecovered

NormalizationScore =
f(SpreadRecovery, VolatilityRecovery, QuoteStability,
  StructuralStability, ExecutionQuality)

Restoration:
NEWS_LOCKDOWN
→ RESTRICTED_REENTRY
→ NORMAL_REENTRY
→ FULL_NORMAL

## 13. Interrupted opportunities

Pre-news opportunities become:
NEWS_INTERRUPTED

They must be revalidated.

If HTF structure changed materially, invalidate and create new lineage.

Post-news opportunities get fresh lineage:
NEWS-ROOT
→ POST_NEWS_SETUP
→ PULLBACK
→ SIGNAL

## 14. Post-news risk

New post-news risk may be reduced:
- early reentry < 1.0 multiplier
- validated reentry, e.g. 0.75 research hypothesis
- normal after full restoration

These are calibration hypotheses, not constitutional numbers.

## 15. Modes under news

Smart Overtrading:
OFF during shock; restricted after.

Counterflow:
heavily restricted early.

Range Rotation:
OFF during shock; range must be revalidated.

Transition Break / post-news repricing:
may activate after stabilization and acceptance.

## 16. Unscheduled shock

If:
price shock + spread shock + velocity shock
occur without a known event:

NEWS_EVENT_UNKNOWN
→ protective lockdown

If calendar unavailable:
- normal market + missing calendar: continue with warning
- abnormal shock + missing calendar: protective lockdown

## 17. News clusters

Multiple nearby events may be treated as one extended macro-risk window when appropriate.

Do not automatically restore normal trading between tightly clustered events.

## 18. Configuration safety

Effective:
NormalConfig v17
→ NewsConfig v18
→ PostNewsConfig v19

When the user changes base configuration during news:
- preserve latest base configuration
- remove only overlay
- never restore stale pre-news configuration

## 19. Active-position checkpoint

For each active strategic object:
- parent valid?
- protected structure intact?
- ownership changed?
- opportunity space changed?

If yes, reattach/revalidate.
Otherwise invalidate.

## 20. NewsPositionState

Suggested fields:
news_exposure
event_id
pre_news_profit
pre_news_R
news_lock_target
news_lock_price
structural_sl_before
structural_sl_after
thesis_state
health_state
action
action_reason
news_override_active
restoration_pending

## 21. Authority

News can:
- block new strategic exposure
- tighten/protect existing positions
- invalidate affected opportunities
- force reconciliation/protection

News cannot:
- manufacture BUY/SELL
- override hard risk safety in the direction of more exposure
- loosen stops
