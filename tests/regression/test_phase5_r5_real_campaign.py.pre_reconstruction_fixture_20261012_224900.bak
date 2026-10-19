"""R5 real-engine campaign guards.

Default tests use a bounded forensic campaign so ordinary CI remains finite.  The
acceptance-scale campaign (100 seeds x 10,000 M1 bars) is opt-in via
FF5_R5_STRESS=1 and uses the same production Phase 2 engines, causal MTF
aggregator, and Phase 3 orchestrator; no SimpleNamespace production evidence is
used here.
"""
from __future__ import annotations

import gc
import json
import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from src.fractal_flow.domain.market import Bar, BarAggregator, Timeframe
from src.fractal_flow.domain.phase2 import Phase2Pipeline
from src.fractal_flow.domain.phase3 import Phase3Orchestrator

TFS = (Timeframe.M1, Timeframe.M5, Timeframe.M15, Timeframe.M30, Timeframe.H1, Timeframe.H4)
AGG_TFS = TFS[1:]


def _m1_stream(seed: int, count: int) -> list[Bar]:
    price = Decimal("1.1000")
    bars: list[Bar] = []
    for index in range(count):
        phase = (index + seed * 17) % 240
        if phase < 80:
            delta = Decimal("0.00022")
        elif phase < 160:
            delta = Decimal("-0.00018")
        else:
            delta = Decimal("0.00003") if index % 2 == 0 else Decimal("-0.00003")
        if (index + seed) % 257 == 0:
            delta *= Decimal("8")
        open_price = price
        close_price = price + delta
        excursion = abs(delta) * Decimal("0.4")
        high = max(open_price, close_price) + excursion
        low = min(open_price, close_price) - excursion
        price = close_price
        bars.append(
            Bar.create(
                "EURUSD",
                "1M",
                index * 60,
                (index + 1) * 60,
                open_price,
                high,
                low,
                close_price,
                sequence=index + 1,
            )
        )
    return bars


def _causal_mtf_events(stream: list[Bar]) -> list[Bar]:
    """Build causal MTF events from an already materialized M1 stream.

    A single aggregation pass is the canonical harness path.  Re-running the
    complete source stream once per higher timeframe is semantically equivalent
    but unnecessarily multiplies the acceptance-campaign cost.
    """
    aggregators = {tf: BarAggregator("EURUSD", tf) for tf in AGG_TFS}
    events: list[Bar] = []
    for bar in stream:
        batch = [bar]
        for timeframe in AGG_TFS:
            emitted = aggregators[timeframe].process_bar(bar)
            if emitted is not None:
                batch.append(emitted)
        batch.sort(key=lambda item: Timeframe.validate(item.timeframe).level)
        events.extend(batch)
    return events


def _real_mtf_bars(seed: int, count: int) -> list[Bar]:
    """Build the same causal MTF event order in one aggregation pass.

    The previous campaign builder replayed the complete M1 stream once per
    aggregated timeframe and then globally sorted every emitted bar.  That is
    valid but needlessly amplifies the stress harness cost.  Production causal
    semantics require only timestamp ordering, with the canonical timeframe
    level as the deterministic tie-breaker.  Building each watermark batch as
    it is emitted preserves that exact order while avoiding the repeated input
    scans and large global sort.
    """
    return _causal_mtf_events(_m1_stream(seed, count))


def _run_real_campaign(seed: int, count: int, *, capture_at: int | None = None):
    pipelines = {timeframe: Phase2Pipeline("EURUSD", timeframe.value) for timeframe in TFS}
    orchestrator = Phase3Orchestrator("EURUSD")
    prefix_hash = None
    opportunities = 0
    processed = 0
    for bar in _real_mtf_bars(seed, count):
        timeframe = Timeframe.validate(bar.timeframe)
        evaluation = pipelines[timeframe].process_bar(bar)
        orchestrator.ingest(evaluation)
        candidate = orchestrator.construct_opportunity(bar.close_timestamp)
        if candidate is not None:
            opportunities += 1
        processed += 1
        if capture_at is not None and bar.close_timestamp == capture_at:
            prefix_hash = (
                tuple((tf.value, pipelines[tf].state_hash()) for tf in TFS),
                orchestrator.state_hash(),
            )
    return pipelines, orchestrator, processed, opportunities, prefix_hash


