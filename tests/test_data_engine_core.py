from decimal import Decimal

import pytest

from src.fractal_flow.data_engine.contracts import (
    InstrumentAlias,
    InstrumentRegistry,
    LaneScope,
    RawQuote,
    SourceIdentity,
    VolumeSemantics,
)
from src.fractal_flow.data_engine.core import DataCore, IngestDisposition


def _source(*, lane: LaneScope = LaneScope.SHARED_MARKET) -> SourceIdentity:
    if lane is LaneScope.ACCOUNT_PRIVATE:
        return SourceIdentity(
            source_id="mt5-terminal-a",
            broker_id="example-broker",
            server_id="example-live",
            lane_scope=lane,
            account_id="account-a",
            lane_id="lane-a",
        )
    return SourceIdentity(
        source_id="mt5-terminal-a",
        broker_id="example-broker",
        server_id="example-live",
        lane_scope=lane,
    )


def _registry(source: SourceIdentity | None = None) -> InstrumentRegistry:
    source = source or _source()
    return InstrumentRegistry(
        [
            InstrumentAlias(
                source=source,
                native_symbol="EURUSD.a",
                instrument_id="FX:EURUSD",
                tick_size=Decimal("0.00001"),
                effective_from_ns=0,
            )
        ]
    )


def _quote(
    *,
    native_record_id: str | None = "native-1",
    source_sequence: int | None = 1,
    bid: str = "1.10000",
    ask: str = "1.10002",
    source: SourceIdentity | None = None,
) -> RawQuote:
    return RawQuote(
        source=source or _source(),
        native_record_id=native_record_id,
        source_sequence=source_sequence,
        source_symbol="EURUSD.a",
        event_time_ns=100,
        received_time_ns=110,
        available_time_ns=120,
        bid=bid,
        ask=ask,
        volume="1",
        volume_semantics=VolumeSemantics.TICK_ACTIVITY_COUNT,
        raw_payload={"feed": "quote"},
    )


def test_exact_decimal_normalization_preserves_volume_semantics_and_source_lineage() -> None:
    result = DataCore(_registry()).ingest(_quote())

    assert result.disposition is IngestDisposition.ACCEPTED
    assert result.quote is not None
    assert result.quote.bid == Decimal("1.10000")
    assert result.quote.ask == Decimal("1.10002")
    assert result.quote.volume_semantics is VolumeSemantics.TICK_ACTIVITY_COUNT
    assert result.quote.source.source_id == "mt5-terminal-a"
    assert result.assessment.suitable_for_trade is True


def test_duplicate_delivery_is_audited_without_collapsing_distinct_identical_quotes() -> None:
    core = DataCore(_registry())
    first = core.ingest(_quote(native_record_id="native-1"))
    duplicate = core.ingest(_quote(native_record_id="native-1"))
    distinct = core.ingest(_quote(native_record_id="native-2", source_sequence=2))

    assert first.disposition is IngestDisposition.ACCEPTED
    assert duplicate.disposition is IngestDisposition.DUPLICATE
    assert duplicate.quote is None
    assert duplicate.assessment.reasons == ("DUPLICATE_DELIVERY",)
    assert distinct.disposition is IngestDisposition.ACCEPTED
    assert distinct.quote is not None
    assert distinct.quote.event_id != first.quote.event_id if first.quote is not None else False


def test_native_identity_conflict_is_quarantined() -> None:
    core = DataCore(_registry())
    assert core.ingest(_quote()).disposition is IngestDisposition.ACCEPTED

    conflicting = core.ingest(_quote(bid="1.10001"))

    assert conflicting.disposition is IngestDisposition.QUARANTINED
    assert conflicting.quote is None
    assert conflicting.assessment.reasons == ("NATIVE_ID_PAYLOAD_CONFLICT",)
    assert conflicting.assessment.suitable_for_trade is False


def test_sequence_gap_is_explicit_and_degrades_suitability_without_rejecting_observation() -> None:
    core = DataCore(_registry())
    assert core.ingest(_quote(source_sequence=1)).disposition is IngestDisposition.ACCEPTED

    gapped = core.ingest(_quote(native_record_id="native-3", source_sequence=3))

    assert gapped.disposition is IngestDisposition.ACCEPTED
    assert gapped.assessment.reasons == ("SOURCE_SEQUENCE_GAP",)
    assert gapped.assessment.suitable_for_trade is False
    assert gapped.gap is not None
    assert gapped.gap.missing_from_sequence == 2
    assert gapped.gap.missing_through_sequence == 2


@pytest.mark.parametrize(
    ("bid", "ask", "reason"),
    [
        ("1.100001", "1.10002", "PRICE_OFF_TICK_GRID"),
        ("1.10003", "1.10002", "CROSSED_QUOTE"),
        ("0", "1.10002", "NON_POSITIVE_PRICE"),
    ],
)
def test_invalid_quote_is_quarantined_and_never_trade_suitable(bid: str, ask: str, reason: str) -> None:
    result = DataCore(_registry()).ingest(_quote(bid=bid, ask=ask))

    assert result.disposition is IngestDisposition.QUARANTINED
    assert result.quote is None
    assert result.assessment.reasons == (reason,)
    assert result.assessment.suitable_for_trade is False


def test_aliases_are_lane_scoped_and_fail_closed_for_foreign_account_lane() -> None:
    shared_source = _source()
    account_source = _source(lane=LaneScope.ACCOUNT_PRIVATE)
    result = DataCore(_registry(shared_source)).ingest(_quote(source=account_source))

    assert result.disposition is IngestDisposition.QUARANTINED
    assert result.assessment.reasons == ("UNKNOWN_INSTRUMENT_ALIAS",)


def test_raw_quote_rejects_float_nonfinite_and_invalid_time_ordering_at_ingress() -> None:
    with pytest.raises(TypeError, match="float"):
        _quote(bid=1.1)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="finite"):
        _quote(bid="NaN")

    with pytest.raises(ValueError, match="timestamp ordering"):
        RawQuote(
            source=_source(),
            native_record_id="native-1",
            source_sequence=1,
            source_symbol="EURUSD.a",
            event_time_ns=100,
            received_time_ns=99,
            available_time_ns=120,
            bid="1.10000",
            ask="1.10002",
            volume=None,
            volume_semantics=VolumeSemantics.UNKNOWN,
        )


def test_missing_native_identity_is_not_deduplicated_by_quote_content() -> None:
    core = DataCore(_registry())
    first = core.ingest(_quote(native_record_id=None, source_sequence=None))
    second = core.ingest(_quote(native_record_id=None, source_sequence=None))

    assert first.disposition is IngestDisposition.ACCEPTED
    assert second.disposition is IngestDisposition.ACCEPTED
    assert first.quote is not None and second.quote is not None
    assert first.quote.event_id != second.quote.event_id
