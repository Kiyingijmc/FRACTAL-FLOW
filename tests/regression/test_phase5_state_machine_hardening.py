from __future__ import annotations

from decimal import Decimal
import random

from src.fractal_flow.domain.envelope import GLOBAL_STATE_REGISTRY
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.phase2 import Phase2Pipeline


def _random_bar(seed_rng: random.Random, index: int, price: Decimal) -> tuple[Bar, Decimal]:
    step = Decimal(str(round(seed_rng.gauss(0, 0.0005), 7)))
    close = max(Decimal("0.5"), price + step)
    high = max(price, close) + Decimal(str(round(abs(seed_rng.gauss(0, 0.0002)), 7)))
    low = min(price, close) - Decimal(str(round(abs(seed_rng.gauss(0, 0.0002)), 7)))
    return (
        Bar.create(
            "EURUSD", "1M", index * 60, (index + 1) * 60,
            price, high, low, close, sequence=index + 1,
        ),
        close,
    )


def test_transition_resolver_routes_only_through_spec_edges() -> None:
    assert GLOBAL_STATE_REGISTRY.resolve_transition("RegimeState", "CHAOTIC", "TREND_UP") == (
        "TRANSITION", "TREND_UP"
    )
    role_path = GLOBAL_STATE_REGISTRY.resolve_transition("RoleState", "BREAKOUT", "COUNTERFLOW")
    assert role_path[-1] == "COUNTERFLOW"
    assert len(role_path) >= 1
    assert GLOBAL_STATE_REGISTRY.resolve_transition(
        "PDEResumptionState", "DISPLACEMENT_CANDIDATE", "RECOVERY_CONFIRMED"
    ) == ("RECOVERY_CONFIRMED",)


def test_real_phase2_random_walks_have_zero_transition_exceptions() -> None:
    failures: list[tuple[int, int, str]] = []
    for seed in range(5):
        rng = random.Random(seed)
        pipeline = Phase2Pipeline("EURUSD", "1M")
        price = Decimal("1.1000")
        for index in range(100):
            bar, price = _random_bar(rng, index, price)
            try:
                pipeline.process_bar(bar)
            except Exception as exc:  # pragma: no cover - assertion captures unexpected failures
                failures.append((seed, index, f"{type(exc).__name__}: {exc}"))
                break
    assert failures == []


def _campaign_bar(rng: random.Random, index: int, price: Decimal, mode: int) -> tuple[Bar, Decimal]:
    """Generate deterministic causal bars spanning distinct market-shape families."""
    phase = index % 125
    if mode == 0:  # random walk
        delta = Decimal(str(round(rng.gauss(0, 0.0005), 7)))
    elif mode == 1:  # trend
        direction = Decimal("0.00018") if (index // 125) % 2 == 0 else Decimal("-0.00018")
        delta = direction + Decimal(str(round(rng.gauss(0, 0.00018), 7)))
    elif mode == 2:  # range
        delta = Decimal(str(round(rng.gauss(0, 0.00022), 7)))
        if phase in (0, 1):
            delta += Decimal("0.00045") if (index // 125) % 2 == 0 else Decimal("-0.00045")
    elif mode == 3:  # volatility shock / gap
        shock = Decimal("0.0015") if (index // 25) % 2 == 0 else Decimal("-0.0015")
        delta = shock + Decimal(str(round(rng.gauss(0, 0.0008), 7))) if phase == 60 else Decimal(str(round(rng.gauss(0, 0.00035), 7)))
    else:  # chaotic alternating pressure
        sign = Decimal("1") if (index + mode) % 2 == 0 else Decimal("-1")
        delta = sign * Decimal(str(round(abs(rng.gauss(0, 0.0007)), 7)))

    close = max(Decimal("0.5"), price + delta)
    wick = Decimal(str(round(abs(rng.gauss(0, 0.00025)), 7)))
    high = max(price, close) + wick
    low = min(price, close) - wick
    return (
        Bar.create(
            "EURUSD", "1M", index * 60, (index + 1) * 60,
            price, high, low, close, sequence=index + 1,
        ),
        close,
    )


def _assert_evaluation_states_are_spec_legal(previous, current) -> None:
    machine_fields = {
        "FlowState": "flow",
        "RegimeState": "regime",
        "PDEState": "pde",
        "PDEResumptionState": "pde_resumption",
        "LocationState": "location",
        "RoleState": "role",
        "DataQualityState": "data_quality",
        "VolatilityState": "volatility",
    }
    previous_states = previous.context.states
    current_states = current.context.states
    for machine, field in machine_fields.items():
        old_value = str(previous_states[field])
        new_value = str(current_states[field])
        if old_value != new_value:
            GLOBAL_STATE_REGISTRY.resolve_transition(machine, old_value, new_value)


def test_r2_real_engine_state_machine_campaign_500x500() -> None:
    """Acceptance-scale fallback for the unavailable Hypothesis state-machine dependency.

    Run only with ``FF5_R2_STRESS=1``.  Partitioning uses inclusive seed ranges via
    ``FF5_R2_SEED_START``/``FF5_R2_SEED_END`` so the 500-seed population can be
    executed in disposable processes without changing the acceptance predicate.
    """
    import os

    if os.getenv("FF5_R2_STRESS") != "1":
        return

    start = int(os.getenv("FF5_R2_SEED_START", "0"))
    end = int(os.getenv("FF5_R2_SEED_END", "500"))
    assert 0 <= start < end <= 500

    failures: list[tuple[int, int, str]] = []
    observed_edges: set[tuple[str, str, str]] = set()
    processed = 0
    for seed in range(start, end):
        rng = random.Random(seed)
        mode = seed % 5
        pipeline = Phase2Pipeline("EURUSD", "1M")
        price = Decimal("1.1000")
        previous = None
        for index in range(500):
            bar, price = _campaign_bar(rng, index, price, mode)
            try:
                evaluation = pipeline.process_bar(bar)
                if previous is not None:
                    _assert_evaluation_states_are_spec_legal(previous, evaluation)
                    for machine, field in {
                        "FlowState": "flow",
                        "RegimeState": "regime",
                        "PDEState": "pde",
                        "PDEResumptionState": "pde_resumption",
                        "LocationState": "location",
                        "RoleState": "role",
                        "DataQualityState": "data_quality",
                        "VolatilityState": "volatility",
                    }.items():
                        old = str(previous.context.states[field])
                        new = str(evaluation.context.states[field])
                        if old != new:
                            path = GLOBAL_STATE_REGISTRY.resolve_transition(machine, old, new)
                            current = old
                            for target in path:
                                observed_edges.add((machine, current, target))
                                current = target
                previous = evaluation
                processed += 1
            except Exception as exc:  # pragma: no cover - failure payload is assertion evidence
                failures.append((seed, index, f"{type(exc).__name__}: {exc}"))
                break

    assert failures == []
    expected = (end - start) * 500
    assert processed == expected
    assert observed_edges, "campaign produced no state transitions"
