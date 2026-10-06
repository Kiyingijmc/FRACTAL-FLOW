from decimal import Decimal
import pytest

from src.fractal_flow.domain.context import InstrumentSpec
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.phase2 import Phase2Pipeline
from src.fractal_flow.persistence.phase2 import Phase2DurableStore, Phase2RecoveryError
from src.fractal_flow.persistence.snapshot import SnapshotCorruptionException


def make_bar(ts: int, close: str, seq: int) -> Bar:
    c = Decimal(close)
    return Bar.create(
        "EURUSD", "1M", ts, ts + 60,
        c - Decimal("0.0005"), c + Decimal("0.001"), c - Decimal("0.001"), c,
        sequence=seq, data_version=1, is_closed=True,
    )


def make_pipeline() -> Phase2Pipeline:
    return Phase2Pipeline("EURUSD", "1M", InstrumentSpec("EURUSD", Decimal("0.00001"), 5), history_capacity=3)


def test_phase2_durable_recovery_is_continuation_equivalent(tmp_path):
    p = make_pipeline()
    store = Phase2DurableStore(str(tmp_path), p)
    for i in range(1, 8):
        store.process_bar(make_bar(i * 60, f"{1.1000 + i * 0.0001:.4f}", i))

    recovered = store.recover()
    assert recovered.snapshot_state() == p.snapshot_state()

    a = p.process_bar(make_bar(8 * 60, "1.1008", 8))
    b = recovered.process_bar(make_bar(8 * 60, "1.1008", 8))
    assert a.context.to_dict() == b.context.to_dict()
    assert a.pde == b.pde
    assert a.role == b.role
    assert a.evidence == b.evidence


def test_phase2_durable_checkpoint_is_explicit_metadata_not_engine_dict(tmp_path):
    p = make_pipeline()
    store = Phase2DurableStore(str(tmp_path), p)
    store.process_bar(make_bar(60, "1.1000", 1))
    snapshot = store.snapshots.load_snapshot("Phase2Pipeline", p.root_id)
    assert snapshot is not None
    assert snapshot.schema_version == "phase2-durable-checkpoint-v1"
    assert "data_quality" not in snapshot.state_payload
    assert "structure" not in snapshot.state_payload
    assert snapshot.state_payload["configuration_id"] == p.configuration_id
    assert snapshot.aggregate_version == 1


def test_phase2_recovery_rejects_checkpoint_ahead_of_journal(tmp_path):
    p = make_pipeline()
    store = Phase2DurableStore(str(tmp_path), p)
    store.process_bar(make_bar(60, "1.1000", 1))
    snap = store.snapshots.load_snapshot("Phase2Pipeline", p.root_id)
    assert snap is not None
    store.snapshots._snapshots[snap.aggregate_type + ":" + snap.aggregate_id] = type(snap)(
        **{**snap.__dict__, "last_sequence_number": snap.last_sequence_number + 1}
    )
    recovered = store.recover()
    assert recovered._last_watermark == (120, 1)
    assert store.lifecycle_state.value == "ACTIVE"


def test_phase2_recovery_survives_crash_after_journal_before_checkpoint(tmp_path, monkeypatch):
    p = make_pipeline()
    store = Phase2DurableStore(str(tmp_path), p)

    def crash_checkpoint():
        raise RuntimeError("simulated crash before checkpoint publication")

    monkeypatch.setattr(store, "checkpoint", crash_checkpoint)
    try:
        store.process_bar(make_bar(60, "1.1000", 1))
    except RuntimeError as exc:
        assert "simulated crash" in str(exc)
    else:
        raise AssertionError("Expected simulated checkpoint crash")

    restarted = Phase2DurableStore(str(tmp_path), make_pipeline())
    recovered = restarted.recover()
    assert recovered._last_watermark == (120, 1)
    assert recovered.historical_evaluation(120) is not None


def test_phase2_configuration_identity_is_bound_to_actual_engine_parameters():
    from dataclasses import replace
    from src.fractal_flow.config.config import build_phase2_effective_config

    instrument = InstrumentSpec("EURUSD", Decimal("0.00001"), 5)
    base = build_phase2_effective_config("EURUSD", "1M", instrument, 3)
    changed_flow = replace(base, flow={**base.flow, "dominance_threshold": Decimal("0.61")})
    a = Phase2Pipeline("EURUSD", "1M", instrument, 3, configuration=base)
    b = Phase2Pipeline("EURUSD", "1M", instrument, 3, configuration=changed_flow)
    assert a.flow.dominance_threshold == Decimal("0.60")
    assert b.flow.dominance_threshold == Decimal("0.61")
    assert a.configuration_id != b.configuration_id
    assert a.configuration.effective_config_id == a.configuration_id
    assert b.configuration.effective_config_id == b.configuration_id


def test_phase2_recovery_rejects_configuration_identity_divergence(tmp_path):
    from dataclasses import replace
    from src.fractal_flow.config.config import build_phase2_effective_config

    instrument = InstrumentSpec("EURUSD", Decimal("0.00001"), 5)
    config = build_phase2_effective_config("EURUSD", "1M", instrument, 3)
    store = Phase2DurableStore(str(tmp_path), Phase2Pipeline("EURUSD", "1M", instrument, 3, configuration=config))
    store.process_bar(make_bar(60, "1.1000", 1))
    altered = replace(config, pde={**config.pde, "recovery_threshold": Decimal("0.76")})
    incompatible = Phase2DurableStore(str(tmp_path), Phase2Pipeline("EURUSD", "1M", instrument, 3, configuration=altered))
    with pytest.raises(Phase2RecoveryError, match="configuration identity"):
        incompatible.recover()


