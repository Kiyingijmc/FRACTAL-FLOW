"""Phase 1H Tests: Live Decisions vs Future Research Label Boundary."""

from src.fractal_flow.domain.market import Tick


def test_live_decision_data_structures_have_no_future_research_labels() -> None:
    tick = Tick.create("EURUSD", 1700006400, "1.0850", "1.0851")

    # Assert live tick and bar structures do not contain future research labels
    forbidden_research_labels = [
        "future_return",
        "future_mfe",
        "future_mae",
        "future_spread",
        "future_structure",
        "future_news",
        "future_volatility",
    ]

    for label in forbidden_research_labels:
        assert not hasattr(tick, label)
