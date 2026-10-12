"""Deterministic protective News Shield authority for Phase 5.

The shield may veto or restrict exposure, but it cannot create direction,
opportunities, execution intents, or orders.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Mapping

from .phase4 import GateEvidence, Phase4GateType


class NewsValidationError(ValueError):
    pass


class NewsImportance(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class NewsState(str, Enum):
    NEWS_NORMAL = "NEWS_NORMAL"
    NORMAL = "NEWS_NORMAL"  # backwards-compatible alias; canonical value is NEWS_NORMAL
    NEWS_WATCH = "NEWS_WATCH"
    NEWS_PREP = "NEWS_PREP"
    NEWS_LOCKDOWN = "NEWS_LOCKDOWN"
    INITIAL_SHOCK = "INITIAL_SHOCK"
    VOLATILITY_DISCOVERY = "VOLATILITY_DISCOVERY"
    PRICE_DISCOVERY = "VOLATILITY_DISCOVERY"  # backwards-compatible alias
    POST_NEWS_VALIDATION = "POST_NEWS_VALIDATION"
    RESTRICTED_REENTRY = "RESTRICTED_REENTRY"
    NORMAL_REENTRY = "NORMAL_REENTRY"
    EXTENDED_PROTECTION = "EXTENDED_PROTECTION"


@dataclass(frozen=True)
class NewsEvent:
    event_id: str
    timestamp: int
    country: str
    currencies: tuple[str, ...]
    category: str
    importance: NewsImportance
    affected_symbols: tuple[str, ...]
    pre_window: int
    shock_window: int
    validation_window: int
    forecast: Decimal | None = None
    previous: Decimal | None = None
    actual: Decimal | None = None
    scheduled: bool = True
    released: bool = False
    revised: bool = False
    status: str = "SCHEDULED"

    def __post_init__(self) -> None:
        if not self.event_id or not self.country or not self.category:
            raise NewsValidationError("news identity fields are required")
        if type(self.timestamp) is not int or self.timestamp < 0:
            raise NewsValidationError("news timestamp must be a non-negative integer")
        if not self.currencies or not self.affected_symbols:
            raise NewsValidationError("news exposure mapping cannot be empty")
        if min(self.pre_window, self.shock_window, self.validation_window) <= 0:
            raise NewsValidationError("news windows must be positive")
        for name in ("forecast", "previous", "actual"):
            value = getattr(self, name)
            if value is not None:
                value = Decimal(str(value))
                if not value.is_finite():
                    raise NewsValidationError(f"{name} must be finite")
                object.__setattr__(self, name, value)
        for name in ("scheduled", "released", "revised"):
            if type(getattr(self, name)) is not bool:
                raise NewsValidationError(f"{name} must be boolean")
        if not self.status.strip():
            raise NewsValidationError("news status is required")


@dataclass(frozen=True)
class NewsObservation:
    event_id: str
    timestamp: int
    shock_magnitude: Decimal
    spread_shock: Decimal
    range_shock: Decimal
    velocity_shock: Decimal

    def __post_init__(self) -> None:
        for name in ("shock_magnitude", "spread_shock", "range_shock", "velocity_shock"):
            value = Decimal(str(getattr(self, name)))
            if not value.is_finite() or value < 0:
                raise NewsValidationError(f"{name} must be finite and non-negative")
            object.__setattr__(self, name, value)
        if type(self.timestamp) is not int or self.timestamp < 0:
            raise NewsValidationError("observation timestamp must be non-negative integer")


@dataclass(frozen=True)
class NormalizationEvidence:
    spread_normalized: bool
    volatility_normalized: bool
    quote_stability_recovered: bool
    price_discovery_completed: bool
    execution_quality_recovered: bool

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if type(getattr(self, name)) is not bool:
                raise NewsValidationError(f"{name} must be boolean")

    @property
    def complete(self) -> bool:
        return all(getattr(self, name) for name in self.__dataclass_fields__)


@dataclass(frozen=True)
class NewsShieldConfig:
    version: int = 1
    provenance: str = "phase5-default-news-policy-v1"
    extreme_threshold: Decimal = Decimal("3")
    shock_threshold: Decimal = Decimal("2")
    elevated_threshold: Decimal = Decimal("1.25")
    calendar_max_age: int = 900
    normal_risk_multiplier: Decimal = Decimal("1")
    restricted_risk_multiplier: Decimal = Decimal("0.50")

    def __post_init__(self) -> None:
        if self.version < 1 or not self.provenance.strip():
            raise NewsValidationError("versioned news policy provenance is required")
        for name in ("extreme_threshold", "shock_threshold", "elevated_threshold", "normal_risk_multiplier", "restricted_risk_multiplier"):
            value = Decimal(str(getattr(self, name)))
            if not value.is_finite() or value <= 0:
                raise NewsValidationError(f"{name} must be positive")
            object.__setattr__(self, name, value)
        if self.calendar_max_age <= 0:
            raise NewsValidationError("calendar_max_age must be positive")
        if not self.extreme_threshold > self.shock_threshold > self.elevated_threshold:
            raise NewsValidationError("news severity thresholds must be strictly ordered")
        if self.normal_risk_multiplier > 1 or self.restricted_risk_multiplier > 1:
            raise NewsValidationError("news risk multipliers must be within (0,1]")


class NewsShield:
    """Protective news authority with explicit state and no trade authority."""

    def __init__(self, config: NewsShieldConfig | None = None) -> None:
        self.config = config or NewsShieldConfig()
        self.state = NewsState.NEWS_NORMAL
        self.scheduled_severity = "NORMAL"
        self.observed_severity = "CALM"
        self._events: dict[str, NewsEvent] = {}
        self._observations: dict[str, NewsObservation] = {}
        self._normalization: dict[str, NormalizationEvidence] = {}
        self._active_event_id: str | None = None
        self._calendar_last_update: int | None = None
        self._latest_observation_timestamp: int | None = None
        self._restricted_until: int | None = None
        self._normal_reentry_until: int | None = None

    def _severity(self, value: Decimal) -> str:
        thresholds = (
            (self.config.extreme_threshold, "EXTREME"),
            (self.config.shock_threshold, "SHOCK"),
            (self.config.elevated_threshold, "ELEVATED"),
        )
        for threshold, name in thresholds:
            if value >= threshold:
                return name
        return "CALM"

    def update_calendar(self, timestamp: int) -> None:
        if type(timestamp) is not int or timestamp < 0:
            raise NewsValidationError("calendar update timestamp must be non-negative integer")
        self._calendar_last_update = timestamp

    def schedule(self, news: NewsEvent) -> None:
        if news.event_id in self._events:
            raise NewsValidationError("duplicate news event")
        self._events[news.event_id] = news

    def observe(self, observation: NewsObservation) -> None:
        event = self._events.get(observation.event_id)
        if event is not None:
            if observation.timestamp < event.timestamp:
                raise NewsValidationError("observation cannot precede the scheduled release timestamp")
            if event.scheduled and not event.released and observation.timestamp >= event.timestamp:
                # The observation itself is authoritative release evidence;
                # transition the event into its released lifecycle explicitly.
                event = NewsEvent(
                    event.event_id, event.timestamp, event.country, event.currencies,
                    event.category, event.importance, event.affected_symbols,
                    event.pre_window, event.shock_window, event.validation_window,
                    event.forecast, event.previous, event.actual, event.scheduled,
                    True, event.revised, "RELEASED",
                )
                self._events[event.event_id] = event
        self._observations[observation.event_id] = observation
        self._latest_observation_timestamp = max(self._latest_observation_timestamp or observation.timestamp, observation.timestamp)
        self.observed_severity = max(
            (self._severity(v) for v in (
                observation.shock_magnitude,
                observation.spread_shock,
                observation.range_shock,
                observation.velocity_shock,
            )),
            key={"CALM": 0, "ELEVATED": 1, "SHOCK": 2, "EXTREME": 3}.get,
        )
        if observation.event_id not in self._events and self.observed_severity in {"SHOCK", "EXTREME"}:
            self._active_event_id = observation.event_id
            self.state = NewsState.EXTENDED_PROTECTION
            return
        event = self._events.get(observation.event_id)
        if event is None:
            return
        self._active_event_id = event.event_id
        self.scheduled_severity = event.importance.value
        if self.observed_severity == "EXTREME":
            self.state = NewsState.EXTENDED_PROTECTION
        else:
            self.state = NewsState.INITIAL_SHOCK

    def _event_for_symbol(self, symbol: str, timestamp: int) -> NewsEvent | None:
        candidates = [
            event for event in self._events.values()
            if symbol in event.affected_symbols
            and event.timestamp - event.pre_window <= timestamp <= event.timestamp + event.validation_window
        ]
        return min(candidates, key=lambda e: (e.timestamp, e.event_id), default=None)

    def advance(self, timestamp: int) -> NewsState:
        if type(timestamp) is not int or timestamp < 0:
            raise NewsValidationError("timestamp must be a non-negative integer")
        if self.state == NewsState.RESTRICTED_REENTRY:
            if self._restricted_until is not None and timestamp >= self._restricted_until:
                self.state = NewsState.NORMAL_REENTRY
            return self.state
        if self.state == NewsState.NORMAL_REENTRY:
            if self._normal_reentry_until is not None and timestamp >= self._normal_reentry_until:
                self.state = NewsState.NEWS_NORMAL
            return self.state
        event = self._events.get(self._active_event_id) if self._active_event_id else None
        if event is None:
            return self.state
        if timestamp < event.timestamp - event.pre_window:
            self.state = NewsState.NEWS_NORMAL
        elif timestamp < event.timestamp - event.shock_window:
            self.state = NewsState.NEWS_WATCH
        elif timestamp < event.timestamp:
            self.state = NewsState.NEWS_PREP
        elif timestamp == event.timestamp:
            self.state = NewsState.NEWS_LOCKDOWN
        elif timestamp < event.timestamp + event.shock_window:
            self.state = NewsState.INITIAL_SHOCK
        elif timestamp < event.timestamp + event.validation_window:
            self.state = NewsState.VOLATILITY_DISCOVERY
        else:
            self.state = NewsState.POST_NEWS_VALIDATION
        return self.state

    def validate_normalization(self, timestamp: int, evidence: NormalizationEvidence) -> None:
        if self._active_event_id is None:
            raise NewsValidationError("no active news event")
        event = self._events.get(self._active_event_id)
        if event is None:
            raise NewsValidationError("normalization requires a scheduled event")
        if timestamp < event.timestamp + event.validation_window:
            raise NewsValidationError("normalization checkpoint reached before validation window")
        self._normalization[event.event_id] = evidence
        if evidence.complete:
            self.state = NewsState.RESTRICTED_REENTRY
            self._restricted_until = timestamp + 1
            self._normal_reentry_until = timestamp + 2
        else:
            self.state = NewsState.EXTENDED_PROTECTION

    def evaluate(self, symbol: str, timestamp: int) -> GateEvidence:
        if self._calendar_last_update is None:
            self.state = NewsState.EXTENDED_PROTECTION
            return GateEvidence(Phase4GateType.TRADEABILITY, False, "NEWS_CALENDAR_STALE", timestamp, producer="NewsShield", evidence_version=1)
        if self._calendar_last_update > timestamp:
            self.state = NewsState.EXTENDED_PROTECTION
            return GateEvidence(Phase4GateType.TRADEABILITY, False, "NEWS_FUTURE_CALENDAR", timestamp, producer="NewsShield", evidence_version=1)
        if self._latest_observation_timestamp is not None and self._latest_observation_timestamp > timestamp:
            self.state = NewsState.EXTENDED_PROTECTION
            return GateEvidence(Phase4GateType.TRADEABILITY, False, "NEWS_FUTURE_OBSERVATION", timestamp, producer="NewsShield", evidence_version=1)
        if timestamp - self._calendar_last_update > self.config.calendar_max_age:
            self.state = NewsState.EXTENDED_PROTECTION
            return GateEvidence(Phase4GateType.TRADEABILITY, False, "NEWS_CALENDAR_STALE", timestamp, producer="NewsShield", evidence_version=1)
        event = self._event_for_symbol(symbol, timestamp)
        if event is not None and self._active_event_id != event.event_id:
            self._active_event_id = event.event_id
            self.scheduled_severity = event.importance.value
        if event is not None:
            self.advance(timestamp)
        passed = self.state in {NewsState.NEWS_NORMAL, NewsState.NORMAL_REENTRY}
        if self.state == NewsState.RESTRICTED_REENTRY:
            passed = False
        reason = f"NEWS_{self.state.value}"
        return GateEvidence(Phase4GateType.TRADEABILITY, passed, reason, timestamp, producer="NewsShield", evidence_version=1)

    @property
    def risk_multiplier(self) -> Decimal:
        if self.state in {NewsState.RESTRICTED_REENTRY, NewsState.NORMAL_REENTRY}:
            return self.config.restricted_risk_multiplier
        return self.config.normal_risk_multiplier

    def normalization_snapshot(self) -> Mapping[str, NormalizationEvidence]:
        return dict(self._normalization)

    def snapshot_state(self) -> dict[str, object]:
        return {
            "config": {
                "version": self.config.version, "provenance": self.config.provenance,
                "extreme_threshold": str(self.config.extreme_threshold),
                "shock_threshold": str(self.config.shock_threshold),
                "elevated_threshold": str(self.config.elevated_threshold),
                "calendar_max_age": self.config.calendar_max_age,
                "normal_risk_multiplier": str(self.config.normal_risk_multiplier),
                "restricted_risk_multiplier": str(self.config.restricted_risk_multiplier),
            },
            "state": self.state.value,
            "scheduled_severity": self.scheduled_severity,
            "observed_severity": self.observed_severity,
            "events": {key: {
                "event_id": value.event_id, "timestamp": value.timestamp, "country": value.country,
                "currencies": list(value.currencies), "category": value.category,
                "importance": value.importance.value, "affected_symbols": list(value.affected_symbols),
                "pre_window": value.pre_window, "shock_window": value.shock_window,
                "validation_window": value.validation_window,
                "forecast": str(value.forecast) if value.forecast is not None else None,
                "previous": str(value.previous) if value.previous is not None else None,
                "actual": str(value.actual) if value.actual is not None else None,
                "scheduled": value.scheduled, "released": value.released, "revised": value.revised,
                "status": value.status,
            } for key, value in sorted(self._events.items())},
            "observations": {key: {
                "event_id": value.event_id, "timestamp": value.timestamp,
                "shock_magnitude": str(value.shock_magnitude), "spread_shock": str(value.spread_shock),
                "range_shock": str(value.range_shock), "velocity_shock": str(value.velocity_shock),
            } for key, value in sorted(self._observations.items())},
            "normalization": {key: {name: getattr(value, name) for name in value.__dataclass_fields__} for key, value in sorted(self._normalization.items())},
            "active_event_id": self._active_event_id,
            "restricted_until": self._restricted_until,
            "normal_reentry_until": self._normal_reentry_until,
            "calendar_last_update": self._calendar_last_update,
            "latest_observation_timestamp": self._latest_observation_timestamp,
        }

    @classmethod
    def from_snapshot_state(cls, snapshot: Mapping[str, object]) -> "NewsShield":
        raw_config = snapshot.get("config", {})
        if not isinstance(raw_config, dict):
            raise NewsValidationError("invalid news policy snapshot")
        shield = cls(NewsShieldConfig(
            version=int(raw_config["version"]), provenance=str(raw_config["provenance"]),
            extreme_threshold=Decimal(str(raw_config["extreme_threshold"])),
            shock_threshold=Decimal(str(raw_config["shock_threshold"])),
            elevated_threshold=Decimal(str(raw_config["elevated_threshold"])),
            calendar_max_age=int(raw_config["calendar_max_age"]),
            normal_risk_multiplier=Decimal(str(raw_config["normal_risk_multiplier"])),
            restricted_risk_multiplier=Decimal(str(raw_config["restricted_risk_multiplier"])),
        ))
        shield.state = NewsState(str(snapshot["state"]))
        shield.scheduled_severity = str(snapshot["scheduled_severity"])
        shield.observed_severity = str(snapshot["observed_severity"])
        events = snapshot.get("events", {})
        if not isinstance(events, dict):
            raise NewsValidationError("invalid news event snapshot")
        for payload in events.values():
            if not isinstance(payload, dict):
                raise NewsValidationError("invalid news event payload")
            shield.schedule(NewsEvent(
                str(payload["event_id"]), int(payload["timestamp"]), str(payload["country"]),
                tuple(str(x) for x in payload["currencies"]), str(payload["category"]),
                NewsImportance(str(payload["importance"])), tuple(str(x) for x in payload["affected_symbols"]),
                int(payload["pre_window"]), int(payload["shock_window"]), int(payload["validation_window"]),
                Decimal(str(payload["forecast"])) if payload.get("forecast") is not None else None,
                Decimal(str(payload["previous"])) if payload.get("previous") is not None else None,
                Decimal(str(payload["actual"])) if payload.get("actual") is not None else None,
                bool(payload["scheduled"]), bool(payload["released"]), bool(payload["revised"]), str(payload["status"]),
            ))
        observations = snapshot.get("observations", {})
        if not isinstance(observations, dict):
            raise NewsValidationError("invalid news observation snapshot")
        for payload in observations.values():
            if not isinstance(payload, dict):
                raise NewsValidationError("invalid news observation payload")
            shield._observations[str(payload["event_id"])] = NewsObservation(
                str(payload["event_id"]), int(payload["timestamp"]), Decimal(str(payload["shock_magnitude"])),
                Decimal(str(payload["spread_shock"])), Decimal(str(payload["range_shock"])), Decimal(str(payload["velocity_shock"])),
            )
        normalization = snapshot.get("normalization", {})
        if not isinstance(normalization, dict):
            raise NewsValidationError("invalid normalization snapshot")
        for key, payload in normalization.items():
            if not isinstance(payload, dict):
                raise NewsValidationError("invalid normalization payload")
            values = {name: payload[name] for name in NormalizationEvidence.__dataclass_fields__}
            if any(type(value) is not bool for value in values.values()):
                raise NewsValidationError("normalization evidence must contain strict booleans")
            shield._normalization[str(key)] = NormalizationEvidence(**values)
        shield._active_event_id = snapshot.get("active_event_id") if isinstance(snapshot.get("active_event_id"), str) else None
        shield._calendar_last_update = int(snapshot["calendar_last_update"]) if snapshot.get("calendar_last_update") is not None else None
        if snapshot.get("latest_observation_timestamp") is not None:
            shield._latest_observation_timestamp = int(snapshot["latest_observation_timestamp"])
        else:
            shield._latest_observation_timestamp = max((item.timestamp for item in shield._observations.values()), default=None)
        shield._restricted_until = int(snapshot["restricted_until"]) if snapshot.get("restricted_until") is not None else None
        shield._normal_reentry_until = int(snapshot["normal_reentry_until"]) if snapshot.get("normal_reentry_until") is not None else None
        return shield

    def state_hash(self) -> str:
        canonical = json.dumps(self.snapshot_state(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
