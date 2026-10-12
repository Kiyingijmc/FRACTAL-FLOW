# FRACTAL FLOW — PHASE 1A EVIDENCE REPORT

**Phase**: 1A — Canonical Market Primitives
**Status**: COMPLETE

---

## 1. Test Commands & Exit Statuses

| Command | Exit Code | Test Count | Status / Notes |
| :--- | :--- | :--- | :--- |
| `poetry run pytest --no-cov -q tests/phase1a` | 0 | 12 | All Phase 1A primitive tests passed |
| `poetry run pytest --no-cov -q tests/phase1a/test_tick_bar_equivalence.py` | 0 | 4 | Construction, Decimal preservation, timeframe rejection, tick-bar equivalence passed |
| `poetry run pytest --no-cov -q tests/phase1a/test_serialization_determinism.py` | 0 | 3 | Deterministic JSON round-trip, fingerprints, timeframe hierarchy passed |
| `poetry run pytest --no-cov -q tests/phase1a/test_aggregation_causality.py` | 0 | 5 | UTC boundary alignment, closed-bar causality, lower-TF bar aggregation, gap handling passed |
| `poetry run pytest` | 0 | 332 | Full test suite passed (Coverage: 87.92%, exceeds 85% requirement) |

---

## 2. Artifact Paths

- **Implementation**:
  - `src/fractal_flow/domain/market.py` — Canonical `Tick`, `Bar`, `Timeframe`, `BarAggregator`, and `aggregate_ticks_to_bars`
  - `src/fractal_flow/domain/__init__.py` — Module exports
- **Test Suite**:
  - `tests/phase1a/test_tick_bar_equivalence.py`
  - `tests/phase1a/test_serialization_determinism.py`
  - `tests/phase1a/test_aggregation_causality.py`
- **Evidence Record**:
  - `artifacts/phase1/phase1a_evidence.md`

---

## 3. Verified Architectural Invariants & Requirements

1. **Canonical Timeframe Model**: Supported hierarchy (`1M`, `5M`, `15M`, `30M`, `1H`, `4H`). Invalid timeframes (e.g. `2M`, `7M`) are strictly rejected with `ValueError`.
2. **Decimal Preservation**: Financial quantities (`bid`, `ask`, `spread`, `open`, `high`, `low`, `close`) use exact `Decimal` types with zero floating-point precision loss.
3. **UTC Normalization**: Period start timestamps use integer UTC boundary alignment (`(ts // tf.seconds) * tf.seconds`).
4. **Closed-Bar Causality**: Bars are marked `is_closed = True` strictly when an observation in a new period arrives or during an explicit period flush. No future observations are consumed.
5. **Deterministic Serialization**: SHA-256 fingerprints and JSON representations are deterministic, sorted-key, and round-trip losslessly using tagged Decimal encoding.
6. **No Competing Abstractions**: `Tick` and `Bar` complement `MarketObservation` without creating parallel or duplicate domain models.
