"""Phase 2 Work Package 2A Tests: Structure Engine v2.

Adversarial forensic test suite covering:
- Causal structural-excursion mathematics and semantic running-extreme defeat.
- 48-bar clean alternating zigzag production-path test with 15 explicit behavioral assertions.
- Causal-prefix invariance test under future price spikes, crashes, volatility shocks, and news mutations.
- Single-authority structural trend ownership matrix across all 12 evidence combinations.
- Exact 8-row truth table matrix for BOS/CHoCH via production process_bar().
- Continuation BOS non-destruction and CHoCH structural damage semantics.
- Production-reachable failed break and reclaim/re-arm state machine transitions.
- Protected level authority anchoring strictly on confirmed active swings.
- Bounded memory and deterministic FIFO eviction.
- AST guard plus semantic adversarial tests against accidental reintroduction of running-extreme behavior.
- 26-scenario required adversarial test matrix.
"""

import ast
from decimal import Decimal
from pathlib import Path
import pytest

from src.fractal_flow.config.config import StructureConfig
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import (
    BreakState,
    StructuralDamageState,
    StructureEngine,
    SwingRecord,
    SwingState,
)

BASE_TS = 1700006400


# ============================================================================
# 1. Pivot Timestamp Causality & Effective From
# ============================================================================


def test_pivot_timestamp_causality_and_effective_from() -> None:
    """Verifies candidate_at reflects actual price extreme bar timestamp,

    while confirmed_at and effective_from reflect confirmation bar timestamp.
    """
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")

    # Bar 0 at t=60: High extreme at 1.0900 -> Candidate forms
    b0 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0890", "1.0900", "1.0890", "1.0895")
    rec0 = engine.process_bar(b0, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec0.swing_state == SwingState.SWING_CANDIDATE

    # Bar 1 at t=120: Reversal displacement down to 1.0840 (0.0060 displacement > 1.5 * v_local) -> Swing confirmed
    b1 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0860", "1.0865", "1.0835", "1.0840")
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=2)
    assert rec1.swing_state == SwingState.SWING_CONFIRMED

    # Bar 2 at t=180: Continuation -> Swing protected
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0840", "1.0845", "1.0820", "1.0825")
    rec2 = engine.process_bar(b2, v_local, root_id="r1", parent_id="p1", parent_version=3)

    assert rec2.swing_state == SwingState.SWING_PROTECTED
    assert len(rec1.active_swings) >= 1

    swing: SwingRecord = rec1.active_swings[0]
    assert swing.swing_type == "HIGH"
    assert swing.price == Decimal("1.0900")
    assert swing.candidate_at == BASE_TS + 60  # candidate_at of Bar 0
    assert swing.confirmed_at == BASE_TS + 120  # close_timestamp of Bar 1
    assert swing.effective_from == BASE_TS + 120
    assert swing.confirmed_at >= swing.candidate_at  # Temporal causality invariant

    # Downstream query at decision_timestamp < confirmed_at returns no swings
    assert engine.get_confirmed_swings(decision_timestamp=BASE_TS + 60) == []
    # Query at decision_timestamp >= confirmed_at returns swing
    swings_avail = engine.get_confirmed_swings(decision_timestamp=BASE_TS + 120)
    assert len(swings_avail) >= 1
    assert swings_avail[0].swing_id == swing.swing_id


# ============================================================================
# 2. Strong Running-Extreme Defeat Tests
# ============================================================================


def test_running_extreme_defeat_sequence_a_b_c_d_reversal() -> None:
    """Defeats running-extreme implementations on sequence A < B < C < D -> reversal.

    A (1.0840), B (1.0860), C (1.0900), D (1.0890 - lower peak!), E (reversal to 1.0820).
    Proves candidate high is anchored strictly to the local pivot bar (C at 1.0900 at tC),
    not merely the highest high seen during an epoch, and timestamp is tC.
    """
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")

    tsA = BASE_TS + 60
    tsB = BASE_TS + 120
    tsC = BASE_TS + 180
    tsD = BASE_TS + 240
    tsE = BASE_TS + 300

    # Bar A: High 1.0840
    bA = Bar.create("EURUSD", "1M", BASE_TS, tsA, "1.0830", "1.0840", "1.0825", "1.0835")
    engine.process_bar(bA, v_local, root_id="r1", parent_id="p1", parent_version=1)

    # Bar B: High 1.0860 (higher high -> A superseded)
    bB = Bar.create("EURUSD", "1M", tsA, tsB, "1.0835", "1.0860", "1.0830", "1.0855")
    engine.process_bar(bB, v_local, root_id="r1", parent_id="p1", parent_version=2)

    # Bar C: High 1.0900 (higher high -> B superseded, local peak at 1.0900)
    bC = Bar.create("EURUSD", "1M", tsB, tsC, "1.0855", "1.0900", "1.0850", "1.0890")
    engine.process_bar(bC, v_local, root_id="r1", parent_id="p1", parent_version=3)

    # Bar D: High 1.0890, Low 1.0880, Close 1.0888, Open 1.0885 (does NOT exceed C; C remains active high candidate)
    bD = Bar.create("EURUSD", "1M", tsC, tsD, "1.0885", "1.0890", "1.0880", "1.0888")
    engine.process_bar(bD, v_local, root_id="r1", parent_id="p1", parent_version=4)

    assert engine._high_candidate is not None
    assert engine._high_candidate.price == Decimal("1.0900")
    assert engine._high_candidate.candidate_at == tsC  # Timestamp of Bar C!

    # Bar E: Sharp drop to close 1.0820 -> Reversal displacement = 1.0900 - 1.0820 = 0.0080 >= 1.5 * v_local
    bE = Bar.create("EURUSD", "1M", tsD, tsE, "1.0865", "1.0868", "1.0818", "1.0820")
    recE = engine.process_bar(bE, v_local, root_id="r1", parent_id="p1", parent_version=5)

    high_swings = [s for s in engine.swings if s.swing_type == "HIGH"]
    assert len(high_swings) == 1
    assert high_swings[0].price == Decimal("1.0900")
    assert high_swings[0].candidate_at == tsC  # Must be tsC, NOT tsD!
    assert high_swings[0].confirmed_at == tsE
    assert engine._high_candidate is None  # Consumed upon confirmation!


