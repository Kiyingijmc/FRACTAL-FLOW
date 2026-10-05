"""Durable event-sourced persistence for the Phase 2 informational pipeline.

Phase 2 engine internals are deliberately not persisted through ``__dict__``.  The
journal is the durable source of truth: closed market bars are immutable input
events and a fresh pipeline is deterministically rebuilt by replaying them.
Snapshots persist only the explicit pipeline identity/checkpoint metadata.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

from src.fractal_flow.config.config import Phase2EffectiveConfiguration
from src.fractal_flow.domain.context import InstrumentSpec
from src.fractal_flow.domain.event import Event
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.phase2 import Phase2Evaluation, Phase2Pipeline
from src.fractal_flow.persistence.journal import DurableEventJournal
from src.fractal_flow.persistence.snapshot import AggregateSnapshot, SnapshotEngine


PHASE2_AGGREGATE_TYPE = "Phase2Pipeline"
PHASE2_SNAPSHOT_SCHEMA = "phase2-durable-checkpoint-v1"
PHASE2_EVENT_TYPE = "PHASE2_BAR_INPUT"


class Phase2RecoveryError(RuntimeError):
    """Raised when durable Phase 2 recovery cannot be proven deterministic."""


@dataclass(frozen=True)
class Phase2Checkpoint:
    aggregate_version: int
    journal_sequence: int
    last_watermark: tuple[int, int]
    configuration_id: str


class Phase2DurableStore:
    """Crash-safe persistence boundary for a single Phase 2 pipeline aggregate.

    Ordering is intentional:
      1. append the immutable input event durably;
      2. mutate the in-memory pipeline;
      3. publish a durable checkpoint.

    A crash between (1) and (3) is safe because recovery replays the journal
    from genesis.  No partially persisted engine ``__dict__`` is authoritative.
    """

    def __init__(self, root_dir: str, pipeline: Phase2Pipeline) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.pipeline = pipeline
        self.pipeline_id = pipeline.root_id
        self.journal = DurableEventJournal(str(self.root_dir / "phase2.journal"))
        self.snapshots = SnapshotEngine(str(self.root_dir / "snapshots"))

    @property
    def _aggregate_version(self) -> int:
        return len(self.journal.get_events_for_aggregate(PHASE2_AGGREGATE_TYPE, self.pipeline_id))

    @staticmethod
    def _instrument_payload(instrument: InstrumentSpec) -> dict[str, object]:
        return {
            "symbol": instrument.symbol,
            "tick_size": str(instrument.tick_size),
            "price_precision": instrument.price_precision,
            "volume_step": str(instrument.volume_step),
            "contract_size": str(instrument.contract_size),
            "timezone": instrument.timezone,
            "asset_class": instrument.asset_class,
        }

    @staticmethod
    def _instrument_from_payload(payload: dict[str, object]) -> InstrumentSpec:
        return InstrumentSpec(
            symbol=str(payload["symbol"]),
            tick_size=Decimal(str(payload["tick_size"])),
            price_precision=int(payload["price_precision"]),
            volume_step=Decimal(str(payload["volume_step"])),
            contract_size=Decimal(str(payload["contract_size"])),
            timezone=str(payload["timezone"]),
            asset_class=str(payload["asset_class"]),
        )

    def _checkpoint_payload(self) -> dict[str, object]:
        return {
            "schema_version": PHASE2_SNAPSHOT_SCHEMA,
            "symbol": self.pipeline.symbol,
            "timeframe": self.pipeline.timeframe,
            "instrument": self._instrument_payload(self.pipeline.instrument),
            "history_capacity": self.pipeline.history_capacity,
            "root_id": self.pipeline.root_id,
            "configuration_version": self.pipeline.configuration_version,
            "configuration_id": self.pipeline.configuration_id,
            "feature_version": self.pipeline.feature_version,
            "last_watermark": [self.pipeline._last_watermark[0], self.pipeline._last_watermark[1]],
            "aggregate_version": self._aggregate_version,
        }

    def checkpoint(self) -> AggregateSnapshot:
        """Persist an explicit identity/checkpoint record after journal commit."""
        version = self._aggregate_version
        payload = self._checkpoint_payload()
        return self.snapshots.save_snapshot(
            PHASE2_AGGREGATE_TYPE,
            self.pipeline_id,
            version,
            self.journal._global_sequence,
            payload,
            schema_version=PHASE2_SNAPSHOT_SCHEMA,
            created_at=self.pipeline._last_watermark[0] if version else 0,
        )

    def process_bar(self, bar: Bar) -> Phase2Evaluation:
        """Durably record and process one closed market-bar input."""
        if not bar.is_closed:
            raise ValueError("Phase2DurableStore accepts closed bars only")
        if bar.symbol != self.pipeline.symbol or bar.timeframe != self.pipeline.timeframe:
            raise ValueError("Phase2DurableStore bar identity does not match pipeline identity")
        if (bar.close_timestamp, bar.sequence) <= self.pipeline._last_watermark:
            raise ValueError("Phase2DurableStore rejects duplicate or out-of-order bars")
        expected_version = self._aggregate_version + 1
        event_id = f"phase2:{self.pipeline_id}:{bar.close_timestamp}:{bar.sequence}"
        event = Event(
            event_id=event_id,
            event_type=PHASE2_EVENT_TYPE,
            aggregate_type=PHASE2_AGGREGATE_TYPE,
            aggregate_id=self.pipeline_id,
            root_id=self.pipeline_id,
            parent_id="market",
            aggregate_version=expected_version,
            source_timestamp=bar.close_timestamp,
            event_timestamp=bar.close_timestamp,
            processing_timestamp=bar.close_timestamp,
            payload={
                "bar": bar.to_dict(),
                "pipeline": {
                    "symbol": self.pipeline.symbol,
                    "timeframe": self.pipeline.timeframe,
                    "instrument": self._instrument_payload(self.pipeline.instrument),
                    "history_capacity": self.pipeline.history_capacity,
                    "root_id": self.pipeline.root_id,
                    "configuration_version": self.pipeline.configuration_version,
                    "configuration_id": self.pipeline.configuration_id,
                    "feature_version": self.pipeline.feature_version,
                    "configuration": self.pipeline.configuration.canonical_payload(),
                },
            },
            configuration_version=self.pipeline.configuration_version,
            data_version=bar.data_version,
            feature_version=self.pipeline.feature_version,
            actor_id="PHASE2_PIPELINE",
            authority="INFORMATIONAL",
        )
        self.journal.append(event)
        result = self.pipeline.process_bar(bar)
        self.checkpoint()
        return result

    @staticmethod
    def _validate_event_contract(event: Event, pipeline_id: str, expected_version: int, pipeline: Phase2Pipeline) -> None:
        """Validate the complete Phase 2 event envelope before replay."""
        if event.event_type != PHASE2_EVENT_TYPE:
            raise Phase2RecoveryError(f"Unexpected Phase 2 event type during recovery: {event.event_type}")
        if event.schema_version != 1:
            raise Phase2RecoveryError(f"Unsupported Phase 2 event schema: {event.schema_version}")
        if event.aggregate_type != PHASE2_AGGREGATE_TYPE or event.aggregate_id != pipeline_id:
            raise Phase2RecoveryError("Phase 2 aggregate identity mismatch")
        if event.root_id != pipeline_id or event.parent_id != "market":
            raise Phase2RecoveryError("Phase 2 lineage identity mismatch")
        if event.aggregate_version != expected_version:
            raise Phase2RecoveryError(
                f"Phase 2 journal aggregate version gap: {event.aggregate_version} != {expected_version}"
            )
        if event.configuration_version != pipeline.configuration_version:
            raise Phase2RecoveryError("Journal configuration version diverged")
        if event.feature_version != pipeline.feature_version:
            raise Phase2RecoveryError("Journal feature version diverged")
        if event.actor_id != "PHASE2_PIPELINE" or event.authority != "INFORMATIONAL":
            raise Phase2RecoveryError("Phase 2 event authority contract mismatch")
        bar_payload = event.payload.get("bar")
        pipe_payload = event.payload.get("pipeline")
        if not isinstance(bar_payload, dict) or not isinstance(pipe_payload, dict):
            raise Phase2RecoveryError("Phase 2 journal event has invalid payload contract")
        try:
            bar = Bar.from_dict(dict(bar_payload))
        except Exception as exc:
            raise Phase2RecoveryError("Phase 2 journal event contains an invalid bar") from exc
        if event.event_id != f"phase2:{pipeline_id}:{bar.close_timestamp}:{bar.sequence}":
            raise Phase2RecoveryError("Phase 2 event_id is not bound to its immutable bar identity")
        if event.source_timestamp != bar.close_timestamp or event.event_timestamp != bar.close_timestamp or event.processing_timestamp != bar.close_timestamp:
            raise Phase2RecoveryError("Phase 2 event timestamps diverge from bar close timestamp")
        if event.data_version != bar.data_version:
            raise Phase2RecoveryError("Phase 2 event data version diverges from bar")
        expected_pipe = {
            "symbol": pipeline.symbol, "timeframe": pipeline.timeframe,
            "instrument": Phase2DurableStore._instrument_payload(pipeline.instrument),
            "history_capacity": pipeline.history_capacity, "root_id": pipeline.root_id,
            "configuration_version": pipeline.configuration_version,
            "configuration_id": pipeline.configuration_id, "feature_version": pipeline.feature_version,
            "configuration": pipeline.configuration.canonical_payload(),
        }
        if dict(pipe_payload) != expected_pipe:
            raise Phase2RecoveryError("Phase 2 event pipeline identity/configuration contract diverged")
        if bar.symbol != pipeline.symbol or bar.timeframe != pipeline.timeframe:
            raise Phase2RecoveryError("Phase 2 journal bar identity mismatch")

    def recover(self) -> Phase2Pipeline:
        """Reconstruct a fresh pipeline solely from the durable journal input stream.

        The latest checkpoint is validated when present, but it is not required
        for correctness. This closes the crash window between a durable event
        append and checkpoint publication: journal replay remains authoritative.
        """
        snapshot = self.snapshots.load_snapshot(PHASE2_AGGREGATE_TYPE, self.pipeline_id)
        if snapshot is not None and snapshot.schema_version != PHASE2_SNAPSHOT_SCHEMA:
            raise Phase2RecoveryError(f"Unsupported Phase 2 checkpoint schema: {snapshot.schema_version!r}")
        if snapshot is not None and snapshot.last_sequence_number > self.journal._global_sequence:
            raise Phase2RecoveryError("Checkpoint is ahead of the durable journal")

        events = self.journal.get_events_for_aggregate(PHASE2_AGGREGATE_TYPE, self.pipeline_id)
        if not events:
            raise Phase2RecoveryError("No durable Phase 2 journal events exist")

        first_pipeline = events[0].payload.get("pipeline")
        if not isinstance(first_pipeline, dict):
            raise Phase2RecoveryError("Phase 2 journal event lacks explicit pipeline identity")
        if first_pipeline.get("root_id") != self.pipeline_id:
            raise Phase2RecoveryError("Journal pipeline identity mismatch")
        if first_pipeline.get("configuration_id") != self.pipeline.configuration_id:
            raise Phase2RecoveryError("Journal configuration identity mismatch")

        config_payload = first_pipeline.get("configuration")
        if not isinstance(config_payload, dict):
            raise Phase2RecoveryError("Phase 2 journal event lacks canonical effective configuration")
        try:
            canonical_config = Phase2EffectiveConfiguration.from_canonical_payload(dict(config_payload))
        except Exception as exc:
            raise Phase2RecoveryError("Phase 2 journal contains invalid effective configuration") from exc
        if canonical_config.effective_config_id != str(first_pipeline.get("configuration_id")):
            raise Phase2RecoveryError("Journal configuration payload does not match configuration identity")
        if canonical_config.effective_config_id != self.pipeline.configuration_id:
            raise Phase2RecoveryError("Journal configuration identity mismatch")
        restored = Phase2Pipeline(
            str(first_pipeline["symbol"]),
            str(first_pipeline["timeframe"]),
            self._instrument_from_payload(first_pipeline["instrument"]),
            int(first_pipeline["history_capacity"]),
            configuration=canonical_config,
        )
        if restored.root_id != self.pipeline_id or restored.configuration_id != str(first_pipeline["configuration_id"]):
            raise Phase2RecoveryError("Journal does not reconstruct the original pipeline identity")

        if snapshot is not None and snapshot.aggregate_version > len(events):
            raise Phase2RecoveryError(
                f"Checkpoint aggregate version {snapshot.aggregate_version} exceeds journal aggregate event count {len(events)}"
            )

        expected_version = 1
        for event in events:
            self._validate_event_contract(event, self.pipeline_id, expected_version, restored)
            bar_payload = event.payload["bar"]
            assert isinstance(bar_payload, dict)
            restored.process_bar(Bar.from_dict(dict(bar_payload)))
            expected_version += 1

        if restored.configuration_id != str(first_pipeline["configuration_id"]):
            raise Phase2RecoveryError("Recovered configuration identity diverged")
        last_bar_payload = events[-1].payload.get("bar")
        if not isinstance(last_bar_payload, dict):
            raise Phase2RecoveryError("Final Phase 2 journal event has invalid bar payload")
        last_bar = Bar.from_dict(dict(last_bar_payload))
        expected_watermark = (last_bar.close_timestamp, last_bar.sequence)
        if restored._last_watermark != expected_watermark:
            raise Phase2RecoveryError("Recovered causal watermark diverged from durable source")
        return restored

    def checkpoint_metadata(self) -> Optional[Phase2Checkpoint]:
        snapshot = self.snapshots.load_snapshot(PHASE2_AGGREGATE_TYPE, self.pipeline_id)
        if snapshot is None:
            return None
        payload = snapshot.state_payload
        wm = payload["last_watermark"]
        return Phase2Checkpoint(
            aggregate_version=snapshot.aggregate_version,
            journal_sequence=snapshot.last_sequence_number,
            last_watermark=(int(wm[0]), int(wm[1])),
            configuration_id=str(payload["configuration_id"]),
        )
