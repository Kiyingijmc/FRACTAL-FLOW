# Phase 2 — Constitutional Feature Dependency Audit

This document audits every occurrence of Fibonacci levels and candle-count / duration metrics across the FRACTAL FLOW codebase, specifications, documentation, and tests to verify that no fixed Fibonacci threshold or fixed candle-count rule acts as a constitutional validity criterion.

---

## 1. Fibonacci Feature Audit

| Feature Reference | File / Location | Occurrence Category | Constitutional Law? | Audit Findings & Evidence |
|---|---|---|---|---|
| Invariant #33 | `spec/invariants.yaml:259` | Specification Rule | **NO** | States explicitly: "Fixed Fibonacci thresholds are not constitutional pullback rules." |
| Decision D-007 | `docs/DECISION_LOG.md:24` | Governance Decision | **NO** | Ratifies: "Pullback depth is a feature, not a fixed Fibonacci law." |
| Pullback Rule | `docs/06_PULLBACK_ENGINE.md:112` | Engine Specification | **NO** | Mandates: "No fixed Fibonacci or candle-count law." |
| Spec Evidence | `spec/phase1_evidence.yaml:470` | Evidence Manifest | **NO** | Identifies Fibonacci levels as descriptive/contextual research features. |
| Test Fixture | `tests/test_phase2_spec_reconciliation.py:237` | Test Fixture | **NO** | `test_fibonacci_independence_principle` verifies constitutional validity is independent of Fibonacci depth. |
| Literal `50.0` | `src/fractal_flow/domain/murg.py:385` | Production Code | **NO** | Local default score assignment in MURG context, not a Fibonacci threshold. |
| Literal `50.0` | `tests/test_units_broker.py:44` | Test Fixture | **NO** | Pip distance unit test fixture value (50.0 pips), not a Fibonacci threshold. |

---

## 2. Candle Count & Duration Metric Audit

| Feature Reference | File / Location | Occurrence Category | Constitutional Law? | Audit Findings & Evidence |
|---|---|---|---|---|
| Invariant #34 | `spec/invariants.yaml:267` | Specification Rule | **NO** | States explicitly: "Fixed candle-count pullback rules are not constitutional." |
| Decision D-008 | `docs/DECISION_LOG.md:26` | Governance Decision | **NO** | Ratifies: "Duration is measured adaptively." |
| `duration_ratio` | `src/fractal_flow/domain/models.py:87` | Domain Model | **NO** | Descriptive ratio metric (`Pullback.duration / Impulse.duration`) on `PullbackObject`, not an entry gate. |
| Structure Engine | `src/fractal_flow/domain/structure.py` | Production Code | **NO** | Uses volatility-normalized reversal displacement ($V_{local} = \text{Displacement} / ATR$), not fixed candle-count fractals. |
| Structure Test | `tests/phase1h/test_invariant_failure_modes.py:14` | Production Test | **NO** | Explicitly proves `StructureEngine` uses $V_{local}$ adaptive displacement rather than 3-candle fractals. |
| Test Fixture | `tests/test_phase2_spec_reconciliation.py:258` | Test Fixture | **NO** | `test_candle_count_independence_principle` verifies structure validity is independent of fixed candle counts. |

---

## 3. Executive Conclusion

Fixed Fibonacci ratios (e.g. 38.2%, 50.0%, 61.8%, 78.6%) and fixed candle counts / bar counts are strictly classified as **descriptive, contextual, research, and diagnostic features**.

No production execution path or constitutional validity gate in FRACTAL FLOW depends on a fixed Fibonacci threshold or fixed candle-count law.
