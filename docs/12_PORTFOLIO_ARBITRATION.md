# PORTFOLIO ARBITRATION
Version 1.0

## 1. Purpose

Prevent individually valid opportunities from combining into unacceptable portfolio exposure.

## 2. Outputs

ALLOW
DEFER
MERGE
REJECT

## 3. Exposure dimensions

At minimum:
- symbol exposure
- currency exposure
- directional exposure
- correlated exposure
- setup exposure
- mode exposure
- total open risk
- daily risk
- total trade count
- entries per opportunity

## 4. Currency exposure

Represent each position as a currency vector.

Example:
EURUSD long:
EUR +, USD -

GBPUSD long:
GBP +, USD -

USDCHF short:
USD -, CHF +

The aggregate may create a large USD-short concentration.

## 5. Correlation

Do not rely solely on static historical correlation.

Consider:
- current regime
- session
- volatility
- recent rolling correlation
- common currency exposure
- common macro exposure

## 6. Arbitration sequence

Opportunity valid
→ tradeability pass
→ risk feasible
→ portfolio exposure calculated
→ candidate ranked/selected among valid opportunities
→ ALLOW/DEFER/MERGE/REJECT

The arbitrator may prioritize among valid opportunities but cannot manufacture direction.

## 7. Merge

MERGE can be used when:
- same structural opportunity
- same direction
- same parent
- same economic exposure
- additional entries would otherwise create redundant trades

Merge into one managed exposure where appropriate.

## 8. Smart Overtrading

Smart Overtrading should be budgeted by:
- opportunity identity
- structural leg
- cooldown
- max entries
- risk budget
- portfolio exposure
- tradeability
- correlation

Per D-036, re-entry authorization MUST verify `Pullback.reentry_allowed == TRUE` before permitting any additional or re-entry trade.

It must not become unlimited M1 churn.

## 9. Flipping

An opposite trade is not authorized merely because a current trade loses.

Requirements:
1. current thesis invalidated
2. structure reverses
3. opposite opportunity created
4. opposite tradeability valid
5. risk/portfolio pass
6. new lineage

## 10. Simultaneous opportunities

When multiple symbols trigger:
- calculate independent validity
- calculate exposure vector
- calculate correlation
- calculate total risk
- allocate within constraints
- defer/reject/merge excess

## 11. Authority

Portfolio arbitration is the final allocation authority before execution, but it does not reinterpret market direction.
