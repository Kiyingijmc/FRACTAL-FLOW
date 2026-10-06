# FRACTAL FLOW — PHASE 1D EVIDENCE REPORT

**Phase**: 1D — No-Lookahead Causal Test Framework
**Status**: COMPLETE

---

## 1. Test Commands & Exit Statuses

| Command | Exit Code | Test Count | Status / Notes |
| :--- | :--- | :--- | :--- |
| `poetry run pytest --no-cov -q tests/phase1d` | 0 | 13 | Causal test suite passed |
| `poetry run pytest --no-cov -q tests/phase1d/test_future_mutations.py` | 0 | 12 | All 12 future mutation tests passed |
| `poetry run pytest --no-cov -q tests/phase1d/test_confirmation_timestamps.py` | 0 | 1 | Confirmation timestamp causality test passed |
| `poetry run pytest` | 0 | 321 | Full test suite passed (Coverage: 87.62%, exceeds 85% requirement) |

---

## 2. Artifact Paths

- **Implementation**:
  - `src/fractal_flow/simulation/causal_framework.py` — Reusable `CausalTestFramework` and field classifier
- **Test Suite**:
  - `tests/phase1d/test_future_mutations.py`
  - `tests/phase1d/test_confirmation_timestamps.py`
- **Evidence Record**:
  - `artifacts/phase1/phase1d_evidence.md`

---

## 3. Future Mutation Experiment Matrix

| ID | Scenario | Test Function | Decision Time $t$ | Permissible Max $t_{input}$ | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Future Price Spike | `test_1_future_price_spike` | `BASE_TS + 40` | `BASE_TS + 40` | PASS |
| 2 | Future Crash | `test_2_future_crash` | `BASE_TS + 40` | `BASE_TS + 40` | PASS |
| 3 | Future Spread Explosion | `test_3_future_spread_explosion` | `BASE_TS + 40` | `BASE_TS + 40` | PASS |
| 4 | Future Volatility Explosion | `test_4_future_volatility_explosion` | `BASE_TS + 40` | `BASE_TS + 40` | PASS |
| 5 | Future Structural Break | `test_5_future_structural_break` | `BASE_TS + 40` | `BASE_TS + 40` | PASS |
| 6 | Future News Event | `test_6_future_news_event` | `BASE_TS + 40` | `BASE_TS + 40` | PASS |
| 7 | Future Session Close | `test_7_future_session_close` | `BASE_TS + 40` | `BASE_TS + 40` | PASS |
| 8 | Future Bar Replacement | `test_8_future_bar_replacement` | `BASE_TS + 40` | `BASE_TS + 40` | PASS |
| 9 | Future Duplicate Data | `test_9_future_duplicate_data` | `BASE_TS + 40` | `BASE_TS + 40` | PASS |
| 10 | Future Missing Data | `test_10_future_missing_data` | `BASE_TS + 40` | `BASE_TS + 40` | PASS |
| 11 | Future Normalization Regime Change | `test_11_future_normalization_regime_change` | `BASE_TS + 40` | `BASE_TS + 40` | PASS |
| 12 | Future Extreme Value | `test_12_future_extreme_value` | `BASE_TS + 40` | `BASE_TS + 40` | PASS |

---

## 4. Field Classification & Confirmation Timestamp Rules

1. **Decision State Classification**: Fields evaluated for equality at time $t$ include `state`, `previous_state`, `version`, `symbol`, `timeframe`, `bid`, `ask`, `open`, `high`, `low`, `close`, `spread`, `reason_codes`, `exposure_allowed`, `root_id`, `parent_id`, `parent_version`.
2. **Processing Metadata Classification**: Infrastructure fields excluded from decision state equality assertions are strictly `processing_timestamp`, `execution_wall_clock`, and `host_id`.
3. **Confirmation Timestamp Invariant**: Retrospectively confirmed structural swings are timestamped at the actual confirmation timestamp ($T_{confirmation} > T_{extreme}$), never at the earlier extreme timestamp, preventing lookahead bias in historical replay.
