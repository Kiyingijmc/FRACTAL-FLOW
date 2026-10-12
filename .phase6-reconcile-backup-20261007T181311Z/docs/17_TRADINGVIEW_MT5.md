# TRADINGVIEW ↔ MT5 ARCHITECTURE
Version 1.0

## 1. Principle

One conceptual strategy, two operational surfaces.

TradingView:
- visualization
- research
- structure display
- state display
- opportunity display
- optional alert/research integration

MT5:
- authoritative live execution
- authoritative live position state
- risk
- protection
- reconciliation

## 2. TradingView display

Example state display:

4H LONG ENVIRONMENT
1H LONG FLOW
30M CONTEXT
15M PULLBACK ACTIVE
5M WEAKENING
1M RECOVERY
NEWS NORMAL
TRADE WAITING

Later:

4H LONG
15M RESUMPTION CONFIRMED
5M FOLLOW-THROUGH
1M EXECUTION READY
TRADE AUTHORIZED

Display state should be human-readable, not a cockpit of every raw feature.

## 3. No split brain

TradingView must not run a competing execution brain.

If TradingView generates an alert:
- it is an informational candidate/input
- MT5 must independently validate current state
- MT5 must enforce lineage, news, risk, portfolio and tradeability

## 4. State mirroring

A state/event stream can expose:
- regime
- role
- structure
- pullback
- flow
- opportunity
- news
- risk
- tradeability
- position

The authoritative version should be clearly identified.

## 5. Research

TradingView may be used to:
- inspect historical state
- visualize structure
- validate interpretation
- compare setups
- support discretionary investigation

Research results must not be treated as production evidence until reproduced through the causal research pipeline.

## 6. MT5

MT5 owns:
- order submission
- fill state
- position state
- SL/TP
- protection
- reconciliation
- broker constraints

## 7. Failure behavior

If TradingView unavailable:
MT5 strategy may continue if its own data/state prerequisites remain valid.

If MT5 unavailable:
new execution must stop; protective mechanisms must follow broker/architecture safety plan.

## 8. Time synchronization

All events require canonical timestamps.

Handle:
- broker timezone
- UTC
- DST
- session boundaries
- calendar timezone
- historical data timestamps

Never mix timezone assumptions silently.

## 9. State display and lineage

A TradingView visualization should be able to identify:
- state id
- object id
- opportunity id
- configuration version
- timestamp

This allows visual state to be traced back to the authoritative engine.
