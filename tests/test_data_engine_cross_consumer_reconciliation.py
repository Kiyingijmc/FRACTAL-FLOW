"""G5 Unit 3 reconciliation proofs across process and consumer boundaries."""
from __future__ import annotations

from decimal import Decimal
import json
import subprocess
import sys

from src.fractal_flow.data_engine.contracts import InstrumentAlias, InstrumentRegistry, LaneScope, RawQuote, SourceIdentity, VolumeSemantics
from src.fractal_flow.data_engine.core import CanonicalQuote, DataCore
from src.fractal_flow.data_engine.correction_codec import CorrectionScope
from src.fractal_flow.data_engine.correction_persistence import DurableCorrectionJournal
from src.fractal_flow.data_engine.replay_consumer import DeterministicReplayConsumer
from src.fractal_flow.data_engine.revisions import QuoteRevision, RevisionOperation
from src.fractal_flow.data_engine.simulated_live_consumer import SimulatedLiveConsumer
from src.fractal_flow.persistence.journal import DurableEventJournal


def _quote(native: str, sequence: int, available: int) -> CanonicalQuote:
    source = SourceIdentity("source-a", "broker", "server", LaneScope.REPLAY)
    core = DataCore(InstrumentRegistry([InstrumentAlias(source, "EURUSD", "FX:EURUSD", Decimal("0.00001"), 0)]))
    result = core.ingest(RawQuote(
        source, native, sequence, "EURUSD", available - 2, available - 1, available,
        "1.10000", "1.10002", "1", VolumeSemantics.TICK_ACTIVITY_COUNT,
    ))
    assert result.quote is not None
    return result.quote


def test_independent_process_and_simulated_live_match_deterministic_replay(tmp_path: object) -> None:
    path = tmp_path / "reconciliation.journal"  # type: ignore[operator]
    journal = DurableEventJournal(str(path))
    store = DurableCorrectionJournal(journal)
    quote = _quote("n1", 1, 100)
    store.append(QuoteRevision("r1", quote.event_id, None, RevisionOperation.UPSERT, 100, quote))
    store.append(QuoteRevision("r2", quote.event_id, "r1", RevisionOperation.CANCEL, 200, None))
    corrected = _quote("n2", 2, 300)
    store.append(QuoteRevision("r3", quote.event_id, "r2", RevisionOperation.UPSERT, 300, corrected))
    scope = CorrectionScope.from_quote(quote)
    expected = DeterministicReplayConsumer(store).replay(300, {scope})
    simulated = SimulatedLiveConsumer(store, scope, b"g5-reconciliation", {scope.source.key}, known_at_ns=300)
    simulated.start()
    assert simulated.snapshot().replay == expected
    journal.close()

    script = """
import json, sys
from src.fractal_flow.data_engine.correction_persistence import DurableCorrectionJournal
from src.fractal_flow.data_engine.replay_consumer import DeterministicReplayConsumer
from src.fractal_flow.data_engine.simulated_live_consumer import SimulatedLiveConsumer
from src.fractal_flow.persistence.journal import DurableEventJournal
journal = DurableEventJournal(sys.argv[1])
store = DurableCorrectionJournal.recover(journal)
scope = store.snapshot().records[0].scope
replay = DeterministicReplayConsumer(store).replay(300, {scope})
live = SimulatedLiveConsumer(store, scope, b'g5-reconciliation', {scope.source.key}, known_at_ns=300)
live.start()
print(json.dumps({'replay': replay.fingerprint, 'live': live.snapshot().fingerprint}, sort_keys=True))
journal.close()
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    fingerprints = json.loads(completed.stdout)
    assert fingerprints == {"live": expected.fingerprint, "replay": expected.fingerprint}
