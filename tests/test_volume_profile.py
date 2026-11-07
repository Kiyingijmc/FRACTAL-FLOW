from decimal import Decimal

import pytest

from src.fractal_flow.research.volume_profile import (
    PriceGrid,
    ProfileDomain,
    ProfileEvent,
    QualityState,
    SourceIdentity,
    VolumeProfileConfig,
    VolumeProfileInputError,
    calculate_volume_profile,
    profiles_comparable,
)

D = Decimal


@pytest.fixture
def source() -> SourceIdentity:
    return SourceIdentity(
        source_id="feed-A",
        symbol="EURUSD",
        domain=ProfileDomain.FX_QUOTE_ACTIVITY,
        activity_unit="quote_events",
        data_version="feed-A-v1",
        calendar_id="FX-24x5",
        calendar_version="calendar-v1",
    )


@pytest.fixture
def grid() -> PriceGrid:
    return PriceGrid(tick_size=D("0.01"), grid_origin=D("0.00"), price_unit="EURUSD_price")


def event(
    event_id: str,
    price: str,
    weight: str = "1",
    *,
    time: int = 1,
    available: int | None = None,
    sequence: int = 1,
    source_id: str = "feed-A",
    symbol: str = "EURUSD",
    domain: ProfileDomain = ProfileDomain.FX_QUOTE_ACTIVITY,
) -> ProfileEvent:
    return ProfileEvent(
        event_id=event_id,
        source_id=source_id,
        symbol=symbol,
        domain=domain,
        event_time_ns=time,
        available_at_ns=time if available is None else available,
        source_sequence=sequence,
        price=D(price),
        weight=D(weight),
    )


def calc(events, source, grid, config=None, watermark=100):
    return calculate_volume_profile(
        events,
        source=source,
        grid=grid,
        config=config or VolumeProfileConfig(),
        watermark_ns=watermark,
    )


def test_hand_calculated_profile_total_poc_and_value_area(source, grid):
    events = [
        event("a", "1.00", "2", time=1),
        event("b", "1.01", "5", time=2),
        event("c", "1.02", "3", time=3),
    ]
    result = calc(events, source, grid, VolumeProfileConfig(bin_ticks=1, value_area_fraction=D("0.70")))
    assert result.quality_state is QualityState.VALID
    assert result.total_weight == D("10")
    assert result.features["poc_bin_index"] == 101
    assert result.features["poc_tie_count"] == 1
    assert result.features["val_price"] == D("1.01")
    assert result.features["vah_price"] == D("1.03")
    assert result.features["value_area_fraction_achieved"] == D("0.8")
    assert result.features["activity_unit"] == "quote_events"
    assert result.features["source_domain"] == "FX_QUOTE_ACTIVITY"


def test_future_append_does_not_change_prior_output(source, grid):
    prefix = [event("a", "1.00", time=1), event("b", "1.01", time=2)]
    future = event("future", "9.99", "1000000", time=101, available=101)
    bounded = VolumeProfileConfig(max_events=2)
    left = calc(prefix, source, grid, bounded, watermark=10)
    right = calc(prefix + [future], source, grid, bounded, watermark=10)
    assert left.fingerprint == right.fingerprint
    assert left.canonical_payload() == right.canonical_payload()


def test_future_available_event_excluded_even_if_event_time_is_old(source, grid):
    events = [event("a", "1.00", time=1), event("late", "1.99", time=2, available=50)]
    result = calc(events, source, grid, watermark=10)
    assert result.included_event_count == 1
    assert result.total_weight == D("1")
    assert result.quality_state is QualityState.WARMING_UP


def test_identical_duplicate_is_idempotent_and_reported(source, grid):
    item = event("a", "1.00", time=1)
    result = calc([item, item], source, grid)
    assert result.included_event_count == 1
    assert result.duplicate_event_count == 1
    assert result.total_weight == D("1")
    assert "IDENTICAL_DUPLICATES_IGNORED" in result.reason_codes


def test_conflicting_duplicate_id_rejected(source, grid):
    with pytest.raises(VolumeProfileInputError, match="conflicting payload") as caught:
        calc([event("same", "1.00"), event("same", "1.01")], source, grid)
    assert caught.value.reason_code == "CONFLICTING_DUPLICATE_EVENT_ID"



def test_future_conflict_does_not_poison_earlier_watermark(source, grid):
    prefix = [event("same", "1.00", time=1)]
    future_conflict = event("same", "9.99", "999", time=50, available=50)
    before = calc(prefix, source, grid, watermark=10)
    after = calc(prefix + [future_conflict], source, grid, watermark=10)
    assert before.fingerprint == after.fingerprint


