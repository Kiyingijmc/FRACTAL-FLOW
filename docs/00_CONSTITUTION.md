# FRACTAL FLOW CONSTITUTION
Version 1.0

## 1. Purpose

FRACTAL FLOW is a hierarchical, state-driven Forex scalping architecture designed to detect and trade structured movement while explicitly modeling:
- market environment
- directional ownership
- structure
- flow
- pullbacks
- weakening
- resumption
- market role
- location
- opportunity space
- tradeability
- news
- risk
- portfolio exposure
- execution state
- position health
- trade decay
- reconciliation

The system should be simple outside and sophisticated inside.

## 2. Core decision philosophy

A signal is not a trade.

A valid trade requires:
1. valid data
2. valid environment
3. valid market role
4. valid setup/pullback
5. valid structural ownership
6. valid location
7. sufficient opportunity space
8. acceptable tradeability
9. acceptable news state
10. acceptable risk state
11. acceptable portfolio exposure
12. arbitration authorization
13. execution readiness

Formal gate model:

D = Q ∧ E ∧ R ∧ P ∧ L ∧ O ∧ T ∧ N ∧ K ∧ A ∧ X

Where:
Q = data quality
E = environment
R = role
P = pullback/setup validity
L = location
O = opportunity space
T = tradeability
N = news state
K = risk
A = arbitration
X = execution readiness

Mandatory failure = no trade.

Confidence belongs to the quality/allocation layer, not the validity layer.

## 3. Hierarchical market model

4H → environment
1H → directional state
30M → structural context
15M → primary opportunity/pullback
5M → confirmation
1M → execution

The system must permit opportunity migration. Initially 15M may be the primary active pullback with 5M confirmation and 1M execution. After a confirmed structural transition, 5M may become the primary active pullback with 1M execution.

Example:
4H bullish
→ 15M bearish pullback
→ bearish weakens
→ 5M bullish recovery
→ 15M ownership returns bullish
→ M1 long

Opposite continuation:
4H bullish
→ 15M bearish pullback
→ bearish strengthens
→ protected 15M bullish structure breaks
→ 15M bearish continuation
→ new bearish opportunity

If 4H protected structure breaks:
4H UP → TRANSITION → DOWN

## 4. Market state versus trade decision

The system describes the market before deciding what to trade.

Flow:
RAW DATA
→ FEATURES
→ STATES
→ SETUPS
→ OPPORTUNITIES
→ VALIDITY
→ TRADEABILITY
→ RISK
→ PORTFOLIO ARBITRATION
→ AUTHORIZATION
→ EXECUTION
→ POSITION MANAGEMENT

No engine may skip layers.

## 5. Strategy families

Initial constitutional families:
- FF-01 FLOW_CONTINUATION
- FF-02 COUNTERFLOW
- FF-03 RANGE_ROTATION
- FF-04 TRANSITION_BREAK

Everything else initially maps to NO_TRADE until separately specified and validated.

Rules:
- liquidity sweep = trigger modifier
- compression = state
- compression + directional expansion + acceptance = breakout candidate
- compression + false break + range re-entry = rotation/reversal candidate

## 6. Market Role

Roles:
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

Direction and role are separate dimensions.

## 7. Flow

Track:
FlowStrength_Long
FlowStrength_Short
FlowImbalance = LongFlowStrength - ShortFlowStrength

Flow is descriptive. It must not itself emit BUY/SELL.

## 8. Opportunity quality

TradeQuality =
SignalQuality × OpportunitySpace × Tradeability

Opportunity space means the usable path from entry toward structural objectives before meaningful obstacles:
- HTF resistance/support
- M15 swing
- liquidity boundary
- session extreme
- other structural congestion

Too congested = no trade.

## 9. Ambiguity

AMBIGUITY_SCORE combines:
- multi-TF conflict
- structure conflict
- flow conflict
- location uncertainty
- compression
- failed breaks
- competing structural ownership

High ambiguity reduces or disables entries.

## 10. Trade frequency

Trade frequency is an output, not a quota.

Breadth across symbols is preferable to forcing M1 entries on one symbol.

## 11. Modes

Profiles over the same underlying engine:
- SCALPING
- SMART SCALPING
- FLIPPING
- SMART OVERTRADING
- SMALL ACCOUNT / COMPOUNDING

Modes may differ by symbol and session and can run simultaneously on one account.

Smart Overtrading is not random churn. It is opportunity-budgeted repeated participation:
- same primary pullback = same opportunity
- new structural leg/pullback = new opportunity
- repeated entry must respect parent identity, quality, cooldowns, risk and correlation

Flipping:
LONG loss ≠ immediate SHORT.
Required:
thesis invalidation → structural reversal → independent opposite setup → M1 trigger → short.