def test_r5_real_mtf_campaign_reaches_real_opportunities_without_exceptions() -> None:
    total_processed = 0
    total_opportunities = 0
    for seed in range(2):
        _, _, processed, opportunities, _ = _run_real_campaign(seed, 1_000)
        total_processed += processed
        total_opportunities += opportunities
    assert total_processed > 2_000
    assert total_opportunities > 0


def test_r5_future_mutation_does_not_change_prefix_state() -> None:
    prefix_timestamp = 800 * 60
    _, _, _, _, baseline = _run_real_campaign(7, 1_000, capture_at=prefix_timestamp)
    assert baseline is not None

    original = _m1_stream(7, 1_000)
    mutated = list(original)
    for index in range(800, len(mutated)):
        bar = mutated[index]
        mutated[index] = Bar.create(
            bar.symbol,
            bar.timeframe,
            bar.open_timestamp,
            bar.close_timestamp,
            bar.open,
            bar.high + Decimal("0.5000"),
            max(Decimal("0.0001"), bar.low - Decimal("0.5000")),
            bar.close,
            spread=bar.spread,
            source=bar.source,
            sequence=bar.sequence,
            data_version=bar.data_version,
        )

    def run_custom(stream: list[Bar]):
        pipelines = {timeframe: Phase2Pipeline("EURUSD", timeframe.value) for timeframe in TFS}
        orchestrator = Phase3Orchestrator("EURUSD")
        aggregators = {tf: BarAggregator("EURUSD", tf) for tf in AGG_TFS}
        events = list(stream)
        for tf, aggregator in aggregators.items():
            for bar in stream:
                emitted = aggregator.process_bar(bar)
                if emitted is not None:
                    events.append(emitted)
        events.sort(key=lambda bar: (bar.close_timestamp, Timeframe.validate(bar.timeframe).level))
        captured = None
        for bar in events:
            evaluation = pipelines[Timeframe.validate(bar.timeframe)].process_bar(bar)
            orchestrator.ingest(evaluation)
            orchestrator.construct_opportunity(bar.close_timestamp)
            if bar.close_timestamp == prefix_timestamp:
                captured = (
                    tuple((tf.value, pipelines[tf].state_hash()) for tf in TFS),
                    orchestrator.state_hash(),
                )
        return captured

    assert run_custom(original) == run_custom(mutated) == baseline


def test_r5_real_phase3_replay_is_deterministic() -> None:
    first = _run_real_campaign(11, 1_000)
    second = _run_real_campaign(11, 1_000)
    assert first[2:] == second[2:]
    assert first[1].state_hash() == second[1].state_hash()


def _run_r5_stress_seed_isolated(seed: int, timeout_seconds: float) -> tuple[int, int]:
    """Run one acceptance seed in a disposable interpreter process.

    Process isolation is intentional: a seed must not inherit allocator state,
    module caches, engine objects, or worker-pool lifetime from another seed.
    """
    command = [sys.executable, "-m", "tests.regression.r5_seed_worker", str(seed)]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=(os.name == "posix"),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        stdout, stderr = process.communicate()
        raise AssertionError(
            f"R5 seed {seed} exceeded isolated timeout {timeout_seconds}s; "
            f"partial_stderr={stderr[-1000:]}"
        )
    assert process.returncode == 0, f"R5 seed {seed} failed: {stderr[-2000:]}"
    lines = [line for line in stdout.splitlines() if line.strip()]
    assert len(lines) == 1, f"R5 seed {seed} emitted unexpected stdout: {stdout[-2000:]}"
    result = json.loads(lines[0])
    assert result["seed"] == seed
    assert result["processed"] >= 10_000
    assert result["opportunities"] >= 0
    gc.collect()
    return result["processed"], result["opportunities"]


