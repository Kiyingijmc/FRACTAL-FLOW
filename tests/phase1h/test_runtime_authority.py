"""Phase 1H Tests: Runtime Authority Enforcement for Phase 1 Engines."""

import pytest

from src.fractal_flow.domain.authority import AuthorityMatrix, AuthorityViolationException


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
