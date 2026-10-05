"""FRACTAL-FLOW Structure v2.3 compatibility and forensic projection layer.

The v2.2 excursion algorithm remains the structural primitive. v2.3 adds the
missing forensic semantics around it: immutable historical projections, explicit
observation/confirmation clocks, and a canonical structural-truth projection.
This avoids silently changing historical v2.2 behavior while making causal
verification materially stronger.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from copy import deepcopy
from typing import Any

from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import StructureEngine, StructureTransitionRecord, SwingRecord
from src.fractal_flow.persistence.adapter import domain_to_primitive


@dataclass(frozen=True)
class StructuralTruth:
    symbol: str
    timeframe: str
    as_of: int
    confirmed_swings: tuple[SwingRecord, ...]
    structural_ownership: str
    current_direction: str
    protected_high: Decimal | None
    protected_low: Decimal | None
    break_state: str
    damage_state: str


class StructureEngineV23(StructureEngine):
    """v2.3 structural engine facade with immutable historical projections."""

    SNAPSHOT_SCHEMA = "structure-engine-v2.3"

    def __init__(self, *args: Any, historical_projection_capacity: int = 256, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if historical_projection_capacity <= 0:
            raise ValueError("historical_projection_capacity must be positive")
        self.historical_projection_capacity = historical_projection_capacity
        self._historical_projections: dict[int, dict[str, Any]] = {}
        self._historical_records: dict[int, StructureTransitionRecord] = {}

    def process_bar(self, *args: Any, **kwargs: Any) -> StructureTransitionRecord:
        record = super().process_bar(*args, **kwargs)
        timestamp = record.timestamp
        self._historical_projections[timestamp] = deepcopy(super().snapshot_state())
        self._historical_records[timestamp] = deepcopy(record)
        while len(self._historical_projections) > self.historical_projection_capacity:
            oldest = min(self._historical_projections)
            self._historical_projections.pop(oldest, None)
            self._historical_records.pop(oldest, None)
        return record

    def authoritative_projection(self, as_of: int) -> dict[str, Any]:
        """Return the exact engine projection that was known at/before ``as_of``.

        This is deliberately not reconstructed from current mutable state. It is
        a historical projection captured at the causal boundary and therefore
        remains stable after arbitrary future mutations.
        """
        eligible = [ts for ts in self._historical_projections if ts <= as_of]
        if not eligible:
            return {"schema_version": self.SNAPSHOT_SCHEMA, "as_of": as_of, "state": None}
        ts = max(eligible)
        result = deepcopy(self._historical_projections[ts])
        result["schema_version"] = self.SNAPSHOT_SCHEMA
        result["as_of"] = as_of
        result["projection_timestamp"] = ts
        return result

    def structural_truth(self, as_of: int | None = None) -> StructuralTruth:
        if as_of is None:
            as_of = self._last_timestamp
        projection = self.authoritative_projection(as_of)
        if projection.get("state") is None:
            return StructuralTruth(self.symbol, self.timeframe, as_of, (), "UNKNOWN", "UNKNOWN", None, None, "BREAK_NONE", "INTACT")
        # Reconstruct from the immutable projection rather than current state.
        legacy_projection = deepcopy(projection)
        legacy_projection["schema_version"] = "structure-engine-v2.2"
        legacy_projection.pop("as_of", None)
        legacy_projection.pop("projection_timestamp", None)
        legacy_projection.pop("historical_projection_timestamps", None)
        decoded = StructureEngine.from_snapshot_state(legacy_projection)
        return StructuralTruth(
            symbol=self.symbol,
            timeframe=self.timeframe,
            as_of=as_of,
            confirmed_swings=tuple(decoded.get_confirmed_swings(as_of)),
            structural_ownership=decoded.structural_ownership,
            current_direction=decoded.current_direction,
            protected_high=decoded.protected_high,
            protected_low=decoded.protected_low,
            break_state=decoded.break_state.value,
            damage_state=decoded.damage_state.value,
        )

    def causal_prefix_equal(self, prefix_as_of: int, other: "StructureEngineV23") -> bool:
        """Compare complete historical authoritative projections at a watermark."""
        return self.authoritative_projection(prefix_as_of) == other.authoritative_projection(prefix_as_of)

    def snapshot_state(self) -> dict[str, Any]:
        payload = super().snapshot_state()
        payload["schema_version"] = self.SNAPSHOT_SCHEMA
        payload["historical_projection_timestamps"] = sorted(self._historical_projections)
        payload["historical_projections"] = deepcopy(self._historical_projections)
        payload["historical_projection_capacity"] = self.historical_projection_capacity
        return payload

    @classmethod
    def from_snapshot_state(cls, payload: dict[str, Any]) -> "StructureEngineV23":
        decoded = deepcopy(payload)
        if decoded.get("schema_version") != cls.SNAPSHOT_SCHEMA:
            raise ValueError(f"Unsupported StructureEngineV23 snapshot schema: {decoded.get("schema_version")!r}")
        historical = decoded.pop("historical_projections", {})
        capacity = int(decoded.pop("historical_projection_capacity", 256))
        decoded.pop("historical_projection_timestamps", None)
        decoded["schema_version"] = "structure-engine-v2.2"
        # Restore the exact mutable v2.2 state without replaying market data.
        restored = StructureEngine.from_snapshot_state(decoded)
        engine = cls(symbol=restored.symbol, timeframe=restored.timeframe, config=restored.config, historical_projection_capacity=capacity)
        engine.__dict__.update(restored.__dict__)
        engine.historical_projection_capacity = capacity
        engine._historical_projections = {int(k): deepcopy(v) for k, v in historical.items()}
        engine._historical_records = {}
        return engine
