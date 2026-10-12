"""Account feasibility and risk allocation authority for Phase 5."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


class RiskValidationError(ValueError):
    pass


@dataclass(frozen=True)
class AccountState:
    account_id: str
    equity: Decimal
    balance: Decimal
    free_margin: Decimal
    drawdown_pct: Decimal
    open_risk: Decimal
    daily_risk: Decimal
    open_trades: int
    currency: str = "USD"
    cooldown_until: int | None = None

    def __post_init__(self) -> None:
        if not self.account_id.strip() or len(self.currency) != 3:
            raise RiskValidationError("canonical account identity and currency are required")
        for name in ("equity", "balance", "free_margin", "drawdown_pct", "open_risk", "daily_risk"):
            value = Decimal(str(getattr(self, name)))
            if not value.is_finite() or value < 0:
                raise RiskValidationError(f"{name} must be finite and non-negative")
            object.__setattr__(self, name, value)
        if type(self.open_trades) is not int or self.open_trades < 0:
            raise RiskValidationError("open_trades must be a non-negative integer")
        if self.cooldown_until is not None and (type(self.cooldown_until) is not int or self.cooldown_until < 0):
            raise RiskValidationError("cooldown_until must be a non-negative integer or None")


@dataclass(frozen=True)
class SymbolSpec:
    symbol: str
    base_currency: str
    quote_currency: str
    contract_size: Decimal
    min_volume: Decimal
    max_volume: Decimal
    volume_step: Decimal
    min_stop_distance: Decimal
    margin_per_unit: Decimal
    spread: Decimal
    commission_per_unit: Decimal
    tick_size: Decimal | None = None
    tick_value: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.symbol or len(self.base_currency) != 3 or len(self.quote_currency) != 3:
            raise RiskValidationError("canonical symbol/currency identity required")
        for name in ("contract_size", "min_volume", "max_volume", "volume_step", "min_stop_distance", "margin_per_unit", "spread", "commission_per_unit"):
            value = Decimal(str(getattr(self, name)))
            if not value.is_finite() or value < 0:
                raise RiskValidationError(f"{name} must be finite and non-negative")
            object.__setattr__(self, name, value)
        if self.min_volume <= 0 or self.volume_step <= 0 or self.max_volume < self.min_volume:
            raise RiskValidationError("invalid volume constraints")
        if self.contract_size <= 0 or self.min_stop_distance <= 0:
            raise RiskValidationError("contract size and minimum stop distance must be positive")
        if (self.tick_size is None) != (self.tick_value is None):
            raise RiskValidationError("tick_size and tick_value must be supplied together")
        if self.tick_size is not None:
            tick_size = Decimal(str(self.tick_size))
            tick_value = Decimal(str(self.tick_value))
            if tick_size <= 0 or tick_value <= 0:
                raise RiskValidationError("tick_size and tick_value must be positive")
            object.__setattr__(self, "tick_size", tick_size)
            object.__setattr__(self, "tick_value", tick_value)


@dataclass(frozen=True)
class FeasibilityResult:
    status: str
    account_id: str
    symbol: str
    reason: str
    volume_step: Decimal
    observed_risk_distance: Decimal


@dataclass(frozen=True)
class RiskConfig:
    version: int = 1
    provenance: str = "phase5-default-risk-policy-v1"
    risk_fraction: Decimal = Decimal("0.01")
    max_risk_per_trade: Decimal = Decimal("100")
    max_total_open_risk: Decimal = Decimal("500")
    max_daily_risk: Decimal = Decimal("1000")
    max_trades: int = 10
    max_drawdown_pct: Decimal = Decimal("20")
    max_spread: Decimal = Decimal("0.00030")
    drawdown_reduction_start_pct: Decimal = Decimal("10")
    drawdown_reduction_multiplier: Decimal = Decimal("0.50")

    def __post_init__(self) -> None:
        for name in ("risk_fraction", "max_risk_per_trade", "max_total_open_risk", "max_daily_risk", "max_drawdown_pct", "max_spread", "drawdown_reduction_start_pct", "drawdown_reduction_multiplier"):
            value = Decimal(str(getattr(self, name)))
            if not value.is_finite() or value < 0:
                raise RiskValidationError(f"{name} must be finite and non-negative")
            object.__setattr__(self, name, value)
        if self.version < 1 or not self.provenance.strip():
            raise RiskValidationError("versioned risk policy provenance is required")
        if self.risk_fraction > 1 or self.drawdown_reduction_multiplier > 1:
            raise RiskValidationError("risk fractions/multipliers must be within [0,1]")
        if self.max_trades < 1:
            raise RiskValidationError("max_trades must be positive")


@dataclass(frozen=True)
class RiskAllocation:
    account_id: str
    symbol: str
    requested_risk: Decimal
    approved_risk: Decimal
    raw_volume: Decimal
    approved_volume: Decimal
    risk_state: str
    reasons: tuple[str, ...]


class AccountFeasibilityEngine:
    """Fresh account/instrument feasibility authority. It does not size trades."""

    def check(self, account: AccountState, spec: SymbolSpec, stop_distance: Decimal, requested_volume: Decimal, max_trades: int = 10, max_spread: Decimal = Decimal("0.00030")) -> FeasibilityResult:
        stop = Decimal(str(stop_distance))
        volume = Decimal(str(requested_volume))
        if stop <= 0 or volume <= 0:
            return FeasibilityResult("INFEASIBLE", account.account_id, spec.symbol, "INVALID_REQUEST", spec.volume_step, stop)
        if stop < spec.min_stop_distance:
            return FeasibilityResult("INFEASIBLE", account.account_id, spec.symbol, "STOP_TOO_CLOSE", spec.volume_step, stop)
        if spec.spread > Decimal(str(max_spread)):
            return FeasibilityResult("INFEASIBLE", account.account_id, spec.symbol, "SPREAD_TOO_WIDE", spec.volume_step, stop)
        if volume < spec.min_volume or volume > spec.max_volume:
            return FeasibilityResult("INFEASIBLE", account.account_id, spec.symbol, "VOLUME_OUT_OF_RANGE", spec.volume_step, stop)
        if account.free_margin <= spec.margin_per_unit * volume:
            return FeasibilityResult("INFEASIBLE", account.account_id, spec.symbol, "INSUFFICIENT_MARGIN", spec.volume_step, stop)
        if max_trades < 1:
            raise RiskValidationError("max_trades must be positive")
        if account.open_trades >= max_trades:
            return FeasibilityResult("RESTRICTED", account.account_id, spec.symbol, "TRADE_COUNT_CAP", spec.volume_step, stop)
        return FeasibilityResult("FEASIBLE", account.account_id, spec.symbol, "FEASIBLE", spec.volume_step, stop)


class RiskEngine:
    """Allocation authority. Direction is deliberately absent from its state/model."""

    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    @staticmethod
    def _floor_step(value: Decimal, step: Decimal) -> Decimal:
        return (value / step).to_integral_value(rounding=ROUND_DOWN) * step

    def size(
        self,
        account: AccountState,
        spec: SymbolSpec,
        stop_distance: Decimal,
        requested_risk: Decimal,
        feasibility: FeasibilityResult,
        news_multiplier: Decimal = Decimal("1"),
        portfolio_multiplier: Decimal = Decimal("1"),
        observed_timestamp: int | None = None,
    ) -> RiskAllocation:
        if feasibility.account_id != account.account_id or feasibility.symbol != spec.symbol:
            raise RiskValidationError("feasibility result identity mismatch")
        if feasibility.status != "FEASIBLE":
            raise ValueError("fresh feasible account result is required before sizing")
        stop = Decimal(str(stop_distance))
        requested = Decimal(str(requested_risk))
        news = Decimal(str(news_multiplier))
        portfolio = Decimal(str(portfolio_multiplier))
        if min(stop, requested, news, portfolio) < 0 or news > 1 or portfolio > 1:
            raise RiskValidationError("risk inputs invalid")
        reasons: list[str] = []
        allowed = min(requested, account.equity * self.config.risk_fraction, self.config.max_risk_per_trade)
        allowed = min(allowed, self.config.max_total_open_risk - account.open_risk)
        allowed = min(allowed, self.config.max_daily_risk - account.daily_risk)
        if account.cooldown_until is not None and observed_timestamp is not None and observed_timestamp < account.cooldown_until:
            allowed = Decimal("0")
            reasons.append("COOLDOWN_ACTIVE")
        elif account.drawdown_pct >= self.config.max_drawdown_pct:
            allowed = Decimal("0")
            reasons.append("DRAWDOWN_HALT")
        elif account.drawdown_pct > self.config.drawdown_reduction_start_pct:
            allowed *= self.config.drawdown_reduction_multiplier
            reasons.append("DRAWDOWN_REDUCED")
        allowed *= news
        allowed *= portfolio
        if news < 1:
            reasons.append("NEWS_THROTTLE")
        if portfolio < 1:
            reasons.append("PORTFOLIO_THROTTLE")
        allowed = max(Decimal("0"), allowed)
        if spec.tick_size is not None and spec.tick_value is not None:
            value_per_price_unit = spec.tick_value / spec.tick_size
        elif spec.quote_currency == account.currency:
            value_per_price_unit = spec.contract_size
        else:
            raise RiskValidationError("cross-currency sizing requires authoritative tick-value conversion")
        raw_volume = allowed / (stop * value_per_price_unit)
        approved_volume = min(spec.max_volume, self._floor_step(raw_volume, spec.volume_step))
        approved_risk = approved_volume * stop * value_per_price_unit
        if approved_volume < spec.min_volume:
            approved_volume = Decimal("0")
            approved_risk = Decimal("0")
            reasons.append("MIN_VOLUME_UNREACHABLE")
        state = "RISK_HALTED" if approved_risk == 0 else ("RISK_REDUCED" if reasons else "RISK_NORMAL")
        return RiskAllocation(account.account_id, spec.symbol, requested, approved_risk, raw_volume, approved_volume, state, tuple(reasons))
