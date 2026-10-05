"""Phase 1C Tests: Clock Injection and Wall-Clock Elimination Audit."""

import pytest

from src.fractal_flow.simulation.clock import SimulationClock

BASE_TS = 1700006400


def test_simulation_clock_advancement_and_seconds_conversion() -> None:
    clock = SimulationClock()
    clock.set_time_seconds(BASE_TS)

    assert clock.now_seconds() == BASE_TS
    assert clock.now_ns() == BASE_TS * 1_000_000_000

    clock.advance_seconds(60)
    assert clock.now_seconds() == BASE_TS + 60
    assert clock.now_ns() == (BASE_TS + 60) * 1_000_000_000

    with pytest.raises(ValueError, match="Cannot rewind"):
        clock.advance_seconds(-10)


def test_wall_clock_call_site_audit() -> None:
    import subprocess

    cmd = "grep -rn -E 'time\\.time\\(|datetime\\.now\\(|datetime\\.utcnow\\(' src/"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    matches = [line.strip() for line in res.stdout.strip().split("\n") if line.strip()]

    allowed_subsystems = [
        "src/fractal_flow/config/config.py",
        "src/fractal_flow/persistence/interfaces.py",
        "src/fractal_flow/persistence/snapshot.py",
        "src/fractal_flow/persistence/journal.py",
        "src/fractal_flow/domain/risk_ledger.py",
        "src/fractal_flow/domain/entry.py",
        "src/fractal_flow/execution/recovery.py",
        "src/fractal_flow/execution/reconciliation.py",
    ]

    for match in matches:
        file_path = match.split(":")[0]
        assert any(subsystem in file_path for subsystem in allowed_subsystems), (
            f"Unapproved direct wall-clock call site in strategy code: {match}"
        )
