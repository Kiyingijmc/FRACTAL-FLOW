from decimal import Decimal

from src.fractal_flow.domain.lane_pipeline import LanePipeline, LanePolicy, LaneRequest


def req(oid: str, lane: str, risk: str = "50", group: str = "FX") -> LaneRequest:
    return LaneRequest(oid, lane, group, Decimal(risk), Decimal("0.8"))


def test_group_cap_is_hard_pre_exposure_control() -> None:
    pipeline = LanePipeline({"PRIMARY": LanePolicy(max_risk=Decimal("100"), max_entries=2)}, {"FX": Decimal("100")})
    result = pipeline.evaluate([req("a", "PRIMARY", "60"), req("b", "PRIMARY", "60")])
    assert result.allowed_ids == ("a",)
    assert "GROUP_CAP" in result.rejections["b"]


def test_lane_ranking_is_deterministic() -> None:
    pipeline = LanePipeline({"PRIMARY": LanePolicy(max_risk=Decimal("100"), max_entries=2)}, {"FX": Decimal("100")})
    result = pipeline.evaluate([req("b", "PRIMARY", "40"), req("a", "PRIMARY", "40")])
    assert result.allowed_ids == ("a", "b")


def test_lane_pipeline_never_changes_direction() -> None:
    request = req("a", "PRIMARY")
    assert not hasattr(request, "direction")


def test_lane_policy_has_versioned_provenance() -> None:
    policy = LanePolicy(max_risk=Decimal("100"), max_entries=2)
    assert policy.version >= 1
    assert policy.provenance
