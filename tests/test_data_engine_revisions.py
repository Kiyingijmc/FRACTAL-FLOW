from dataclasses import replace
from decimal import Decimal

import pytest

from src.fractal_flow.data_engine.contracts import InstrumentAlias, InstrumentRegistry, LaneScope, RawQuote, SourceIdentity, VolumeSemantics
from src.fractal_flow.data_engine.core import CanonicalQuote, DataCore
from src.fractal_flow.data_engine.revisions import QuoteRevision, RevisionConflict, RevisionOperation, resolve_revisions


def _quote(event_id: str, available_at_ns: int, bid: str = "1.10000") -> CanonicalQuote:
    source = SourceIdentity("source-a", "broker", "server", LaneScope.REPLAY)
    core = DataCore(InstrumentRegistry([InstrumentAlias(source, "EURUSD", "FX:EURUSD", Decimal("0.00001"), 0)]))
    result = core.ingest(RawQuote(source, event_id, 1, "EURUSD", 100, 110, available_at_ns, bid, "1.10002", "1", VolumeSemantics.TICK_ACTIVITY_COUNT))
    assert result.quote is not None
    return result.quote


def test_revision_chain_is_exactly_visible_at_availability_watermark() -> None:
    original = _quote("native-original", 120)
    corrected = replace(_quote("native-correction", 220, "1.10001"), event_id="corrected-observation")
    revisions = (
        QuoteRevision("r1", original.event_id, None, RevisionOperation.UPSERT, 120, original),
        QuoteRevision("r2", original.event_id, "r1", RevisionOperation.UPSERT, 220, corrected),
    )

    assert resolve_revisions(revisions, 219)[original.event_id].quote == original
    assert resolve_revisions(revisions, 220)[original.event_id].quote == corrected


def test_cancel_and_conflicting_chain_fail_closed() -> None:
    original = _quote("native-original", 120)
    revisions = (
        QuoteRevision("r1", original.event_id, None, RevisionOperation.UPSERT, 120, original),
        QuoteRevision("r2", original.event_id, "r1", RevisionOperation.CANCEL, 220, None),
    )
    assert resolve_revisions(revisions, 220) == {}

    with pytest.raises(RevisionConflict, match="availability regressed"):
        resolve_revisions((revisions[0], replace(revisions[1], available_at_ns=119)), 220)
