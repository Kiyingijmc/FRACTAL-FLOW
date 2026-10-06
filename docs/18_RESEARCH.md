# RESEARCH / BACKTEST / CALIBRATION PROTOCOL
Version 1.0

## 1. Purpose

Research whether each architectural layer adds incremental information and whether the behavior generalizes.

Do not optimize solely for maximum historical PnL.

## 2. Incremental architecture tests

Test:
P(+1R | Pullback)

versus:
P(+1R | Pullback + Weakening)

versus:
P(+1R | Pullback + Weakening + Resumption)

versus:
P(+1R | Pullback + Weakening + Resumption + Location + OpportunitySpace)

versus:
same + Tradeability

Then separately test:
News
Risk
Portfolio
Dynamic TP
Structural trailing
TTL

## 3. Research record

For every observation:
timestamp
symbol
session
mode
all relevant timeframe features
regime
role
setup
pullback state
spread
volatility
entry
future returns:
1m
3m
5m
10m
20m
30m
MFE
MAE
time to MFE
time to MAE
exit reason
mode
news state
tradeability
risk state

Also record:
observation timestamp
feature timestamp
calculation version
data version
configuration version

## 4. Anti-lookahead

Decision_t =
f(Data_≤t)

No future:
- bar
- spread
- event actual
- structure
- label
- normalization

may influence the decision at t.

Beware:
- centered indicators
- future-confirmed pivots used retrospectively
- post-event data leaking into pre-event state
- survivorship bias
- selection bias
- parameter selection on OOS

## 5. Walk-forward

Historical data
→ feature extraction
→ state reconstruction
→ outcome labeling
→ training/calibration
→ validation
→ walk-forward
→ OOS evaluation

## 6. Research versions

FF-A:
HTF environment + structure

FF-B:
+ primary pullback

FF-C:
+ weakening + resumption

FF-D:
+ location + opportunity space + tradeability

Then separately add:
News
Risk
Portfolio
dynamic TP
structural trailing
TTL

## 7. Feature stability

Evaluate across:
- time periods
- symbols
- sessions
- volatility regimes
- market conditions

Symbol×session-specific features are allowed where evidence supports them.

## 8. Parameter classes

### Structural constants
Constitutional architecture; not freely optimized away.

### Calibration parameters
Thresholds/weights supported by research.

### Account parameters
Equity, leverage, contract size, broker limits.

### Market profile parameters
Symbol/session characteristics.

### Operational parameters
timeouts, retries, polling intervals, etc.

## 9. Feature timestamping

Every feature must identify:
- source data timestamp
- computation timestamp
- feature version

## 10. Labels

Future outcome labels are for research only and must never be available to live decision code.

## 11. Probability

Confidence is not automatically probability.

To become probability:
- define outcome
- calibrate
- validate
- measure reliability

## 12. Metrics

Do not rely only on:
- net profit
- win rate

Also measure:
- expectancy
- payoff distribution
- MFE/MAE
- drawdown
- risk-adjusted return
- trade frequency
- exposure
- cost sensitivity
- slippage sensitivity
- stability across regimes
- stability across symbols
- OOS degradation
- tail behavior

## 13. Research of tradeability

Study:
- spread percentile
- spread shock
- cost/expected move
- execution latency
- slippage
- partial fills

## 14. Research of news

Separate:
- scheduled event
- observed shock
- recovery/normalization

Measure:
- pre-event behavior
- shock
- price discovery
- validation
- post-news structure

## 15. Research of TTL

Measure:
- time to favorable resolution
- time to adverse resolution
- stagnation probability
- decay markers
- rescue outcomes

## 16. Research of Smart Overtrading

Compare:
- single entry per opportunity
- controlled re-entry
- unlimited-like behavior

The objective is not maximum trade count. It is whether repeated participation improves expectancy after costs/risk/correlation.

## 17. Research reproducibility

Each experiment must have:
- dataset/version
- code version
- configuration version
- random seed where applicable
- exact parameter set
- symbol/session selection
- train/validation/OOS ranges

## 18. Research principle

If an architectural layer cannot demonstrate incremental information, investigate whether it should remain descriptive rather than directly influence execution.

Do not remove a safety layer merely because it does not increase historical PnL.
