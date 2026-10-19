from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from src.fractal_flow.execution.command_ledger import (
    CommandLedgerRecord,
    DurableCommandLedger,
)
from src.fractal_flow.execution.ffbp_protocol import (
    CommandConflictError,
    CommandState,
)


def rec(fp: str = "fp") -> CommandLedgerRecord:
    return CommandLedgerRecord(
        "A", "C1", "I1", fp, CommandState.PERSISTED, 1, 1, 1000
    )


def test_durable_command_identity_and_restart(tmp_path: Path) -> None:
    db = tmp_path / "commands.sqlite"
    ledger = DurableCommandLedger(str(db))
    assert ledger.create(rec()).state is CommandState.PERSISTED
    ledger.transition("A", "C1", CommandState.DISPATCHABLE, 2)
    ledger.transition("A", "C1", CommandState.SENT, 3)
    ledger.transition("A", "C1", CommandState.UNKNOWN, 4)

    restarted = DurableCommandLedger(str(db))
    persisted = restarted.get("A", "C1")
    assert persisted is not None
    assert persisted.state is CommandState.UNKNOWN


def test_transition_returns_updated_record_from_same_transaction(
    tmp_path: Path,
) -> None:
    db = tmp_path / "commands.sqlite"
    ledger = DurableCommandLedger(str(db))
    ledger.create(rec())

    updated = ledger.transition(
        "A",
        "C1",
        CommandState.DISPATCHABLE,
        2,
        result={"decision": "accepted"},
        broker_reference="test-reference",
    )

    assert updated.state is CommandState.DISPATCHABLE
    assert updated.updated_at_ms == 2
    assert updated.result == {"decision": "accepted"}
    assert updated.broker_reference == "test-reference"
    assert ledger.get("A", "C1") == updated


def test_same_identity_is_idempotent_but_conflict_is_fatal(
    tmp_path: Path,
) -> None:
    ledger = DurableCommandLedger(str(tmp_path / "c.sqlite"))
    first = ledger.create(rec())
    assert ledger.create(rec()) == first
    with pytest.raises(CommandConflictError):
        ledger.create(rec("different"))


def test_unknown_cannot_blindly_resend(tmp_path: Path) -> None:
    ledger = DurableCommandLedger(str(tmp_path / "c.sqlite"))
    ledger.create(rec())
    ledger.transition("A", "C1", CommandState.DISPATCHABLE, 2)
    ledger.transition("A", "C1", CommandState.SENT, 3)
    ledger.transition("A", "C1", CommandState.UNKNOWN, 4)
    with pytest.raises(ValueError, match="blindly resend"):
        ledger.transition("A", "C1", CommandState.SENT, 5)


def test_same_state_transition_is_not_accepted_as_a_fresh_claim(tmp_path: Path) -> None:
    ledger = DurableCommandLedger(str(tmp_path / "c.sqlite"))
    ledger.create(rec())
    ledger.transition("A", "C1", CommandState.DISPATCHABLE, 2)
    ledger.transition("A", "C1", CommandState.SENT, 3)

    with pytest.raises(ValueError, match="same-state"):
        ledger.transition("A", "C1", CommandState.SENT, 4)


def test_dispatch_claim_succeeds_only_once(tmp_path: Path) -> None:
    ledger = DurableCommandLedger(str(tmp_path / "c.sqlite"))
    ledger.create(rec())
    ledger.transition("A", "C1", CommandState.DISPATCHABLE, 2)

    claimed = ledger.claim_dispatch("A", "C1", 3)
    assert claimed is not None
    assert claimed.state is CommandState.SENT
    assert claimed.updated_at_ms == 3
    assert ledger.claim_dispatch("A", "C1", 4) is None
    assert ledger.get("A", "C1").state is CommandState.SENT


def test_dispatch_claim_competing_ledger_instances_only_one_wins(tmp_path: Path) -> None:
    db = str(tmp_path / "c.sqlite")
    DurableCommandLedger(db).create(rec())
    DurableCommandLedger(db).transition("A", "C1", CommandState.DISPATCHABLE, 2)
    ledgers = [DurableCommandLedger(db) for _ in range(12)]

    def claim(index: int):
        return ledgers[index].claim_dispatch("A", "C1", 3 + index)

    with ThreadPoolExecutor(max_workers=len(ledgers)) as pool:
        results = list(pool.map(claim, range(len(ledgers))))

    winners = [result for result in results if result is not None]
    assert len(winners) == 1
    assert winners[0].state is CommandState.SENT
    assert DurableCommandLedger(db).get("A", "C1").state is CommandState.SENT


