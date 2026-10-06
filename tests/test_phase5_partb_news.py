from decimal import Decimal

import pytest

from src.fractal_flow.domain.news_shield import (
    NewsEvent,
    NewsImportance,
    NewsObservation,
    NewsShield,
    NewsState,
    NormalizationEvidence,
)


def event(released: int = 1_000) -> NewsEvent:
    return NewsEvent(
        event_id="CPI-US-001",
        timestamp=released,
        country="US",
        currencies=("USD",),
        category="CPI",
        importance=NewsImportance.HIGH,
        affected_symbols=("EURUSD", "USDJPY", "XAUUSD"),
        pre_window=300,
        shock_window=120,
        validation_window=600,
    )


def test_scheduled_and_observed_severity_are_separate() -> None:
    shield = NewsShield()
    shield.update_calendar(1_000)
    shield.schedule(event())
    shield.observe(
        NewsObservation(
            event_id="CPI-US-001",
            timestamp=1_010,
            shock_magnitude=Decimal("4"),
            spread_shock=Decimal("3"),
            range_shock=Decimal("3"),
            velocity_shock=Decimal("4"),
        )
    )
    evidence = shield.evaluate("EURUSD", 1_010)
    assert shield.observed_severity == "EXTREME"
    assert shield.scheduled_severity == NewsImportance.HIGH.value
    assert evidence.passed is False
    assert evidence.producer == "NewsShield"


def test_ten_minute_checkpoint_does_not_auto_restore() -> None:
    shield = NewsShield()
    shield.update_calendar(1_000)
    shield.schedule(event())
    shield.observe(
        NewsObservation("CPI-US-001", 1_010, Decimal("2"), Decimal("2"), Decimal("2"), Decimal("2"))
    )
    shield.advance(1_700)
    assert shield.state == NewsState.POST_NEWS_VALIDATION
    assert shield.evaluate("EURUSD", 1_700).passed is False


def test_normalization_allows_restricted_then_normal_reentry() -> None:
    shield = NewsShield()
    shield.update_calendar(1_000)
    shield.schedule(event())
    shield.observe(
        NewsObservation("CPI-US-001", 1_010, Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"))
    )
    shield.advance(1_700)
    shield.validate_normalization(
        1_700,
        NormalizationEvidence(True, True, True, True, True),
    )
    assert shield.state == NewsState.RESTRICTED_REENTRY
    assert shield.evaluate("EURUSD", 1_700).passed is False
    shield.advance(1_701)
    assert shield.state == NewsState.NORMAL_REENTRY
    shield.advance(1_702)
    assert shield.state == NewsState.NORMAL
    assert shield.evaluate("EURUSD", 1_702).passed is True


def test_unknown_unscheduled_shock_fails_closed() -> None:
    shield = NewsShield()
    shield.update_calendar(1_000_000)
    shield.observe(
        NewsObservation("UNKNOWN-SHOCK", 2_000, Decimal("4"), Decimal("3"), Decimal("3"), Decimal("4"))
    )
    assert shield.state == NewsState.EXTENDED_PROTECTION
    assert shield.evaluate("EURUSD", 2_000).passed is False


def test_news_cannot_create_trade_or_direction() -> None:
    shield = NewsShield()
    shield.update_calendar(1_000_000)
    with pytest.raises(AttributeError):
        getattr(shield, "create_trade")
    assert not hasattr(shield, "direction")


def test_news_restart_equivalence_is_deterministic() -> None:
    shield = NewsShield()
    shield.update_calendar(1_000)
    shield.schedule(event())
    shield.observe(NewsObservation("CPI-US-001", 1_010, Decimal("2"), Decimal("2"), Decimal("2"), Decimal("2")))
    shield.advance(1_700)
    snapshot = shield.snapshot_state()
    restored = NewsShield.from_snapshot_state(snapshot)
    assert restored.state_hash() == shield.state_hash()
    assert restored.evaluate("EURUSD", 1_700) == shield.evaluate("EURUSD", 1_700)


def test_stale_calendar_fails_closed() -> None:
    shield = NewsShield()
    shield.update_calendar(100)
    assert shield.evaluate("EURUSD", 100 + shield.config.calendar_max_age + 1).passed is False
    assert shield.state == NewsState.EXTENDED_PROTECTION


def test_news_policy_has_versioned_provenance() -> None:
    shield = NewsShield()
    assert shield.config.version >= 1
    assert shield.config.provenance


def test_normal_reentry_uses_reduced_risk_multiplier() -> None:
    shield = NewsShield()
    shield.update_calendar(1_000)
    shield.schedule(event())
    shield.observe(NewsObservation("CPI-US-001", 1_010, Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1")))
    shield.advance(1_700)
    shield.validate_normalization(1_700, NormalizationEvidence(True, True, True, True, True))
    shield.advance(1_701)
    assert shield.state == NewsState.NORMAL_REENTRY
    assert shield.risk_multiplier == shield.config.restricted_risk_multiplier


def test_news_shield_rejects_future_calendar_evidence() -> None:
    shield = NewsShield()
    shield.update_calendar(200)
    evidence = shield.evaluate("EURUSD", 100)
    assert evidence.passed is False
    assert evidence.reason == "NEWS_FUTURE_CALENDAR"


def test_news_shield_rejects_future_observation_evidence() -> None:
    shield = NewsShield()
    shield.update_calendar(100)
    shield.observe(NewsObservation("UNSCHEDULED", 200, Decimal("4"), Decimal("4"), Decimal("4"), Decimal("4")))
    evidence = shield.evaluate("EURUSD", 150)
    assert evidence.passed is False
    assert evidence.reason == "NEWS_FUTURE_OBSERVATION"


def test_scheduled_news_observation_before_release_is_rejected() -> None:
    shield = NewsShield()
    shield.update_calendar(900)
    shield.schedule(event())
    from src.fractal_flow.domain.news_shield import NewsValidationError
    with pytest.raises(NewsValidationError):
        shield.observe(NewsObservation("CPI-US-001", 999, Decimal("3"), Decimal("3"), Decimal("3"), Decimal("3")))
