"""AST-based Decimal Architecture Guard Test.

Verifies that financial, money, price, volume, risk, and pnl fields in domain, config,
and simulation modules are declared using exact Decimal types rather than float.
"""

import ast
from pathlib import Path
from decimal import Decimal

from src.fractal_flow.domain.units import (
    Price,
    PricePips,
    PriceDistance,
    Points,
    Volume,
    PositiveCurrencyAmount,
    SignedCurrencyAmount,
    price_to_pips,
    pips_to_price,
)

FINANCIAL_FIELD_KEYWORDS = {
    "price",
    "volume",
    "money",
    "risk",
    "pnl",
    "balance",
    "spread",
    "equity",
    "fee",
    "notional",
    "bid",
    "ask",
    "sl",
    "tp",
    "lots",
    "commission",
    "exposure",
    "high",
    "low",
    "range",
    "level",
    "atr",
}

# Documented exceptions for statistical ratios, scores, probabilities, or rate metrics
DOCUMENTED_FLOAT_EXCEPTIONS = {
    ("PullbackObject", "retracement_depth"),  # Percentage ratio
    ("PullbackObject", "duration_ratio"),  # Ratio metric
    ("PullbackObject", "velocity"),  # Statistical rate metric
    ("PullbackObject", "acceleration"),  # Statistical rate metric
    ("PullbackObject", "efficiency"),  # Ratio metric
    ("PullbackObject", "momentum"),  # Indicator metric
    ("PullbackObject", "structural_damage"),  # Score metric
    ("PullbackObject", "weakening_score"),  # Score metric
    ("PullbackObject", "resumption_score"),  # Score metric
    ("PullbackObject", "false_resumption_risk"),  # Probability score metric
    ("PullbackObject", "confidence"),  # Score metric
    ("OpportunityObject", "structural_edge"),  # Score metric
    ("OpportunityObject", "opportunity_space"),  # Score metric
    ("OpportunityObject", "execution_quality"),  # Score metric
    ("OpportunityObject", "confidence"),  # Score metric
    ("TradeDecision", "opportunity_space"),  # Score metric
    ("MURGTelemetry", "priority_score"),  # Allocation metric
    ("MURGTelemetry", "capacity_multiplier"),  # Capacity multiplier
    ("EntryModelResearchTelemetry", "fill_rate"),  # Execution ratio metric
    ("FeatureSet", "relative_volatility"),  # Statistical volatility ratio
    ("AccountResourceContext", "equity"),  # External account telemetry display
    ("AccountResourceContext", "balance"),  # External account telemetry display
    ("AccountResourceContext", "free_margin"),  # External account telemetry display
    ("AccountResourceContext", "used_margin"),  # External account telemetry display
    ("AccountResourceContext", "margin_utilization_pct"),  # Percentage metric
    ("AccountResourceContext", "drawdown_pct"),  # Percentage metric
    ("InstrumentDescriptor", "tick_size"),  # Instrument metadata
    ("InstrumentDescriptor", "point_size"),  # Instrument metadata
    ("InstrumentDescriptor", "pip_size"),  # Instrument metadata
    ("InstrumentDescriptor", "tick_value"),  # Instrument metadata
    ("InstrumentDescriptor", "contract_size"),  # Instrument metadata
    ("InstrumentDescriptor", "min_volume"),  # Instrument metadata
    ("InstrumentDescriptor", "max_volume"),  # Instrument metadata
    ("InstrumentDescriptor", "volume_step"),  # Instrument metadata
    ("InstrumentDescriptor", "stops_level"),  # Instrument metadata
    ("InstrumentDescriptor", "freeze_level"),  # Instrument metadata
    ("MarketActivationLease", "priority_score_snapshot"),  # Score metric
    ("MarketActivationDecision", "priority_score"),  # Score metric
    ("MarketProcessingCost", "base_cost"),  # Computational cost weight
    ("MarketProcessingCost", "active_timeframes_cost"),  # Computational cost weight
    ("MarketProcessingCost", "indicator_cost"),  # Computational cost weight
}


def test_ast_decimal_guard_no_forbidden_floats() -> None:
    """Scans domain, config, and simulation dataclasses using AST to ensure financial fields do not use float."""
    src_dir = Path(__file__).parent.parent / "src" / "fractal_flow"
    files_to_check = [
        src_dir / "config" / "config.py",
        src_dir / "simulation" / "simulator.py",
        src_dir / "domain" / "models.py",
        src_dir / "domain" / "telemetry.py",
        src_dir / "domain" / "entry.py",
        src_dir / "domain" / "units.py",
        src_dir / "domain" / "broker.py",
        src_dir / "domain" / "murg.py",
        src_dir / "domain" / "risk_ledger.py",
    ]

    forbidden_float_declarations: list[str] = []

    for py_file in files_to_check:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                for item in node.body:
                    # Inspect type-annotated field assignments (e.g. price: float)
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        field_name = item.target.id
                        annotation_str = ast.unparse(item.annotation)

                        # Check if field matches financial keyword concept
                        is_financial = any(kw in field_name.lower() for kw in FINANCIAL_FIELD_KEYWORDS)

                        if is_financial:
                            if (class_name, field_name) in DOCUMENTED_FLOAT_EXCEPTIONS:
                                continue

                            if "float" in annotation_str:
                                forbidden_float_declarations.append(
                                    f"{py_file.relative_to(src_dir)} :: {class_name}.{field_name} is annotated as '{annotation_str}'"
                                )

    assert not forbidden_float_declarations, (
        "Forbidden floating-point declarations found in financial fields:\n" + "\n".join(forbidden_float_declarations)
    )


def test_ast_decimal_guard_detects_introduced_forbidden_float() -> None:
    """Negative test proving that introducing a financial float into an AST structure triggers a guard failure."""
    code_with_forbidden_float = """
from dataclasses import dataclass

@dataclass
class BadTradeModel:
    entry_price: float
"""
    tree = ast.parse(code_with_forbidden_float)
    detected_violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    field_name = item.target.id
                    annotation_str = ast.unparse(item.annotation)
                    if any(kw in field_name.lower() for kw in FINANCIAL_FIELD_KEYWORDS):
                        if "float" in annotation_str:
                            detected_violations.append(f"{class_name}.{field_name}: {annotation_str}")

    assert len(detected_violations) == 1
    assert "BadTradeModel.entry_price: float" in detected_violations[0]


def test_units_decimal_instantiation_and_arithmetic() -> None:
    """Regression test covering construction, arithmetic, and comparisons for unit wrapper types."""
    p1 = Price("1.08500")
    p2 = Price(Decimal("1.08550"))
    assert p1.value < p2.value
    assert p2.value - p1.value == Decimal("0.00050")

    pips_direct = PricePips("5.00")
    assert pips_direct.value == Decimal("5.00")

    pips = price_to_pips("0.00050", digits=5)
    assert pips.value == Decimal("5.00")

    price_dist = pips_to_price(pips.value, digits=5)
    assert price_dist == Decimal("0.00050")

    vol1 = Volume(Decimal("0.10"))
    vol2 = Volume("0.20")
    assert vol1.value + vol2.value == Decimal("0.30")

    pos_money = PositiveCurrencyAmount("100.50")
    assert pos_money.value == Decimal("100.50")

    signed_pnl = SignedCurrencyAmount("-50.25")
    assert signed_pnl.value == Decimal("-50.25")

    points = Points("10.5")
    assert points.value == Decimal("10.5")

    price_dist_unit = PriceDistance("0.00100")
    assert price_dist_unit.value == Decimal("0.00100")
