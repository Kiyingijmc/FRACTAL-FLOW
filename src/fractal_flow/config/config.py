"""Versioned Immutable Configuration Schema with Canonical Deterministic Hashing."""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
import hashlib
import json


@dataclass(frozen=True)
class BaseConfig:
    version: int = 1
    max_spread_pips: float = 2.0
    risk_per_trade_pct: float = 0.01
    news_pre_watch_mins: int = 60
    news_pre_lockdown_mins: int = 15
    news_post_lockdown_mins: int = 10
    ttl_default_ns: int = 300_000_000_000  # 5 mins in ns
    max_currency_exposure_lots: float = 10.0


@dataclass(frozen=True)
class SymbolOverlay:
    symbol: str
    max_spread_pips: Optional[float] = None
    overlay_version: int = 1


@dataclass(frozen=True)
class NewsOverlay:
    news_lockdown_active: bool = False
    risk_multiplier: float = 1.0
    overlay_version: int = 1


@dataclass(frozen=True)
class EffectiveConfiguration:
    effective_config_id: str
    version: int
    symbol: str
    max_spread_pips: float
    risk_per_trade_pct: float
    news_lockdown_active: bool
    risk_multiplier: float
    ttl_default_ns: int
    max_currency_exposure_lots: float

    def produce_observation(self, session_id: str, capability: Any) -> Any:
        """Produces a sealed observation proving authoritative configuration provenance."""
        from src.fractal_flow.execution.recovery import CapabilityRole, SealedObservation, RecoveryEvidenceError, ProducerCapability
        if not isinstance(capability, ProducerCapability) or capability.role != CapabilityRole.EFFECTIVE_CONFIGURATION:
            raise RecoveryEvidenceError("EffectiveConfiguration observation requires a valid EFFECTIVE_CONFIGURATION ProducerCapability.")

        import time
        payload = {
            "effective_config_id": self.effective_config_id,
            "version": self.version,
            "symbol": self.symbol,
            "max_spread_pips": self.max_spread_pips,
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "news_lockdown_active": self.news_lockdown_active,
            "risk_multiplier": self.risk_multiplier,
            "ttl_default_ns": self.ttl_default_ns,
            "max_currency_exposure_lots": self.max_currency_exposure_lots,
        }
        return SealedObservation.create(capability, session_id, int(time.time()), payload)


def compute_effective_config(
    base: BaseConfig,
    symbol: str,
    symbol_overlay: Optional[SymbolOverlay] = None,
    news_overlay: Optional[NewsOverlay] = None,
) -> EffectiveConfiguration:
    """Computes immutable EffectiveConfiguration with canonical deterministic SHA256 hashing covering all fields."""
    max_spread = base.max_spread_pips
    if symbol_overlay and symbol_overlay.max_spread_pips is not None:
        max_spread = symbol_overlay.max_spread_pips

    news_active = news_overlay.news_lockdown_active if news_overlay else False
    risk_mult = news_overlay.risk_multiplier if news_overlay else 1.0

    eff_dict = {
        "version": base.version,
        "symbol": symbol,
        "max_spread_pips": max_spread,
        "risk_per_trade_pct": base.risk_per_trade_pct * risk_mult,
        "news_lockdown_active": news_active,
        "risk_multiplier": risk_mult,
        "ttl_default_ns": base.ttl_default_ns,
        "max_currency_exposure_lots": base.max_currency_exposure_lots,
        "symbol_overlay": asdict(symbol_overlay) if symbol_overlay else None,
        "news_overlay": asdict(news_overlay) if news_overlay else None,
    }

    # Canonical sorted JSON serialization
    canonical_json = json.dumps(eff_dict, sort_keys=True)
    config_id = f"cfg_{hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()[:12]}"

    return EffectiveConfiguration(
        effective_config_id=config_id,
        version=base.version,
        symbol=symbol,
        max_spread_pips=max_spread,
        risk_per_trade_pct=base.risk_per_trade_pct * risk_mult,
        news_lockdown_active=news_active,
        risk_multiplier=risk_mult,
        ttl_default_ns=base.ttl_default_ns,
        max_currency_exposure_lots=base.max_currency_exposure_lots,
    )