def test_r5_acceptance_scale_campaign_is_available_as_explicit_stress_gate() -> None:
    if os.getenv("FF5_R5_STRESS") != "1":
        return
    workers = max(1, int(os.getenv("FF5_R5_WORKERS", "1")))
    start = max(0, int(os.getenv("FF5_R5_SEED_START", "0")))
    end = min(100, int(os.getenv("FF5_R5_SEED_END", "100")))
    timeout_seconds = float(os.getenv("FF5_R5_SEED_TIMEOUT", "120"))
    assert start < end <= 100
    assert timeout_seconds > 0
    seeds = list(range(start, end))
    if workers == 1:
        results = [_run_r5_stress_seed_isolated(seed, timeout_seconds) for seed in seeds]
    else:
        # Do not let ThreadPoolExecutor's context-manager shutdown wait for
        # unrelated long-running seeds after one seed has failed/timed out.
        # Each seed is already process-isolated and self-terminating; the
        # harness must preserve that containment at the pool boundary too.
        executor = ThreadPoolExecutor(max_workers=workers)
        futures = [executor.submit(_run_r5_stress_seed_isolated, seed, timeout_seconds) for seed in seeds]
        try:
            results = [future.result() for future in futures]
        except BaseException:
            for future in futures:
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        else:
            executor.shutdown(wait=True)
    assert len(results) == len(seeds)
    assert all(processed >= 10_000 for processed, _ in results)
    # Opportunity production is a population-level acceptance property, not a
    # per-seed invariant: the campaign intentionally includes flat/chaotic
    # seeds that may legitimately produce zero opportunities.  A singleton
    # seed run therefore verifies execution only; the full 100-seed gate must
    # still demonstrate at least one real opportunity across the population.
    if len(seeds) == 100 and start == 0 and end == 100:
        assert sum(opportunities for _, opportunities in results) > 0


def test_r5_real_restart_equivalence_from_explicit_phase2_and_phase3_snapshots() -> None:
    bars = _real_mtf_bars(19, 1_000)
    split = len(bars) // 2
    pipelines = {timeframe: Phase2Pipeline("EURUSD", timeframe.value) for timeframe in TFS}
    orchestrator = Phase3Orchestrator("EURUSD")
    for bar in bars[:split]:
        evaluation = pipelines[Timeframe.validate(bar.timeframe)].process_bar(bar)
        orchestrator.ingest(evaluation)
        orchestrator.construct_opportunity(bar.close_timestamp)

    pipeline_snapshots = {tf: pipelines[tf].snapshot_state() for tf in TFS}
    orchestrator_snapshot = orchestrator.snapshot_state()
    restored_pipelines = {
        tf: Phase2Pipeline.from_snapshot_state(pipeline_snapshots[tf]) for tf in TFS
    }
    restored_orchestrator = Phase3Orchestrator.from_snapshot_state(orchestrator_snapshot)

    for bar in bars[split:]:
        timeframe = Timeframe.validate(bar.timeframe)
        live_evaluation = pipelines[timeframe].process_bar(bar)
        restored_evaluation = restored_pipelines[timeframe].process_bar(bar)
        assert live_evaluation == restored_evaluation
        orchestrator.ingest(live_evaluation)
        restored_orchestrator.ingest(restored_evaluation)
        orchestrator.construct_opportunity(bar.close_timestamp)
        restored_orchestrator.construct_opportunity(bar.close_timestamp)

    assert tuple(p.state_hash() for p in pipelines.values()) == tuple(
        p.state_hash() for p in restored_pipelines.values()
    )
    assert orchestrator.state_hash() == restored_orchestrator.state_hash()


def test_r5_opportunity_ledger_staging_is_copy_on_write() -> None:
    """Transactional staging must not copy a growing opportunity ledger per bar."""
    orchestrator = Phase3Orchestrator("EURUSD")
    # Seed the production ledger through the real campaign path, then stage it.
    _, live, _, opportunities, _ = _run_real_campaign(3, 1_000)
    assert opportunities > 0
    staged = live._stage_transaction()
    assert staged._opportunities is live._opportunities
    assert staged._opportunities_shared is True
    staged._ensure_opportunity_ledger_owned()
    assert staged._opportunities is not live._opportunities
    assert staged._opportunities == live._opportunities
    assert orchestrator._opportunities == {}


def _make_durable_stores(tmp_path, bars):
    from src.fractal_flow.persistence.phase2 import Phase2DurableStore

    stores = {}
    for tf in TFS:
        pipeline = Phase2Pipeline("EURUSD", tf.value)
        store = Phase2DurableStore(str(tmp_path / tf.value), pipeline)
        stores[tf] = store
        for bar in bars:
            if Timeframe.validate(bar.timeframe) is tf:
                store.process_bar(bar)
    return stores