def test_dispatch_claim_after_restart_does_not_reauthorize_sent_command(
    tmp_path: Path,
) -> None:
    db = str(tmp_path / "c.sqlite")
    first = DurableCommandLedger(db)
    first.create(rec())
    first.transition("A", "C1", CommandState.DISPATCHABLE, 2)
    assert first.claim_dispatch("A", "C1", 3) is not None

    restarted = DurableCommandLedger(db)
    assert restarted.claim_dispatch("A", "C1", 4) is None
    assert restarted.get("A", "C1").state is CommandState.SENT


def test_dispatch_claim_unknown_command_raises_key_error(tmp_path: Path) -> None:
    ledger = DurableCommandLedger(str(tmp_path / "c.sqlite"))
    with pytest.raises(KeyError, match="unknown command"):
        ledger.claim_dispatch("A", "missing", 1)


@pytest.mark.parametrize("now_ms", [-1, True, 1.5])
def test_dispatch_claim_rejects_invalid_timestamp(tmp_path: Path, now_ms) -> None:
    ledger = DurableCommandLedger(str(tmp_path / "c.sqlite"))
    ledger.create(rec())
    ledger.transition("A", "C1", CommandState.DISPATCHABLE, 2)
    with pytest.raises(ValueError, match="now_ms"):
        ledger.claim_dispatch("A", "C1", now_ms)


def test_dispatch_claim_does_not_claim_unknown_or_terminal_state(tmp_path: Path) -> None:
    ledger = DurableCommandLedger(str(tmp_path / "c.sqlite"))
    ledger.create(rec())
    assert ledger.claim_dispatch("A", "C1", 2) is None
    assert ledger.get("A", "C1").state is CommandState.PERSISTED

def test_dispatch_claim_before_expiry_succeeds(tmp_path: Path) -> None:
    ledger = DurableCommandLedger(str(tmp_path / "c.sqlite"))
    ledger.create(rec())
    ledger.transition("A", "C1", CommandState.DISPATCHABLE, 2)

    claimed = ledger.claim_dispatch("A", "C1", 999)

    assert claimed is not None
    assert claimed.state is CommandState.SENT


@pytest.mark.parametrize("now_ms", [1000, 1001])
def test_dispatch_claim_at_or_after_expiry_persists_expired_state(
    tmp_path: Path, now_ms: int,
) -> None:
    db = str(tmp_path / "c.sqlite")
    ledger = DurableCommandLedger(db)
    ledger.create(rec())
    ledger.transition("A", "C1", CommandState.DISPATCHABLE, 2)

    assert ledger.claim_dispatch("A", "C1", now_ms) is None

    restarted = DurableCommandLedger(db)
    record = restarted.get("A", "C1")
    assert record is not None
    assert record.state is CommandState.EXPIRED
    assert record.updated_at_ms == now_ms


def test_dispatch_claim_without_expiry_deadline_is_allowed(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    ledger = DurableCommandLedger(str(tmp_path / "c.sqlite"))
    ledger.create(replace(rec(), expires_at_ms=None))
    ledger.transition("A", "C1", CommandState.DISPATCHABLE, 2)

    claimed = ledger.claim_dispatch("A", "C1", 10_000)

    assert claimed is not None
    assert claimed.state is CommandState.SENT


def test_competing_claims_cannot_dispatch_an_expired_command(
    tmp_path: Path,
) -> None:
    db = str(tmp_path / "c.sqlite")
    DurableCommandLedger(db).create(rec())
    DurableCommandLedger(db).transition("A", "C1", CommandState.DISPATCHABLE, 2)
    ledgers = [DurableCommandLedger(db) for _ in range(12)]

    def claim(index: int):
        return ledgers[index].claim_dispatch("A", "C1", 1000 + index)

    with ThreadPoolExecutor(max_workers=len(ledgers)) as pool:
        results = list(pool.map(claim, range(len(ledgers))))

    assert all(result is None for result in results)
    record = DurableCommandLedger(db).get("A", "C1")
    assert record is not None
    assert record.state is CommandState.EXPIRED
