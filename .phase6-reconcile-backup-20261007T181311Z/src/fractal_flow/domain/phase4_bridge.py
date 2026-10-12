from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from .phase3 import OpportunityCandidate, Phase3Orchestrator, Phase3Role
from .phase4 import (
    ConfidenceEvidence, EntryPlanV4, ExecutionQualityProfile, GateEvidence,
    Opportunity, OpportunityState, Phase4GateType, TradeDecisionV4,
    TradeabilityEngine, make_decision, AccountRegistry,
)


class NewsShieldPort(Protocol):
    """Informational Phase-5 news boundary; it cannot submit or authorize orders."""

    def evaluate(self, symbol: str, timestamp: int) -> GateEvidence: ...


@dataclass(frozen=True)
class DecisionAdapterConfig:
    version: int = 1
    max_spread: Decimal = Decimal("0.00030")
    max_cost_ratio: Decimal = Decimal("0.50")
    min_opportunity_space: Decimal = Decimal("1")
    min_execution_quality: Decimal = Decimal("0.50")
    commission: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    atr_buffer_multiplier: Decimal = Decimal("1")
    minimum_rr_after_costs: Decimal = Decimal("1.5")
    target_space_multiplier: Decimal = Decimal("2")

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise ValueError("adapter configuration version must be positive")
        if any(v < 0 for v in (self.max_spread, self.max_cost_ratio, self.min_opportunity_space,
                               self.min_execution_quality, self.commission, self.slippage,
                               self.atr_buffer_multiplier, self.target_space_multiplier)):
            raise ValueError("decision adapter thresholds cannot be negative")
        if self.max_cost_ratio <= 0 or self.min_execution_quality > 1 or self.atr_buffer_multiplier <= 0:
            raise ValueError("invalid decision adapter configuration")
        if self.minimum_rr_after_costs <= 0 or self.target_space_multiplier <= 0:
            raise ValueError("invalid decision geometry configuration")


