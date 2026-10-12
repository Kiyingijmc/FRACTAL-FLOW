"""Reusable No-Lookahead Causal Test Framework for FRACTAL FLOW.

Proves that for any decision time 't', output computed on prefix [0..t] is identical to
output computed when arbitrary future mutations (Future A vs Future B) are appended.
"""

from dataclasses import dataclass, field
from typing import Any, Callable

from src.fractal_flow.domain.market import Tick
from src.fractal_flow.persistence.adapter import canonical_json_dumps

PROCESSING_METADATA_FIELDS: set[str] = {
    "processing_timestamp",
    "execution_wall_clock",
    "host_id",
}


@dataclass
class CausalVerificationResult:
    decision_time: int
    prefix_output: dict[str, Any]
    future_a_output_at_t: dict[str, Any]
    future_b_output_at_t: dict[str, Any]
    is_causal: bool
    latest_permissible_input_timestamp: int
    discrepancies: list[str] = field(default_factory=list)


def extract_decision_state(full_output: dict[str, Any]) -> dict[str, Any]:
    """Filters full output to extract strictly decision state fields, excluding metadata."""
    decision_state = {}
    for k, v in full_output.items():
        if k not in PROCESSING_METADATA_FIELDS:
            decision_state[k] = v
    return decision_state


class CausalTestFramework:
    """Causal test harness executing future mutation experiments."""

    @staticmethod
    def verify_causality(
        prefix_ticks: list[Tick],
        future_a_ticks: list[Tick],
        future_b_ticks: list[Tick],
        decision_time: int,
        processor_fn: Callable[[list[Tick], int], dict[str, Any]],
    ) -> CausalVerificationResult:
        """Executes prefix, prefix + future_A, prefix + future_B and asserts output at time t is invariant."""
        valid_prefix = [t for t in prefix_ticks if t.timestamp <= decision_time]
        latest_input_ts = max((t.timestamp for t in valid_prefix), default=0)

        if latest_input_ts > decision_time:
            raise ValueError(
                f"Prefix contains lookahead data: latest tick ts ({latest_input_ts}) > decision_time ({decision_time})"
            )

        # 1. Output on prefix alone at decision_time
        out_prefix = processor_fn(valid_prefix, decision_time)

        # 2. Output on prefix + future A at decision_time
        stream_a = valid_prefix + future_a_ticks
        out_a = processor_fn(stream_a, decision_time)

        # 3. Output on prefix + future B at decision_time
        stream_b = valid_prefix + future_b_ticks
        out_b = processor_fn(stream_b, decision_time)

        ds_prefix = extract_decision_state(out_prefix)
        ds_a = extract_decision_state(out_a)
        ds_b = extract_decision_state(out_b)

        discrepancies: list[str] = []

        json_prefix = canonical_json_dumps(ds_prefix)
        json_a = canonical_json_dumps(ds_a)
        json_b = canonical_json_dumps(ds_b)

        if json_prefix != json_a:
            discrepancies.append(f"Future A mutated decision state at time t: {json_prefix} != {json_a}")

        if json_prefix != json_b:
            discrepancies.append(f"Future B mutated decision state at time t: {json_prefix} != {json_b}")

        is_causal = len(discrepancies) == 0 and latest_input_ts <= decision_time

        return CausalVerificationResult(
            decision_time=decision_time,
            prefix_output=out_prefix,
            future_a_output_at_t=out_a,
            future_b_output_at_t=out_b,
            is_causal=is_causal,
            latest_permissible_input_timestamp=latest_input_ts,
            discrepancies=discrepancies,
        )
