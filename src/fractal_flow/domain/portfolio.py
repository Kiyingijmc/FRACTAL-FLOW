"""Deterministic portfolio arbitration authority for Phase 5."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping


class PortfolioValidationError(ValueError):
    pass


@dataclass(frozen=True)
class PortfolioCandidate:
    opportunity_id: str
    symbol: str
    direction: str
    base_currency: str
    quote_currency: str
    volume: Decimal
    risk: Decimal
    score: Decimal
    notional: Decimal
    parent_opportunity_id: str | None = None
    exposure_unit: str = "STANDARD_LOT_EQUIVALENT"
    setup_family: str | None = None
    strategy_mode: str | None = None

    def __post_init__(self) -> None:
        if self.direction not in {"LONG", "SHORT"}:
            raise PortfolioValidationError("candidate direction must already be established by strategy")
        if not self.opportunity_id or not self.symbol:
            raise PortfolioValidationError("candidate identity is required")
        for name in ("volume", "risk", "score"):
            value = Decimal(str(getattr(self, name)))
            if not value.is_finite() or value < 0:
                raise PortfolioValidationError(f"{name} must be finite and non-negative")
            object.__setattr__(self, name, value)
        try:
            notional = Decimal(str(self.notional))
        except (ArithmeticError, ValueError, TypeError) as exc:
            raise PortfolioValidationError("notional must be finite and positive") from exc
        if not notional.is_finite() or notional <= 0:
            raise PortfolioValidationError("notional must be finite and positive")
        object.__setattr__(self, "notional", notional)


@dataclass(frozen=True)
class StructuralReversalEvidence:
    prior_opportunity_id: str
    new_opportunity_id: str
    structurally_reversed: bool
    reason: str

    def __post_init__(self) -> None:
        if not self.prior_opportunity_id or not self.new_opportunity_id or not self.reason:
            raise PortfolioValidationError("structural reversal provenance is required")
        if type(self.structurally_reversed) is not bool:
            raise PortfolioValidationError("structurally_reversed must be boolean")


@dataclass(frozen=True)
class PortfolioConfig:
    version: int = 1
    provenance: str = "phase5-default-portfolio-policy-v1"
    max_currency_exposure: Decimal = Decimal("10")
    max_correlated_risk: Decimal = Decimal("300")
    max_total_risk: Decimal = Decimal("500")
    max_trades: int = 10
    max_entries_per_opportunity: int = 1
    max_setup_exposure: Decimal = Decimal("1000000000")
    max_mode_exposure: Decimal = Decimal("1000000000")

    def __post_init__(self) -> None:
        if self.version < 1 or not self.provenance.strip():
            raise PortfolioValidationError("versioned portfolio policy provenance is required")
        for name in ("max_currency_exposure", "max_correlated_risk", "max_total_risk", "max_setup_exposure", "max_mode_exposure"):
            value = Decimal(str(getattr(self, name)))
            if not value.is_finite() or value < 0:
                raise PortfolioValidationError(f"{name} must be non-negative")
            object.__setattr__(self, name, value)
        if self.max_trades < 1 or self.max_entries_per_opportunity < 1:
            raise PortfolioValidationError("portfolio count caps must be positive")


@dataclass(frozen=True)
class PortfolioState:
    open_positions: tuple[PortfolioCandidate, ...] = ()
    currency_exposure: Mapping[str, Decimal] | None = None

    def __post_init__(self) -> None:
        exposure = {} if self.currency_exposure is None else dict(self.currency_exposure)
        for position in self.open_positions:
            vector = PortfolioArbitrator._vector(position)
            for key, value in vector.items():
                exposure[key] = exposure.get(key, Decimal("0")) + value
        for key, value in exposure.items():
            normalized = Decimal(str(value))
            if not normalized.is_finite():
                raise PortfolioValidationError("currency exposure must be finite")
            exposure[key] = normalized
        object.__setattr__(self, "currency_exposure", exposure)


@dataclass(frozen=True)
class PortfolioDecision:
    result: str
    opportunity_ids: tuple[str, ...]
    currency_exposure: Mapping[str, Decimal]
    correlated_risk: Decimal
    total_risk: Decimal
    reasons: tuple[str, ...]
    deferred_ids: tuple[str, ...] = ()
    merged_ids: tuple[str, ...] = ()
    risk_multiplier: Decimal = Decimal("0")
    exposure_unit: str = "STANDARD_LOT_EQUIVALENT"


class PortfolioArbitrator:
    """Final pre-execution exposure authority; never creates market direction."""

    def __init__(self, config: PortfolioConfig) -> None:
        self.config = config

    @staticmethod
    def rank(candidates: list[PortfolioCandidate]) -> list[PortfolioCandidate]:
        return sorted(candidates, key=lambda item: (-item.score, item.opportunity_id))

    @staticmethod
    def _vector(candidate: PortfolioCandidate) -> dict[str, Decimal]:
        sign = Decimal("1") if candidate.direction == "LONG" else Decimal("-1")
        exposure = candidate.notional
        return {
            candidate.base_currency: sign * exposure,
            candidate.quote_currency: -sign * exposure,
        }

    def _correlated_risk(
        self,
        candidate: PortfolioCandidate,
        positions: tuple[PortfolioCandidate, ...],
        correlations: Mapping[tuple[str, str], Decimal],
    ) -> Decimal:
        total = candidate.risk
        for position in positions:
            key = (candidate.symbol, position.symbol)
            reverse = (position.symbol, candidate.symbol)
            correlation = abs(Decimal(str(correlations.get(key, correlations.get(reverse, Decimal("0"))))))
            # Shared-risk contribution scales with both sides of the existing
            # exposure.  The geometric mean avoids the old bug where a tiny
            # candidate was blind to a very large correlated position.
            shared = (candidate.risk * position.risk).sqrt() * correlation
            total += shared
        return total

    def _entry_count(self, candidates: tuple[PortfolioCandidate, ...], opportunity_id: str) -> int:
        return sum(1 for item in candidates if item.opportunity_id == opportunity_id)

    def _group_exposure(self, candidates: tuple[PortfolioCandidate, ...], attr: str, value: str | None) -> Decimal:
        if value is None:
            return Decimal("0")
        return sum((item.notional for item in candidates if getattr(item, attr) == value), Decimal("0"))

    def _hard_constraints(
        self,
        candidates: tuple[PortfolioCandidate, ...],
        state: PortfolioState,
        correlations: Mapping[tuple[str, str], Decimal],
    ) -> tuple[tuple[str, ...], dict[str, Decimal], Decimal, Decimal]:
        reasons: list[str] = []
        combined = dict(state.currency_exposure)
        for item in candidates:
            for currency, value in self._vector(item).items():
                combined[currency] = combined.get(currency, Decimal("0")) + value
                if abs(combined[currency]) > self.config.max_currency_exposure:
                    reasons.append("CURRENCY_LIMIT")
        total_risk = sum((position.risk for position in state.open_positions), Decimal("0")) + sum((item.risk for item in candidates), Decimal("0"))
        if total_risk > self.config.max_total_risk:
            reasons.append("TOTAL_RISK_LIMIT")
        if len(state.open_positions) + len(candidates) > self.config.max_trades:
            reasons.append("TRADE_COUNT_LIMIT")
        for item in candidates:
            if self._entry_count(state.open_positions, item.opportunity_id) + self._entry_count(candidates, item.opportunity_id) > self.config.max_entries_per_opportunity:
                reasons.append("OPPORTUNITY_ENTRY_CAP")
            setup = self._group_exposure(state.open_positions + candidates, "setup_family", item.setup_family)
            if setup > self.config.max_setup_exposure:
                reasons.append("SETUP_EXPOSURE_LIMIT")
            mode = self._group_exposure(state.open_positions + candidates, "strategy_mode", item.strategy_mode)
            if mode > self.config.max_mode_exposure:
                reasons.append("MODE_EXPOSURE_LIMIT")
        corr = Decimal("0")
        for item in candidates:
            corr += self._correlated_risk(item, state.open_positions, correlations)
        if len(candidates) > 1:
            for i, left in enumerate(candidates):
                for right in candidates[i + 1:]:
                    key = (left.symbol, right.symbol)
                    reverse = (right.symbol, left.symbol)
                    correlation = abs(Decimal(str(correlations.get(key, correlations.get(reverse, Decimal("0"))))))
                    corr += (left.risk * right.risk).sqrt() * correlation
        if corr > self.config.max_correlated_risk:
            reasons.append("CORRELATION_LIMIT")
        return tuple(sorted(set(reasons))), combined, corr, total_risk

    def _risk_throttle(
        self,
        candidate: PortfolioCandidate,
        state: PortfolioState,
        correlations: Mapping[tuple[str, str], Decimal],
    ) -> Decimal:
        current_total = sum((position.risk for position in state.open_positions), Decimal("0"))
        remaining_total = self.config.max_total_risk - current_total
        multiplier = Decimal("1")
        if candidate.risk > 0:
            multiplier = min(multiplier, max(Decimal("0"), remaining_total / candidate.risk))
        current_corr = self._correlated_risk(candidate, state.open_positions, correlations)
        if current_corr > 0:
            multiplier = min(multiplier, max(Decimal("0"), self.config.max_correlated_risk / current_corr))
        vector = self._vector(candidate)
        for currency, value in vector.items():
            magnitude = abs(value)
            if magnitude == 0:
                continue
            remaining = self.config.max_currency_exposure - abs(state.currency_exposure.get(currency, Decimal("0")))
            multiplier = min(multiplier, max(Decimal("0"), remaining / magnitude))
        return min(Decimal("1"), multiplier)

    def evaluate(
        self,
        candidates: list[PortfolioCandidate],
        state: PortfolioState,
        correlations: Mapping[tuple[str, str], Decimal] | None = None,
        reversal: StructuralReversalEvidence | None = None,
    ) -> PortfolioDecision:
        if not candidates:
            return PortfolioDecision("REJECT", (), dict(state.currency_exposure), Decimal("0"), Decimal("0"), ("NO_CANDIDATE",), risk_multiplier=Decimal("0"))
        ranked = self.rank(candidates)
        correlations = correlations or {}
        for key, value in correlations.items():
            correlation = Decimal(str(value))
            if not correlation.is_finite() or correlation < 0 or correlation > 1:
                return PortfolioDecision("REJECT", (ranked[0].opportunity_id,), dict(state.currency_exposure), Decimal("0"), sum((p.risk for p in state.open_positions), Decimal("0")), ("INVALID_CORRELATION",), deferred_ids=tuple(item.opportunity_id for item in ranked[1:]), risk_multiplier=Decimal("0"))
        units = {item.exposure_unit for item in ranked} | {item.exposure_unit for item in state.open_positions}
        if len(units) > 1:
            return PortfolioDecision("REJECT", (ranked[0].opportunity_id,), dict(state.currency_exposure), Decimal("0"), sum((p.risk for p in state.open_positions), Decimal("0")), ("EXPOSURE_UNIT_MISMATCH",), risk_multiplier=Decimal("0"))
        # MERGE is an optimization only; it must satisfy exactly the same hard
        # constraints as ordinary admission, never a privileged bypass.
        merge_group = tuple(item for item in ranked if item.parent_opportunity_id is not None and item.parent_opportunity_id == ranked[0].parent_opportunity_id and item.direction == ranked[0].direction)
        if len(merge_group) > 1:
            merge_reasons, merge_vector, merge_corr, merge_risk = self._hard_constraints(merge_group, state, correlations)
            if not merge_reasons:
                return PortfolioDecision("MERGE", tuple(item.opportunity_id for item in merge_group), merge_vector, merge_corr, merge_risk, ("REDUNDANT_SAME_PARENT",), merged_ids=tuple(item.opportunity_id for item in merge_group), risk_multiplier=Decimal("1"), exposure_unit=next(iter(units)))
        deferred = tuple(item.opportunity_id for item in ranked[1:])
        failure_reasons: list[str] = []
        for candidate in ranked:
            candidate_reasons: list[str] = []
            for existing in state.open_positions:
                if existing.symbol == candidate.symbol and existing.direction != candidate.direction:
                    if reversal is None or reversal.prior_opportunity_id != existing.opportunity_id or reversal.new_opportunity_id != candidate.opportunity_id or not reversal.structurally_reversed:
                        candidate_reasons.append("FLIP_REQUIRES_STRUCTURAL_REVERSAL")
            reasons, combined, corr, total_risk = self._hard_constraints((candidate,), state, correlations)
            reasons = tuple(sorted(set(reasons + tuple(candidate_reasons))))
            throttle = self._risk_throttle(candidate, state, correlations)
            # A candidate may be reduced by portfolio policy; it is only a hard
            # rejection when no positive exposure can fit. The RiskEngine will
            # re-size the candidate using this multiplier before final commit.
            if throttle <= 0:
                failure_reasons.extend(reasons or ("PORTFOLIO_THROTTLE_ZERO",))
                continue
            hard_reasons = tuple(reason for reason in reasons if reason not in {"TOTAL_RISK_LIMIT", "CORRELATION_LIMIT", "CURRENCY_LIMIT"})
            if hard_reasons:
                failure_reasons.extend(hard_reasons)
                continue
            result = "ALLOW" if candidate.opportunity_id == ranked[0].opportunity_id else "DEFER"
            return PortfolioDecision(result, (candidate.opportunity_id,), combined, corr, total_risk, tuple(sorted(set(failure_reasons))), deferred_ids=deferred, risk_multiplier=throttle, exposure_unit=next(iter(units)))
        return PortfolioDecision("REJECT", (ranked[0].opportunity_id,), dict(state.currency_exposure), Decimal("0"), sum((p.risk for p in state.open_positions), Decimal("0")), tuple(sorted(set(failure_reasons))), deferred_ids=deferred, risk_multiplier=Decimal("0"), exposure_unit=next(iter(units)))

