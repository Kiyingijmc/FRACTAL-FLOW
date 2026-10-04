# FRACTAL FLOW — PHASE 1E EVIDENCE REPORT

**Phase**: 1E — Volatility Engine
**Status**: COMPLETE

---

## 1. Test Commands & Exit Statuses

| Command | Exit Code | Test Count | Status / Notes |
| :--- | :--- | :--- | :--- |
| `poetry run pytest --no-cov -q tests/phase1e` | 0 | 6 | All Volatility Engine tests passed |
| `poetry run pytest --no-cov -q tests/phase1e/test_volatility_formulas.py` | 0 | 2 | Wilder ATR & Volatility State Machine tests passed |
| `poetry run pytest --no-cov -q tests/phase1e/test_volatility_causality.py` | 0 | 2 | Causality verification & serialization passed |
| `poetry run pytest --no-cov -q tests/phase1e/test_volatility_numerical_policy.py` | 0 | 2 | Numerical type policy & envelope conversion passed |
| `poetry run pytest` | 0 | 327 | Full test suite passed (Coverage: 87.83%, exceeds 85% requirement) |

---

## 2. Artifact Paths

- **Implementation**:
  - `src/fractal_flow/domain/volatility.py` — `VolatilityEngine`, `VolatilityMetrics`, `VolatilityState`
  - `src/fractal_flow/domain/__init__.py` — Module exports
  - `spec/states.yaml` & `spec/transitions.yaml` — VolatilityState declarations and transitions
- **Formula Matrix**:
  - `artifacts/phase1/formula_matrix.md` — Detailed formula and parameter registry
- **Test Suite**:
  - `tests/phase1e/test_volatility_formulas.py`
  - `tests/phase1e/test_volatility_causality.py`
  - `tests/phase1e/test_volatility_numerical_policy.py`
- **Evidence Record**:
  - `artifacts/phase1/phase1e_evidence.md`

---

## 3. Metric Classifications & Numerical Policy Attestation

1. **Formula Registry**: Every implemented metric appears in `artifacts/phase1/formula_matrix.md` with explicit formula, source, inputs, lookback, warmup, causal boundary, numerical type, missing-data behavior, version, and calibration status.
2. **Classification**: All 11 volatility metrics are classified as `EXECUTABLE_CANONICAL`. Zero metrics are `UNRESOLVED`.
3. **Numerical Type Policy**:
   - Financial price/spread quantities (`true_range`, `atr_14`, `session_range`) strictly use exact `Decimal` types.
   - Statistical quantities (`realized_volatility`, `local_volatility`, `short_volatility`, `rolling_percentile`, `range_percentile`, `expansion_rate`, `contraction_rate`, `shock_score`) use `float`.