def test_phase2_recovery_validates_full_event_envelope(tmp_path):
    from dataclasses import replace
    p = make_pipeline()
    store = Phase2DurableStore(str(tmp_path), p)
    store.process_bar(make_bar(60, "1.1000", 1))
    events = store.journal.get_events_for_aggregate("Phase2Pipeline", p.root_id)
    assert len(events) == 1
    tampered = replace(events[0], actor_id="UNTRUSTED")
    with pytest.raises(Phase2RecoveryError, match="authority"):
        store._validate_event_contract(tampered, p.root_id, 1, p)


def test_phase2_recovery_validates_event_identity_binding(tmp_path):
    from dataclasses import replace
    p = make_pipeline()
    store = Phase2DurableStore(str(tmp_path), p)
    store.process_bar(make_bar(60, "1.1000", 1))
    event = store.journal.get_events_for_aggregate("Phase2Pipeline", p.root_id)[0]
    tampered = replace(event, event_id="phase2:forged")
    with pytest.raises(Phase2RecoveryError, match="event_id"):
        store._validate_event_contract(tampered, p.root_id, 1, p)


def test_phase2_custom_effective_configuration_survives_runtime_snapshot():
    from dataclasses import replace
    from src.fractal_flow.config.config import build_phase2_effective_config
    instrument = InstrumentSpec("EURUSD", Decimal("0.00001"), 5)
    config = build_phase2_effective_config("EURUSD", "1M", instrument, 3)
    custom = replace(config, pde={**config.pde, "recovery_threshold": Decimal("0.76")})
    p = Phase2Pipeline("EURUSD", "1M", instrument, 3, configuration=custom)
    p.process_bar(make_bar(60, "1.1000", 1))
    restored = Phase2Pipeline.from_snapshot_state(p.snapshot_state())
    assert restored.configuration_id == p.configuration_id
    assert restored.pde.recovery_threshold == Decimal("0.76")
    assert restored.snapshot_state() == p.snapshot_state()


def test_phase2_custom_effective_configuration_survives_durable_replay(tmp_path):
    from dataclasses import replace
    from src.fractal_flow.config.config import build_phase2_effective_config
    instrument = InstrumentSpec("EURUSD", Decimal("0.00001"), 5)
    base = build_phase2_effective_config("EURUSD", "1M", instrument, 3)
    custom = replace(base, pde={**base.pde, "recovery_threshold": Decimal("0.76")})
    p = Phase2Pipeline("EURUSD", "1M", instrument, 3, configuration=custom)
    store = Phase2DurableStore(str(tmp_path), p)
    store.process_bar(make_bar(60, "1.1000", 1))
    recovered = store.recover()
    assert recovered.configuration_id == custom.effective_config_id
    assert recovered.pde.recovery_threshold == Decimal("0.76")


def test_phase2_checkpoint_semantics_reject_identity_tamper_with_valid_checksum(tmp_path):
    from dataclasses import replace
    from src.fractal_flow.persistence.snapshot import AggregateSnapshot

    p = make_pipeline()
    store = Phase2DurableStore(str(tmp_path), p)
    store.process_bar(make_bar(60, "1.1000", 1))
    snap = store.snapshots.load_snapshot("Phase2Pipeline", p.root_id)
    assert snap is not None
    payload = dict(snap.state_payload)
    payload["configuration_id"] = "forged-config-id"
    state_hash = AggregateSnapshot.compute_state_hash(payload)
    checksum = AggregateSnapshot.compute_checksum(
        snap.aggregate_type, snap.aggregate_id, snap.aggregate_version,
        snap.last_sequence_number, payload, snap.schema_version, snap.created_at,
        state_hash=state_hash,
    )
    store.snapshots._snapshots[snap.aggregate_type + ":" + snap.aggregate_id] = replace(
        snap, state_payload=payload, state_hash=state_hash, checksum=checksum
    )
    recovered = store.recover()
    assert recovered._last_watermark == (120, 1)
    assert store.lifecycle_state.value == "ACTIVE"


def test_phase2_replay_evaluations_reconstructs_complete_journal_stream(tmp_path):
    p = make_pipeline()
    store = Phase2DurableStore(str(tmp_path), p)
    for i in range(1, 4):
        store.process_bar(make_bar(i * 60, f"{1.1000 + i * 0.0001:.4f}", i))
    replayed = store.replay_evaluations()
    assert [evaluation.bar.sequence for evaluation in replayed] == [1, 2, 3]
    assert [evaluation.bar.close_timestamp for evaluation in replayed] == [120, 180, 240]
    assert replayed[-1].context.watermark.timestamp == 240


def test_phase2_replay_evaluations_rejects_missing_journal(tmp_path):
    store = Phase2DurableStore(str(tmp_path), make_pipeline())
    with pytest.raises(Phase2RecoveryError, match="No durable Phase 2 journal events"):
        store.replay_evaluations()