def test_off_grid_price_rejected_without_rounding(source, grid):
    with pytest.raises(VolumeProfileInputError) as caught:
        calc([event("a", "1.001")], source, grid)
    assert caught.value.reason_code == "OFF_GRID_PRICE"


def test_negative_tick_index_uses_floor_bin_assignment(source):
    grid = PriceGrid(D("1"), D("0"), "generic_price")
    cfg = VolumeProfileConfig(bin_ticks=2, anchor_tick_index=0)
    result = calc([
        event("a", "-1", source_id="feed-A", symbol="EURUSD", domain=ProfileDomain.FX_QUOTE_ACTIVITY),
        event("b", "-2", source_id="feed-A", symbol="EURUSD", domain=ProfileDomain.FX_QUOTE_ACTIVITY),
    ], source, grid, cfg)
    assert [item.bin_index for item in result.bins] == [-1]


def test_poc_tie_is_deterministic_and_lower_index_breaks_symmetric_tie(source, grid):
    events = [event("lo", "1.00", time=1), event("hi", "1.02", time=2)]
    result = calc(events, source, grid, VolumeProfileConfig(bin_ticks=1))
    assert result.features["poc_tie_count"] == 2
    assert result.features["poc_bin_index"] == 100
    reordered = calc(list(reversed(events)), source, grid, VolumeProfileConfig(bin_ticks=1))
    assert result.fingerprint == reordered.fingerprint


def test_value_area_adjacent_equal_weight_prefers_lower_bin(source, grid):
    events = [
        event("lo", "1.00", "1", time=1),
        event("poc", "1.01", "2", time=2),
        event("hi", "1.02", "1", time=3),
    ]
    result = calc(events, source, grid, VolumeProfileConfig(value_area_fraction=D("0.75")))
    assert result.features["val_price"] == D("1.00")
    assert result.features["vah_price"] == D("1.02")
    assert result.features["value_area_fraction_achieved"] == D("0.75")


def test_value_area_expands_across_zero_weight_gap_deterministically(source, grid):
    events = [
        event("lo", "1.00", "1", time=1),
        event("poc", "1.04", "3", time=2),
        event("mid", "1.02", "1", time=3),
    ]
    result = calc(events, source, grid, VolumeProfileConfig(value_area_fraction=D("0.80")))
    assert result.features["poc_bin_index"] == 104
    assert result.features["val_price"] == D("1.02")
    assert result.features["vah_price"] == D("1.05")
    assert result.features["value_area_fraction_achieved"] == D("0.8")


def test_zero_total_weight_is_degraded_not_nan(source, grid):
    result = calc([event("z", "1.00", "0")], source, grid)
    assert result.quality_state is QualityState.DEGRADED
    assert result.reason_codes == ("ZERO_TOTAL_WEIGHT",)
    assert result.features == {}


def test_one_occupied_bin_has_defined_entropy_and_hhi(source, grid):
    result = calc([event("a", "1.00", "2"), event("b", "1.00", "3", time=2)], source, grid)
    assert result.features["normalized_entropy"] == D("0")
    assert result.features["concentration_hhi"] == D("1")


def test_max_event_and_bin_limits_are_explicit(source, grid):
    too_many_events = [event(f"e{i}", "1.00", time=i) for i in range(1, 4)]
    event_limited = calc(too_many_events, source, grid, VolumeProfileConfig(max_events=2))
    assert event_limited.quality_state is QualityState.RESOURCE_LIMIT
    assert event_limited.reason_codes == ("MAX_EVENTS_EXCEEDED",)

    bin_limited = calc(
        [event("a", "1.00", time=1), event("b", "1.01", time=2)],
        source,
        grid,
        VolumeProfileConfig(max_bins=1),
    )
    assert bin_limited.quality_state is QualityState.RESOURCE_LIMIT
    assert bin_limited.reason_codes == ("MAX_BINS_EXCEEDED",)


def test_availability_timestamp_cannot_precede_event_timestamp():
    with pytest.raises(VolumeProfileInputError) as caught:
        event("bad-clock", "1.00", time=10, available=9)
    assert caught.value.reason_code == "INVALID_EVENT_TIME"


def test_source_domain_unit_mismatch_is_rejected():
    with pytest.raises(VolumeProfileInputError) as caught:
        SourceIdentity("fx-feed", "EURUSD", ProfileDomain.FX_QUOTE_ACTIVITY, "contracts", "v1")
    assert caught.value.reason_code == "SEMANTIC_UNIT_MISMATCH"


