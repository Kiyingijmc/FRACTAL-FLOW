#!/usr/bin/env python3
"""Canonical Phase 5 R5 verification-lifecycle runner.

R5 mixes ordinary CPU-heavy regression with real fsync-backed recovery tests.
This runner keeps all 13 tests and their assertions intact, but executes them in
truthful verification lanes with independent budgets and process containment.

The runner is verification-only: it does not alter production persistence or
trading semantics and it never enables the population-scale stress campaigns.
"""
from __future__ import annotations

import argparse
import os
import resource
import signal
import shlex
import subprocess
import tempfile
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

R5_TEST_FILE = "tests/regression/test_phase5_r5_real_campaign.py"

NORMAL_TESTS = (
    f"{R5_TEST_FILE}::test_r5_real_mtf_campaign_reaches_real_opportunities_without_exceptions",
    f"{R5_TEST_FILE}::test_r5_future_mutation_does_not_change_prefix_state",
    f"{R5_TEST_FILE}::test_r5_real_phase3_replay_is_deterministic",
    f"{R5_TEST_FILE}::test_r5_real_restart_equivalence_from_explicit_phase2_and_phase3_snapshots",
    f"{R5_TEST_FILE}::test_r5_opportunity_ledger_staging_is_copy_on_write",
    f"{R5_TEST_FILE}::test_r5_full_causal_census_shape_is_exactly_300",
    f"{R5_TEST_FILE}::test_r5_causal_mutation_census_300_real_prefix_trials",
)

DURABLE_TESTS = (
    f"{R5_TEST_FILE}::test_r5_phase3_reconstruction_from_durable_phase2_journals_matches_live",
    f"{R5_TEST_FILE}::test_r5_durable_replay_survives_crash_after_journal_fsync_before_checkpoint",
    f"{R5_TEST_FILE}::test_r5_checkpoint_faults_recover_to_same_state",
)

GATE_TESTS = (
    f"{R5_TEST_FILE}::test_r5_acceptance_scale_campaign_is_available_as_explicit_stress_gate",
    f"{R5_TEST_FILE}::test_r5_campaign_scale_durable_replay_matrix_is_available_as_explicit_stress_gate",
    f"{R5_TEST_FILE}::test_r5_campaign_scale_durable_fault_matrix_is_available_as_explicit_stress_gate",
)

ALL_TESTS = NORMAL_TESTS + DURABLE_TESTS + GATE_TESTS


@dataclass(frozen=True)
class Lane:
    name: str
    tests: tuple[str, ...]
    timeout_seconds: float


@dataclass(frozen=True)
class LaneResult:
    name: str
    returncode: int | None
    elapsed_seconds: float
    timed_out: bool
    output: str
    cleanup_ok: bool
    user_cpu_seconds: float
    system_cpu_seconds: float

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and not self.timed_out and self.cleanup_ok


def _positive_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    value = default if raw is None else float(raw)
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def build_lanes() -> tuple[Lane, ...]:
    return (
        Lane("R5-A-normal", NORMAL_TESTS, _positive_env("FF5_R5_NORMAL_TIMEOUT", 180.0)),
        Lane("R5-B-durable", DURABLE_TESTS, _positive_env("FF5_R5_DURABLE_TIMEOUT", 300.0)),
        Lane("R5-C-gates", GATE_TESTS, _positive_env("FF5_R5_GATE_TIMEOUT", 60.0)),
    )


def _descendant_pids(root_pid: int) -> set[int]:
    if os.name != "posix" or not Path("/proc").is_dir():
        return set()
    parent_map: dict[int, int] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text(encoding="utf-8").split()
            if len(fields) > 3:
                parent_map[int(entry.name)] = int(fields[3])
        except (FileNotFoundError, PermissionError, ValueError):
            continue
    descendants: set[int] = set()
    frontier = [root_pid]
    while frontier:
        parent = frontier.pop()
        for pid, ppid in parent_map.items():
            if ppid == parent and pid not in descendants:
                descendants.add(pid)
                frontier.append(pid)
    return descendants


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    descendants = _descendant_pids(process.pid)
    if os.name == "posix":
        for pid in sorted(descendants, reverse=True):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        time.sleep(0.2)
        for pid in sorted(_descendant_pids(process.pid), reverse=True):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
    else:
        process.kill()


