"""Deterministic Replay Harness and Clock Injection for FRACTAL FLOW.

Provides deterministic event identity generation, clock-driven event processing,
snapshot checkpointing, and restart equivalence verification without future lookahead.
"""

from dataclasses import dataclass, field
import hashlib
from typing import Any, Callable, Optional

from src.fractal_flow.domain.event import Event, ImmutablePayloadDict
from src.fractal_flow.domain.market import Tick
from src.fractal_flow.persistence.adapter import canonical_json_dumps, compute_canonical_fingerprint
from src.fractal_flow.persistence.journal import DurableEventJournal, JournalRecord
from src.fractal_flow.persistence.snapshot import SnapshotEngine
from src.fractal_flow.simulation.clock import SimulationClock


def generate_deterministic_event_id(
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    sequence_number: int,
    source_timestamp: int,
    payload: dict[str, Any],
) -> str:
    """Generates a deterministic 16-character hex event identity derived strictly from event inputs."""
    raw_payload_json = canonical_json_dumps(payload)
    identity_data = (
        f"{aggregate_type}|{aggregate_id}|{event_type}|{sequence_number}|{source_timestamp}|{raw_payload_json}"
    )
    return hashlib.sha256(identity_data.encode("utf-8")).hexdigest()[:16]


@dataclass
class ReplayState:
    processed_count: int = 0
    latest_timestamp: int = 0
    state_hash: str = ""
    event_ids: list[str] = field(default_factory=list)


class DeterministicReplayHarness:
    """Deterministic Replay Harness processing recorded inputs with injected clock and snapshot checkpointing."""

    def __init__(
        self,
        clock: Optional[SimulationClock] = None,
        journal: Optional[DurableEventJournal] = None,
        snapshot_engine: Optional[SnapshotEngine] = None,
    ) -> None:
        self.clock = clock or SimulationClock()
        self.journal = journal
        self.snapshot_engine = snapshot_engine
        self.processed_ticks: list[Tick] = []
        self.emitted_event_records: list[JournalRecord] = []
        self.sequence_number = 0

    def process_tick(
        self, tick: Tick, processor_fn: Optional[Callable[[Tick], dict[str, Any]]] = None
    ) -> JournalRecord:
        """Processes a single tick causally using injected clock time without lookahead."""
        self.clock.set_time_seconds(tick.timestamp)
        self.processed_ticks.append(tick)
        self.sequence_number += 1

        payload_details = processor_fn(tick) if processor_fn else {"tick_bid": str(tick.bid), "tick_ask": str(tick.ask)}

        event_id = generate_deterministic_event_id(
            aggregate_type="MarketStream",
            aggregate_id=tick.symbol,
            event_type="TickProcessed",
            sequence_number=self.sequence_number,
            source_timestamp=tick.timestamp,
            payload=payload_details,
        )

        event_obj = Event(
            event_id=event_id,
            event_type="TickProcessed",
            aggregate_type="MarketStream",
            aggregate_id=tick.symbol,
            root_id=f"root_{tick.symbol}",
            parent_id=f"parent_{tick.symbol}",
            aggregate_version=self.sequence_number,
            source_timestamp=tick.timestamp,
            event_timestamp=self.clock.now_seconds(),
            processing_timestamp=self.clock.now_seconds(),
            payload=ImmutablePayloadDict(payload_details),
            configuration_version=1,
            data_version=tick.data_version,
            feature_version=1,
        )

        record = JournalRecord(
            sequence_number=self.sequence_number,
            event=event_obj,
            checksum="",
        )

        if self.journal is not None:
            self.journal.append(event_obj)

        self.emitted_event_records.append(record)
        return record

    def compute_replay_digest(self) -> str:
        """Computes a SHA-256 fingerprint over all emitted event IDs and payloads."""
        records_repr = [
            {
                "seq": r.sequence_number,
                "event_id": r.event.event_id,
                "event_type": r.event.event_type,
                "source_ts": r.event.source_timestamp,
                "payload": dict(r.event.payload),
            }
            for r in self.emitted_event_records
        ]
        return compute_canonical_fingerprint(records_repr)
