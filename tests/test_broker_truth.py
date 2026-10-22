from decimal import Decimal
from src.fractal_flow.execution.broker_truth import *


def account():
    return AccountContext("A", 1, "Broker", "Server", "USD", MarginMode.NETTING, "T", "S")


def test_position_ticket_and_identifier_are_distinct_and_serializable():
    obs = BrokerObservation("O1", account(), (), (), (PositionTruth("ticket", "identifier", "EURUSD", "BUY", Decimal("1"), Decimal("1.1"), Decimal("1.0"), Decimal("1.2"), 10),), "BROKER_SNAPSHOT", ObservationAuthority.AUTHORITATIVE, 10)
    wire = obs.to_wire()
    assert wire["positions"][0]["ticket"] == "ticket"
    assert wire["positions"][0]["identifier"] == "identifier"
    assert obs.digest


def test_absence_without_observed_orders_or_deals_is_unknown():
    auth = BrokerObservation("O1", account(), (), (), (), "BROKER_QUERY", ObservationAuthority.AUTHORITATIVE, 10)
    weak = BrokerObservation("O2", account(), (), (), (), "EVENT", ObservationAuthority.NON_AUTHORITATIVE, 11)
    authoritative_absence = reconcile_command("C1", Decimal("1"), auth)
    assert authoritative_absence.status is ReconciliationStatus.UNKNOWN
    assert authoritative_absence.reason == "COMMAND_NOT_OBSERVED_NO_REJECTION_PROOF"
    assert reconcile_command("C1", Decimal("1"), weak).status is ReconciliationStatus.UNKNOWN


def test_partial_fill_is_explicit():
    order = OrderTruth("O", "EURUSD", "BUY", Decimal("1"), Decimal("1.1"), "ACCEPTED", "C1", "I1", 10)
    deal = DealTruth("D", "O", "EURUSD", "BUY", Decimal("0.4"), Decimal("1.1"), "P", "PI", "OPEN", 11)
    pos = PositionTruth("P", "PI", "EURUSD", "BUY", Decimal("0.4"), Decimal("1.1"), None, None, 11)
    obs = BrokerObservation("OBS", account(), (order,), (deal,), (pos,), "BROKER_QUERY", ObservationAuthority.AUTHORITATIVE, 12)
    result = reconcile_command("C1", Decimal("1"), obs)
    assert result.status is ReconciliationStatus.PARTIAL
    assert result.filled_volume == Decimal("0.4")
    assert result.remaining_volume == Decimal("0.6")