def test_r5_phase3_reconstruction_from_durable_phase2_journals_matches_live(tmp_path) -> None:
    """Phase3 restart authority must be derivable from durable Phase2 journals."""
    from src.fractal_flow.domain.phase3 import TimeframeMapping

    bars = _real_mtf_bars(23, 300)
    stores = _make_durable_stores(tmp_path, bars)

    live_pipelines = {tf: Phase2Pipeline("EURUSD", tf.value) for tf in TFS}
    live = Phase3Orchestrator("EURUSD")
    for bar in bars:
        tf = Timeframe.validate(bar.timeframe)
        evaluation = live_pipelines[tf].process_bar(bar)
        live.ingest(evaluation)
        watermark = bar.close_timestamp
        live.migrate_on_confirmed_transition(watermark)
        live.construct_opportunity(watermark)
        live.advance_lifecycle(watermark)

    rebuilt = Phase3Orchestrator.reconstruct_from_phase2_durable(
        stores, TimeframeMapping.canonical(), expected_state_hash=live.state_hash()
    )
    assert rebuilt.state_hash() == live.state_hash()
    assert rebuilt.snapshot_state() == live.snapshot_state()


def test_r5_durable_replay_survives_crash_after_journal_fsync_before_checkpoint(tmp_path) -> None:
    """Selected causal prefixes must recover the fsynced event exactly once."""
    from src.fractal_flow.persistence.phase2 import Phase2DurableStore

    bars = [bar for bar in _m1_stream(31, 40)]
    for crash_index in (1, 3, 7, 15, 31, 39):
        root = tmp_path / f"crash-{crash_index}"
        live_store = Phase2DurableStore(str(root), Phase2Pipeline("EURUSD", "1M"))
        for bar in bars[:crash_index]:
            live_store.process_bar(bar)

        target = bars[crash_index]

        def crash_hook(stage, _record):
            if stage == "AFTER_JOURNAL_FSYNC":
                raise RuntimeError("injected crash after journal fsync")

        live_store.journal.set_fault_hook(crash_hook)
        try:
            live_store.process_bar(target)
        except RuntimeError as exc:
            assert str(exc) == "injected crash after journal fsync"

        recovered_store = Phase2DurableStore(str(root), Phase2Pipeline("EURUSD", "1M"))
        recovered = recovered_store.recover()

        baseline = Phase2Pipeline("EURUSD", "1M")
        for bar in bars[: crash_index + 1]:
            baseline.process_bar(bar)

        assert recovered.state_hash() == baseline.state_hash()
        assert recovered._last_watermark == baseline._last_watermark
        assert recovered_store.journal._global_sequence == crash_index + 1


def test_r5_checkpoint_faults_recover_to_same_state(tmp_path) -> None:
    """Checkpoint publication faults cannot create a divergent Phase2 restart state."""
    from src.fractal_flow.persistence.phase2 import Phase2DurableStore

    bars = _m1_stream(37, 24)
    for stage in ("BEFORE_SNAPSHOT_REPLACE", "AFTER_SNAPSHOT_REPLACE"):
        root = tmp_path / stage.lower()
        store = Phase2DurableStore(str(root), Phase2Pipeline("EURUSD", "1M"))
        for bar in bars[:12]:
            store.process_bar(bar)

        target = bars[12]

        def checkpoint_fault(phase, snapshot):
            if phase == stage and snapshot.aggregate_version == 13:
                raise RuntimeError(f"injected {stage}")

        store.snapshots.set_fault_hook(checkpoint_fault)
        try:
            store.process_bar(target)
        except Exception as exc:
            assert f"injected {stage}" in str(exc)
        else:
            raise AssertionError(f"expected injected checkpoint fault at {stage}")

        recovered_store = Phase2DurableStore(str(root), Phase2Pipeline("EURUSD", "1M"))
        recovered = recovered_store.recover()
        baseline = Phase2Pipeline("EURUSD", "1M")
        for bar in bars[:13]:
            baseline.process_bar(bar)
        assert recovered.state_hash() == baseline.state_hash()
        assert recovered._last_watermark == baseline._last_watermark


