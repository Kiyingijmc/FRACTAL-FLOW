# FRACTAL FLOW — AGENT INSTRUCTIONS
Version: 1.0
Status: Canonical project handoff
Purpose: Persistent instructions for Codex/Claude/other coding agents working on FRACTAL FLOW.

## 1. Project identity

FRACTAL FLOW is a hierarchical, state-driven Forex scalping system. It is NOT HFT.

Core thesis:
- Higher timeframes establish environment, directional ownership, structure, and permission.
- Lower timeframes confirm recovery/resumption and execute.
- A trade is the final result of multiple independent validity gates.
- Trade frequency is an output, never a quota.

Timeframe hierarchy:
4H → environment
1H → directional state
30M → structural context
15M → opportunity / primary pullback
5M → confirmation
1M → execution

Higher timeframes provide context/permission, not direct orders.

TradingView:
- visualization
- research
- state mirroring
- structure/opportunity display

MT5:
- authoritative execution
- live position state
- risk enforcement
- protective management
- reconciliation

TradingView must never override MT5.

## 2. Non-negotiable architectural invariants

1. Raw market data must flow through features → states → setups/opportunities → validity → tradeability → risk → portfolio arbitration → authorization → execution.
2. Strategy engines must not directly place MT5 orders.
3. PDE cannot call OrderSend.
4. Flow cannot open a position.
5. Risk cannot manufacture a signal.
6. Portfolio arbitration cannot manufacture direction.
7. Execution cannot reinterpret strategy.
8. News Shield cannot manufacture trades.
9. Confidence cannot turn an invalid object into a valid object.
10. Mandatory validity gates cannot be bypassed by a high score.
11. Every executable strategic object must have valid lineage.
12. Every child object carries parent_id, parent_version, and root_id.
13. A child cannot act when its required parent state/version is no longer valid.
14. Orphaned signals never execute.
15. Orphaned orders are reconciled before cancellation/finalization.
16. Orphaned positions may be protectively managed while ownership is reconstructed.
17. Uncertain state cannot create new exposure.
18. Strategy may be offline while protective control remains active.
19. Existing protective stops must never be loosened by a news/risk/management overlay.
20. No strategic new exposure during NEWS_LOCKDOWN.
21. Scheduled news and observed shock are separate concepts.
22. Ten minutes after news is a validation checkpoint, not an automatic restart rule.
23. No future data/lookahead.
24. Decisions use data available at or before decision time.
25. Pullbacks are hierarchical; an M1 micro pullback is not automatically a primary pullback.
26. Primary pullback normally occurs on a timeframe strictly higher than execution timeframe.
27. Lower-TF pullback exceptions must be explicit and classified as micro/subordinate.
28. Flipping is not immediate loss-to-opposite; opposite direction requires an independently valid structural reversal.
29. Liquidity sweeps are trigger modifiers, not standalone strategies.
30. Compression is a state, not an automatic signal.
31. Static EMA crossover is not the core strategy.
32. Fixed three-candle fractals are not the core structure engine.
33. Fixed Fibonacci thresholds are not constitutional pullback rules.
34. Fixed candle-count pullback rules are not constitutional.
35. Structural stops are primary; ATR/volatility is a buffer/rescue reference, not the thesis.
36. Every trade has finite lifetime through TTL.
37. Portfolio exposure must be currency-aware and correlation-aware.
38. Account feasibility must be checked before sizing/execution.
39. Configuration is versioned; news overlays must not overwrite the latest base configuration.
40. Reconciliation must complete before strategy authorization after restart/disconnect.
41. Research must test incremental information value rather than merely maximize backtest profit.
42. Constitutional rules are never optimized away.

## 3. Required development discipline

Before changing architecture:
- inspect existing implementation
- inspect canonical docs
- identify affected engines
- identify affected state transitions
- identify lineage implications
- identify persistence/restart implications
- identify race conditions
- identify tests that must change
- implement
- run unit/integration/adversarial tests
- verify invariants

Do not begin with entry code. Establish canonical types, state envelopes, events, lineage, versioning, persistence interfaces, and invariants first.

## 4. Canonical reading order

Read:
1. docs/00_CONSTITUTION.md
2. docs/01_ARCHITECTURE.md
3. docs/02_ENGINE_CONTRACTS.md
4. docs/03_STATE_MACHINE.md
5. docs/04_STRUCTURE_ENGINE.md
6. docs/05_FLOW_ENGINE.md
7. docs/06_PULLBACK_ENGINE.md
8. docs/07_REGIME_ENGINE.md
9. docs/08_OPPORTUNITY_ENGINE.md
10. docs/09_TRADEABILITY.md
11. docs/10_NEWS_SHIELD.md
12. docs/11_RISK_ENGINE.md
13. docs/12_PORTFOLIO_ARBITRATION.md
14. docs/13_EXECUTION.md
15. docs/14_RECONCILIATION.md
16. docs/15_POSITION_MANAGEMENT.md
17. docs/16_TTL.md
18. docs/17_TRADINGVIEW_MT5.md
19. docs/18_RESEARCH.md
20. docs/19_ADVERSARIAL_TESTING.md
21. CODEX_HANDOFF.md

## 5. Conflict resolution

If old brainstorming conflicts with the latest explicitly versioned canonical documentation:
- prefer the latest canonical decision
- preserve the old idea in DECISION_LOG if useful
- do not silently resurrect rejected designs

If the repository contains a newer versioned specification than this package, inspect it before modifying code.

## 6. Implementation phases

Phase 1: canonical types/state/events/lineage/versioning/invariants
Phase 2: Data Quality + Volatility + Structure
Phase 3: Flow + PDE + Regime + Role + Location
Phase 4: Opportunity + Tradeability + Decision authorization
Phase 5: News + Risk + Portfolio arbitration
Phase 6: MT5 execution + reconciliation + position management + TTL + protection
Phase 7: TradingView + research/replay + adversarial verification

No phase may bypass the safety architecture of earlier phases.
