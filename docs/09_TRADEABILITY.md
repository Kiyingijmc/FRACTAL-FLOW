# TRADEABILITY ENGINE
Version 1.0

## 1. Principle

Signal ≠ trade.

A structurally valid opportunity may still be economically untradeable.

## 2. States

UNKNOWN
PASS
MARGINAL
FAIL_SPREAD
FAIL_COST
FAIL_LIQUIDITY
FAIL_EXECUTION
FAIL_OPPORTUNITY_SPACE

## 3. Spread

Track:
- current spread
- historical spread
- spread percentile
- spread volatility
- spread / SL
- spread / expected move

Spread is first-class, not a cosmetic filter.

## 4. Costs

Include:
- spread
- commission
- expected slippage
- known execution costs

NetExpectedMove =
GrossExpectedMove - Spread - Commission - Slippage

Potential:
NetOpportunityRatio =
ExpectedGrossMove / TotalExpectedCosts

Do not treat an attractive gross target as attractive if costs consume the expected move.

## 5. Liquidity

Evaluate:
- quote stability
- market-open status
- recent fill quality
- spread stability
- abnormal gaps
- symbol-specific liquidity conditions

## 6. Opportunity space

Tradeability fails if entry is too close to a meaningful obstacle.

Obstacle types:
- HTF structure
- M15 swing
- session extreme
- liquidity boundary
- congestion

## 7. Execution quality

Consider:
- broker response latency
- price freshness
- slippage
- partial fills
- order type
- market state
- spread shock

## 8. Decision rule

A high-quality signal with poor tradeability remains untradeable.

Confidence cannot override FAIL_SPREAD, FAIL_COST, FAIL_EXECUTION or FAIL_OPPORTUNITY_SPACE.

## 9. Calibration

Tradeability thresholds should be calibrated by:
- symbol
- session
- volatility regime
- account/broker constraints

Do not assume one universal spread threshold is valid across all instruments.

## 10. Small account

Minimum lot size may make structurally correct risk sizing impossible.

Account Feasibility Engine must be allowed to return:
INFEASIBLE

Do not force a trade merely because a strategy signal exists.
