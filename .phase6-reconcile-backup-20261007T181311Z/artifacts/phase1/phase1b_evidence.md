# FRACTAL FLOW — PHASE 1B EVIDENCE REPORT

**Phase**: 1B — Data Quality Engine
**Status**: COMPLETE

---

## 1. Test Commands & Exit Statuses

| Command | Exit Code | Test Count | Status / Notes |
| :--- | :--- | :--- | :--- |
| `poetry run pytest --no-cov -q tests/phase1b` | 0 | 14 | All Data Quality engine tests passed |
| `poetry run pytest --no-cov -q tests/phase1b/test_data_quality_anomalies.py` | 0 | 9 | Anomaly detection test suite passed |
| `poetry run pytest --no-cov -q tests/phase1b/test_state_envelope_transitions.py` | 0 | 2 | Envelope creation & state machine transition tests passed |
| `poetry run pytest --no-cov -q tests/phase1b/test_invalid_data_blocks_exposure.py` | 0 | 3 | Guard rule DATA != VALID -> NEW EXPOSURE FORBIDDEN tests passed |
| `poetry run pytest` | 0 | 332 | Full test suite passed (Coverage: 87.92%, exceeds 85% requirement) |

---

## 2. Artifact Paths

- **Implementation**:
  - `src/fractal_flow/domain/data_quality.py` — Data Quality Engine, state machine, anomaly evaluator, and assessment models
  - `src/fractal_flow/domain/reason_codes.py` — Data quality reason codes
  - `src/fractal_flow/domain/__init__.py` — Module exports
  - `spec/states.yaml` & `spec/transitions.yaml` — Canonical DataQualityState declarations and transitions
- **Test Suite**:
  - `tests/phase1b/test_data_quality_anomalies.py`
  - `tests/phase1b/test_state_envelope_transitions.py`
  - `tests/phase1b/test_invalid_data_blocks_exposure.py`
- **Evidence Record**:
  - `artifacts/phase1/phase1b_evidence.md`

---

## 3. Verified Anomaly Detection & State Coverage

The engine evaluates data stream integrity and detects all required anomaly classes with deterministic reason codes:

1. **Duplicate Ticks & Bars**: Detected via fingerprint caching (`DUPLICATE_DATA`).
2. **Sequence Gaps**: Sequence increments > 1 trigger `SEQUENCE_GAP`.
3. **Out-of-Order Data**: Chronology regression triggers `OUT_OF_ORDER_DATA`.
4. **Stale Quotes & Bars**: Observation age > max staleness triggers `DATA_STALE`.
5. **Zero/Negative/Spiking Spreads**: Spread <= 0 triggers `SPREAD_ZERO_OR_NEGATIVE`; spread > max allowed pips triggers `SPREAD_SPIKE_DETECTED`.
6. **Malformed Timestamps**: Negative or invalid timestamps trigger `TIMESTAMP_MALFORMED`.
7. **UTC/DST Anomalies**: Future processing clock skew triggers `UTC_DST_ANOMALY`.
8. **Weekend & Session Discontinuities**: Multi-day gaps without session close metadata trigger `SESSION_DISCONTINUITY`.
9. **Impossible OHLC**: High < Low or zero/negative prices trigger `IMPOSSIBLE_OHLC`.
10. **Missing Timeframe Observations**: Timeframe bar gaps trigger `TIMEFRAME_OBSERVATION_MISSING`.

---

## 4. Enforcement of Exposure Blocking & Non-Strategy Boundary

1. **Guard Rule Enforcement**: `DATA != VALID -> NEW EXPOSURE FORBIDDEN`. `is_valid_for_exposure()` returns `True` strictly when `state in (DATA_NORMAL, DATA_VALID)`. For any degraded, stale, corrupted, boot, or unavailable state, `exposure_allowed` evaluates to `False` and attaches `EXPOSURE_FORBIDDEN_DATA_INVALID`.
2. **Strategy Separation**: The `DataQualityEngine` emits only `DataQualityAssessment` and `StateEnvelope` objects. Tests prove that it carries zero strategy direction (direction, order type, position size, or buy/sell signals).
