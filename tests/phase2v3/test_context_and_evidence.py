from decimal import Decimal
import pytest
from src.fractal_flow.domain.context import CausalWatermark, DataStatus, InstrumentSpec, MarketContextSnapshot
from src.fractal_flow.domain.evidence import EvidenceAggregator, EvidenceDirection, EvidenceItem

def test_instrument_tick_relation_is_deterministic():
    spec = InstrumentSpec("XAUUSD", Decimal("0.1"), 2, asset_class="METAL")
    assert spec.price_relation(Decimal("2350.04"), Decimal("2350.05")) == "EQ"
    assert spec.price_relation(Decimal("2350.11"), Decimal("2350.05")) == "GT"

def test_watermark_rejects_future_observation():
    wm = CausalWatermark(100)
    assert wm.admits(100)
    assert not wm.admits(101)

def test_context_requires_valid_volatility():
    spec = InstrumentSpec("EURUSD", Decimal("0.00001"), 5)
    ctx = MarketContextSnapshot("r", "EURUSD", "1M", CausalWatermark(10), spec, DataStatus.VALID, Decimal("0.001"), True, 1, 1, 1, 1)
    assert ctx.is_usable(10)
    assert not ctx.is_usable(11) if ctx.valid_until == 10 else True

def test_evidence_caps_correlated_sources():
    agg = EvidenceAggregator(family_cap=Decimal("1"), total_cap=Decimal("3"))
    a = EvidenceItem("a", "Structure", "STRUCTURAL", EvidenceDirection.LONG, Decimal("1"), 1, None, correlation_group="structure")
    b = EvidenceItem("b", "Structure2", "STRUCTURAL", EvidenceDirection.LONG, Decimal("1"), 1, None, correlation_group="structure")
    s = agg.summarize([a, b], now=1)
    assert s.long_score == Decimal("1")
    assert not s.contradiction