def test_futures_quantity_cannot_be_mislabeled_as_event_count():
    with pytest.raises(VolumeProfileInputError) as caught:
        SourceIdentity("fut-feed", "ESZ6", ProfileDomain.FUTURES_EXECUTED_VOLUME, "trade_count", "v1")
    assert caught.value.reason_code == "SEMANTIC_UNIT_MISMATCH"


def test_unknown_semantics_are_not_accepted():
    with pytest.raises(VolumeProfileInputError) as caught:
        SourceIdentity("unknown", "X", ProfileDomain.UNKNOWN_ACTIVITY_SEMANTICS, "unknown", "v1")
    assert caught.value.reason_code == "UNKNOWN_ACTIVITY_SEMANTICS"


def test_disabled_feature_is_inert_analytics(source, grid):
    result = calc([event("a", "1.00")], source, grid, VolumeProfileConfig(enabled=False))
    assert result.quality_state is QualityState.DISABLED
    assert result.reason_codes == ("FEATURE_DISABLED",)
    assert result.authority == "ANALYTICAL_ONLY"
    assert result.features == {}


def test_source_identity_mismatch_rejected(source, grid):
    with pytest.raises(VolumeProfileInputError) as caught:
        calc([event("a", "1.00", source_id="other")], source, grid)
    assert caught.value.reason_code == "SOURCE_IDENTITY_MISMATCH"


def test_fingerprint_changes_with_semantic_identity(source, grid):
    events = [event("a", "1.00", time=1), event("b", "1.01", time=2)]
    original = calc(events, source, grid)
    other_source = SourceIdentity(
        source_id="feed-B", symbol="EURUSD", domain=ProfileDomain.FX_QUOTE_ACTIVITY,
        activity_unit="quote_events", data_version="feed-A-v1", calendar_id="FX-24x5",
        calendar_version="calendar-v1",
    )
    other_events = [event(e.event_id, str(e.price), str(e.weight), time=e.event_time_ns,
                          source_id="feed-B") for e in events]
    changed = calc(other_events, other_source, grid)
    assert original.fingerprint != changed.fingerprint


def test_profile_comparability_requires_same_source_semantics(source, grid):
    events = [event("a", "1.00", time=1), event("b", "1.01", time=2)]
    first = calc(events, source, grid)
    other = SourceIdentity("feed-B", "EURUSD", ProfileDomain.FX_QUOTE_ACTIVITY,
                           "quote_events", "v1", "FX-24x5", "calendar-v1")
    other_events = [event(e.event_id, str(e.price), str(e.weight), time=e.event_time_ns,
                          source_id="feed-B") for e in events]
    second = calc(other_events, other, grid)
    assert not profiles_comparable(first, second)


def test_config_validation_rejects_invalid_bin_and_fraction():
    with pytest.raises(VolumeProfileInputError) as caught:
        VolumeProfileConfig(bin_ticks=0)
    assert caught.value.reason_code == "INVALID_BIN_WIDTH"
    with pytest.raises(VolumeProfileInputError) as caught:
        VolumeProfileConfig(value_area_fraction=D("0"))
    assert caught.value.reason_code == "INVALID_VALUE_AREA_FRACTION"


def test_future_mutation_does_not_change_prefix_fingerprint(source, grid):
    prefix = [event("a", "1.00", time=1), event("b", "1.01", time=2)]
    poison_a = event("future", "9.99", "999999", time=200, available=200)
    poison_b = event("future", "0.01", "0.0001", time=200, available=200)
    first = calc(prefix + [poison_a], source, grid, watermark=10)
    second = calc(prefix + [poison_b], source, grid, watermark=10)
    assert first.fingerprint == second.fingerprint


def test_canonical_payload_is_stable_and_contains_no_float(source, grid):
    result = calc([event("a", "1.00", time=1), event("b", "1.01", time=2)], source, grid)
    encoded = result.canonical_payload()
    assert encoded["authority"] == "ANALYTICAL_ONLY"
    assert encoded["fingerprint"] == result.fingerprint
    assert encoded["grid"]["tick_size"] == "0.01"
    assert b'"1.00"' not in str(encoded).encode("ascii")  # Decimal canonicalization is normalized.


def test_fingerprint_is_hash_of_canonical_payload_without_fingerprint(source, grid):
    import hashlib
    import json

    result = calc([event("a", "1.00", time=1), event("b", "1.01", time=2)], source, grid)
    payload = result.canonical_payload()
    fingerprint = payload.pop("fingerprint")
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    assert hashlib.sha256(encoded).hexdigest() == fingerprint


