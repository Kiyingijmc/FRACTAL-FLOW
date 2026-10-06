# FRACTAL-FLOW Phase 2 / v2.3 Implementation Record

v2.3 establishes a causal cross-engine substrate and deterministic informational engines while preserving explicit Strategy/Risk/Execution authority boundaries.

## New substrate
- `InstrumentSpec` and tick-grid price relations.
- `CausalWatermark` and same-watermark `MarketContextSnapshot`.
- Explicit data validity semantics for cross-engine consumption.
- Deterministic evidence items, correlation groups, family caps and contradiction detection.

## New informational engines
- Regime: efficiency/persistence/volatility/compression/dispersion scorecard with dwell.
- PDE: project-specific **Price Dynamics Episode** state machine for impulse/pullback/resumption.
- Role: semantic interpretation only.
- Location: geometric context only; no risk authority.

## Safety boundary
No new engine can manufacture execution intent, size risk, submit orders, or reinterpret strategy authority.

## Compatibility
The existing v2.2 StructureEngine remains backward compatible. v2.3 adds the canonical substrate around it so migration can be validated independently rather than silently changing historical structural semantics.
