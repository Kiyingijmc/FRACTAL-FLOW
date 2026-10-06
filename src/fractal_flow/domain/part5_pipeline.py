"""Phase 5 protection/allocation pipeline.

The pipeline composes independent authorities without allowing any downstream
layer to manufacture strategy direction or bypass an upstream veto.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping

from .phase4 import Opportunity

from .lane_pipeline import LanePipeline, LaneRequest
from .news_shield import NewsShield
from .phase4 import TradeDecisionV4
from .portfolio import PortfolioArbitrator, PortfolioCandidate, PortfolioConfig, PortfolioState
from .risk_engine import AccountFeasibilityEngine, AccountState, RiskAllocation, RiskConfig, RiskEngine, SymbolSpec
from src.fractal_flow.persistence.part5 import PartBDecisionJournal


@dataclass(frozen=True)
class PartBResult:
    status: str
    reason: str
    allocation: RiskAllocation | None = None


class PartBDecisionPipeline:
    """Final protective/allocation boundary before any execution layer."""

    def __init__(self, risk_config: RiskConfig, portfolio_config: PortfolioConfig, lane_pipeline: LanePipeline | None = None, journal: PartBDecisionJournal | None = None) -> None:
        self._feasibility = AccountFeasibilityEngine()
        self._risk = RiskEngine(risk_config)
        self._portfolio = PortfolioArbitrator(portfolio_config)
        self._lane_pipeline = lane_pipeline
        self._journal = journal
        self._authorized_opportunities: dict[tuple[str, str], int] = {}
        self._lane_history: list[tuple[str, LaneRequest]] = []
        self._current_risk_config = risk_config
        self._current_portfolio_config = portfolio_config
        if journal is not None:
            for record in journal.replay():
                if record.status == "ALLOW":
                    oid = str(record.context.get("opportunity_id", ""))
                    if oid:
                        key = (record.account_id, oid)
                        self._authorized_opportunities[key] = self._authorized_opportunities.get(key, 0) + 1
                    raw_lane = record.context.get("lane")
                    raw_group = record.context.get("group")
                    raw_alloc = record.context.get("allocation", {})
                    if isinstance(raw_lane, str) and isinstance(raw_group, str) and isinstance(raw_alloc, dict):
                        try:
                            risk = Decimal(str(raw_alloc["approved_risk"]))
                            score = Decimal(str(record.context.get("decision_confidence", "0")))
                            self._lane_history.append((record.account_id, LaneRequest(oid, raw_lane, raw_group, risk, score)))
                        except (KeyError, ValueError):
                            continue

    @staticmethod
    def _canonicalize(value: Any) -> object:
        """Convert authoritative decision inputs to deterministic JSON-safe data."""
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if is_dataclass(value):
            return {field.name: PartBDecisionPipeline._canonicalize(getattr(value, field.name)) for field in fields(value) if field.name != "_authority_proof"}
        if isinstance(value, Mapping):
            return {str(key): PartBDecisionPipeline._canonicalize(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
        if isinstance(value, (tuple, list)):
            return [PartBDecisionPipeline._canonicalize(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if hasattr(value, "__dict__"):
            return {str(key): PartBDecisionPipeline._canonicalize(item) for key, item in sorted(value.__dict__.items()) if key != "_authority_proof"}
        raise TypeError(f"unsupported journal context value: {type(value).__name__}")

    def _input_context(
        self,
        decision: TradeDecisionV4,
        account: AccountState,
        spec: SymbolSpec,
        portfolio_state: PortfolioState,
        news: NewsShield,
        observed_timestamp: int,
        requested_risk: Decimal,
        correlations: Mapping[tuple[str, str], Decimal] | None,
        lane: str | None,
        group: str | None,
        authoritative_opportunity: Opportunity,
        parent_opportunity: Opportunity | None,
    ) -> dict[str, object]:
        return {
            "context_version": 2,
            "decision": self._canonicalize(decision),
            "authoritative_opportunity": self._canonicalize(authoritative_opportunity),
            "parent_opportunity": self._canonicalize(parent_opportunity),
            "account": self._canonicalize(account),
            "symbol_spec": self._canonicalize(spec),
            "portfolio_state": self._canonicalize(portfolio_state),
            "requested_risk": self._canonicalize(requested_risk),
            "risk_config": self._canonicalize(self._current_risk_config),
            "portfolio_config": self._canonicalize(self._current_portfolio_config),
            "correlations": self._canonicalize(correlations or {}),
            "lane": lane,
            "group": group,
            "observed_timestamp": observed_timestamp,
            "news_state_hash": news.state_hash(),
        }

    def _finish(
        self,
        decision: TradeDecisionV4,
        result: PartBResult,
        news: NewsShield,
        observed_timestamp: int,
        context: dict[str, object] | None = None,
    ) -> PartBResult:
        if self._journal is not None:
            allocation = None
            if result.allocation is not None:
                allocation = {
                    "account_id": result.allocation.account_id,
                    "symbol": result.allocation.symbol,
                    "requested_risk": str(result.allocation.requested_risk),
                    "approved_risk": str(result.allocation.approved_risk),
                    "raw_volume": str(result.allocation.raw_volume),
                    "approved_volume": str(result.allocation.approved_volume),
                    "risk_state": result.allocation.risk_state,
                    "reasons": "|".join(result.allocation.reasons),
                }
            record_context = dict(context or {})
            record_context.update({
                "outcome_status": result.status,
                "outcome_reason": result.reason,
                "outcome_allocation": allocation,
                "outcome_news_state_hash": news.state_hash(),
            })
            self._journal.append(
                account_id=str(decision.account_id),
                decision_id=decision.decision_id,
                observed_timestamp=observed_timestamp,
                status=result.status,
                reason=result.reason,
                allocation=allocation,
                news_state_hash=news.state_hash(),
                context=record_context,
            )
        return result

    def evaluate(
        self,
        decision: TradeDecisionV4,
        account: AccountState,
        spec: SymbolSpec,
        portfolio_state: PortfolioState,
        news: NewsShield,
        observed_timestamp: int,
        requested_risk: Decimal,
        correlations: Mapping[tuple[str, str], Decimal] | None = None,
        lane: str | None = None,
        group: str | None = None,
        *,
        authoritative_opportunity: Opportunity,
        parent_opportunity: Opportunity | None = None,
    ) -> PartBResult:
        base_context = self._input_context(
            decision, account, spec, portfolio_state, news, observed_timestamp,
            requested_risk, correlations, lane, group, authoritative_opportunity, parent_opportunity,
        )

        def finish(result: PartBResult, extra: Mapping[str, object] | None = None) -> PartBResult:
            context = dict(base_context)
            if extra:
                context.update(extra)
            return self._finish(decision, result, news, observed_timestamp, context)

        # Phase 4 is an upstream authority, but Part B must independently
        # revalidate the current authoritative opportunity at the decision-use
        # boundary.  A stale, replaced, forged, or expired decision cannot
        # enter allocation merely because its old `authorized` bit is true.
        if not decision.authorized:
            return finish(PartBResult("REJECT", "PHASE4_NOT_AUTHORIZED"))
        if not decision.is_live_authorized(authoritative_opportunity, observed_timestamp, parent_opportunity):
            return finish(PartBResult("REJECT", "PHASE4_AUTHORITY_STALE_OR_MISMATCHED"))
        if decision.account_id is None or decision.account_id != account.account_id:
            return finish(PartBResult("REJECT", "ACCOUNT_IDENTITY_MISMATCH"))
        if observed_timestamp < decision.created_at:
            return finish(PartBResult("REJECT", "OBSERVATION_PRECEDES_DECISION"))
        key = (account.account_id, authoritative_opportunity.opportunity_id)
        prior_count = self._authorized_opportunities.get(key, 0)
        if self._journal is not None:
            prior_count = max(prior_count, len(self._journal.authorized_for_opportunity(account.account_id, authoritative_opportunity.opportunity_id)))
        max_entries = min(self._portfolio.config.max_entries_per_opportunity, authoritative_opportunity.max_entries)
        if prior_count >= max_entries:
            return finish(PartBResult("REJECT", "PORTFOLIO:OPPORTUNITY_ENTRY_CAP"))

        news_evidence = news.evaluate(spec.symbol, observed_timestamp)
        if not news_evidence.passed:
            return finish(PartBResult("REJECT", f"NEWS:{news_evidence.reason}"))
        if decision.entry_plan.symbol != spec.symbol or decision.entry_plan.direction not in {"LONG", "SHORT"}:
            return finish(PartBResult("REJECT", "ENTRY_IDENTITY"))
        if authoritative_opportunity.symbol != spec.symbol or authoritative_opportunity.direction != decision.entry_plan.direction:
            return finish(PartBResult("REJECT", "OPPORTUNITY_ENTRY_IDENTITY"))
        if authoritative_opportunity.max_entries < 1:
            return finish(PartBResult("REJECT", "OPPORTUNITY_MAX_ENTRIES_INVALID"))
        if decision.entry_plan.direction == "LONG":
            effective_stop = decision.entry_plan.structural_stop - decision.entry_plan.atr_buffer
        else:
            effective_stop = decision.entry_plan.structural_stop + decision.entry_plan.atr_buffer
        stop_distance = abs(decision.entry_plan.entry_price - effective_stop)
        minimum_feasibility = self._feasibility.check(account, spec, stop_distance, spec.min_volume, self._risk.config.max_trades, self._risk.config.max_spread)
        if minimum_feasibility.status != "FEASIBLE":
            return finish(PartBResult("REJECT", f"FEASIBILITY:{minimum_feasibility.reason}"))
        allocation = self._risk.size(
            account, spec, stop_distance, requested_risk, minimum_feasibility,
            news_multiplier=news.risk_multiplier, portfolio_multiplier=Decimal("1"),
            observed_timestamp=observed_timestamp,
        )
        if allocation.approved_volume <= 0 or allocation.approved_risk <= 0:
            return finish(PartBResult("REJECT", f"RISK:{allocation.risk_state}", allocation))

        def candidate_from(allocation_result: RiskAllocation) -> PortfolioCandidate:
            return PortfolioCandidate(
                opportunity_id=decision.opportunity_id, symbol=spec.symbol, direction=decision.entry_plan.direction,
                base_currency=spec.base_currency, quote_currency=spec.quote_currency,
                volume=allocation_result.approved_volume, risk=allocation_result.approved_risk,
                score=decision.confidence.value, notional=allocation_result.approved_volume,
                exposure_unit="STANDARD_LOT_EQUIVALENT", setup_family=authoritative_opportunity.setup_family,
                strategy_mode=authoritative_opportunity.strategy_mode, parent_opportunity_id=authoritative_opportunity.parent_opportunity_id,
            )

        candidate = candidate_from(allocation)
        portfolio = self._portfolio.evaluate([candidate], portfolio_state, correlations)
        if portfolio.result not in {"ALLOW", "MERGE"} or portfolio.risk_multiplier <= 0:
            return finish(PartBResult("REJECT", f"PORTFOLIO:{','.join(portfolio.reasons)}", allocation))
        # Portfolio arbitration may throttle risk without becoming risk
        # authority. Re-size through the RiskEngine so the final volume and
        # approved risk are mathematically derived from the throttle.
        if portfolio.risk_multiplier < 1:
            allocation = self._risk.size(
                account, spec, stop_distance, requested_risk, minimum_feasibility,
                news_multiplier=news.risk_multiplier, portfolio_multiplier=portfolio.risk_multiplier,
                observed_timestamp=observed_timestamp,
            )
            if allocation.approved_volume <= 0 or allocation.approved_risk <= 0:
                return finish(PartBResult("REJECT", "RISK:PORTFOLIO_THROTTLE_ZERO", allocation))
            candidate = candidate_from(allocation)
            portfolio = self._portfolio.evaluate([candidate], portfolio_state, correlations)
            if portfolio.result not in {"ALLOW", "MERGE"} or portfolio.risk_multiplier <= 0:
                return finish(PartBResult("REJECT", f"PORTFOLIO:{','.join(portfolio.reasons)}", allocation))

        final_feasibility = self._feasibility.check(account, spec, stop_distance, allocation.approved_volume, self._risk.config.max_trades, self._risk.config.max_spread)
        if final_feasibility.status != "FEASIBLE":
            return finish(PartBResult("REJECT", f"FEASIBILITY_FINAL:{final_feasibility.reason}", allocation))
        if self._lane_pipeline is not None:
            if lane is None or group is None:
                return finish(PartBResult("REJECT", "LANE:EXPLICIT_LANE_AND_GROUP_REQUIRED", allocation))
            current_lane_request = LaneRequest(decision.opportunity_id, lane, group, allocation.approved_risk, decision.confidence.value)
            historical_lane_requests = [request for account_id, request in self._lane_history if account_id == account.account_id]
            lane_result = self._lane_pipeline.evaluate(historical_lane_requests + [current_lane_request])
            if decision.opportunity_id not in lane_result.allowed_ids:
                return finish(PartBResult("REJECT", f"LANE:{','.join(lane_result.rejections.get(decision.opportunity_id, ("LANE_REJECTED",)))}", allocation))
        context = {
            # Stable top-level projections preserve restart/index consumers while
            # the nested context remains the canonical complete input envelope.
            "opportunity_id": authoritative_opportunity.opportunity_id,
            "lane": lane,
            "group": group,
            "decision_confidence": str(decision.confidence.value),
            "allocation": self._canonicalize(allocation),
            "final_portfolio_result": portfolio.result,
            "final_portfolio_multiplier": str(portfolio.risk_multiplier),
            "final_allocation": self._canonicalize(allocation),
        }
        result = PartBResult("ALLOW", "PART_B_AUTHORIZED", allocation)
        final = finish(result, context)
        self._authorized_opportunities[key] = prior_count + 1
        if lane is not None and group is not None:
            self._lane_history.append((account.account_id, LaneRequest(decision.opportunity_id, lane, group, allocation.approved_risk, decision.confidence.value)))
        return final

