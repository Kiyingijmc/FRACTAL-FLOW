"""AST-based Decimal Architecture Guard Test.

Verifies that financial, money, price, volume, risk, and pnl fields in domain, config,
and simulation modules are declared using exact Decimal types rather than float.
"""

import ast
from pathlib import Path

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