## 12. Configuration hierarchy

GLOBAL
→ ASSET CLASS
→ SYMBOL
→ SESSION
→ SYMBOL×SESSION
→ MODE
→ SETUP
→ ENTRY PROFILE

Inheritance must be explicit and versioned.

## 13. Sessions

Primary sessions:
ASIA
LONDON
LONDON_NY_OVERLAP
NEW_YORK
LATE_NEW_YORK
ROLLOVER

Substates:
SESSION_OPEN
SESSION_EARLY
SESSION_CORE
SESSION_LATE
SESSION_TRANSITION

## 14. Risk constitution

Position size derives from actual structural stop and allowed risk:

PositionSize = AllowedRisk / (SL_distance × ValuePerUnit)

Account Feasibility Engine must consider:
- equity
- margin
- leverage
- contract size
- minimum volume
- volume step
- spread
- commission
- slippage
- structural SL
- expected move

Hard caps override dynamic adjustments.

## 15. Tradeability constitution

Tradeability is separate from signal validity.

NetExpectedMove =
GrossExpectedMove - Spread - Commission - Slippage

Potential:
NetOpportunityRatio = ExpectedGrossMove / TotalExpectedCosts

Spread metrics:
- current spread
- historical spread
- spread percentile
- spread volatility
- spread / SL
- spread / expected move

## 16. Dynamic exits

TP modes:
STATIC
STRUCTURAL
VOLATILITY
MOMENTUM
LIQUIDITY
HYBRID
ADAPTIVE

Default design intent is dynamic/hybrid/adaptive, subject to research.

Partial examples such as 25/25/50, 33/67, 40/30/30 are examples only, not optimized truths.

## 17. Structural trailing

Primary trailing uses structure:
- long: below protected pullback low
- short: above protected pullback high
- stop ratchets only

Hierarchy:
- early: M5 structure
- established: M5 protected pullback
- runner: 15M protected structure

ATR/volatility may buffer or rescue but must not replace structural thesis.

## 18. TTL constitution

Every trade has finite lifetime.

TradeDecay =
f(TimeDecay, ProgressShortfall, MomentumDecay, StructuralDamage, VolatilityCollapse, OpportunityDecay)

States:
FRESH → AGING → DECAYING → STALE → EXPIRING → EXPIRED

Expiry rescue:
- winning/protected: 1.5× adaptive volatility unit as a research hypothesis
- inadequate: 1×
- still inadequate: close
- never rescue through hard structural invalidation

## 19. News constitution

News is an overlay on strategy, not a separate strategy.

Core state machine:
NORMAL → NEWS_WATCH → NEWS_PREP → NEWS_LOCKDOWN → INITIAL_SHOCK → PRICE_DISCOVERY → POST_NEWS_VALIDATION → RESTRICTED_REENTRY → NORMAL_REENTRY → NORMAL

No strategic new exposure in LOCKDOWN/SHOCK.

Profitable positions may be protected with a default research target around 75% of current realizable profit, but the final stop must respect broker constraints, spread, commission, slippage and structural logic.

Never loosen an existing stop.

Ten minutes is an earliest validation checkpoint, not an automatic restart.

Post-news principle:
Do not trade information arrival; trade the structure formed after information has been processed.

## 20. Orphan and restart constitution

Lineage:
ROOT → REGIME → SETUP → PRIMARY_PULLBACK → [SECONDARY_PULLBACK →] [MICRO_PULLBACK →] OPPORTUNITY → SIGNAL → ORDER → POSITION → TRADE → MANAGEMENT

Orphan states:
ACTIVE → SUSPECTED_ORPHAN → RECONCILING → REATTACHED / RECOVERED / EXPIRED / QUARANTINED

Uncertain state cannot create exposure.

After restart:
persistent state → broker positions/orders/history → reconciliation → lineage reconstruction → quarantine uncertainty → protective management → strategy enabled only after reconciliation complete.

## 21. Authority

MT5 is authoritative for live execution.

TradingView cannot:
- authorize a trade
- override risk
- override news lock
- override reconciliation
- modify authoritative position state

## 22. Research constitution

Never optimize only for maximum backtest PnL.

Test incremental information:
P(+1R | Pullback)
vs
P(+1R | Pullback + Weakening)
vs
P(+1R | Pullback + Weakening + Resumption)
vs
... + Location + OpportunitySpace + Tradeability

Walk-forward and OOS validation are mandatory.

No lookahead.

## 23. Safety principle

Survival and correctness precede speed and profit.

A system that cannot reliably preserve lineage, protection, state integrity, reconciliation and execution safety is not ready for live deployment.