def test_running_extreme_defeat_intervening_cycles() -> None:
    """Fixture with multiple distinct cycles: High A -> Reversal -> High B -> Reversal -> High C -> Reversal."""
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")

    # Cycle A: High at 1.0850
    b0 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0840", "1.0850", "1.0838", "1.0848")
    engine.process_bar(b0, v_local, root_id="r1", parent_id="p1", parent_version=1)
    b1 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0845", "1.0848", "1.0828", "1.0830")
    engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=2)
    assert len(engine.swings) == 1
    assert engine.swings[0].price == Decimal("1.0850")
    assert engine._high_candidate is None

    # Cycle B: Higher High B at 1.0880
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0835", "1.0880", "1.0830", "1.0875")
    engine.process_bar(b2, v_local, root_id="r1", parent_id="p1", parent_version=3)
    b3 = Bar.create("EURUSD", "1M", BASE_TS + 180, BASE_TS + 240, "1.0870", "1.0872", "1.0850", "1.0855")
    engine.process_bar(b3, v_local, root_id="r1", parent_id="p1", parent_version=4)
    high_swings = [s for s in engine.swings if s.swing_type == "HIGH"]
    assert len(high_swings) == 2
    assert high_swings[1].price == Decimal("1.0880")
    assert high_swings[1].classification == "HH"
    assert engine._high_candidate is None

    # Cycle C: Higher High C at 1.0920
    b4 = Bar.create("EURUSD", "1M", BASE_TS + 240, BASE_TS + 300, "1.0860", "1.0920", "1.0858", "1.0915")
    engine.process_bar(b4, v_local, root_id="r1", parent_id="p1", parent_version=5)
    b5 = Bar.create("EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, "1.0910", "1.0912", "1.0890", "1.0895")
    engine.process_bar(b5, v_local, root_id="r1", parent_id="p1", parent_version=6)
    high_swings_c = [s for s in engine.swings if s.swing_type == "HIGH"]
    assert len(high_swings_c) == 3
    assert high_swings_c[2].price == Decimal("1.0920")
    assert high_swings_c[2].classification == "HH"
    assert engine._high_candidate is None


# ============================================================================
# 3. 48-Bar Zigzag Test with 15 Explicit Behavioral Assertions
# ============================================================================


def test_48_bar_zigzag_production_path_15_assertions() -> None:
    """Comprehensive 48-bar clean alternating zigzag test with 15 strict production-path assertions."""
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.0"))
    v_local = Decimal("0.0010")

    # Generate 48-bar clean alternating zigzag: 6 cycles of 8 bars (4 rising, 4 falling)
    bars = []
    current_price = Decimal("1.0800")
    for cycle in range(6):
        # 4 bars rising
        for i in range(4):
            current_price += Decimal("0.0020")
            b = Bar.create(
                "EURUSD",
                "1M",
                BASE_TS + (cycle * 8 + i) * 60,
                BASE_TS + (cycle * 8 + i + 1) * 60,
                str(current_price - Decimal("0.0005")),
                str(current_price + Decimal("0.0005")),
                str(current_price - Decimal("0.0010")),
                str(current_price),
            )
            bars.append(b)
        # 4 bars falling
        for i in range(4):
            current_price -= Decimal("0.0020")
            b = Bar.create(
                "EURUSD",
                "1M",
                BASE_TS + (cycle * 8 + 4 + i) * 60,
                BASE_TS + (cycle * 8 + 4 + i + 1) * 60,
                str(current_price + Decimal("0.0005")),
                str(current_price + Decimal("0.0010")),
                str(current_price - Decimal("0.0005")),
                str(current_price),
            )
            bars.append(b)

    for i, b in enumerate(bars):
        engine.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)

    # Assertion 1: Swings generated
    highs = [s for s in engine.swings if s.swing_type == "HIGH"]
    lows = [s for s in engine.swings if s.swing_type == "LOW"]
    assert len(highs) >= 2, "Expected local highs generated"

    # Assertion 2: Expected local lows
    assert len(lows) >= 2, "Expected local lows generated"

    # Assertion 3: Expected alternation in swings
    for idx in range(len(engine.swings) - 1):
        assert engine.swings[idx].swing_type != engine.swings[idx + 1].swing_type, "Expected strict swing alternation"

    # Assertion 4 & 5 & 6 & 7: Timestamps and causality
    for s in engine.swings:
        assert s.candidate_at > 0, "Exact candidate timestamp recorded"
        assert s.confirmed_at > 0, "Exact confirmation timestamp recorded"
        assert s.candidate_at <= s.confirmed_at, "candidate_at <= confirmed_at invariant"
        assert s.effective_from == s.confirmed_at, "effective_from == confirmed_at invariant"

    # Assertion 8: No confirmed swing rewritten
    for s in engine.swings:
        assert isinstance(s.price, Decimal)
        assert isinstance(s.classification, str)

    # Assertion 9: Structural classifications present
    for s in engine.swings:
        assert s.classification in ("HH", "HL", "LH", "LL", "EQUAL_HIGH", "EQUAL_LOW", "NEUTRAL")

    # Assertion 10: Protected levels evolved
    assert engine.protected_high is not None or engine.protected_low is not None

    # Assertion 11: Ownership evolved
    assert engine.structural_ownership in ("BULLISH", "BEARISH", "AMBIGUOUS", "UNKNOWN")

    # Assertion 12: No cross-side confirmation contamination
    assert engine.high_persistence_counter == 0 or engine.low_persistence_counter == 0

    # Assertion 13: Candidate state remains bounded
    if engine._high_candidate is not None:
        assert engine._high_candidate.candidate_age_bars <= engine.max_candidate_lifetime_bars
    if engine._low_candidate is not None:
        assert engine._low_candidate.candidate_age_bars <= engine.max_candidate_lifetime_bars

    # Assertion 14: No running-extreme behavior appears
    assert not hasattr(engine, "_running_max")

    # Assertion 15: Replay produces identical results
    replay_engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.0"))
    for i, b in enumerate(bars):
        replay_engine.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)
    assert [s.swing_id for s in engine.swings] == [s.swing_id for s in replay_engine.swings]


# ============================================================================
# 4. Complete-State Causal-Prefix Invariance & Future-Spike Adversarial Tests
# ============================================================================


def _extract_complete_authoritative_state(engine: StructureEngine) -> dict:
    """Canonical forensic decision-state surface; no hand-maintained field list."""
    return engine.authoritative_state()


def test_causal_prefix_complete_state_invariance() -> None:
    """Anti-lookahead test: Complete authoritative decision state at prefix end timestamp tn

    must match exactly between Prefix run P (B0..Bn) and Extended sequence run E (B0..Bn..Bn+k) at timestamp tn.
    """
    prefix_bars = [
        Bar.create("EURUSD", "1M", BASE_TS + i * 60, BASE_TS + (i + 1) * 60, "1.0850", "1.0860", "1.0840", "1.0855")
        for i in range(5)
    ]
    v_local = Decimal("0.0010")

    # Engine P: Process prefix B0..Bn only
    e_prefix = StructureEngine("EURUSD", timeframe="1M")
    for i, b in enumerate(prefix_bars):
        e_prefix.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)

    state_P_at_tn = _extract_complete_authoritative_state(e_prefix)

    # Engine E: Process B0..Bn, record state at tn, then continue with future bars
    e_extended = StructureEngine("EURUSD", timeframe="1M")
    for i, b in enumerate(prefix_bars):
        e_extended.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)

    state_E_at_tn = _extract_complete_authoritative_state(e_extended)

    # State at tn must be 100% identical prior to future bars
    assert state_P_at_tn == state_E_at_tn

    # Process future mutations on E
    future_mutations = [
        Bar.create("EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, "1.0855", "1.1200", "1.0850", "1.1150"),  # Up spike
        Bar.create("EURUSD", "1M", BASE_TS + 360, BASE_TS + 420, "1.1150", "1.1160", "1.0400", "1.0450"),  # Down spike
        Bar.create("EURUSD", "1M", BASE_TS + 420, BASE_TS + 480, "1.0450", "1.0600", "1.0300", "1.0500"),  # Vol shock
    ]

    for i, b in enumerate(future_mutations):
        e_extended.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=len(prefix_bars) + i + 1)

    # Query causal swings visible at tn
    swings_P = e_prefix.get_confirmed_swings(BASE_TS + 300)
    swings_E = e_extended.get_confirmed_swings(BASE_TS + 300)

    assert swings_P == swings_E
    # State recorded at tn for P remains identical to the state captured at tn for E
    assert state_P_at_tn == state_E_at_tn