def _cleanup_ok(process: subprocess.Popen[str]) -> bool:
    if process.poll() is None:
        return False
    return not _descendant_pids(process.pid) if os.name == "posix" else True


def _coerce_output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def run_lane(lane: Lane) -> LaneResult:
    env = os.environ.copy()
    for name in (
        "FF5_R5_STRESS",
        "FF5_R5_DURABLE_STRESS",
        "FF5_R5_DURABLE_FAULT_STRESS",
        "FF5_R5_CAUSAL_STRESS",
    ):
        env.pop(name, None)

    # The verification subprocess must not inherit repository pytest addopts or
    # auto-loaded third-party plugins. Those plugins are outside the R5 workload
    # and can retain interpreter resources after the assertions have passed.
    # R5 is already a no-coverage lane, so explicitly disable plugin autoload and
    # clear configured addopts rather than depending on pytest-cov being loaded.
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTEST_ADDOPTS"] = ""
    pytest_command = [sys.executable, "-m", "pytest", "-o", "addopts=", "-q", *lane.tests]
    if os.name == "posix":
        # Launch through a tiny shell exec wrapper. In the containerized Linux
        # verification environment, direct Python->Python spawning can retain
        # pytest/plugin subprocess state in a way that does not occur when the
        # exact same command is launched by the shell. The shell performs no
        # test transformation; exec replaces it with the canonical pytest
        # process.
        command = ["/bin/sh", "-c", "exec " + shlex.join(pytest_command)]
    else:
        command = pytest_command

    output = ""
    timed_out = False
    with tempfile.TemporaryFile(mode="w+b") as output_file:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdout=output_file,
            stderr=subprocess.STDOUT,
        )
        usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        started = time.monotonic()
        try:
            process.wait(timeout=lane.timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_process_tree(process)
            process.wait()
        output_file.seek(0)
        output = output_file.read().decode(errors="replace")
    elapsed = time.monotonic() - started
    usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cleanup_ok = _cleanup_ok(process)
    return LaneResult(
        lane.name,
        process.returncode,
        elapsed,
        timed_out,
        output,
        cleanup_ok,
        usage_after.ru_utime - usage_before.ru_utime,
        usage_after.ru_stime - usage_before.ru_stime,
    )

def _filesystem_type() -> str:
    if os.name != "posix":
        return "unknown"
    try:
        result = subprocess.run(
            ["stat", "-f", "-c", "%T", str(ROOT)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def run(*, lane_name: str | None = None) -> int:
    lanes = build_lanes()
    if lane_name is not None:
        lanes = tuple(lane for lane in lanes if lane.name == lane_name)
        if not lanes:
            raise SystemExit(f"unknown lane: {lane_name}")

    print(f"R5_ENV python={sys.version.split()[0]} platform={sys.platform} filesystem={_filesystem_type()}")
    results: list[LaneResult] = []
    for lane in lanes:
        print(f"=== {lane.name} timeout={lane.timeout_seconds:.1f}s tests={len(lane.tests)} ===")
        result = run_lane(lane)
        results.append(result)
        print(result.output.rstrip())
        print(
            f"R5_LANE_RESULT name={result.name} pass={result.passed} "
            f"returncode={result.returncode} timeout={result.timed_out} "
            f"elapsed={result.elapsed_seconds:.2f}s cleanup={result.cleanup_ok} "
            f"user_cpu={result.user_cpu_seconds:.2f}s system_cpu={result.system_cpu_seconds:.2f}s"
        )
        if not result.passed:
            print("R5 verification blocked: stop before running later lanes.")
            return 1

    print(
        "R5_VERIFICATION_SUMMARY "
        f"lanes={len(results)} passed={sum(result.passed for result in results)} "
        f"total={len(results)}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", choices=("R5-A-normal", "R5-B-durable", "R5-C-gates"))
    args = parser.parse_args()
    return run(lane_name=args.lane)


if __name__ == "__main__":
    raise SystemExit(main())
