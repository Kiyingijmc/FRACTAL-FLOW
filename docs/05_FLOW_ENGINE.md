# FLOW OWNERSHIP ENGINE
Version 1.0

## 1. Objective

Describe which side currently controls directional pressure and whether that ownership is strengthening, weakening or transitioning.

## 2. Core quantities

FlowStrength_Long
FlowStrength_Short

FlowImbalance =
FlowStrength_Long - FlowStrength_Short

These are descriptive variables, not direct BUY/SELL commands.

## 3. States

UNKNOWN
LONG_EMERGING
LONG_DOMINANT
LONG_WEAKENING
BALANCED
CONTESTED
SHORT_EMERGING
SHORT_DOMINANT
SHORT_WEAKENING
TRANSITIONING

## 4. Inputs

Potential evidence:
- structural progression
- directional displacement
- momentum
- efficiency
- persistence
- range expansion
- failed extension
- pullback behavior
- resumption behavior
- volatility context

The engine should use multiple evidence classes rather than a single indicator.

## 5. Hysteresis

Flow ownership must not flip direction on every noisy candle.

Use:
- minimum evidence
- persistence
- state dwell
- weakening thresholds
- recovery thresholds
- transition confirmation

## 6. Flow versus structure

Flow can weaken before structure breaks.

Therefore:
LONG_DOMINANT → LONG_WEAKENING does not equal bearish reversal.

Likewise:
SHORT_WEAKENING does not equal bullish reversal.

A true transition requires independent structural evidence.

## 7. Flow examples

Bullish environment:
4H long environment
→ 15M bearish pullback
→ short flow emerges locally
→ short flow weakens
→ bullish recovery
→ long ownership returns

Bearish continuation:
4H long environment
→ 15M short flow strengthens
→ protected 15M bullish structure breaks
→ 15M short ownership becomes dominant

## 8. Feature ideas

Flow evidence may include:
- normalized directional displacement
- directional efficiency
- structure progression rate
- persistence
- impulse quality
- failed extension rate
- counter-pressure
- velocity/acceleration
- volatility-normalized movement

All features must be timestamped and causal.

## 9. Authority

Flow:
- creates flow state
- informs role/regime/opportunity
- can contribute to parent invalidation when explicitly contracted

Flow cannot:
- place orders
- bypass news
- bypass risk
- bypass portfolio limits
- convert weak evidence into execution

## 10. Research

Do not assume FlowStrength is probabilistic until calibrated.

Test incremental value:
structure alone
vs structure + flow
vs structure + flow + PDE
across symbols, sessions and volatility regimes.
