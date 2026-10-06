from __future__ import annotations

from pathlib import Path

import pytest

from src.fractal_flow.domain.phase4 import AccountRegistry, Phase4ValidationError
from src.fractal_flow.domain.phase4_bridge import Phase3DecisionAdapter


def test_accounts_yaml_is_strict_and_registry_is_explicit() -> None:
    registry = AccountRegistry.from_yaml("config/accounts.yaml")
    profile = registry.get("ACT_PRIMARY")
    assert profile.account_id == "ACT_PRIMARY"
    assert profile.enabled is True


def test_accounts_yaml_rejects_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "accounts.yaml"
    path.write_text(
        "accounts:\n  ACC_A:\n    broker: B\n    currency: USD\n    enabled: true\n    default_lane: PRIMARY\n    unexpected: true\n",
        encoding="utf-8",
    )
    with pytest.raises(Phase4ValidationError):
        AccountRegistry.from_yaml(path)


def test_unknown_or_disabled_account_cannot_cross_decision_bridge() -> None:
    registry = AccountRegistry.from_yaml("config/accounts.yaml")
    adapter = Phase3DecisionAdapter(account_registry=registry)
    assert adapter.account_registry is registry
    with pytest.raises(Phase4ValidationError):
        registry.get("MISSING_ACCOUNT")


def test_source_contains_no_silent_act_primary_defaults() -> None:
    source_root = Path("src/fractal_flow")
    offenders: list[str] = []
    for path in source_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if '"ACT_PRIMARY"' in text:
            offenders.append(str(path))
    assert offenders == []