class Phase3DecisionAdapter:
    """Canonical Phase-3 -> Phase-4 bridge.

    It derives gates from authoritative Phase-2/3 evidence. Callers cannot
    supply arbitrary gate booleans, prices, or structural stops.
    """

    def __init__(self, config: DecisionAdapterConfig | None = None, account_registry: AccountRegistry | None = None) -> None:
        self.config = config or DecisionAdapterConfig()
        self.account_registry = account_registry
        self.tradeability = TradeabilityEngine()

    @staticmethod
    def _phase4_opportunity(candidate: OpportunityCandidate) -> Opportunity:
        raw = candidate.opportunity
        family = raw.setup_type.split(" ", 1)[0]
        if family not in {"FF-01", "FF-02", "FF-03", "FF-04"}:
            raise ValueError("Phase3 candidate has no canonical setup family")
        oid = Opportunity.deterministic_id(
            raw.root_id, raw.symbol, raw.primary_pullback_id, family, raw.direction.value,
        )
        return Opportunity(
            opportunity_id=oid,
            root_id=raw.root_id,
            parent_opportunity_id=raw.parent_opportunity_id,
            symbol=raw.symbol,
            direction=raw.direction.value,
            setup_family=family,
            primary_pullback_id=raw.primary_pullback_id,
            created_at=candidate.source_watermark,
            expires_at=candidate.expires_at,
            state=OpportunityState(raw.state),
            opportunity_space=Decimal(str(raw.opportunity_space)),
            structural_edge=Decimal(str(raw.structural_edge)),
            confidence=Decimal(str(raw.confidence)),
            strategy_mode=raw.strategy_mode,
        )

    @staticmethod
    def _derived_gates(candidate: OpportunityCandidate, observed: int, news: GateEvidence) -> tuple[GateEvidence, ...]:
        hierarchy = candidate.hierarchy
        required = {Phase3Role.CONTEXT, Phase3Role.DIRECTION, Phase3Role.STRUCTURE,
                    Phase3Role.PRIMARY, Phase3Role.SECONDARY, Phase3Role.CONFIRMATION,
                    Phase3Role.EXECUTION}
        nodes = {n.role: n for n in hierarchy.nodes}
        primary = nodes.get(Phase3Role.PRIMARY)
        execution = nodes.get(Phase3Role.EXECUTION)
        all_present = required.issubset(nodes)
        valid_nodes = all_present and all(nodes[r].valid for r in required)
        states = set()
        for n in nodes.values():
            states.add(n.location)
        data_ok = all_present and valid_nodes and all(n.valid for n in nodes.values())
        structure_ok = bool(primary and primary.structure in {"BULLISH", "BEARISH"}) and not hierarchy.contradiction
        regime_location_ok = bool(primary and primary.regime not in {"UNKNOWN", "INVALID", "BLOCKED"}
                                  and primary.location not in {"UNKNOWN", "BLOCKED"})
        containment_ok = all(binding.containment != "DIVERGENT" for binding in hierarchy.bindings)
        opportunity_ok = candidate.opportunity.entry_allowed or OpportunityState(candidate.opportunity.state) in {
            OpportunityState.VALID, OpportunityState.TRIGGER_READY,
        }
        execution_ok = bool(execution and execution.valid)
        # The legacy three gates remain the top-level handoff gates. Each is
        # derived from the complete lower-level evidence set.
        return (
            GateEvidence(Phase4GateType.OPPORTUNITY, opportunity_ok and data_ok and structure_ok, "DERIVED_PHASE3_OPPORTUNITY", observed),
            GateEvidence(Phase4GateType.TRADEABILITY, regime_location_ok and containment_ok and execution_ok, "DERIVED_PHASE3_PERMISSION", observed),
            GateEvidence(Phase4GateType.ENTRY_PLAN, structure_ok and execution_ok, "DERIVED_STRUCTURE_ENTRY_GEOMETRY", observed),
            news,
        )

    def build(self, candidate: OpportunityCandidate, orchestrator: Phase3Orchestrator,
              observed_timestamp: int, news_shield: NewsShieldPort, account_id: str) -> TradeDecisionV4:
        if self.account_registry is None:
            raise ValueError("Phase3DecisionAdapter requires an explicit AccountRegistry")
        profile = self.account_registry.get(account_id)
        if not profile.enabled:
            raise ValueError(f"account_id is disabled: {account_id}")
        if observed_timestamp < candidate.source_watermark:
            raise ValueError("decision observation precedes Phase3 source watermark")
        opportunity = self._phase4_opportunity(candidate)
        if opportunity.opportunity_id != candidate.opportunity.opportunity_id:
            # Phase3 and Phase4 use different historical identity schemes. The
            # adapter binds the Phase4 identity to the immutable Phase3 root/content.
            opportunity = Opportunity(
                **{**opportunity.__dict__, "opportunity_id": opportunity.opportunity_id}
            )
        primary = orchestrator._latest_at(orchestrator.mapping.primary, candidate.source_watermark)
        if primary is None:
            raise ValueError("authoritative primary evaluation is unavailable")
        structure = primary.structure
        direction = candidate.opportunity.direction.value
        protected = structure.protected_low if direction == "LONG" else structure.protected_high
        if protected is None:
            raise ValueError("authoritative structural protected level is unavailable")
        atr = primary.volatility.atr_14
        if atr <= 0:
            raise ValueError("authoritative ATR is unavailable")
        buffer = atr * self.config.atr_buffer_multiplier
        execution_node = candidate.hierarchy.node(Phase3Role.EXECUTION)
        if execution_node is None or execution_node.close_price == "0":
            raise ValueError("authoritative execution quote is unavailable")
        entry = Decimal(execution_node.close_price)
        quote_timestamp = execution_node.evaluation_timestamp
        if quote_timestamp < opportunity.created_at or quote_timestamp > observed_timestamp:
            raise ValueError("authoritative execution quote is causally outside decision lifetime")
        if direction == "LONG":
            effective_stop = protected - buffer
            risk = entry - effective_stop
            target = entry + max(risk * self.config.minimum_rr_after_costs, atr * self.config.target_space_multiplier)
        else:
            effective_stop = protected + buffer
            risk = effective_stop - entry
            target = entry - max(risk * self.config.minimum_rr_after_costs, atr * self.config.target_space_multiplier)
        profile = ExecutionQualityProfile(
            self.config.max_spread, self.config.max_cost_ratio,
            self.config.min_opportunity_space, self.config.min_execution_quality,
        )
        execution_quality = Decimal("1") if execution_node.valid else Decimal("0")
        tb = self.tradeability.evaluate(
            opportunity, primary.bar.spread, self.config.commission, self.config.slippage,
            abs(target - entry), execution_quality >= self.config.min_execution_quality,
            execution_quality, profile, observed_timestamp=observed_timestamp,
        )
        plan = EntryPlanV4(
            entry_plan_id=f"phase3:{candidate.opportunity.opportunity_id}:{candidate.source_watermark}",
            opportunity_id=opportunity.opportunity_id, symbol=opportunity.symbol, direction=direction,
            entry_price=entry, structural_stop=protected, atr_buffer=buffer,
            target_price=target, minimum_rr_after_costs=self.config.minimum_rr_after_costs,
            quote_timestamp=quote_timestamp, expected_total_cost=tb.total_cost,
        )
        conf = ConfidenceEvidence(opportunity.confidence, "phase3", f"phase3-{candidate.opportunity_version}", candidate.source_watermark)
        news = news_shield.evaluate(opportunity.symbol, observed_timestamp)
        gates = self._derived_gates(candidate, observed_timestamp, news)
        if not news.passed:
            raise ValueError("News Shield interface is not permitting the Phase-4 handoff")
        return make_decision(opportunity, tb, plan, gates[:3], conf, observed_timestamp, account_id=account_id)

    def recheck_liveness(self, decision: TradeDecisionV4, candidate: OpportunityCandidate, at: int) -> bool:
        current = self._phase4_opportunity(candidate)
        return decision.is_live_authorized(current, at)
