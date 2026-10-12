"""Contract tests for the canonical R5 verification-lifecycle runner."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from tools.r5_verification_runner import (
    ALL_TESTS,
    DURABLE_TESTS,
    GATE_TESTS,
    NORMAL_TESTS,
    Lane,
    build_lanes,
    run_lane,
    _coerce_output_text,
)


def test_r5_runner_partitions_all_thirteen_tests_without_overlap() -> None:
    assert len(ALL_TESTS) == 13
    assert len(set(ALL_TESTS)) == 13
    assert set(NORMAL_TESTS).isdisjoint(DURABLE_TESTS)
    assert set(NORMAL_TESTS).isdisjoint(GATE_TESTS)
    assert set(DURABLE_TESTS).isdisjoint(GATE_TESTS)
    assert len(DURABLE_TESTS) == 3
    assert len(GATE_TESTS) == 3


def test_r5_runner_defaults_use_separate_budgets() -> None:
    lanes = build_lanes()
    assert [lane.name for lane in lanes] == ["R5-A-normal", "R5-B-durable", "R5-C-gates"]
    assert [lane.timeout_seconds for lane in lanes] == [180.0, 300.0, 60.0]
    assert [len(lane.tests) for lane in lanes] == [7, 3, 3]


def test_r5_runner_timeout_path_normalizes_bytes_and_reports_failure(tmp_path: Path) -> None:
    child = tmp_path / "test_timeout_probe.py"
    child.write_text(
        "import time\n\ndef test_timeout_probe():\n    print('child-start', flush=True)\n    time.sleep(5)\n",
        encoding="utf-8",
    )
    lane = Lane(
        "timeout-probe",
        (str(child) + "::test_timeout_probe",),
        0.05,
    )
    result = run_lane(lane)
    assert result.timed_out is True
    assert result.passed is False
    assert result.cleanup_ok is True
    assert result.returncode is not None and result.returncode != 0


def test_r5_runner_normalizes_timeout_output_bytes() -> None:
    assert _coerce_output_text(b"partial\xff") == "partial\ufffd"
    assert _coerce_output_text("text") == "text"
    assert _coerce_output_text(None) == ""