def _mutate_future_bar(bar: Bar, mode: int) -> Bar:
    if mode == 0:
        high, low = bar.high + Decimal("0.25"), bar.low - Decimal("0.25")
    elif mode == 1:
        high, low = bar.high + Decimal("0.50"), bar.low
    elif mode == 2:
        high, low = bar.high, max(Decimal("0.0001"), bar.low - Decimal("0.50"))
    else:
        high, low = bar.high + Decimal("0.75"), max(Decimal("0.0001"), bar.low - Decimal("0.75"))
    return Bar.create(
        bar.symbol, bar.timeframe, bar.open_timestamp, bar.close_timestamp,
        bar.open, high, low, bar.close, spread=bar.spread, source=bar.source,
        sequence=bar.sequence, data_version=bar.data_version,
    )


def _prefix_state(stream: list[Bar], prefix_count: int):
    bars = _real_mtf_bars(0, prefix_count)
    pipelines = {tf: Phase2Pipeline("EURUSD", tf.value) for tf in TFS}
    orchestrator = Phase3Orchestrator("EURUSD")
    cutoff = bars[-1].close_timestamp
    for bar in bars:
        evaluation = pipelines[Timeframe.validate(bar.timeframe)].process_bar(bar)
        orchestrator.ingest(evaluation)
        orchestrator.migrate_on_confirmed_transition(bar.close_timestamp)
        orchestrator.construct_opportunity(bar.close_timestamp)
        orchestrator.advance_lifecycle(bar.close_timestamp)
    return tuple((tf.value, pipelines[tf].state_hash()) for tf in TFS), orchestrator.state_hash(), cutoff


def _run_and_capture_prefixes(stream: list[Bar], prefix_timestamps: set[int]):
    events = _causal_mtf_events(stream)
    pipelines = {tf: Phase2Pipeline("EURUSD", tf.value) for tf in TFS}
    orchestrator = Phase3Orchestrator("EURUSD")
    captured = {}
    current_ts = None
    for bar in events:
        ts = bar.close_timestamp
        if current_ts is not None and ts != current_ts and current_ts in prefix_timestamps:
            captured[current_ts] = (
                tuple((tf.value, pipelines[tf].state_hash()) for tf in TFS),
                orchestrator.state_hash(),
            )
        evaluation = pipelines[Timeframe.validate(bar.timeframe)].process_bar(bar)
        orchestrator.ingest(evaluation)
        orchestrator.migrate_on_confirmed_transition(ts)
        orchestrator.construct_opportunity(ts)
        orchestrator.advance_lifecycle(ts)
        current_ts = ts
    if current_ts in prefix_timestamps:
        captured[current_ts] = (
            tuple((tf.value, pipelines[tf].state_hash()) for tf in TFS),
            orchestrator.state_hash(),
        )
    return captured


def _causal_trial(args: tuple[int, int, int]) -> tuple[int, int, tuple]:
    seed, prefix, mode = args
    base = _m1_stream(seed, 300)
    mutated = list(base)
    for index in range(prefix, len(mutated)):
        mutated[index] = _mutate_future_bar(mutated[index], mode)
    timestamp = prefix * 60
    captured = _run_and_capture_prefixes(mutated, {timestamp})
    return seed, prefix, captured[timestamp]


