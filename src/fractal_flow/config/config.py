"""Versioned Immutable Configuration Schema with Canonical Deterministic Hashing."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, overload


@overload
def _to_decimal(val: None) -> None: ...


@overload
def _to_decimal(val: Decimal | float | str) -> Decimal: ...


def _to_decimal(val: Decimal | float | str | None) -> Decimal | None:
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def _normalize_decimal_dict(d: Any) -> Any:
    """Recursively converts Decimal objects to string representation for canonical serialization."""
    if isinstance(d, Decimal):
        return str(d)
    if isinstance(d, dict):
        return {k: _normalize_decimal_dict(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_normalize_decimal_dict(v) for v in d]
    return d


@dataclass(frozen=True)
class BaseConfig:
    version: int = 1
    max_spread_pips: Decimal = field(default_factory=lambda: Decimal("2.0"))
    risk_per_trade_pct: Decimal = field(default_factory=lambda: Decimal("0.01"))
    news_pre_watch_mins: int = 60
    news_pre_lockdown_mins: int = 15
    news_post_lockdown_mins: int = 10
    ttl_default_ns: int = 300_000_000_000  # 5 mins in ns
    max_currency_exposure_lots: Decimal = field(default_factory=lambda: Decimal("10.0"))

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_spread_pips", _to_decimal(self.max_spread_pips))
        object.__setattr__(self, "risk_per_trade_pct", _to_decimal(self.risk_per_trade_pct))
        object.__setattr__(
            self,
            "max_currency_exposure_lots",
            _to_decimal(self.max_currency_exposure_lots),
        )


@dataclass(frozen=True)
class StructureConfig:
    version: int = 1
    min_reversal_magnitude: Decimal = field(default_factory=lambda: Decimal("1.5"))
    displacement_threshold_mult: Decimal = field(default_factory=lambda: Decimal("0.5"))
    persistence_bars_required: int = 2
    max_swing_history: int = 20
    min_v_local_floor: Decimal = field(default_factory=lambda: Decimal("0.0001"))
    equality_tolerance_pips: Decimal = field(default_factory=lambda: Decimal("0.00001"))
    atr_stop_buffer_mult: Decimal = field(default_factory=lambda: Decimal("0.5"))
    # Deprecated compatibility field; StructureEngine v2.2 no longer uses a trailing neighborhood.
    pivot_neighborhood_bars: int = 1
    max_candidate_lifetime_bars: int = 50

    def __post_init__(self) -> None:
        object.__setattr__(self, "min_reversal_magnitude", _to_decimal(self.min_reversal_magnitude))
        object.__setattr__(self, "displacement_threshold_mult", _to_decimal(self.displacement_threshold_mult))
        object.__setattr__(self, "min_v_local_floor", _to_decimal(self.min_v_local_floor))
        object.__setattr__(self, "equality_tolerance_pips", _to_decimal(self.equality_tolerance_pips))
        object.__setattr__(self, "atr_stop_buffer_mult", _to_decimal(self.atr_stop_buffer_mult))


@dataclass(frozen=True)
class SymbolOverlay:
    symbol: str
    max_spread_pips: Decimal | None = None
    overlay_version: int = 1

    def __post_init__(self) -> None:
        if self.max_spread_pips is not None:
            object.__setattr__(self, "max_spread_pips", _to_decimal(self.max_spread_pips))


@dataclass(frozen=True)
class NewsOverlay:
    news_lockdown_active: bool = False
    risk_multiplier: Decimal = field(default_factory=lambda: Decimal("1.0"))
    overlay_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "risk_multiplier", _to_decimal(self.risk_multiplier))


@dataclass(frozen=True)
class EffectiveConfiguration:
    effective_config_id: str
    version: int
    symbol: str
    max_spread_pips: Decimal
    risk_per_trade_pct: Decimal
    news_lockdown_active: bool
    risk_multiplier: Decimal
    ttl_default_ns: int
    max_currency_exposure_lots: Decimal
    account_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_spread_pips", _to_decimal(self.max_spread_pips))
        object.__setattr__(self, "risk_per_trade_pct", _to_decimal(self.risk_per_trade_pct))
        object.__setattr__(self, "risk_multiplier", _to_decimal(self.risk_multiplier))
        object.__setattr__(
            self,
            "max_currency_exposure_lots",
            _to_decimal(self.max_currency_exposure_lots),
        )

    def produce_observation(self, session_id: str, capability: Any) -> Any:
        """Produces a sealed observation proving authoritative configuration provenance."""
        from src.fractal_flow.execution.recovery import (
            CapabilityRole,
            ProducerCapability,
            RecoveryEvidenceError,
            SealedObservation,
        )

        if not isinstance(capability, ProducerCapability) or capability.role != CapabilityRole.EFFECTIVE_CONFIGURATION:
            raise RecoveryEvidenceError(
                "EffectiveConfiguration observation requires a valid EFFECTIVE_CONFIGURATION ProducerCapability."
            )

        import time

        payload = {
            "effective_config_id": self.effective_config_id,
            "version": self.version,
            "symbol": self.symbol,
            "max_spread_pips": str(self.max_spread_pips),
            "risk_per_trade_pct": str(self.risk_per_trade_pct),
            "news_lockdown_active": self.news_lockdown_active,
            "risk_multiplier": str(self.risk_multiplier),
            "ttl_default_ns": self.ttl_default_ns,
            "max_currency_exposure_lots": str(self.max_currency_exposure_lots),
        }
        return SealedObservation.create(capability, session_id, int(time.time()), payload)


def compute_effective_config(
    base: BaseConfig,
    symbol: str,
    symbol_overlay: SymbolOverlay | None = None,
    news_overlay: NewsOverlay | None = None,
    account_id: str | None = None,
) -> EffectiveConfiguration:
    """Computes immutable EffectiveConfiguration with canonical deterministic SHA256 hashing covering all fields."""
    base_spread = _to_decimal(base.max_spread_pips)
    base_risk = _to_decimal(base.risk_per_trade_pct)
    base_exposure = _to_decimal(base.max_currency_exposure_lots)

    max_spread = base_spread
    if symbol_overlay and symbol_overlay.max_spread_pips is not None:
        max_spread = _to_decimal(symbol_overlay.max_spread_pips)

    news_active = news_overlay.news_lockdown_active if news_overlay else False
    risk_mult = _to_decimal(news_overlay.risk_multiplier) if news_overlay else Decimal("1.0")

    effective_risk_per_trade = base_risk * risk_mult

    eff_dict = {
        "version": base.version,
        "symbol": symbol,
        "max_spread_pips": max_spread,
        "risk_per_trade_pct": effective_risk_per_trade,
        "news_lockdown_active": news_active,
        "risk_multiplier": risk_mult,
        "ttl_default_ns": base.ttl_default_ns,
        "max_currency_exposure_lots": base_exposure,
        "symbol_overlay": asdict(symbol_overlay) if symbol_overlay else None,
        "news_overlay": asdict(news_overlay) if news_overlay else None,
        "account_id": account_id,
    }

    # Canonical sorted JSON serialization with Decimal string normalization
    normalized_dict = _normalize_decimal_dict(eff_dict)
    canonical_json = json.dumps(normalized_dict, sort_keys=True)
    config_id = f"cfg_{hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()[:12]}"

    return EffectiveConfiguration(
        effective_config_id=config_id,
        version=base.version,
        symbol=symbol,
        max_spread_pips=max_spread,
        risk_per_trade_pct=effective_risk_per_trade,
        news_lockdown_active=news_active,
        risk_multiplier=risk_mult,
        ttl_default_ns=base.ttl_default_ns,
        max_currency_exposure_lots=base_exposure,
        account_id=account_id,
    )


@dataclass(frozen=True)
class Phase2EffectiveConfiguration:
    """Canonical immutable configuration for every Phase 2 engine constructor.

    The object is the single configuration authority for Phase 2. Its canonical
    payload is derived from the actual constructor parameters rather than a
    second hand-maintained identity dictionary.
    """

    version: int
    symbol: str
    timeframe: str
    instrument: dict[str, Any]
    history_capacity: int
    structure: dict[str, Any]
    flow: dict[str, Any]
    regime: dict[str, Any]
    pde: dict[str, Any]
    location: dict[str, Any]
    volatility: dict[str, Any]
    base_effective_config_id: str
    effective_config_id: str = field(init=False)

    def __post_init__(self) -> None:
        payload = self.canonical_payload()
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        object.__setattr__(self, "effective_config_id", "phase2_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16])

    @classmethod
    def from_canonical_payload(cls, payload: dict[str, Any]) -> "Phase2EffectiveConfiguration":
        """Rehydrate canonical JSON payload into typed constructor parameters."""
        data = dict(payload)
        for section in ("structure", "flow", "regime", "pde", "location", "volatility"):
            data[section] = dict(data[section])
        decimal_fields = {
            "structure": {"min_reversal_magnitude", "displacement_threshold_mult", "min_v_local_floor", "equality_tolerance_pips", "atr_stop_buffer_mult"},
            "flow": {"dominance_threshold", "emerging_threshold", "weakening_threshold", "displacement_weight", "efficiency_weight", "persistence_weight", "structure_progression_weight", "persistence_scale"},
            "regime": {"efficiency_trend", "efficiency_range", "persistence_trend", "compression_range", "chaos_dispersion", "chaos_volatility_ratio"},
            "pde": {"pullback_min", "pullback_max", "min_impulse", "recovery_threshold", "impulse_displacement_weight", "impulse_efficiency_weight", "impulse_structure_weight", "impulse_persistence_weight", "impulse_range_weight"},
            "location": {"congestion_threshold", "extreme_threshold"},
        }
        for section, fields in decimal_fields.items():
            values = dict(data[section])
            for name in fields:
                values[name] = Decimal(str(values[name]))
            data[section] = values
        data["structure"]["version"] = int(data["structure"]["version"])
        for name in ("persistence_bars_required", "max_swing_history", "pivot_neighborhood_bars", "max_candidate_lifetime_bars"):
            data["structure"][name] = int(data["structure"][name])
        for name in ("min_persistence_bars", "min_dwell_bars", "transition_confirm_bars", "max_history_capacity"):
            data["flow"][name] = int(data["flow"][name])
        for name in ("window", "dwell_bars"):
            data["regime"][name] = int(data["regime"][name])
        for name in ("max_episode_bars",):
            data["pde"][name] = int(data["pde"][name])
        for name in ("atr_period", "window_size"):
            data["volatility"][name] = int(data["volatility"][name])
        data["version"] = int(data["version"])
        data["history_capacity"] = int(data["history_capacity"])
        return cls(**data)

    def canonical_payload(self) -> dict[str, Any]:
        return _normalize_decimal_dict({
            "version": self.version,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "instrument": self.instrument,
            "history_capacity": self.history_capacity,
            "structure": self.structure,
            "flow": self.flow,
            "regime": self.regime,
            "pde": self.pde,
            "location": self.location,
            "volatility": self.volatility,
            "base_effective_config_id": self.base_effective_config_id,
        })

def build_phase2_effective_config(
    symbol: str,
    timeframe: str,
    instrument: Any,
    history_capacity: int,
    *,
    structure: StructureConfig | None = None,
    flow: dict[str, Any] | None = None,
    regime: dict[str, Any] | None = None,
    pde: dict[str, Any] | None = None,
    location: dict[str, Any] | None = None,
    volatility: dict[str, Any] | None = None,
    version: int = 1,
) -> Phase2EffectiveConfiguration:
    """Build the canonical Phase 2 configuration from actual engine parameters."""
    base = compute_effective_config(BaseConfig(), symbol)
    structure_cfg = structure or StructureConfig()
    return Phase2EffectiveConfiguration(
        version=version, symbol=symbol, timeframe=timeframe, instrument=asdict(instrument),
        history_capacity=history_capacity, structure=asdict(structure_cfg),
        flow=flow or {
            "dominance_threshold": Decimal("0.60"), "emerging_threshold": Decimal("0.30"),
            "weakening_threshold": Decimal("0.40"), "min_persistence_bars": 2, "min_dwell_bars": 2,
            "transition_confirm_bars": 1, "max_history_capacity": 100,
            "displacement_weight": Decimal("0.3"), "efficiency_weight": Decimal("0.3"),
            "persistence_weight": Decimal("0.2"), "structure_progression_weight": Decimal("0.2"),
            "persistence_scale": Decimal("5.0"),
        },
        regime=regime or {
            "window": 10, "dwell_bars": 2, "efficiency_trend": Decimal("0.55"),
            "efficiency_range": Decimal("0.20"), "persistence_trend": Decimal("0.35"),
            "compression_range": Decimal("0.60"), "chaos_dispersion": Decimal("2.5"),
            "chaos_volatility_ratio": Decimal("2.5"),
        },
        pde=pde or {
            "max_episode_bars": 30, "pullback_min": Decimal("0.10"), "pullback_max": Decimal("0.80"),
            "min_impulse": Decimal("1.0"), "recovery_threshold": Decimal("0.75"),
            "impulse_displacement_weight": Decimal("0.20"), "impulse_efficiency_weight": Decimal("0.20"),
            "impulse_structure_weight": Decimal("0.20"), "impulse_persistence_weight": Decimal("0.20"),
            "impulse_range_weight": Decimal("0.20"),
        },
        location=location or {"congestion_threshold": Decimal("0.5"), "extreme_threshold": Decimal("2.0")},
        volatility=volatility or {"atr_period": 14, "window_size": 100},
        base_effective_config_id=base.effective_config_id,
    )
