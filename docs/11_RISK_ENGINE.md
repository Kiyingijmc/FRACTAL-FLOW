# RISK ENGINE
Version 1.0

## 1. Purpose

Convert a valid trade opportunity into an executable risk allocation while enforcing constitutional limits.

## 2. States

RISK_NORMAL
RISK_REDUCED
RISK_RESTRICTED
RISK_HALTED

## 3. Position sizing

PositionSize =
AllowedRisk / (SL_distance × ValuePerUnit)

SL must be the actual structural stop for the trade, not a convenient arbitrary distance.

## 4. Dynamic risk inputs

Risk may be throttled by:
- drawdown
- news
- volatility
- mode
- portfolio concentration
- recent losses
- execution quality
- account feasibility

Dynamic throttles cannot exceed hard constitutional caps.

## 5. Hard caps

At minimum:
- max risk per trade
- max symbol risk
- max total open risk
- max daily risk
- max correlated exposure
- max directional exposure
- max trades
- max entries per opportunity
- mode-specific budget

## 6. Account Feasibility Engine

Inputs:
- equity
- balance
- leverage
- margin
- contract size
- minimum volume
- volume step
- spread
- commission
- slippage
- structural SL
- expected move

Output:
FEASIBLE / INFEASIBLE / RESTRICTED

Never force a position that violates broker volume or account constraints.

## 7. Drawdown

Drawdown can reduce:
- risk multiplier
- maximum simultaneous exposure
- entry frequency
- Smart Overtrading budget

Drawdown cannot turn invalid setups into valid ones.

## 8. Small Account / Compounding

Use equity-based sizing with explicit:
- minimum lot constraints
- exposure throttles
- drawdown protection
- minimum economic opportunity

The system should recognize when compounding assumptions are operationally infeasible.

## 9. Structural stop

Stop location should normally derive from:
- protected swing
- protected pullback
- structural invalidation

Volatility can add a safety buffer.

## 10. Dynamic TP interaction

Risk engine communicates approved risk to TP engine.

TP modes:
STATIC
STRUCTURAL
VOLATILITY
MOMENTUM
LIQUIDITY
HYBRID
ADAPTIVE

Risk does not decide market direction.

## 11. News interaction

During news:
- no new strategic exposure during lockdown
- existing positions may be protected/reduced
- risk multiplier may be reduced after validation

Risk must never loosen protection.

## 12. Risk versus confidence

Confidence is an allocation input only after validity.

A high-confidence but invalid opportunity is rejected.

## 13. Exposure accounting

Use currency-aware exposure vectors.

Example:
EURUSD long
+ GBPUSD long
+ USDCHF short

can represent concentrated USD-short exposure despite three separate trades.

Portfolio arbitration owns the final concentration decision.

## 14. Auditability

Every approved trade records:
- requested risk
- throttles
- approved risk
- sizing inputs
- final volume
- SL
- configuration version
- risk state
- reason codes
