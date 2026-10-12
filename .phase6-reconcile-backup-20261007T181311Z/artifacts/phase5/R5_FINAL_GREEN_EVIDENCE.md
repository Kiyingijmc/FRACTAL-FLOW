# FRACTAL-FLOW — R5 FINAL GREEN EVIDENCE

Date: 2026-10-07
Scope: R5 verification lifecycle remediation and closure only.

## Gate result

**🟢 FINAL GREEN — ARTIFACT MAY BE GENERATED**

## Reproducible evidence

### R5 canonical lifecycle

Command:

```bash
python tools/r5_verification_runner.py
```

Result:

- R5-A-normal: 7 passed; returncode=0; timeout=False; cleanup=True
- R5-B-durable: 3 passed; returncode=0; timeout=False; cleanup=True
- R5-C-gates: 3 passed; returncode=0; timeout=False; cleanup=True
- Summary: `R5_VERIFICATION_SUMMARY lanes=3 passed=3 total=3`

The runner isolates the no-coverage subprocess from inherited pytest plugin/addopts state. The underlying R5 test nodeids and assertions are unchanged.

### Runner contract / timeout path

Command:

```bash
python -m pytest --no-cov -q tests/test_r5_verification_runner.py
```

Result: **4 passed**.

The forced-timeout path proves timeout is reported as failure, cleanup succeeds, and no bytes/str exception escapes.

### Compilation / focused final checks

Commands:

```bash
python -m compileall -q src tests tools
python -m pytest --no-cov -q tests/test_r5_verification_runner.py tests/regression/test_phase5_r5_real_campaign.py::test_r5_full_causal_census_shape_is_exactly_300
```

Result: **5 passed** for the focused pytest command; compileall passed.

### Full regression

Command:

```bash
python -m pytest --no-cov -q
```

Result: **761 passed, 6 xfailed**.

### Full coverage

Command:

```bash
python -m pytest -q
```

Result: **761 passed, 6 xfailed; 89.58% total coverage**.

Required floor: **85%**.

## Environmental exceptions

- Ruff: UNVERIFIED / ENVIRONMENTAL EXCEPTION (executable unavailable)
- mypy: UNVERIFIED / ENVIRONMENTAL EXCEPTION (executable unavailable)
- Git provenance: UNVERIFIED / ENVIRONMENTAL EXCEPTION (`.git` metadata unavailable)

These are not represented as successful tool runs.

## Scope boundary

This green gate closes the **R5 verification lifecycle**. It does not authorize live trading and does not establish Phase 6 MT5 execution, broker interoperability, protective autonomy, or live-account safety.
