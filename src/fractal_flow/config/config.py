"""Versioned Immutable Configuration Schema with Overlays."""

from dataclasses import dataclass, field, replace
from typing import Dict, Any, Optional


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


@dataclass(frozen=True)
class NewsOverlay:
    news_lockdown_active: bool = False
    risk_multiplier: float = 1.0


@dataclass(frozen=True)
class EffectiveConfiguration:
    version: int
    symbol: str
    max_spread_pips: float
    risk_per_trade_pct: float
    news_lockdown_active: bool
    risk_multiplier: float
    ttl_default_ns: int
    max_currency_exposure_lots: float


def compute_effective_config(
    base: BaseConfig,
    symbol: str,
    symbol_overlay: Optional[SymbolOverlay] = None,
    news_overlay: Optional[NewsOverlay] = None,
) -> EffectiveConfiguration:
    """Computes immutable EffectiveConfiguration without mutating BaseConfig."""
    max_spread = base.max_spread_pips
    if symbol_overlay and symbol_overlay.max_spread_pips is not None:
        max_spread = symbol_overlay.max_spread_pips

    news_active = news_overlay.news_lockdown_active if news_overlay else False
    risk_mult = news_overlay.risk_multiplier if news_overlay else 1.0

    return EffectiveConfiguration(
        version=base.version,
        symbol=symbol,
        max_spread_pips=max_spread,
        risk_per_trade_pct=base.risk_per_trade_pct * risk_mult,
        news_lockdown_active=news_active,
        risk_multiplier=risk_mult,
        ttl_default_ns=base.ttl_default_ns,
        max_currency_exposure_lots=base.max_currency_exposure_lots,
    )
