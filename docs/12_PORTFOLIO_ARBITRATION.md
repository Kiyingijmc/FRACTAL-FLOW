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

## Phase 5 implementation boundary

The canonical runtime implementation is `src/fractal_flow/domain/portfolio.py`, composed by `src/fractal_flow/domain/part5_pipeline.py`. Portfolio arbitration is the final pre-execution exposure authority: it calculates currency vectors, correlation-aware risk, deterministic rankings and hard exposure/trade caps. Opposite-direction exposure requires independent structural-reversal evidence. It cannot manufacture market direction. Lane/group hard caps are implemented by `src/fractal_flow/domain/lane_pipeline.py` before final Part-B authorization.

## 12.1 Forensic remediation contract

The portfolio layer is a hard pre-exposure authority, not a best-effort advisory calculator. `MERGE` is permitted only when the aggregate merged candidate set passes the same hard constraints as ordinary admission. `max_entries_per_opportunity` is enforced before exposure and is reconciled with the authoritative opportunity's own entry budget.

Portfolio exposure is explicit and unit-bound: `PortfolioCandidate.notional` is mandatory and carries `exposure_unit=STANDARD_LOT_EQUIVALENT` by default. Silent fallback from raw volume is forbidden. Mixed exposure units are rejected rather than compared numerically.

Correlation-aware risk incorporates the candidate's risk and the risk magnitude of existing correlated positions. The arbitrator may return a deterministic `risk_multiplier < 1` as a portfolio throttle; it never sizes the trade itself. The Risk Engine must consume that multiplier and produce the final approved risk/volume.
