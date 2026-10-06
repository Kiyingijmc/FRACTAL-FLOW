"""Disposable worker for the R5 causal mutation census.

The worker intentionally owns one bounded census execution and then exits.
This prevents cumulative pytest state/coverage/plugin lifetimes from retaining
large production object graphs across R5 tests.
"""
from __future__ import annotations

import json
import os

from tests.regression.test_phase5_r5_real_campaign import (
    _causal_seed_mode_batch,
    _m1_stream,
    _run_and_capture_prefixes,
)

def main() -> int:
    full = os.getenv("FF5_R5_CAUSAL_STRESS") == "1"
    prefixes = (20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 295) if full else (20, 100, 200)
    seeds = tuple(range(10)) if full else tuple(range(2))
    partitions = int(os.getenv("FF5_R5_CAUSAL_PARTS", "1"))
    partition = int(os.getenv("FF5_R5_CAUSAL_PART", "0"))
    if not 1 <= partitions <= len(seeds) * 2 or not 0 <= partition < partitions:
        raise SystemExit("invalid causal worker partition")
    jobs = [(seed, prefix, mode) for seed in seeds for prefix in prefixes for mode in (0, 1)]
    selected = jobs[partition::partitions]
    limit_raw = os.getenv("FF5_R5_CAUSAL_WORKER_LIMIT")
    if limit_raw and not full:
        limit = int(limit_raw)
        if limit < 1:
            raise SystemExit("FF5_R5_CAUSAL_WORKER_LIMIT must be positive")
        selected = selected[:limit]
    grouped: dict[tuple[int, int], list[int]] = {}
    for seed, prefix, mode in selected:
        grouped.setdefault((seed, mode), []).append(prefix)
    baseline: dict[int, dict[int, tuple]] = {}
    for seed in sorted({seed for seed, _, _ in selected}):
        selected_prefixes = {prefix for s, prefix, _ in selected if s == seed}
        baseline[seed] = _run_and_capture_prefixes(_m1_stream(seed, 300), {p * 60 for p in selected_prefixes})
    observed = 0
    for (seed, mode), selected_prefixes in sorted(grouped.items()):
        result = _causal_seed_mode_batch(seed, tuple(selected_prefixes), mode)
        for prefix in selected_prefixes:
            if result[prefix] != baseline[seed][prefix * 60]:
                raise AssertionError(f"causal prefix mismatch seed={seed} prefix={prefix} mode={mode}")
            observed += 1
    print(json.dumps({"selected_jobs": len(selected), "observed_trials": observed, "full_stress": full}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