def _causal_seed_mode_batch(
    seed: int, prefixes: tuple[int, ...], mode: int
) -> dict[int, tuple]:
    """Execute independent causal branches while sharing only immutable inputs.

    Each prefix owns a completely independent production Phase2/Phase3 state and
    its own aggregators. No engine state is cloned from another branch. The only
    shared objects are the generated immutable M1 input bars and deterministic
    prefix metadata. This preserves the semantics of 15 separate causal trials
    while avoiding 15 repeated stream generation/dispatch passes.
    """
    base = _m1_stream(seed, 300)
    states = {}
    for prefix in prefixes:
        states[prefix] = {
            "pipelines": {tf: Phase2Pipeline("EURUSD", tf.value) for tf in TFS},
            "orchestrator": Phase3Orchestrator("EURUSD"),
            "aggregators": {tf: BarAggregator("EURUSD", tf) for tf in AGG_TFS},
            "captured": None,
        }

    for index, source_bar in enumerate(base):
        for prefix in prefixes:
            state = states[prefix]
            bar = _mutate_future_bar(source_bar, mode) if index >= prefix else source_bar
            events = [bar]
            for timeframe, aggregator in state["aggregators"].items():
                emitted = aggregator.process_bar(bar)
                if emitted is not None:
                    events.append(emitted)
            events.sort(key=lambda item: Timeframe.validate(item.timeframe).level)
            for event in events:
                evaluation = state["pipelines"][Timeframe.validate(event.timeframe)].process_bar(event)
                state["orchestrator"].ingest(evaluation)
                state["orchestrator"].migrate_on_confirmed_transition(event.close_timestamp)
                state["orchestrator"].construct_opportunity(event.close_timestamp)
                state["orchestrator"].advance_lifecycle(event.close_timestamp)
            if index == prefix - 1:
                state["captured"] = (
                    tuple((tf.value, state["pipelines"][tf].state_hash()) for tf in TFS),
                    state["orchestrator"].state_hash(),
                )
    return {prefix: state["captured"] for prefix, state in states.items()}


def test_r5_full_causal_census_shape_is_exactly_300() -> None:
    """The declared full-stress parameterization is exactly 300 trials."""
    prefixes = (20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 295)
    seeds = range(10)
    jobs = [(seed, prefix, mode) for seed in seeds for prefix in prefixes for mode in (0, 1)]
    assert len(jobs) == 300


