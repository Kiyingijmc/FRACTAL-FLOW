# FRACTAL FLOW — CODEX HANDOFF
Version 1.0

## 1. Mission

Take over implementation of FRACTAL FLOW without losing the architectural reasoning developed before implementation.

The repository should become the durable source of truth.

Do not treat this project as a generic Forex EA.

It is a hierarchical state-driven scalping architecture with:
- adaptive market structure
- flow ownership
- primary/secondary/micro pullbacks
- weakening/resumption
- regime/role/location
- opportunity space
- tradeability
- dynamic risk
- news protection
- portfolio arbitration
- MT5 execution
- reconciliation
- position management
- TTL
- TradingView visualization
- research and adversarial verification

## 2. First task: audit, not code

Before implementing significant trading logic:

1. Read AGENTS.md.
2. Read all docs in numerical order.
3. Inspect the existing repository.
4. Map existing code to intended architecture.
5. Identify missing modules.
6. Identify contradictions.
7. Identify unsafe shortcuts.
8. Identify state-machine gaps.
9. Identify persistence gaps.
10. Identify execution/reconciliation race conditions.
11. Produce an architecture audit.

Do not silently resolve contradictions.

When ambiguity exists:
- identify it
- state the competing interpretations
- select only when the canonical documents establish a decision
- otherwise mark as OPEN DECISION

## 3. Canonical implementation order

### Phase 1 — primitives

Implement:
- enums
- StateEnvelope
- object identities
- parent/root lineage
- versions
- reason codes
- events
- configuration versions
- invariants
- persistence interfaces
- idempotency interfaces

Write tests first for lineage and state invariants.

### Phase 2 — market state

Implement:
- Data Quality
- Volatility
- Structure

Do not implement live order execution yet.

### Phase 3 — behavioral state

Implement:
- Flow Ownership
- PDE
- Regime
- Market Role
- Location

Verify parent-child behavior.

### Phase 4 — opportunity

Implement:
- Opportunity Engine
- timeframe mapping
- opportunity identity
- opportunity migration
- opportunity space
- Tradeability
- Unified TradeDecision
- final authorization gates

Still do not bypass MT5 authority.

### Phase 5 — protection/allocation

Implement:
- News Shield
- Risk
- Account Feasibility
- Portfolio Arbitration

Write adversarial tests before live execution integration.

### Phase 6 — execution

Implement:
- MT5 gateway
- order lifecycle
- idempotency
- partial fill
- unknown execution
- position reconciliation
- protection

### Phase 7 — management

Implement:
- dynamic TP
- partials
- structural trailing
- runner
- TTL
- decay
- news overlays
- configuration versioning

### Phase 8 — research/visualization

Implement:
- replay
- feature store
- labels
- calibration
- walk-forward
- adversarial suite
- TradingView visualization/state mirror

## 4. Core strategy rules

Use:
4H environment
1H directional state
30M structural context
15M primary opportunity/pullback
5M confirmation
1M execution

Do not permanently hard-code these as the only possible mapping; the mapping engine can migrate after confirmed structural transition.

## 5. Strategy families

Initial:
FF-01 FLOW_CONTINUATION
FF-02 COUNTERFLOW
FF-03 RANGE_ROTATION
FF-04 TRANSITION_BREAK

Everything else initially NO_TRADE.

## 6. Pullback rules

Primary pullback normally must be on a higher timeframe than execution.

Never classify an M1 micro pullback as the primary trading opportunity unless an explicit setup exception says so.

Pullback quality must consider:
- impulse
- counter displacement
- retracement
- duration
- velocity
- acceleration
- efficiency
- momentum
- range
- structural damage
- weakening
- resumption

No fixed Fibonacci law.
No fixed candle-count law.

## 7. Structure rules

Do not use fixed three-candle fractals as the core structure model.

Use adaptive:
- swings
- protected levels
- breaks
- failed breaks
- reclaims

Structural break requires more than a level touch:
LevelCross × DisplacementConfirmation × PersistenceConfirmation.

## 8. Flow rules

Flow is descriptive:
LongStrength
ShortStrength
Imbalance

Flow cannot directly produce BUY/SELL.

Use hysteresis to avoid ownership chatter.

## 9. Weakening and resumption

Weakening is not resumption.

Resumption requires structural recovery plus directional displacement and follow-through evidence.

False resumption must be modeled explicitly.

## 10. News

No strategic new exposure during NEWS_LOCKDOWN.

Ten minutes after news is a validation checkpoint, not an automatic restart.

If normalization fails, remain restricted.

Unscheduled abnormal shock can trigger protective lockdown.

## 11. Risk

Hard caps override dynamic risk.

Position size:
AllowedRisk / (SL_distance × ValuePerUnit)

Account feasibility can reject otherwise valid trades.

## 12. Portfolio

Currency exposure is mandatory.

Example:
EURUSD long + GBPUSD long + USDCHF short can be one concentrated USD-short thesis from an exposure perspective.

Arbitration:
ALLOW / DEFER / MERGE / REJECT

## 13. Execution

MT5 is authoritative.

Before submitting:
- reread current state
- verify lineage
- verify version
- verify news
- verify tradeability
- verify risk
- verify portfolio
- verify broker state

If state changes:
abort/revalidate.

Unknown execution state is not rejection.

## 14. Reconciliation

After restart:
persistent state
→ broker positions
→ pending orders
→ recent history
→ matching
→ lineage reconstruction
→ quarantine
→ protection
→ strategy enabled only after reconciliation

## 15. Position management

Structural trailing:
long below protected pullback low
short above protected pullback high

Ratchet only.

Runner may migrate to higher-timeframe structure.

TP is dynamic and can use:
structure
liquidity
momentum
volatility
session
expected resolution

## 16. TTL

Every trade has finite lifetime.

Decay:
time
progress shortfall
momentum
structural damage
volatility collapse
opportunity decay

Never rescue through hard structural invalidation.

## 17. Smart Overtrading

Smart Overtrading is an opportunity-budget engine.

It must not:
- treat every M1 trigger as a new opportunity
- ignore parent identity
- ignore risk/correlation
- churn through the same pullback

It may:
- re-enter within valid opportunity budgets
- participate in new structural legs
- respond to newly confirmed opportunities

## 18. Flipping

Never:
loss → immediate opposite trade.

Required:
thesis invalidation
→ structural reversal
→ independent opposite opportunity
→ valid entry
→ portfolio/risk authorization.

## 19. Research

Research must be causal.

Decision_t = f(Data_≤t)

Test incremental architecture:
FF-A
→ FF-B
→ FF-C
→ FF-D

Do not optimize away constitutional safety layers.

## 20. Definition of done

FRACTAL FLOW is not ready for live trading merely because:
- it compiles
- it produces signals
- it wins in one backtest
- it has a high win rate

Readiness requires:
- state integrity
- lineage integrity
- restart safety
- reconciliation
- execution idempotency
- risk enforcement
- news protection
- portfolio enforcement
- adversarial tests
- no-lookahead research
- OOS validation
- realistic spread/slippage/commission modeling
- broker constraint handling
- protective continuity

## 21. Final instruction

Do not optimize for impressive code volume.

Optimize for:
correctness
state integrity
risk containment
lineage integrity
testability
observability
reproducibility
maintainability
and only then performance.

If a requested implementation conflicts with this architecture, stop and identify the conflict before coding.