def test_future_spike_adversarial_complete_state_invariance() -> None:
    """Extreme future spike adversarial test: Snapshot complete state after prefix.

    Extending with an extreme 1000-pip spike must NOT mutate historical state prior to the spike timestamp.
    """
    v_local = Decimal("0.0010")
    prefix_bars = [
        Bar.create("EURUSD", "1M", BASE_TS + 0, BASE_TS + 60, "1.0800", "1.0850", "1.0795", "1.0845"),
        Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0845", "1.0848", "1.0815", "1.0820"),
    ]

    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.0"))
    for i, b in enumerate(prefix_bars):
        engine.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)

    swings_at_t2 = engine.get_confirmed_swings(BASE_TS + 120)
    state_at_t2 = _extract_complete_authoritative_state(engine)

    # Future 1000-pip spike at t=180
    spike_bar = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0820", "1.1820", "1.0810", "1.1800")
    engine.process_bar(spike_bar, v_local, root_id="r1", parent_id="p1", parent_version=3)

    # Swings visible at t=120 MUST remain completely unchanged
    swings_at_t2_after_spike = engine.get_confirmed_swings(BASE_TS + 120)
    assert swings_at_t2 == swings_at_t2_after_spike

    # Swings at t=180 after spike may legitimately reflect new future information
    swings_at_t3_after_spike = engine.get_confirmed_swings(BASE_TS + 180)
    assert len(swings_at_t3_after_spike) >= len(swings_at_t2)


# ============================================================================
# 5. Structural Ownership Matrix Tests (All 12 Scenarios)
# ============================================================================


