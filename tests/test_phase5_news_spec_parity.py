from src.fractal_flow.domain.news_shield import NewsState


def test_news_state_enum_matches_canonical_spec() -> None:
    canonical = {member.value for member in NewsState}
    expected = {
        "NEWS_NORMAL", "NEWS_WATCH", "NEWS_PREP", "NEWS_LOCKDOWN",
        "INITIAL_SHOCK", "VOLATILITY_DISCOVERY", "POST_NEWS_VALIDATION",
        "RESTRICTED_REENTRY", "NORMAL_REENTRY", "EXTENDED_PROTECTION",
    }
    assert canonical == expected


def test_news_state_aliases_do_not_create_noncanonical_states() -> None:
    assert NewsState.NORMAL is NewsState.NEWS_NORMAL
    assert NewsState.PRICE_DISCOVERY is NewsState.VOLATILITY_DISCOVERY
