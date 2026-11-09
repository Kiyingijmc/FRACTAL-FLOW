from src.fractal_flow.domain.context import DataStatus


def test_data_status_matches_verified_data_engine_contract() -> None:
    assert tuple((item.name, item.value) for item in DataStatus) == (
        ("VALID", "VALID"),
        ("DEGRADED", "DEGRADED"),
        ("STALE", "STALE"),
        ("CONFLICT", "CONFLICT"),
        ("INVALID", "INVALID"),
        ("UNAVAILABLE", "UNAVAILABLE"),
        ("RECOVERY_REQUIRED", "RECOVERY_REQUIRED"),
    )
