"""Phase 1B Tests: StateEnvelope Integration and Transitions."""

import pytest

from src.fractal_flow.domain.data_quality import DataQualityEngine
from src.fractal_flow.domain.envelope import InvalidStateTransitionException, StateEnvelope
from src.fractal_flow.domain.market import Tick

BASE_TS = 1700006400


def test_data_quality_state_envelope_creation_and_transition() -> None:
    engine = DataQualityEngine("EURUSD")
    t1 = Tick.create("EURUSD", BASE_TS, "1.0850", "1.0851")
    assessment = engine.evaluate_tick(t1, current_processing_time=BASE_TS)

    envelope = assessment.to_envelope(
        object_id="dq_eurusd",
        root_id="root_01",
        parent_id="parent_01",
        parent_version=1,
        version=1,
        source_ts=BASE_TS,
        event_ts=BASE_TS,
        processing_ts=BASE_TS,
    )

    assert envelope.object_type == "DataQualityState"
    assert envelope.state == "DATA_VALID"
    assert envelope.symbol == "EURUSD"
    assert envelope.version == 1

    envelope.transition_to("DATA_DEGRADED")
    assert envelope.state == "DATA_DEGRADED"
    assert envelope.previous_state == "DATA_VALID"
    assert envelope.version == 2


def test_illegal_data_quality_state_transition_rejection() -> None:
    envelope = StateEnvelope(
        state_id="dq_s1",
        object_id="dq_obj_1",
        object_type="DataQualityState",
        symbol="EURUSD",
        timeframe="1M",
        root_id="root_01",
        parent_id="parent_01",
        parent_version=1,
        state="DATA_BOOT",
        previous_state="DATA_BOOT",
        version=1,
        source_timestamp=BASE_TS,
        event_timestamp=BASE_TS,
        processing_timestamp=BASE_TS,
        valid_until=BASE_TS + 300,
        last_seen=BASE_TS,
        authority="DATA_QUALITY",
    )

    with pytest.raises(InvalidStateTransitionException):
        envelope.transition_to("DATA_CORRUPTED")
