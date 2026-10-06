from decimal import Decimal

import pytest

from src.fractal_flow.domain.risk_engine import (
    AccountFeasibilityEngine,
    AccountState,
    RiskConfig,
    RiskEngine,
    RiskValidationError,
    SymbolSpec,
)


@pytest.fixture
def account() -> AccountState:
    return AccountState(
        account_id="ACC_1",
        equity=Decimal("10000"),
        balance=Decimal("10000"),
        free_margin=Decimal("9000"),
        drawdown_pct=Decimal("2"),
        open_risk=Decimal("100"),
        daily_risk=Decimal("100"),
        open_trades=1,
    )


@pytest.fixture
def spec() -> SymbolSpec:
    return SymbolSpec(
        symbol="EURUSD",
        base_currency="EUR",
        quote_currency="USD",
        contract_size=Decimal("100000"),
        min_volume=Decimal("0.01"),
        max_volume=Decimal("10"),
        volume_step=Decimal("0.01"),
        min_stop_distance=Decimal("0.0005"),
        margin_per_unit=Decimal("1000"),
        spread=Decimal("0.0001"),
        commission_per_unit=Decimal("0"),
    )


def test_feasibility_is_required_before_sizing(account: AccountState, spec: SymbolSpec) -> None:
    result = AccountFeasibilityEngine().check(account, spec, Decimal("0.001"), Decimal("0.01"))
    assert result.status == "FEASIBLE"
    assert result.volume_step == spec.volume_step


def test_infeasible_account_cannot_be_sized(account: AccountState, spec: SymbolSpec) -> None:
    bad = AccountState(**{**account.__dict__, "free_margin": Decimal("10")})
    result = AccountFeasibilityEngine().check(bad, spec, Decimal("0.001"), Decimal("0.01"))
    assert result.status == "INFEASIBLE"
    with pytest.raises(ValueError):
        RiskEngine(RiskConfig()).size(bad, spec, Decimal("0.001"), Decimal("100"), result)


def test_volume_rounds_down_never_up(account: AccountState, spec: SymbolSpec) -> None:
    feasibility = AccountFeasibilityEngine().check(account, spec, Decimal("0.001"), Decimal("0.10"))
    result = RiskEngine(RiskConfig(max_risk_per_trade=Decimal("1000"))).size(
        account, spec, Decimal("0.001"), Decimal("1000"), feasibility
    )
    assert result.approved_volume % spec.volume_step == 0
    assert result.approved_volume <= result.raw_volume


def test_risk_caps_only_reduce_allowed_risk(account: AccountState, spec: SymbolSpec) -> None:
    feasibility = AccountFeasibilityEngine().check(account, spec, Decimal("0.001"), Decimal("0.01"))
    normal = RiskEngine(RiskConfig(max_risk_per_trade=Decimal("500"))).size(
        account, spec, Decimal("0.001"), Decimal("500"), feasibility
    )
    reduced = RiskEngine(RiskConfig(max_risk_per_trade=Decimal("200"))).size(
        account, spec, Decimal("0.001"), Decimal("500"), feasibility
    )
    assert reduced.approved_risk <= normal.approved_risk
    assert normal.approved_risk <= Decimal("500")


def test_risk_has_no_direction_authority() -> None:
    assert not hasattr(RiskEngine(RiskConfig()), "direction")


def test_risk_policy_has_versioned_provenance() -> None:
    config = RiskConfig()
    assert config.version >= 1
    assert config.provenance


def test_cross_currency_sizing_requires_authoritative_tick_value() -> None:
    account = AccountState("ACC_EUR", Decimal("10000"), Decimal("10000"), Decimal("9000"), Decimal("2"), Decimal("0"), Decimal("0"), 0, currency="EUR")
    cross = SymbolSpec("USDJPY", "USD", "JPY", Decimal("100000"), Decimal("0.01"), Decimal("10"), Decimal("0.01"), Decimal("0.05"), Decimal("1000"), Decimal("0.0002"), Decimal("0"))
    feasibility = AccountFeasibilityEngine().check(account, cross, Decimal("0.10"), Decimal("0.01"))
    assert feasibility.status == "FEASIBLE"
    with pytest.raises(RiskValidationError):
        RiskEngine(RiskConfig()).size(account, cross, Decimal("0.10"), Decimal("100"), feasibility)


def test_cooldown_is_a_fail_closed_risk_throttle() -> None:
    account = AccountState("ACC", Decimal("10000"), Decimal("10000"), Decimal("9000"), Decimal("2"), Decimal("0"), Decimal("0"), 0, cooldown_until=200)
    spec = SymbolSpec("EURUSD", "EUR", "USD", Decimal("100000"), Decimal("0.01"), Decimal("10"), Decimal("0.01"), Decimal("0.0005"), Decimal("1000"), Decimal("0.0001"), Decimal("0"))
    feasible = AccountFeasibilityEngine().check(account, spec, Decimal("0.01"), Decimal("0.01"))
    allocation = RiskEngine(RiskConfig(risk_fraction=Decimal("0.10"), max_risk_per_trade=Decimal("500"))).size(
        account, spec, Decimal("0.01"), Decimal("500"), feasible, observed_timestamp=199
    )
    assert allocation.approved_risk == Decimal("0")
    assert "COOLDOWN_ACTIVE" in allocation.reasons
