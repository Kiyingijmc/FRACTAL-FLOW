# FLOW OWNERSHIP ENGINE
Version 1.1

## 1. Objective

Describe which side currently controls directional pressure and whether that ownership is strengthening, weakening, balanced, contested, or transitioning.

## 2. Core quantities

FlowStrength_Long
FlowStrength_Short

FlowImbalance = FlowStrength_Long - FlowStrength_Short

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

## 4. Temporal Mechanisms

The Flow Engine explicitly separates four temporal controls:

1. **Persistence**: Accumulation of consecutive directional evidence (long vs. short).
2. **Hysteresis**: Asymmetric thresholds preventing oscillation across boundaries.
3. **State Dwell**: Minimum residence observation count (`min_dwell_bars`) required in the active state before transition eligibility.
4. **Transition Confirmation**: Consecutive candidate observation count (`transition_confirm_bars`) required before committing a state transition.

## 5. Authority & Boundaries

Flow:
- creates flow state
- informs role/regime/opportunity
- cannot place orders, size trades, or alter risk parameters.
