"""Tests for Flow Evidence Provenance Binding, Context Validation, and Parameter Mismatch Rejection."""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.flow import FlowEngine, FlowEvidence
from src.fractal_flow.domain.market import Bar, Timeframe


def make_bar(
    symbol: str = "EURUSD",
    open_p: str = "1.1000",
    high_p: str = "1.1020",
    low_p: str = "1.0990",
    close_p: str = "1.1015",
    ts: int = 1700000000,
) -> Bar:
    return Bar.create(
        symbol=symbol,
        timeframe=Timeframe.M1,
        open_timestamp=ts,
        close_timestamp=ts + 60,
        open=Decimal(open_p),
        high=Decimal(high_p),
        low=Decimal(low_p),
        close=Decimal(close_p),
        spread=Decimal("0.0001"),
    )


def test_flow_evidence_provenance_valid_override_accepted():
    engine = FlowEngine(symbol="EURUSD", timeframe="1M")
    bar = make_bar(ts=1700000000)
    ev = FlowEvidence(
        long_strength=Decimal("0.70"),
        short_strength=Decimal("0.20"),
        imbalance=Decimal("0.50"),
        directional_displacement=Decimal("1.5"),
        directional_efficiency=Decimal("0.8"),
        structure_progression=Decimal("0.5"),
        persistence=Decimal("3"),
        volatility_context=Decimal("0.0010"),
        timestamp=1700000060,
        symbol="EURUSD",
        timeframe="1M",
        config_version=1,
        data_version=1,
        feature_version=1,
    )
    rec = engine.process_bar(
        bar=bar,
        v_local=Decimal("0.0010"),
        root_id="root_1",
        parent_id="p1",
        parent_version=1,
        override_evidence=ev,
    )
    assert rec.evidence == ev


def test_flow_evidence_provenance_symbol_mismatch_rejected():
    engine = FlowEngine(symbol="EURUSD")
    bar = make_bar(symbol="EURUSD", ts=1700000000)
    ev_mismatch = FlowEvidence(
        long_strength=Decimal("0.70"),
        short_strength=Decimal("0.20"),
        imbalance=Decimal("0.50"),
        directional_displacement=Decimal("1.5"),
        directional_efficiency=Decimal("0.8"),
        structure_progression=Decimal("0.5"),
        persistence=Decimal("3"),
        volatility_context=Decimal("0.0010"),
        timestamp=1700000060,
        symbol="GBPUSD",  # Mismatch!
        timeframe="1M",
    )
    with pytest.raises(ValueError, match=r"FlowEvidence provenance mismatch \(symbol\)"):
        engine.process_bar(
            bar=bar,
            v_local=Decimal("0.0010"),
            root_id="root_1",
            parent_id="p1",
            parent_version=1,
            override_evidence=ev_mismatch,
        )


def test_flow_evidence_provenance_timestamp_mismatch_rejected():
    engine = FlowEngine(symbol="EURUSD")
    bar = make_bar(ts=1700000000)  # bar.close_timestamp = 1700000060
    ev_mismatch = FlowEvidence(
        long_strength=Decimal("0.70"),
        short_strength=Decimal("0.20"),
        imbalance=Decimal("0.50"),
        directional_displacement=Decimal("1.5"),
        directional_efficiency=Decimal("0.8"),
        structure_progression=Decimal("0.5"),
        persistence=Decimal("3"),
        volatility_context=Decimal("0.0010"),
        timestamp=1700000999,  # Mismatch!
        symbol="EURUSD",
        timeframe="1M",
    )
    with pytest.raises(ValueError, match=r"FlowEvidence provenance mismatch \(timestamp\)"):
        engine.process_bar(
            bar=bar,
            v_local=Decimal("0.0010"),
            root_id="root_1",
            parent_id="p1",
            parent_version=1,
            override_evidence=ev_mismatch,
        )


def test_flow_evidence_provenance_version_mismatch_rejected():
    engine = FlowEngine(symbol="EURUSD")
    bar = make_bar(ts=1700000000)
    ev_mismatch = FlowEvidence(
        long_strength=Decimal("0.70"),
        short_strength=Decimal("0.20"),
        imbalance=Decimal("0.50"),
        directional_displacement=Decimal("1.5"),
        directional_efficiency=Decimal("0.8"),
        structure_progression=Decimal("0.5"),
        persistence=Decimal("3"),
        volatility_context=Decimal("0.0010"),
        timestamp=1700000060,
        symbol="EURUSD",
        timeframe="1M",
        config_version=2,  # Config version mismatch!
    )
    with pytest.raises(ValueError, match=r"FlowEvidence provenance mismatch \(config_version\)"):
        engine.process_bar(
            bar=bar,
            v_local=Decimal("0.0010"),
            root_id="root_1",
            parent_id="p1",
            parent_version=1,
            config_version=1,
            override_evidence=ev_mismatch,
        )
