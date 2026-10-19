from decimal import Decimal

import pytest

from src.fractal_flow.management.stop_gate import (
    StopGateError,
    StopGateReason,
    StopProposal,
    validate_stop_proposal,
)


def proposal(**overrides):
    values = dict(
        position_id="P-1",
        side="LONG",
        current_stop=Decimal("1.1000"),
        proposed_stop=Decimal("1.1050"),
        bid=Decimal("1.1100"),
        ask=Decimal("1.1102"),
        tick_size=Decimal("0.0001"),
        stops_distance_price=Decimal("0.0010"),
        freeze_distance_price=Decimal("0.0005"),
        structure_confirmed_at_ms=100,
        decision_at_ms=120,
    )
    values.update(overrides)
    return StopProposal(**values)


def test_accepts_causal_tick_aligned_long_ratchet_with_broker_distance():
    result = validate_stop_proposal(proposal())
    assert result.accepted is True
    assert result.reason is StopGateReason.ACCEPTED
    assert result.proposed_stop == Decimal("1.1050")


def test_accepts_short_ratchet_using_ask_side_distance():
    result = validate_stop_proposal(proposal(
        side="SHORT", current_stop=Decimal("1.1200"),
        proposed_stop=Decimal("1.1150"), bid=Decimal("1.1100"),
        ask=Decimal("1.1102"),
    ))
    assert result.accepted is True


def test_future_structure_is_rejected():
    result = validate_stop_proposal(proposal(structure_confirmed_at_ms=121))
    assert result.reason is StopGateReason.STALE_OR_FUTURE_STRUCTURE


def test_stop_loosening_is_rejected():
    result = validate_stop_proposal(proposal(proposed_stop=Decimal("1.0990")))
    assert result.reason is StopGateReason.NOT_A_RATCHET


def test_unaligned_stop_is_rejected_without_rounding():
    result = validate_stop_proposal(proposal(proposed_stop=Decimal("1.10505")))
    assert result.reason is StopGateReason.PRICE_NOT_TICK_ALIGNED
    assert result.proposed_stop == Decimal("1.10505")


def test_stops_level_violation_is_rejected():
    result = validate_stop_proposal(proposal(
        proposed_stop=Decimal("1.1095"), stops_distance_price=Decimal("0.0010"),
    ))
    assert result.reason is StopGateReason.BROKER_STOPS_DISTANCE


def test_freeze_level_violation_is_rejected_even_if_stops_level_passes():
    result = validate_stop_proposal(proposal(
        proposed_stop=Decimal("1.1090"), stops_distance_price=Decimal("0.0005"),
        freeze_distance_price=Decimal("0.0015"),
    ))
    assert result.reason is StopGateReason.BROKER_FREEZE_DISTANCE


@pytest.mark.parametrize("tick", [Decimal("0"), Decimal("-0.0001")])
def test_nonpositive_tick_size_rejected(tick):
    with pytest.raises(StopGateError, match="tick_size must be positive"):
        proposal(tick_size=tick)


def test_nonfinite_market_value_rejected():
    with pytest.raises(StopGateError, match="finite"):
        proposal(bid=Decimal("NaN"))


def test_invalid_market_spread_rejected():
    with pytest.raises(StopGateError, match="bid must not exceed ask"):
        proposal(bid=Decimal("1.1110"), ask=Decimal("1.1100"))