def test_decimal_weight_aggregation_is_exact_beyond_default_context(source, grid):
    events = [
        event("dominant", "1.00", "1E+30", time=1),
        event("small", "1.00", "1", time=2),
        event("other-bin", "1.01", "1", time=3),
    ]
    result = calc(events, source, grid)
    expected = D("1000000000000000000000000000002")
    assert result.total_weight == expected
    assert next(item.weight for item in result.bins if item.bin_index == 100) == D(
        "1000000000000000000000000000001"
    )


def test_zero_weight_observation_does_not_create_occupied_bin(source, grid):
    result = calc(
        [event("mass", "1.00", "1", time=1), event("zero-only-bin", "1.02", "0", time=2)],
        source,
        grid,
    )
    assert result.included_event_count == 2
    assert result.occupied_bin_count == 1
    assert [item.bin_index for item in result.bins] == [100]
    assert result.features["normalized_entropy"] == D("0")


def test_decimal_exponent_span_is_bounded_fail_closed(source, grid):
    with pytest.raises(VolumeProfileInputError) as caught:
        calc(
            [event("huge", "1.00", "1E+512", time=1), event("tiny", "1.00", "1E-512", time=2)],
            source,
            grid,
        )
    assert caught.value.reason_code == "NUMERIC_PRECISION_LIMIT_EXCEEDED"


def test_cross_process_and_timezone_fingerprints_are_identical():
    import os
    import subprocess
    import sys
    from pathlib import Path

    source_root = str(Path(__file__).resolve().parents[1] / "src")
    script = """
from decimal import Decimal as D
from src.fractal_flow.research.volume_profile import (
    PriceGrid, ProfileDomain, ProfileEvent, SourceIdentity,
    VolumeProfileConfig, calculate_volume_profile,
)
s = SourceIdentity("feed-A", "EURUSD", ProfileDomain.FX_QUOTE_ACTIVITY,
                   "quote_events", "v1", "FX-24x5", "calendar-v1")
g = PriceGrid(D("0.01"), D("0"), "EURUSD_price")
e = [
    ProfileEvent("b", "feed-A", "EURUSD", ProfileDomain.FX_QUOTE_ACTIVITY, 2, 2, 2, D("1.01"), D("3")),
    ProfileEvent("a", "feed-A", "EURUSD", ProfileDomain.FX_QUOTE_ACTIVITY, 1, 1, 1, D("1.00"), D("2")),
]
r = calculate_volume_profile(e, source=s, grid=g, config=VolumeProfileConfig(), watermark_ns=10)
print(r.fingerprint)
"""
    fingerprints = []
    for timezone, hash_seed in (("UTC", "1"), ("Pacific/Honolulu", "8675309")):
        env = os.environ.copy()
        env["PYTHONPATH"] = source_root
        env["TZ"] = timezone
        env["PYTHONHASHSEED"] = hash_seed
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        fingerprints.append(completed.stdout.strip())
    assert fingerprints[0] == fingerprints[1]


def test_window_end_is_inclusive(source, grid):
    result = calc(
        [event("edge", "1.00", time=10), event("after", "1.01", time=11)],
        source,
        grid,
        VolumeProfileConfig(window_start_ns=0, window_end_ns=10),
        watermark=100,
    )
    assert result.included_event_count == 1
    assert result.total_weight == D("1")


def test_nonfinite_decimal_helpers_fail_closed() -> None:
    from decimal import Decimal

    from src.fractal_flow.research.volume_profile import (
        VolumeProfileInputError,
        _decimal_magnitude_is_bounded,
        _exact_decimal_sum,
        _exact_decimal_times_int,
    )

    assert not _decimal_magnitude_is_bounded(Decimal("NaN"))
    assert not _decimal_magnitude_is_bounded(Decimal("Infinity"))
    with pytest.raises(VolumeProfileInputError):
        _exact_decimal_sum([Decimal("NaN")])
    with pytest.raises(VolumeProfileInputError):
        _exact_decimal_times_int(Decimal("Infinity"), 2)


def test_exact_decimal_helpers_preserve_mixed_scales() -> None:
    from decimal import Decimal

    from src.fractal_flow.research.volume_profile import (
        _exact_decimal_sum,
        _exact_decimal_times_int,
    )

    assert _exact_decimal_sum([Decimal("1.20"), Decimal("0.003")]) == Decimal("1.203")
    assert _exact_decimal_times_int(Decimal("1.25"), 4) == Decimal("5.00")
