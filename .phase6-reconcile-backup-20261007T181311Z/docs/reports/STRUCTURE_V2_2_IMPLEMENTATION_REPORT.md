# FRACTAL-FLOW Structure Engine v2.2 — Implementation & Verification Report

## Baseline

- Source baseline: remediated Structure v2 artifact derived from `816a142386abcb3ddf1c6c5b5a040f6075dd1b5a`.
- This artifact is an update of the remediated ZIP, not a modification of the historical original ZIP.
- Working-tree source tree SHA for the packaged tree (computed from a temporary Git index): `fc7aa7f023d0c212f8734ec8388e5076cd2d071c`.

## Implemented changes

1. Replaced the former trailing local-dominance candidate algorithm with an explicit bounded structural-excursion lifecycle.
2. Preserved immutable excursion origin (`created_from_timestamp`) while allowing a causal excursion extreme to extend (`candidate_at`, `price`).
3. Added explicit excursion ownership (`_active_excursion_side`) so one unresolved directional excursion is authoritative until confirmation or expiry.
4. Required directional continuation evidence for excursion extension; contrary wicks are reversal evidence rather than automatic candidate replacement.
5. Prevented same-observation confirmation of a newly created candidate by requiring positive candidate age.
6. Preserved first-observation ambiguity and deterministic stronger-evidence resolution when competing provisional candidates exist.
7. Made candidate expiry fail-closed and prevented same-observation recreation after expiry.
8. Preserved protected-level authority exclusively on confirmed structural swings.
9. Added `StructureEngine.authoritative_state()` as the canonical complete bounded decision-state surface for forensic causal-prefix and recovery tests.
10. Advanced StructureEngine snapshot schema to `structure-engine-v2.2`; the loader remains backward-compatible with `structure-engine-v2.1` snapshots.
11. Added adversarial tests for monotonic extension, shallow reversal, genuine reversal, authoritative-state completeness, and v2.2 snapshot round-trip.
12. Updated Structure v2 design and decision-log documentation to describe the implemented mathematics rather than the former local-neighborhood model.

## Verification

- Full pytest suite: **466 passed, 0 failed**.
- Coverage: **89%** with explicit `--cov=src` measurement.
- Warnings: 52, all from the existing pytest-asyncio/coverage environment; no test failures.
- `python -m compileall -q src tests`: PASS.
- Phase 2 Structure tests: **55 passed**.

## Environment limitations

The runtime used for this artifact did not contain the `ruff` executable or the `mypy` module. Therefore Ruff and mypy were not independently executed in this environment and are not claimed as verified here. GitHub CI remains the authoritative place to verify repository CI/toolchain gates.

## Mathematical closure

The implemented contract is:

`Market observation -> provisional excursion -> directional extension -> causal normalized reversal -> confirmed pivot -> structural relationship/event`

A new extreme inside an unresolved excursion extends that excursion; it does not create a new pivot epoch. Confirmed pivots are immutable historical facts, and their visibility begins only at `confirmed_at`.
