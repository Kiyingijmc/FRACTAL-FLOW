"""Isolated R5 acceptance worker.

One process owns exactly one seed.  The parent campaign runner treats this
process as disposable: no engine state, caches, or allocator lifetime crosses
seed boundaries.
"""
from __future__ import annotations

import json
import resource
import sys
import time

from tests.regression.test_phase5_r5_real_campaign import _run_real_campaign


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m tests.regression.r5_seed_worker SEED", file=sys.stderr)
        return 2
    seed = int(sys.argv[1])
    started = time.monotonic()
    _, _, processed, opportunities, _ = _run_real_campaign(seed, 10_000)
    elapsed = time.monotonic() - started
    usage = resource.getrusage(resource.RUSAGE_SELF)
    print(
        json.dumps(
            {
                "seed": seed,
                "processed": processed,
                "opportunities": opportunities,
                "elapsed_seconds": elapsed,
                "max_rss": usage.ru_maxrss,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