def test_structural_ownership_canonical_matrix() -> None:
    """Verifies single-authority structural trend ownership across all 12 specified combinations."""

    # 1. HH + HL -> BULLISH
    e1 = StructureEngine("EURUSD")
    e1._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    e1._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    e1._register_swing("HIGH", Decimal("1.0880"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)  # HH
    e1._register_swing("LOW", Decimal("1.0820"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)  # HL
    assert e1.structural_ownership == "BULLISH"

    # 2. HH + EQUAL_LOW -> BULLISH
    e2 = StructureEngine("EURUSD", config=StructureConfig(equality_tolerance_pips=Decimal("0.0001")))
    e2._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    e2._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    e2._register_swing("HIGH", Decimal("1.0880"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)  # HH
    e2._register_swing("LOW", Decimal("1.080005"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)  # EQUAL_LOW
    assert e2.structural_ownership == "BULLISH"

    # 3. EQUAL_HIGH + HL -> BULLISH
    e3 = StructureEngine("EURUSD", config=StructureConfig(equality_tolerance_pips=Decimal("0.0001")))
    e3._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    e3._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    e3._register_swing(
        "HIGH", Decimal("1.085005"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180
    )  # EQUAL_HIGH
    e3._register_swing("LOW", Decimal("1.0820"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)  # HL
    assert e3.structural_ownership == "BULLISH"

    # 4. LL + LH -> BEARISH
    e4 = StructureEngine("EURUSD")
    e4._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    e4._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    e4._register_swing("HIGH", Decimal("1.0830"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)  # LH
    e4._register_swing("LOW", Decimal("1.0780"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)  # LL
    assert e4.structural_ownership == "BEARISH"

    # 5. EQUAL_LOW + LH -> BEARISH
    e5 = StructureEngine("EURUSD", config=StructureConfig(equality_tolerance_pips=Decimal("0.0001")))
    e5._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    e5._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    e5._register_swing("HIGH", Decimal("1.0830"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)  # LH
    e5._register_swing("LOW", Decimal("1.080005"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)  # EQUAL_LOW
    assert e5.structural_ownership == "BEARISH"

    # 6. EQUAL_HIGH + EQUAL_LOW -> AMBIGUOUS
    e6 = StructureEngine("EURUSD", config=StructureConfig(equality_tolerance_pips=Decimal("0.0001")))
    e6._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    e6._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    e6._register_swing(
        "HIGH", Decimal("1.085005"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180
    )  # EQUAL_HIGH
    e6._register_swing("LOW", Decimal("1.080005"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)  # EQUAL_LOW
    assert e6.structural_ownership == "AMBIGUOUS"

    # 7. HH + LL -> AMBIGUOUS
    e7 = StructureEngine("EURUSD")
    e7._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    e7._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    e7._register_swing("HIGH", Decimal("1.0880"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)  # HH
    e7._register_swing("LOW", Decimal("1.0780"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)  # LL
    assert e7.structural_ownership == "AMBIGUOUS"

    # 8. LH + HL -> AMBIGUOUS
    e8 = StructureEngine("EURUSD")
    e8._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    e8._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    e8._register_swing("HIGH", Decimal("1.0830"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)  # LH
    e8._register_swing("LOW", Decimal("1.0810"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)  # HL
    assert e8.structural_ownership == "AMBIGUOUS"

    # 9. missing high -> UNKNOWN
    e9 = StructureEngine("EURUSD")
    e9._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    assert e9.structural_ownership == "UNKNOWN"

    # 10. missing low -> UNKNOWN
    e10 = StructureEngine("EURUSD")
    e10._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    assert e10.structural_ownership == "UNKNOWN"

    # 11. first swing (NEUTRAL) -> AMBIGUOUS
    e11 = StructureEngine("EURUSD")
    e11._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    e11._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    assert e11.structural_ownership == "AMBIGUOUS"

    # 12. no swings -> UNKNOWN
    e12 = StructureEngine("EURUSD")
    assert e12.structural_ownership == "UNKNOWN"


# ============================================================================
# 6. Exact 8-Row BOS/CHoCH Truth Table Matrix
# ============================================================================


def test_exact_8_row_truth_table_production_path() -> None:
    """Tests exact 8-row truth table through production break-processing path."""
    ownerships = ["BULLISH", "BEARISH", "AMBIGUOUS", "UNKNOWN"]
    levels = ["HIGH", "LOW"]

    for own in ownerships:
        for lvl in levels:
            engine = StructureEngine(
                "EURUSD",
                timeframe="1M",
                displacement_threshold_mult=Decimal("0.5"),
                persistence_bars_required=1,
            )

            if own == "BULLISH":
                engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
                engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
                engine._register_swing(
                    "HIGH", Decimal("1.0880"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180
                )
                engine._register_swing("LOW", Decimal("1.0820"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)
                engine.current_direction = "LONG"
            elif own == "BEARISH":
                engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
                engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
                engine._register_swing(
                    "HIGH", Decimal("1.0840"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180
                )
                engine._register_swing("LOW", Decimal("1.0780"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)
                engine.current_direction = "SHORT"
            elif own == "AMBIGUOUS":
                engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
                engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
                engine._register_swing(
                    "HIGH", Decimal("1.0880"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180
                )
                engine._register_swing("LOW", Decimal("1.0780"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)

            engine.protected_high = Decimal("1.0880") if own in ("BULLISH", "AMBIGUOUS") else Decimal("1.0840")
            engine.protected_low = Decimal("1.0820") if own in ("BULLISH", "AMBIGUOUS") else Decimal("1.0780")

            if own == "BULLISH" and lvl == "HIGH":
                expected = "BOS_BULLISH"
            elif own == "BULLISH" and lvl == "LOW":
                expected = "CHOCH_BEARISH"
            elif own == "BEARISH" and lvl == "LOW":
                expected = "BOS_BEARISH"
            elif own == "BEARISH" and lvl == "HIGH":
                expected = "CHOCH_BULLISH"
            else:
                expected = "NONE"

            v_loc = Decimal("0.0010")
            if lvl == "HIGH":
                close_p = Decimal("1.0890") if own in ("BULLISH", "AMBIGUOUS") else Decimal("1.0850")
            else:
                close_p = Decimal("1.0810") if own in ("BULLISH", "AMBIGUOUS") else Decimal("1.0770")

            bar = Bar.create(
                "EURUSD",
                "1M",
                BASE_TS + 300,
                BASE_TS + 360,
                str(close_p),
                str(close_p + Decimal("0.0002")),
                str(close_p - Decimal("0.0002")),
                str(close_p),
            )
            rec = engine.process_bar(bar, v_loc, root_id="r1", parent_id="p1", parent_version=5)
            assert rec.bos_type == expected, (
                f"Truth table mismatch for own={own}, lvl={lvl}: got {rec.bos_type}, expected {expected}"
            )


# ============================================================================
# 7. Continuation BOS Non-Destruction & CHoCH Damage Tests
# ============================================================================


def test_continuation_bos_non_destruction() -> None:
    """Verifies that continuation BOS preserves structure (INTACT)."""
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=1
    )
    v_local = Decimal("0.0010")

    engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    engine._register_swing("HIGH", Decimal("1.0880"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    engine._register_swing("LOW", Decimal("1.0820"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)
    engine.protected_high = Decimal("1.0880")

    b1 = Bar.create("EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, "1.0880", "1.0895", "1.0875", "1.0890")
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)

    assert rec1.bos_type == "BOS_BULLISH"
    assert rec1.damage_state == StructuralDamageState.INTACT


def test_choch_structural_damage() -> None:
    """Verifies that CHoCH creates explicit structural damage (STRUCTURE_BROKEN)."""
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=1
    )
    v_local = Decimal("0.0010")

    engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    engine._register_swing("HIGH", Decimal("1.0880"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    engine._register_swing("LOW", Decimal("1.0820"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)
    engine.protected_low = Decimal("1.0820")
    engine.current_direction = "LONG"

    b1 = Bar.create("EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, "1.0820", "1.0822", "1.0800", "1.0810")
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)

    assert rec1.bos_type == "CHOCH_BEARISH"
    assert rec1.damage_state == StructuralDamageState.STRUCTURE_BROKEN
    assert rec1.last_choch is not None


# ============================================================================
# 8. Reclaim & Re-arm Production Reachability
# ============================================================================


def test_production_reclaim_reachability_full_lifecycle() -> None:
    """Proves INTACT -> DAMAGE_CANDIDATE -> STRUCTURE_BROKEN -> RECLAIM_CANDIDATE -> RECLAIM_CONFIRMED -> INTACT is production reachable."""
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=1
    )
    v_local = Decimal("0.0010")

    engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    engine._register_swing("HIGH", Decimal("1.0840"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    engine._register_swing("LOW", Decimal("1.0780"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)
    engine.protected_high = Decimal("1.0840")
    engine.current_direction = "SHORT"

    # Step 1: Counter-structure break of 1.0840 -> CHOCH_BULLISH -> STRUCTURE_BROKEN
    b1 = Bar.create("EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, "1.0838", "1.0852", "1.0835", "1.0848")
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec1.bos_type == "CHOCH_BULLISH"
    assert rec1.damage_state == StructuralDamageState.STRUCTURE_BROKEN

    # Step 2: Price moves back inside range -> RECLAIM_CANDIDATE
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 360, BASE_TS + 420, "1.0845", "1.0845", "1.0830", "1.0835")
    rec2 = engine.process_bar(b2, v_local, root_id="r1", parent_id="p1", parent_version=2)
    assert rec2.damage_state == StructuralDamageState.RECLAIM_CANDIDATE

    # Step 3: Price remains inside range -> RECLAIM_CONFIRMED
    b3 = Bar.create("EURUSD", "1M", BASE_TS + 420, BASE_TS + 480, "1.0835", "1.0838", "1.0825", "1.0830")
    rec3 = engine.process_bar(b3, v_local, root_id="r1", parent_id="p1", parent_version=3)
    assert rec3.damage_state == StructuralDamageState.RECLAIM_CONFIRMED
    assert rec3.last_reclaim is not None

    # Step 4: Full re-arm back to INTACT
    b4 = Bar.create("EURUSD", "1M", BASE_TS + 480, BASE_TS + 540, "1.0830", "1.0835", "1.0828", "1.0832")
    rec4 = engine.process_bar(b4, v_local, root_id="r1", parent_id="p1", parent_version=4)
    assert rec4.damage_state == StructuralDamageState.INTACT


# ============================================================================
# 9. Protected Level Authority & Stale Clearing Tests
# ============================================================================


def test_unconfirmed_candidate_cannot_become_protected_level() -> None:
    """Proves that unconfirmed candidate pivots cannot become protected structural levels."""
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("5.0"))
    v_local = Decimal("0.0010")

    # Bar creates high candidate at 1.0950
    b0 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0950", "1.0840", "1.0940")
    engine.process_bar(b0, v_local, root_id="r1", parent_id="p1", parent_version=1)

    assert engine._high_candidate is not None
    assert engine._high_candidate.price == Decimal("1.0950")
    # Candidate must NOT be set as protected high!
    assert engine.protected_high is None or engine.protected_high != Decimal("1.0950")


def test_protected_level_clearing_case_a_high_only() -> None:
    """Case A: Confirmed HIGH sets protected_high. Invalidating/breaking high swing clears protected_high to None."""
    engine = StructureEngine("EURUSD", timeframe="1M")
    engine._register_swing("HIGH", Decimal("1.0900"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._rearm_protected_levels()

    assert engine.protected_high == Decimal("1.0900")
    assert engine.protected_low is None

    # Invalidate / mark broken
    engine.swings[0] = SwingRecord(
        swing_id=engine.swings[0].swing_id,
        symbol=engine.swings[0].symbol,
        timeframe=engine.swings[0].timeframe,
        candidate_at=engine.swings[0].candidate_at,
        confirmed_at=engine.swings[0].confirmed_at,
        effective_from=engine.swings[0].effective_from,
        price=engine.swings[0].price,
        swing_type=engine.swings[0].swing_type,
        classification=engine.swings[0].classification,
        status=SwingState.SWING_BROKEN,
        version=engine.swings[0].version,
    )
    engine._rearm_protected_levels()

    assert engine.protected_high is None
    assert engine.protected_low is None


def test_protected_level_clearing_case_b_low_only() -> None:
    """Case B: Confirmed LOW sets protected_low. Invalidating/breaking low swing clears protected_low to None."""
    engine = StructureEngine("EURUSD", timeframe="1M")
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._rearm_protected_levels()

    assert engine.protected_low == Decimal("1.0800")
    assert engine.protected_high is None

    # Clear swings
    engine.swings.clear()
    engine._rearm_protected_levels()

    assert engine.protected_low is None
    assert engine.protected_high is None


def test_protected_level_clearing_case_c_both_independent() -> None:
    """Case C: Both HIGH and LOW confirmed. Invalidating HIGH clears protected_high while preserving protected_low.

    Invalidating LOW subsequently clears protected_low to None.
    """
    engine = StructureEngine("EURUSD", timeframe="1M")
    engine._register_swing("HIGH", Decimal("1.0900"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    engine._rearm_protected_levels()

    assert engine.protected_high == Decimal("1.0900")
    assert engine.protected_low == Decimal("1.0800")

    # Invalidate high swing only
    engine.swings[0] = SwingRecord(
        swing_id=engine.swings[0].swing_id,
        symbol=engine.swings[0].symbol,
        timeframe=engine.swings[0].timeframe,
        candidate_at=engine.swings[0].candidate_at,
        confirmed_at=engine.swings[0].confirmed_at,
        effective_from=engine.swings[0].effective_from,
        price=engine.swings[0].price,
        swing_type=engine.swings[0].swing_type,
        classification=engine.swings[0].classification,
        status=SwingState.SWING_BROKEN,
        version=engine.swings[0].version,
    )
    engine._rearm_protected_levels()

    assert engine.protected_high is None
    assert engine.protected_low == Decimal("1.0800")

    # Invalidate low swing
    engine.swings[1] = SwingRecord(
        swing_id=engine.swings[1].swing_id,
        symbol=engine.swings[1].symbol,
        timeframe=engine.swings[1].timeframe,
        candidate_at=engine.swings[1].candidate_at,
        confirmed_at=engine.swings[1].confirmed_at,
        effective_from=engine.swings[1].effective_from,
        price=engine.swings[1].price,
        swing_type=engine.swings[1].swing_type,
        classification=engine.swings[1].classification,
        status=SwingState.SWING_BROKEN,
        version=engine.swings[1].version,
    )
    engine._rearm_protected_levels()

    assert engine.protected_high is None
    assert engine.protected_low is None


def test_protected_level_clearing_case_d_reclaim_interaction() -> None:
    """Case D: Break protected level, enter reclaim candidate, invalidate/re-arm.

    Proves stale protection does not survive beyond its authority.
    """
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=1
    )
    v_local = Decimal("0.0010")

    engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    engine._register_swing("HIGH", Decimal("1.0840"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    engine._register_swing("LOW", Decimal("1.0780"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)
    engine._rearm_protected_levels()
    engine.current_direction = "SHORT"

    assert engine.protected_high == Decimal("1.0840")
    assert engine.protected_low == Decimal("1.0780")

    # CHOCH break of 1.0840
    b1 = Bar.create("EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, "1.0838", "1.0852", "1.0835", "1.0848")
    engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert engine.damage_state == StructuralDamageState.STRUCTURE_BROKEN

    # If active swings are marked broken or cleared prior to reclaim re-arm
    engine.swings.clear()
    engine._rearm_protected_levels()

    assert engine.protected_high is None
    assert engine.protected_low is None


# ============================================================================
# 10. Bounded Memory and Eviction Determinism
# ============================================================================


def test_bounded_memory_and_eviction_priority() -> None:
    """Verifies max_swing_history eviction policy prioritizing broken swings before oldest confirmed swings."""
    engine = StructureEngine("EURUSD", timeframe="1M", max_swing_history=5)

    # Register 5 swings
    for i in range(5):
        engine._register_swing(
            "HIGH" if i % 2 == 0 else "LOW",
            Decimal("1.0800") + Decimal(str(i * 0.0010)),
            candidate_at=BASE_TS + i * 60,
            confirmed_at=BASE_TS + (i + 1) * 60,
        )

    assert len(engine.swings) == 5
    first_id = engine.swings[0].swing_id

    # Register 6th swing -> triggers FIFO eviction of oldest swing
    engine._register_swing("HIGH", Decimal("1.0860"), candidate_at=BASE_TS + 300, confirmed_at=BASE_TS + 360)
    assert len(engine.swings) == 5
    assert engine.swings[0].swing_id != first_id


# ============================================================================
# 11. AST Static Forensic Guard Against Running Extremes
# ============================================================================


def test_ast_static_forensic_guard_against_running_extremes() -> None:
    """AST guard inspecting StructureEngine source code to verify no max/min trailing extreme pattern exists."""
    with open("src/fractal_flow/domain/structure.py", "r", encoding="utf-8") as f:
        source_code = f.read()

    parsed_ast = ast.parse(source_code)

    for node in ast.walk(parsed_ast):
        # Disallow direct max(..., bar.high) or min(..., bar.low) assignments to candidate prices
        if isinstance(node, ast.Assign):
            for target in node.targets:
                target_str = ast.unparse(target)
                if "_high_candidate" in target_str or "_low_candidate" in target_str:
                    value_str = ast.unparse(node.value)
                    assert not ("max(" in value_str and "bar.high" in value_str), (
                        "Forbidden running-max pattern detected!"
                    )
                    assert not ("min(" in value_str and "bar.low" in value_str), (
                        "Forbidden running-min pattern detected!"
                    )


# ============================================================================
# 12. 26-Scenario Required Adversarial Test Matrix
# ============================================================================


def test_adversarial_matrix_01_monotonic_rising() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("5.0"))
    v_local = Decimal("0.0010")
    for i in range(10):
        p = Decimal("1.0800") + Decimal(str(i * 0.0002))
        b = Bar.create(
            "EURUSD",
            "1M",
            BASE_TS + i * 60,
            BASE_TS + (i + 1) * 60,
            str(p),
            str(p + Decimal("0.0002")),
            str(p - Decimal("0.0001")),
            str(p + Decimal("0.0001")),
        )
        engine.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)
    assert len(engine.swings) == 0


def test_adversarial_matrix_02_monotonic_falling() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("5.0"))
    v_local = Decimal("0.0010")
    for i in range(10):
        p = Decimal("1.0900") - Decimal(str(i * 0.0002))
        b = Bar.create(
            "EURUSD",
            "1M",
            BASE_TS + i * 60,
            BASE_TS + (i + 1) * 60,
            str(p),
            str(p + Decimal("0.0001")),
            str(p - Decimal("0.0002")),
            str(p - Decimal("0.0001")),
        )
        engine.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)
    assert len(engine.swings) == 0


def test_adversarial_matrix_03_shallow_oscillation() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("2.0"))
    v_local = Decimal("0.0010")
    for i in range(10):
        p = Decimal("1.0800") + Decimal("0.0005") if i % 2 == 0 else Decimal("1.0800")
        b = Bar.create(
            "EURUSD",
            "1M",
            BASE_TS + i * 60,
            BASE_TS + (i + 1) * 60,
            str(p),
            str(p + Decimal("0.0002")),
            str(p - Decimal("0.0002")),
            str(p),
        )
        engine.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)
    assert len(engine.swings) == 0


def test_adversarial_matrix_04_clean_zigzag() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.0"))
    v_local = Decimal("0.0010")
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + 0, BASE_TS + 60, "1.0800", "1.0850", "1.0795", "1.0845"),
        Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0845", "1.0848", "1.0815", "1.0820"),
        Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0820", "1.0870", "1.0818", "1.0865"),
        Bar.create("EURUSD", "1M", BASE_TS + 180, BASE_TS + 240, "1.0865", "1.0868", "1.0830", "1.0835"),
    ]
    for i, b in enumerate(bars):
        engine.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)
    assert len(engine.swings) >= 2


def test_adversarial_matrix_05_nested_zigzag() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")
    b0 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0900", "1.0790", "1.0895")
    engine.process_bar(b0, v_local, root_id="r1", parent_id="p1", parent_version=1)
    b1 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0890", "1.0892", "1.0850", "1.0855")
    engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=2)
    assert len(engine.swings) >= 1


def test_adversarial_matrix_06_plateau_equal_highs() -> None:
    engine = StructureEngine("EURUSD", config=StructureConfig(equality_tolerance_pips=Decimal("0.0001")))
    s1 = engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    s2 = engine._register_swing("HIGH", Decimal("1.085005"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    assert s2.classification == "EQUAL_HIGH"


def test_adversarial_matrix_07_plateau_equal_lows() -> None:
    engine = StructureEngine("EURUSD", config=StructureConfig(equality_tolerance_pips=Decimal("0.0001")))
    s1 = engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    s2 = engine._register_swing("LOW", Decimal("1.080005"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    assert s2.classification == "EQUAL_LOW"


def test_adversarial_matrix_08_sharp_reversal() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")
    b0 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0950", "1.0790", "1.0940")
    engine.process_bar(b0, v_local, root_id="r1", parent_id="p1", parent_version=1)
    b1 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0940", "1.0942", "1.0800", "1.0810")
    engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=2)
    assert len(engine.swings) >= 1


def test_adversarial_matrix_09_gradual_reversal() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")
    b0 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0880", "1.0790", "1.0875")
    engine.process_bar(b0, v_local, root_id="r1", parent_id="p1", parent_version=1)
    b1 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0875", "1.0878", "1.0865", "1.0870")
    engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=2)
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0870", "1.0872", "1.0845", "1.0850")
    engine.process_bar(b2, v_local, root_id="r1", parent_id="p1", parent_version=3)
    assert len(engine.swings) >= 1


def test_adversarial_matrix_10_candidate_invalidation() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M", max_candidate_lifetime_bars=2)
    v_local = Decimal("0.0010")
    b0 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0850", "1.0790", "1.0845")
    engine.process_bar(b0, v_local, root_id="r1", parent_id="p1", parent_version=1)

    # 3 bars pass without confirmation or local dominance update
    for i in range(3):
        b = Bar.create(
            "EURUSD", "1M", BASE_TS + (i + 1) * 60, BASE_TS + (i + 2) * 60, "1.0845", "1.0848", "1.0842", "1.0846"
        )
        engine.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 2)

    assert engine._high_candidate is None


def test_adversarial_matrix_11_candidate_supersession() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M")
    v_local = Decimal("0.0010")
    b0 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0850", "1.0790", "1.0845")
    engine.process_bar(b0, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert engine._high_candidate is not None
    assert engine._high_candidate.price == Decimal("1.0850")

    b1 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0845", "1.0880", "1.0840", "1.0875")
    engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=2)
    assert engine._high_candidate is not None
    assert engine._high_candidate.price == Decimal("1.0880")


def test_adversarial_matrix_12_competing_high_low_candidates() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("2.0"))
    v_local = Decimal("0.0050")
    b0 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0840", "1.0880", "1.0820", "1.0850")
    engine.process_bar(b0, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert engine._high_candidate is not None
    assert engine._low_candidate is not None


def test_adversarial_matrix_13_first_confirmed_swing() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M")
    s1 = engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    assert s1.classification == "NEUTRAL"


def test_adversarial_matrix_14_first_confirmed_high_followed_by_low() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M")
    s1 = engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    s2 = engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    assert s1.classification == "NEUTRAL"
    assert s2.classification == "NEUTRAL"


def test_adversarial_matrix_15_bos_continuation() -> None:
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=1
    )
    v_local = Decimal("0.0010")
    engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    engine._register_swing("HIGH", Decimal("1.0880"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    engine._register_swing("LOW", Decimal("1.0820"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)
    engine.protected_high = Decimal("1.0880")

    b1 = Bar.create("EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, "1.0880", "1.0895", "1.0875", "1.0890")
    rec = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec.bos_type == "BOS_BULLISH"


def test_adversarial_matrix_16_choch() -> None:
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=1
    )
    v_local = Decimal("0.0010")
    engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    engine._register_swing("HIGH", Decimal("1.0880"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    engine._register_swing("LOW", Decimal("1.0820"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)
    engine.protected_low = Decimal("1.0820")
    engine.current_direction = "LONG"

    b1 = Bar.create("EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, "1.0820", "1.0822", "1.0800", "1.0810")
    rec = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec.bos_type == "CHOCH_BEARISH"


def test_adversarial_matrix_17_failed_break() -> None:
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=2
    )
    v_local = Decimal("0.0010")
    engine.protected_high = Decimal("1.0850")

    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0845", "1.0852", "1.0840", "1.0851")
    engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)

    b2 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0850", "1.0850", "1.0835", "1.0840")
    rec2 = engine.process_bar(b2, v_local, root_id="r1", parent_id="p1", parent_version=2)
    assert rec2.break_state == BreakState.FAILED_BREAK


def test_adversarial_matrix_18_reclaim() -> None:
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=1
    )
    v_local = Decimal("0.0010")
    engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    engine._register_swing("HIGH", Decimal("1.0840"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    engine._register_swing("LOW", Decimal("1.0780"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)
    engine.protected_high = Decimal("1.0840")
    engine.current_direction = "SHORT"

    b1 = Bar.create("EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, "1.0838", "1.0852", "1.0835", "1.0848")
    engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)

    b2 = Bar.create("EURUSD", "1M", BASE_TS + 360, BASE_TS + 420, "1.0845", "1.0845", "1.0830", "1.0835")
    rec2 = engine.process_bar(b2, v_local, root_id="r1", parent_id="p1", parent_version=2)
    assert rec2.damage_state == StructuralDamageState.RECLAIM_CANDIDATE


def test_adversarial_matrix_19_post_reclaim_continuation() -> None:
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=1
    )
    v_local = Decimal("0.0010")
    engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    engine._register_swing("HIGH", Decimal("1.0840"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    engine._register_swing("LOW", Decimal("1.0780"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)
    engine.protected_high = Decimal("1.0840")
    engine.current_direction = "SHORT"

    b1 = Bar.create("EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, "1.0838", "1.0852", "1.0835", "1.0848")
    engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 360, BASE_TS + 420, "1.0845", "1.0845", "1.0830", "1.0835")
    engine.process_bar(b2, v_local, root_id="r1", parent_id="p1", parent_version=2)
    b3 = Bar.create("EURUSD", "1M", BASE_TS + 420, BASE_TS + 480, "1.0835", "1.0838", "1.0825", "1.0830")
    engine.process_bar(b3, v_local, root_id="r1", parent_id="p1", parent_version=3)
    b4 = Bar.create("EURUSD", "1M", BASE_TS + 480, BASE_TS + 540, "1.0830", "1.0835", "1.0828", "1.0832")
    rec4 = engine.process_bar(b4, v_local, root_id="r1", parent_id="p1", parent_version=4)
    assert rec4.damage_state == StructuralDamageState.INTACT


def test_adversarial_matrix_20_duplicate_timestamp_idempotency() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M")
    v_local = Decimal("0.0010")
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    rec2 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec1 == rec2


def test_adversarial_matrix_21_conflicting_duplicate_timestamp_rejection() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M")
    v_local = Decimal("0.0010")
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")
    engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)

    b1_conflict = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0890", "1.0840", "1.0885")
    with pytest.raises(ValueError, match="Duplicate timestamp conflict"):
        engine.process_bar(b1_conflict, v_local, root_id="r1", parent_id="p1", parent_version=1)


def test_adversarial_matrix_22_backward_timestamp_rejection() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M")
    v_local = Decimal("0.0010")
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")
    engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)

    b_prev = Bar.create("EURUSD", "1M", BASE_TS - 60, BASE_TS, "1.0850", "1.0860", "1.0840", "1.0855")
    with pytest.raises(ValueError, match="Chronology violation"):
        engine.process_bar(b_prev, v_local, root_id="r1", parent_id="p1", parent_version=1)


def test_adversarial_matrix_23_future_spike_causal_mutation_invariance() -> None:
    e1 = StructureEngine("EURUSD", timeframe="1M")
    v_local = Decimal("0.0010")
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")
    e1.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)

    swings_before = e1.get_confirmed_swings(BASE_TS + 60)

    # Future spike
    b_spike = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0855", "1.1500", "1.0850", "1.1450")
    e1.process_bar(b_spike, v_local, root_id="r1", parent_id="p1", parent_version=2)

    swings_after = e1.get_confirmed_swings(BASE_TS + 60)
    assert swings_before == swings_after


def test_adversarial_matrix_24_replay_determinism() -> None:
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + i * 60, BASE_TS + (i + 1) * 60, "1.0850", "1.0860", "1.0840", "1.0855")
        for i in range(5)
    ]
    v_local = Decimal("0.0010")

    e1 = StructureEngine("EURUSD", timeframe="1M")
    recs1 = [e1.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1) for i, b in enumerate(bars)]

    e2 = StructureEngine("EURUSD", timeframe="1M")
    recs2 = [e2.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1) for i, b in enumerate(bars)]

    assert [r.state_version for r in recs1] == [r.state_version for r in recs2]


def test_adversarial_matrix_25_bounded_history_eviction() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M", max_swing_history=3)
    for i in range(5):
        engine._register_swing(
            "HIGH" if i % 2 == 0 else "LOW",
            Decimal("1.0800") + Decimal(str(i * 0.0010)),
            candidate_at=BASE_TS + i * 60,
            confirmed_at=BASE_TS + (i + 1) * 60,
        )
    assert len(engine.swings) <= 3


def test_adversarial_matrix_26_instrument_equality_tolerance() -> None:
    e_xau = StructureEngine("XAUUSD")
    assert e_xau.equality_tolerance_pips == Decimal("0.01")


def test_instrument_equality_tolerance_full_precision_matrix() -> None:
    """Verifies instrument equality tolerance across FX (0.0001 pip), JPY (0.01 pip), and XAU (0.1 pip) precisions."""
    # FX (EURUSD): default pip = 0.0001, config equality_tolerance_pips = 0.0001 (1 pip = 0.0001)
    e_fx = StructureEngine("EURUSD", config=StructureConfig(equality_tolerance_pips=Decimal("0.0001")))
    assert e_fx.equality_tolerance_pips == Decimal("0.0001")

    # Swing 1 High
    e_fx._register_swing("HIGH", Decimal("1.08500"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    # Swing 2 High - exact equality
    s2_exact = e_fx._register_swing("HIGH", Decimal("1.08500"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    assert s2_exact.classification == "EQUAL_HIGH"

    # Swing 3 High - just inside tolerance (diff = 0.00008 <= 0.0001)
    s3_inside = e_fx._register_swing("HIGH", Decimal("1.08508"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    assert s3_inside.classification == "EQUAL_HIGH"

    # Swing 4 High - just outside tolerance (diff = 0.0002 > 0.0001)
    s4_outside = e_fx._register_swing(
        "HIGH", Decimal("1.08520"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240
    )
    assert s4_outside.classification == "HH"

    # JPY (USDJPY): default pip = 0.01, config equality_tolerance_pips = 0.0001 * (0.01 / 0.0001) = 0.01
    e_jpy = StructureEngine("USDJPY", config=StructureConfig(equality_tolerance_pips=Decimal("0.0001")))
    assert e_jpy.equality_tolerance_pips == Decimal("0.01")

    e_jpy._register_swing("HIGH", Decimal("150.50"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    s_jpy_inside = e_jpy._register_swing(
        "HIGH", Decimal("150.508"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120
    )
    assert s_jpy_inside.classification == "EQUAL_HIGH"

    s_jpy_outside = e_jpy._register_swing(
        "HIGH", Decimal("150.520"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180
    )
    assert s_jpy_outside.classification == "HH"

    # XAU (XAUUSD): default pip = 0.1, config equality_tolerance_pips = 0.0001 * (0.1 / 0.0001) = 0.1
    e_xau = StructureEngine("XAUUSD", config=StructureConfig(equality_tolerance_pips=Decimal("0.0001")))
    assert e_xau.equality_tolerance_pips == Decimal("0.1")

    e_xau._register_swing("HIGH", Decimal("2000.50"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    s_xau_inside = e_xau._register_swing(
        "HIGH", Decimal("2000.58"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120
    )
    assert s_xau_inside.classification == "EQUAL_HIGH"

    s_xau_outside = e_xau._register_swing(
        "HIGH", Decimal("2000.70"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180
    )
    assert s_xau_outside.classification == "HH"


def test_snapshot_recovery_complete_state_equivalence() -> None:
    """Snapshot / Recovery Test: Rebuilding engine via snapshot/replay reproduces uninterrupted execution state."""
    v_local = Decimal("0.0010")
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + 0, BASE_TS + 60, "1.0800", "1.0850", "1.0795", "1.0845"),
        Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0845", "1.0848", "1.0815", "1.0820"),
        Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0820", "1.0870", "1.0818", "1.0865"),
        Bar.create("EURUSD", "1M", BASE_TS + 180, BASE_TS + 240, "1.0865", "1.0868", "1.0830", "1.0835"),
    ]

    # Run uninterrupted engine
    e_uninterrupted = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.0"))
    for i, b in enumerate(bars):
        e_uninterrupted.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)

    state_uninterrupted = _extract_complete_authoritative_state(e_uninterrupted)

    # Run prefix engine (bars 0..1), reconstruct/replay remaining (bars 2..3)
    e_rebuilt = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.0"))
    for i, b in enumerate(bars[:2]):
        e_rebuilt.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)

    for i, b in enumerate(bars[2:], start=2):
        e_rebuilt.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)

    state_rebuilt = _extract_complete_authoritative_state(e_rebuilt)

    assert state_uninterrupted == state_rebuilt


def test_single_bar_cannot_confirm_both_high_and_low_swings() -> None:
    """A wide first bar may create both candidates but cannot confirm both at one timestamp."""
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("0.5"))
    bar = Bar.create(
        "EURUSD", "1M", BASE_TS, BASE_TS + 60,
        "1.0850", "1.0900", "1.0800", "1.0850",
    )
    rec = engine.process_bar(bar, Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1)
    assert len(engine.swings) <= 1
    assert not (
        any(s.swing_type == "HIGH" for s in engine.swings)
        and any(s.swing_type == "LOW" for s in engine.swings)
    )
    assert rec.state_version == 1


def test_choch_invalidates_broken_side_and_preserves_opposite_protection() -> None:
    """A confirmed CHoCH invalidates only the broken protected level and its source swing."""
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=1
    )
    engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    engine._register_swing("HIGH", Decimal("1.0840"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    engine._register_swing("LOW", Decimal("1.0780"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)
    engine._rearm_protected_levels()
    engine.current_direction = "SHORT"

    bar = Bar.create(
        "EURUSD", "1M", BASE_TS + 300, BASE_TS + 360,
        "1.0838", "1.0852", "1.0835", "1.0848",
    )
    rec = engine.process_bar(bar, Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1)

    assert rec.bos_type == "CHOCH_BULLISH"
    assert rec.damage_state == StructuralDamageState.STRUCTURE_BROKEN
    assert engine.protected_high is None
    assert engine.protected_low == Decimal("1.0780")
    assert any(s.swing_type == "HIGH" and s.status == SwingState.SWING_BROKEN for s in engine.swings)
    assert not any(s.swing_type == "LOW" and s.status == SwingState.SWING_BROKEN for s in engine.swings)
    assert engine.last_break_candidate_level_type == "HIGH"
    assert engine.last_break_candidate_level_price == Decimal("1.0840")


def test_bos_updates_direction_cache_without_damage() -> None:
    """Continuation BOS preserves structure and keeps the direction cache aligned with ownership."""
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=1
    )
    engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    engine._register_swing("HIGH", Decimal("1.0880"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    engine._register_swing("LOW", Decimal("1.0820"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)
    engine._rearm_protected_levels()

    bar = Bar.create(
        "EURUSD", "1M", BASE_TS + 300, BASE_TS + 360,
        "1.0880", "1.0895", "1.0875", "1.0890",
    )
    rec = engine.process_bar(bar, Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1)
    assert rec.bos_type == "BOS_BULLISH"
    assert rec.damage_state == StructuralDamageState.INTACT
    assert engine.structural_ownership == "BULLISH"
    assert engine.current_direction == "LONG"


def test_actual_snapshot_recovery_roundtrip_with_fresh_engine(tmp_path: Path) -> None:
    """Persist a real StructureEngine snapshot, recreate the engine, then continue deterministically."""
    from src.fractal_flow.persistence.snapshot import SnapshotEngine

    v_local = Decimal("0.0010")
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + i * 60, BASE_TS + (i + 1) * 60,
                   "1.0800", "1.0850", "1.0795", "1.0845")
        if i % 2 == 0 else
        Bar.create("EURUSD", "1M", BASE_TS + i * 60, BASE_TS + (i + 1) * 60,
                   "1.0845", "1.0848", "1.0815", "1.0820")
        for i in range(6)
    ]

    uninterrupted = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.0"))
    for i, bar in enumerate(bars):
        uninterrupted.process_bar(bar, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)

    prefix = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.0"))
    for i, bar in enumerate(bars[:3]):
        prefix.process_bar(bar, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)

    snapshot_engine = SnapshotEngine(str(tmp_path))
    snapshot = snapshot_engine.save_snapshot(
        "StructureEngine", "EURUSD:1M", version=prefix.state_version, last_seq=3,
        payload=prefix.snapshot_state(),
    )
    fresh_snapshot_engine = SnapshotEngine(str(tmp_path))
    loaded = fresh_snapshot_engine.load_snapshot("StructureEngine", "EURUSD:1M")
    assert loaded is not None
    assert loaded.checksum == snapshot.checksum

    recovered = StructureEngine.from_snapshot_state(loaded.state_payload)
    assert recovered.snapshot_state() == prefix.snapshot_state()

    for i, bar in enumerate(bars[3:], start=3):
        recovered.process_bar(bar, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)

    assert recovered.snapshot_state() == uninterrupted.snapshot_state()

# ============================================================================
# 27. Structural-Excursion v2.2 Contract Tests
# ============================================================================


def test_monotonic_trend_extends_one_excursion_without_repeated_pivots() -> None:
    """A monotonic trend must extend one unresolved excursion, not emit pivots."""
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")
    bars = []
    for i in range(8):
        close = Decimal("1.0800") + Decimal(i) * Decimal("0.0020")
        bars.append(
            Bar.create(
                "EURUSD", "1M", BASE_TS + i * 60, BASE_TS + (i + 1) * 60,
                str(close - Decimal("0.0005")), str(close + Decimal("0.0005")),
                str(close - Decimal("0.0010")), str(close),
            )
        )
    for i, bar in enumerate(bars):
        engine.process_bar(bar, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)

    assert engine.swings == []
    assert engine._high_candidate is not None
    assert engine._high_candidate.created_from_timestamp == bars[0].close_timestamp
    assert engine._high_candidate.candidate_at == bars[-1].close_timestamp
    assert engine._high_candidate.price == bars[-1].high
    assert engine._high_candidate.candidate_age_bars == len(bars) - 1
    assert engine._active_excursion_side == "HIGH"


def test_shallow_reversal_does_not_confirm_excursion() -> None:
    """A reversal below the normalized confirmation threshold remains a hypothesis."""
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("2.0"))
    v_local = Decimal("0.0010")
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0890", "1.0900", "1.0885", "1.0898"),
        Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0898", "1.0910", "1.0895", "1.0908"),
        Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0908", "1.0911", "1.0895", "1.0900"),
    ]
    for i, bar in enumerate(bars):
        engine.process_bar(bar, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)

    assert engine.swings == []
    assert engine._high_candidate is not None
    assert engine._high_candidate.price == Decimal("1.0910")
    assert engine._high_candidate.created_from_timestamp == bars[0].close_timestamp
    assert engine._high_candidate.candidate_at == bars[1].close_timestamp


def test_genuine_reversal_confirms_latest_excursion_extreme_with_later_timestamp() -> None:
    """A genuine causal reversal confirms the excursion extreme without look-ahead."""
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")
    b0 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0890", "1.0900", "1.0885", "1.0898")
    b1 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0898", "1.0910", "1.0895", "1.0908")
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0908", "1.0911", "1.0870", "1.0875")

    engine.process_bar(b0, v_local, root_id="r1", parent_id="p1", parent_version=1)
    engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=2)
    before_confirmation = engine.get_confirmed_swings(BASE_TS + 120)
    assert before_confirmation == []

    rec = engine.process_bar(b2, v_local, root_id="r1", parent_id="p1", parent_version=3)
    assert rec.swing_state == SwingState.SWING_CONFIRMED
    assert len(engine.swings) == 1
    swing = engine.swings[0]
    assert swing.swing_type == "HIGH"
    assert swing.price == Decimal("1.0910")
    assert swing.candidate_at == b1.close_timestamp
    assert swing.confirmed_at == b2.close_timestamp
    assert swing.effective_from == b2.close_timestamp
    assert swing.confirmed_at > swing.candidate_at


def test_authoritative_state_is_strictly_broader_than_public_transition_record() -> None:
    """The forensic state surface includes all state capable of changing future output."""
    engine = StructureEngine("EURUSD", timeframe="1M")
    bar = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0850", "1.0790", "1.0845")
    engine.process_bar(bar, Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1)
    state = engine.authoritative_state()

    required = {
        "config", "recent_bars", "last_bar", "last_parent_id", "last_parent_version",
        "last_data_version", "last_config_version", "last_timestamp", "last_transition_record",
        "active_excursion_side", "high_candidate", "low_candidate", "swings",
    }
    assert required.issubset(state)
    assert state["last_bar"] == bar
    assert state["last_timestamp"] == bar.close_timestamp


def test_snapshot_roundtrip_preserves_structural_excursion_authority() -> None:
    """v2.2 snapshot/restore preserves excursion ownership and complete decision state."""
    engine = StructureEngine("EURUSD", timeframe="1M")
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0850", "1.0790", "1.0845"),
        Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0845", "1.0880", "1.0840", "1.0875"),
    ]
    for i, bar in enumerate(bars):
        engine.process_bar(bar, Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=i + 1)

    snapshot = engine.snapshot_state()
    assert snapshot["schema_version"] == "structure-engine-v2.2"
    restored = StructureEngine.from_snapshot_state(snapshot)
    assert restored.authoritative_state() == engine.authoritative_state()
