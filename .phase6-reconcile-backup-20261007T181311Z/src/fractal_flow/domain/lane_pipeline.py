"""Deterministic multi-lane/group resource arbitration for Phase 5."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping


@dataclass(frozen=True)
class LanePolicy:
    version: int = 1
    provenance: str = "phase5-default-lane-policy-v1"
    max_risk: Decimal = Decimal("0")
    max_entries: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_risk", Decimal(str(self.max_risk)))
        if self.version < 1 or not self.provenance.strip():
            raise ValueError("versioned lane policy provenance is required")
        if self.max_risk < 0 or self.max_entries < 1:
            raise ValueError("invalid lane policy")


@dataclass(frozen=True)
class LaneRequest:
    opportunity_id: str
    lane: str
    group: str
    risk: Decimal
    score: Decimal

    def __post_init__(self) -> None:
        if not self.opportunity_id or not self.lane or not self.group:
            raise ValueError("lane request identity is required")
        for name in ("risk", "score"):
            value = Decimal(str(getattr(self, name)))
            if not value.is_finite() or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class LaneResult:
    allowed_ids: tuple[str, ...]
    rejections: Mapping[str, tuple[str, ...]]


class LanePipeline:
    """Hard pre-exposure lane/group caps with deterministic tie-breaking."""

    def __init__(self, lane_policies: Mapping[str, LanePolicy], group_caps: Mapping[str, Decimal]) -> None:
        self._lane_policies = dict(lane_policies)
        self._group_caps = {key: Decimal(str(value)) for key, value in group_caps.items()}

    def evaluate(self, requests: list[LaneRequest]) -> LaneResult:
        ordered = sorted(requests, key=lambda r: (-r.score, r.opportunity_id))
        lane_risk: dict[str, Decimal] = {}
        lane_count: dict[str, int] = {}
        group_risk: dict[str, Decimal] = {}
        allowed: list[str] = []
        rejections: dict[str, tuple[str, ...]] = {}
        for request in ordered:
            reasons: list[str] = []
            policy = self._lane_policies.get(request.lane)
            if policy is None:
                reasons.append("UNKNOWN_LANE")
            else:
                if lane_count.get(request.lane, 0) >= policy.max_entries:
                    reasons.append("LANE_ENTRY_CAP")
                if lane_risk.get(request.lane, Decimal("0")) + request.risk > policy.max_risk:
                    reasons.append("LANE_RISK_CAP")
            cap = self._group_caps.get(request.group)
            if cap is None:
                reasons.append("UNKNOWN_GROUP")
            elif group_risk.get(request.group, Decimal("0")) + request.risk > cap:
                reasons.append("GROUP_CAP")
            if reasons:
                rejections[request.opportunity_id] = tuple(sorted(set(reasons)))
                continue
            allowed.append(request.opportunity_id)
            lane_risk[request.lane] = lane_risk.get(request.lane, Decimal("0")) + request.risk
            lane_count[request.lane] = lane_count.get(request.lane, 0) + 1
            group_risk[request.group] = group_risk.get(request.group, Decimal("0")) + request.risk
        return LaneResult(tuple(allowed), rejections)
