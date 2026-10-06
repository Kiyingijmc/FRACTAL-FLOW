"""Phase 1H Tests: Runtime Authority Enforcement for Phase 1 Engines."""

import pytest

from src.fractal_flow.domain.authority import AuthorityMatrix, AuthorityViolationException


from decimal import Decimal
from unittest.mock import patch

from src.fractal_flow.domain.data_quality import DataQualityEngine
from src.fractal_flow.domain.market import Bar, Tick
from src.fractal_flow.domain.structure import StructureEngine
from src.fractal_flow.domain.volatility import VolatilityEngine


def test_data_quality_volatility_structure_authority_matrix() -> None:
    # Allowed actions
    AuthorityMatrix.verify_capability("DataQuality", "WRITE_DATA_QUALITY_STATE")
    AuthorityMatrix.verify_capability("Volatility", "COMPUTE_VOLATILITY_METRICS")
    AuthorityMatrix.verify_capability("Structure", "OUTPUT_STRUCTURAL_STOP_CANDIDATE")

    # Forbidden actions
    with pytest.raises(AuthorityViolationException, match="forbidden"):
        AuthorityMatrix.verify_capability("DataQuality", "CREATE_EXECUTION_INTENT")

    with pytest.raises(AuthorityViolationException, match="forbidden"):
        AuthorityMatrix.verify_capability("Volatility", "SUBMIT_ORDER")

    with pytest.raises(AuthorityViolationException, match="forbidden"):
        AuthorityMatrix.verify_capability("Structure", "AUTHORIZE_TRADE")

    with pytest.raises(AuthorityViolationException, match="forbidden"):
        AuthorityMatrix.verify_capability("Structure", "SIZE_TRADE")


def test_production_call_paths_invoke_authority_matrix() -> None:
    """Verifies that production engine execution paths actively invoke AuthorityMatrix guards."""
    tick = Tick.create("EURUSD", 1700006400, "1.0850", "1.0851", sequence=1)
    bar = Bar.create("EURUSD", "1M", 1700006400, 1700006460, "1.0850", "1.0860", "1.0840", "1.0855")

    dq_engine = DataQualityEngine("EURUSD")
    vol_engine = VolatilityEngine("EURUSD", timeframe="1M")
    struct_engine = StructureEngine("EURUSD", timeframe="1M")

    # 1. Normal production execution paths succeed
    dq_engine.evaluate_tick(tick)
    dq_engine.evaluate_bar(bar)
    vol_engine.update_bar(bar)
    struct_engine.process_bar(bar, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1)
    struct_engine.get_structural_stop_candidate("LONG", atr_14=Decimal("0.0010"))

    # 2. Tampered / intercepted AuthorityMatrix raises AuthorityViolationException on production call path
    with patch.object(
        AuthorityMatrix,
        "verify_capability",
        side_effect=AuthorityViolationException("Authority Violation: Capability revoked"),
    ):
        with pytest.raises(AuthorityViolationException, match="Capability revoked"):
            dq_engine.evaluate_tick(tick)

        with pytest.raises(AuthorityViolationException, match="Capability revoked"):
            vol_engine.update_bar(bar)

        with pytest.raises(AuthorityViolationException, match="Capability revoked"):
            struct_engine.process_bar(bar, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1)