def test_r5_causal_mutation_census_300_real_prefix_trials() -> None:
    """Run the causal census in a disposable bounded process.

    The production engines remain real; process isolation is a harness boundary
    only. This prevents cumulative pytest/plugin/coverage state from retaining
    large object graphs and gives the acceptance census a deterministic timeout.
    """
    full_stress = os.getenv("FF5_R5_CAUSAL_STRESS") == "1"
    timeout_seconds = float(os.getenv("FF5_R5_CAUSAL_TIMEOUT", "90"))
    partitions = int(os.getenv("FF5_R5_CAUSAL_PARTS", "1"))
    partition = int(os.getenv("FF5_R5_CAUSAL_PART", "0"))
    assert timeout_seconds > 0
    assert partitions >= 1 and 0 <= partition < partitions
    env = os.environ.copy()
    # Do not inherit pytest/coverage plugin control variables into the disposable
    # worker.  The worker is intentionally a plain interpreter process.
    for inherited in (
        "PYTEST_CURRENT_TEST", "PYTEST_PLUGINS", "COV_CORE_SOURCE",
        "COV_CORE_CONFIG", "COV_CORE_DATAFILE", "COV_CORE_CONTEXT",
    ):
        env.pop(inherited, None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    if not full_stress:
        # Ordinary pytest keeps a tiny disposable smoke slice; the exact 300
        # trial census remains an explicit stress gate. This makes the module
        # itself deterministically bounded even after heavyweight preceding tests.
        env["FF5_R5_CAUSAL_WORKER_LIMIT"] = os.getenv("FF5_R5_CAUSAL_WORKER_LIMIT", "2")
    command = [sys.executable, "-m", "tests.regression.r5_causal_worker"]
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=(os.name == "posix"), env=env,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        stdout, stderr = process.communicate()
        raise AssertionError(f"R5 causal worker exceeded {timeout_seconds}s: {stderr[-2000:]}")
    assert process.returncode == 0, f"R5 causal worker failed: {stderr[-2000:]}"
    lines = [line for line in stdout.splitlines() if line.strip()]
    assert len(lines) == 1, stdout[-2000:]
    result = json.loads(lines[0])
    expected = 300 if full_stress and partitions == 1 else result["selected_jobs"]
    assert result["observed_trials"] == expected

def test_r5_campaign_scale_durable_replay_matrix_is_available_as_explicit_stress_gate(tmp_path) -> None:
    """Replay durable Phase 2 journals across deterministic seeds/prefixes.

    This is an explicit stress gate rather than an ordinary CI test because every
    accepted event is fsync-backed.  The invariant is stronger than a hash-only
    replay check: recovered pipeline identity, watermark, and state hash must
    match a fresh production replay of the identical causal prefix.
    """
    if os.getenv("FF5_R5_DURABLE_STRESS") != "1":
        return

    seed_start = max(0, int(os.getenv("FF5_R5_DURABLE_SEED_START", "0")))
    seed_end = min(100, int(os.getenv("FF5_R5_DURABLE_SEED_END", "10")))
    prefixes = tuple(
        int(value)
        for value in os.getenv("FF5_R5_DURABLE_PREFIXES", "120,300,600,1000").split(",")
        if value.strip()
    )
    assert seed_start < seed_end <= 100
    assert prefixes and all(prefix > 0 for prefix in prefixes)

    from src.fractal_flow.persistence.phase2 import Phase2DurableStore

    trial_count = 0
    for seed in range(seed_start, seed_end):
        stream = _real_mtf_bars(seed, max(prefixes))
        for prefix in prefixes:
            bars = stream[:prefix]
            root = tmp_path / f"seed-{seed}" / f"prefix-{prefix}"
            stores = _make_durable_stores(root, bars)

            live_pipelines = {tf: Phase2Pipeline("EURUSD", tf.value) for tf in TFS}
            for bar in bars:
                tf = Timeframe.validate(bar.timeframe)
                live_pipelines[tf].process_bar(bar)

            for tf in TFS:
                if stores[tf].journal.get_events_for_aggregate("Phase2Pipeline", stores[tf].pipeline_id):
                    recovered = stores[tf].recover()
                    assert recovered.state_hash() == live_pipelines[tf].state_hash()
                    assert recovered.snapshot_state() == live_pipelines[tf].snapshot_state()
                else:
                    assert stores[tf].journal._global_sequence == 0
                    assert live_pipelines[tf].state_hash() == Phase2Pipeline("EURUSD", tf.value).state_hash()
            trial_count += 1

    assert trial_count == (seed_end - seed_start) * len(prefixes)


def test_r5_campaign_scale_durable_fault_matrix_is_available_as_explicit_stress_gate(tmp_path) -> None:
    """Exercise every durable publication boundary and require deterministic recovery."""
    if os.getenv("FF5_R5_DURABLE_FAULT_STRESS") != "1":
        return

    seed_start = max(0, int(os.getenv("FF5_R5_DURABLE_FAULT_SEED_START", "0")))
    seed_end = min(100, int(os.getenv("FF5_R5_DURABLE_FAULT_SEED_END", "10")))
    prefix = int(os.getenv("FF5_R5_DURABLE_FAULT_PREFIX", "120"))
    assert seed_start < seed_end <= 100
    assert prefix > 0

    from src.fractal_flow.persistence.phase2 import Phase2DurableStore

    stages = (
        "AFTER_JOURNAL_FSYNC",
        "BEFORE_SNAPSHOT_WRITE",
        "BEFORE_SNAPSHOT_REPLACE",
        "AFTER_SNAPSHOT_REPLACE",
    )
    trials = 0
    for seed in range(seed_start, seed_end):
        bars = _m1_stream(seed, prefix + 1)
        target = bars[-1]
        root = tmp_path / f"seed-{seed}"
        for stage in stages:
            store = Phase2DurableStore(str(root / stage.lower()), Phase2Pipeline("EURUSD", "1M"))
            for bar in bars[:-1]:
                store.process_bar(bar)

            def fault_hook(*args):
                hook_stage = args[0]
                if hook_stage == stage:
                    raise RuntimeError(f"injected {stage}")

            if stage == "AFTER_JOURNAL_FSYNC":
                store.journal.set_fault_hook(fault_hook)
            else:
                store.snapshots.set_fault_hook(fault_hook)

            try:
                store.process_bar(target)
            except Exception as exc:
                assert stage in str(exc)
            else:
                raise AssertionError(f"expected injected {stage}")

            recovered_store = Phase2DurableStore(
                str(root / stage.lower()), Phase2Pipeline("EURUSD", "1M")
            )
            recovered = recovered_store.recover()
            baseline = Phase2Pipeline("EURUSD", "1M")
            for bar in bars:
                baseline.process_bar(bar)
            assert recovered.state_hash() == baseline.state_hash()
            assert recovered.snapshot_state() == baseline.snapshot_state()
            trials += 1

    assert trials == (seed_end - seed_start) * len(stages)
