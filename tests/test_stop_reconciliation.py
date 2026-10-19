from decimal import Decimal

import pytest

from src.fractal_flow.execution.broker_truth import (
    AccountContext,
    BrokerObservation,
    MarginMode,
    ObservationAuthority,
    PositionTruth,
)
from src.fractal_flow.execution.stop_reconciliation import (
    StopChangeRequest,
    StopReconciliationStatus as Status,
    reconcile_stop_change,
)


def account(account_id="A", session_id="S"):
    return AccountContext(account_id, 1, "Broker", "Server", "USD", MarginMode.NETTING, "T", session_id)


def request(**overrides):
    values = dict(
        account_id="A", account_login=1, broker="Broker", server="Server",
        terminal_instance="T", session_id="S", command_id="C1", position_ticket="P1",
        position_identifier="PI1", symbol="EURUSD", side="BUY",
        requested_stop=Decimal("1.1000"), dispatched_at_ms=100,
        decision_at_ms=90, max_observation_age_ms=50,
    )
    values.update(overrides)
    return StopChangeRequest(**values)


def observation(*, authority=ObservationAuthority.AUTHORITATIVE, observed_at_ms=120,
                account_value=None, positions=None, session_id="S", observation_id="O1"):
    if positions is None:
        positions = (PositionTruth("P1", "PI1", "EURUSD", "BUY", Decimal("1"),
                                   Decimal("1.2"), Decimal("1.1000"), None, observed_at_ms),)
    return BrokerObservation(observation_id, account_value or account(), (), (), tuple(positions),
                             "BROKER_QUERY", authority, observed_at_ms, 1, session_id)


def reconcile(req=None, obs=None, now_ms=130):
    return reconcile_stop_change(req or request(), obs or observation(), now_ms=now_ms)


def test_exact_stop_on_fresh_authoritative_matching_position_confirms():
    result = reconcile()
    assert result.status is Status.CONFIRMED
    assert result.confirmed
    assert result.observed_stop == Decimal("1.1000")


def test_non_authoritative_observation_never_confirms():
    result = reconcile(obs=observation(authority=ObservationAuthority.NON_AUTHORITATIVE))
    assert result.status is Status.UNKNOWN
    assert not result.confirmed


@pytest.mark.parametrize("observed_at,now,expected", [
    (99, 130, Status.UNKNOWN),       # before dispatch
    (131, 130, Status.UNKNOWN),      # future observation
    (70, 130, Status.UNKNOWN),       # also before dispatch
    (120, 171, Status.UNKNOWN),      # stale
])
def test_temporally_invalid_observation_is_unknown(observed_at, now, expected):
    assert reconcile(obs=observation(observed_at_ms=observed_at), now_ms=now).status is expected


def test_wrong_account_context_conflicts():
    result = reconcile(obs=observation(account_value=account("OTHER")))
    assert result.status is Status.CONFLICT
    assert result.reason == "ACCOUNT_CONTEXT_MISMATCH"


def test_missing_or_wrong_observation_session_conflicts():
    assert reconcile(obs=observation(session_id=None)).status is Status.CONFLICT
    assert reconcile(obs=observation(session_id="OTHER")).status is Status.CONFLICT


def test_side_aliases_are_normalized_but_stale_position_state_is_not_accepted():
    long_position = PositionTruth("P1", "PI1", "EURUSD", "LONG", Decimal("1"),
                                  Decimal("1.2"), Decimal("1.1000"), None, 120)
    assert reconcile(obs=observation(positions=(long_position,))).status is Status.CONFIRMED
    stale_position = PositionTruth("P1", "PI1", "EURUSD", "BUY", Decimal("1"),
                                   Decimal("1.2"), Decimal("1.1000"), None, 99)
    assert reconcile(obs=observation(positions=(stale_position,))).status is Status.UNKNOWN


def test_position_missing_is_not_confirmation():
    result = reconcile(obs=observation(positions=()))
    assert result.status is Status.POSITION_MISSING
    assert not result.confirmed


def test_ticket_or_identifier_alias_does_not_allow_mixed_identity():
    bad = PositionTruth("P1", "OTHER-ID", "EURUSD", "BUY", Decimal("1"),
                        Decimal("1.2"), Decimal("1.1000"), None, 120)
    result = reconcile(obs=observation(positions=(bad,)))
    assert result.status is Status.CONFLICT
    assert result.reason == "POSITION_IDENTITY_MISMATCH"


def test_symbol_and_side_mismatch_conflict():
    bad = PositionTruth("P1", "PI1", "GBPUSD", "BUY", Decimal("1"),
                        Decimal("1.2"), Decimal("1.1000"), None, 120)
    assert reconcile(obs=observation(positions=(bad,))).status is Status.CONFLICT


def test_missing_stop_does_not_confirm():
    bad = PositionTruth("P1", "PI1", "EURUSD", "BUY", Decimal("1"),
                        Decimal("1.2"), None, None, 120)
    assert reconcile(obs=observation(positions=(bad,))).status is Status.STOP_MISMATCH


def test_old_stop_does_not_authorize_retry():
    bad = PositionTruth("P1", "PI1", "EURUSD", "BUY", Decimal("1"),
                        Decimal("1.2"), Decimal("1.0900"), None, 120)
    result = reconcile(obs=observation(positions=(bad,)))
    assert result.status is Status.STOP_MISMATCH
    assert "NO_RETRY_AUTHORIZED" in result.reason


def test_tighter_external_stop_is_not_misreported_as_command_confirmation():
    tighter = PositionTruth("P1", "PI1", "EURUSD", "BUY", Decimal("1"),
                            Decimal("1.2"), Decimal("1.1100"), None, 120)
    assert reconcile(obs=observation(positions=(tighter,))).status is Status.STOP_MISMATCH


def test_ambiguous_duplicate_identity_conflicts():
    p = PositionTruth("P2", "PI1", "EURUSD", "BUY", Decimal("1"),
                      Decimal("1.2"), Decimal("1.1000"), None, 120)
    result = reconcile(obs=observation(positions=(observation().positions[0], p)))
    assert result.status is Status.CONFLICT


def test_session_mismatch_conflicts():
    result = reconcile(obs=observation(session_id="OTHER"))
    assert result.status is Status.CONFLICT


@pytest.mark.parametrize("kwargs", [
    {"requested_stop": Decimal("NaN")},
    {"requested_stop": Decimal("0")},
    {"dispatched_at_ms": -1},
    {"decision_at_ms": 101},
    {"max_observation_age_ms": -1},
    {"position_ticket": ""},
])
def test_invalid_request_fails_closed(kwargs):
    with pytest.raises(ValueError):
        request(**kwargs)


def test_now_timestamp_rejects_bool_and_negative():
    with pytest.raises(ValueError):
        reconcile_stop_change(request(), observation(), now_ms=True)
    with pytest.raises(ValueError):
        reconcile_stop_change(request(), observation(), now_ms=-1)
