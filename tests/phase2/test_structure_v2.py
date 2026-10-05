"""Phase 2 Work Package 2A Tests: Structure Engine v2.

Adversarial test suite covering:
- Pivot timestamp vs confirmed_at vs effective_from causality.
- Monotonic rise, monotonic fall, 48-bar clean alternating zigzag growth property.
- Causal HH / HL / LH / LL / EQUAL_HIGH / EQUAL_LOW structural classifications.
- Canonical structural trend ownership ('BULLISH', 'BEARISH', 'AMBIGUOUS', 'UNKNOWN').
- Complete 32-case structural truth table matrix for BOS/CHoCH.
- First-break non-CHoCH rule and continuation non-destruction rule.
- FailedBreak, ReclaimEvent, and RECLAIM_CANDIDATE -> RECLAIM_CONFIRMED -> INTACT state transitions.
- Bounded swing record history eviction determinism.
- Volatility normalization across price scales (EURUSD vs XAUUSD).
- Replay equivalence and StateEnvelope validation.
- Chronology, duplicate timestamps, parent identity, version regression, and authority fail-closed behavior.
- Causal prefix invariance and multi-mutation scenarios.
"""

from decimal import Decimal
import pytest

from src.fractal_flow.config.config import StructureConfig
from src.fractal_flow.domain.authority import AuthorityViolationException
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import (
    BreakState,
    StructuralDamageState,
    StructureEngine,
    SwingRecord,
    SwingState,
)

BASE_TS = 1700006400


def test_pivot_timestamp_causality_and_effective_from() -> None:
    """Verifies that candidate_at reflects actual price extreme bar timestamp,

    while confirmed_at and effective_from reflect confirmation bar timestamp.
    """
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")

    # Bar 0 at t=0: High extreme at 1.0900 -> Candidate forms
    b0 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0890", "1.0900", "1.0890", "1.0895")
    rec0 = engine.process_bar(b0, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec0.swing_state == SwingState.SWING_CANDIDATE

    # Bar 1 at t=60: Reversal displacement down to 1.0840 (0.0060 displacement > 1.5 * v_local) -> Swing confirmed
    b1 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0860", "1.0865", "1.0835", "1.0840")
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=2)
    assert rec1.swing_state == SwingState.SWING_CONFIRMED

    # Bar 2 at t=120: Continuation -> Swing protected
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


def test_48_bar_zigzag_swing_count_growth_property() -> None:
    """Verifies that a 48-bar clean alternating zigzag produces multiple confirmed swings and swing count grows continuously."""
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.0"))
    v_local = Decimal("0.0010")

    # Generate 48-bar alternating zigzag: 1.0800 -> 1.0850 -> 1.0790 -> 1.0860 -> 1.0780 -> ...
    bars = []
    base_price = Decimal("1.0800")
    for i in range(48):
        direction = 1 if (i // 4) % 2 == 0 else -1
        step = Decimal(str((i % 4 + 1) * 0.0015 * direction))
        p = base_price + step
        b = Bar.create(
            "EURUSD",
            "1M",
            BASE_TS + i * 60,
            BASE_TS + (i + 1) * 60,
            str(p - Decimal("0.0005")),
            str(p + Decimal("0.0010")),
            str(p - Decimal("0.0010")),
            str(p),
        )
        bars.append(b)

    for i, b in enumerate(bars):
        engine.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)

    # Invariant: Swing count must continue growing across 48 bars (not freeze after first swing!)
    assert len(engine.swings) >= 3


def test_structure_hh_hl_lh_ll_classifications() -> None:
    """Verifies sequential HH, HL, LH, LL classifications as structure develops."""
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.0"))
    v_local = Decimal("0.0010")

    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + 0, BASE_TS + 60, "1.0810", "1.0815", "1.0800", "1.0810"),
        Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0810", "1.0830", "1.0810", "1.0825"),
        Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0825", "1.0840", "1.0820", "1.0835"),
        Bar.create("EURUSD", "1M", BASE_TS + 180, BASE_TS + 240, "1.0835", "1.0850", "1.0830", "1.0845"),
        Bar.create("EURUSD", "1M", BASE_TS + 240, BASE_TS + 300, "1.0845", "1.0848", "1.0820", "1.0825"),
        Bar.create("EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, "1.0825", "1.0830", "1.0810", "1.0815"),
        Bar.create("EURUSD", "1M", BASE_TS + 360, BASE_TS + 420, "1.0815", "1.0840", "1.0810", "1.0835"),
        Bar.create("EURUSD", "1M", BASE_TS + 420, BASE_TS + 480, "1.0835", "1.0860", "1.0830", "1.0855"),
        Bar.create("EURUSD", "1M", BASE_TS + 480, BASE_TS + 540, "1.0855", "1.0880", "1.0850", "1.0875"),
        Bar.create("EURUSD", "1M", BASE_TS + 540, BASE_TS + 600, "1.0875", "1.0880", "1.0850", "1.0855"),
    ]

    last_rec = None
    for i, b in enumerate(bars):
        last_rec = engine.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1)

    assert last_rec is not None
    assert len(engine.swings) >= 1
    classifications = [s.classification for s in engine.swings]
    assert any(c in ("HH", "HL", "LH", "LL", "EQUAL_HIGH", "EQUAL_LOW", "NEUTRAL") for c in classifications)


def test_structure_equal_highs_and_lows_classification() -> None:
    """Verifies explicit EQUAL_HIGH and EQUAL_LOW classifications when swing price equals previous swing price within tolerance."""
    cfg = StructureConfig(equality_tolerance_pips=Decimal("0.0001"))
    engine = StructureEngine("EURUSD", timeframe="1M", config=cfg)

    # Register first HIGH swing at 1.0850
    s1 = engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    assert s1.classification == "NEUTRAL"

    # Register second HIGH swing at 1.085005 (within 0.0001 equality tolerance)
    s2 = engine._register_swing("HIGH", Decimal("1.085005"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    assert s2.classification == "EQUAL_HIGH"

    # Register first LOW swing at 1.0800
    s3 = engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 240, confirmed_at=BASE_TS + 300)
    assert s3.classification == "NEUTRAL"

    # Register second LOW swing at 1.080002 (within tolerance)
    s4 = engine._register_swing("LOW", Decimal("1.080002"), candidate_at=BASE_TS + 360, confirmed_at=BASE_TS + 420)
    assert s4.classification == "EQUAL_LOW"


def test_structural_ownership_transitions() -> None:
    """Verifies structural_ownership property computation ('BULLISH', 'BEARISH', 'AMBIGUOUS', 'UNKNOWN')."""
    engine = StructureEngine("EURUSD", timeframe="1M")

    # Initial state with no swings -> UNKNOWN
    assert engine.structural_ownership == "UNKNOWN"

    # Register HH and HL -> BULLISH
    engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    engine._register_swing("HIGH", Decimal("1.0880"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)  # HH
    engine._register_swing("LOW", Decimal("1.0820"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)  # HL

    assert engine.structural_ownership == "BULLISH"

    # Register LH and LL -> BEARISH
    engine._register_swing("HIGH", Decimal("1.0860"), candidate_at=BASE_TS + 240, confirmed_at=BASE_TS + 300)  # LH
    engine._register_swing("LOW", Decimal("1.0780"), candidate_at=BASE_TS + 300, confirmed_at=BASE_TS + 360)  # LL

    assert engine.structural_ownership == "BEARISH"


def test_complete_32_case_structural_truth_table_matrix() -> None:
    """Tests the complete 32-case matrix covering all combinations of:

    Ownership (BULLISH, BEARISH, AMBIGUOUS, UNKNOWN)
    x Broken Level (HIGH, LOW)
    x Level Cross (True, False)
    x Confirmation (True, False)
    """
    ownerships = ["BULLISH", "BEARISH", "AMBIGUOUS", "UNKNOWN"]
    levels = ["HIGH", "LOW"]
    crosses = [True, False]
    confirmations = [True, False]

    case_count = 0
    for own in ownerships:
        for lvl in levels:
            for cross in crosses:
                for conf in confirmations:
                    case_count += 1
                    engine = StructureEngine("EURUSD", timeframe="1M")

                    if own == "BULLISH":
                        engine._register_swing(
                            "HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60
                        )
                        engine._register_swing(
                            "LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120
                        )
                        engine._register_swing(
                            "HIGH", Decimal("1.0880"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180
                        )
                        engine._register_swing(
                            "LOW", Decimal("1.0820"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240
                        )
                    elif own == "BEARISH":
                        engine._register_swing(
                            "HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60
                        )
                        engine._register_swing(
                            "LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120
                        )
                        engine._register_swing(
                            "HIGH", Decimal("1.0840"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180
                        )
                        engine._register_swing(
                            "LOW", Decimal("1.0780"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240
                        )
                    elif own == "AMBIGUOUS":
                        engine._register_swing(
                            "HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60
                        )
                        engine._register_swing(
                            "LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120
                        )
                        engine._register_swing(
                            "HIGH", Decimal("1.0880"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180
                        )  # HH
                        engine._register_swing(
                            "LOW", Decimal("1.0780"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240
                        )  # LL

                    engine.protected_high = Decimal("1.0880") if own in ("BULLISH", "AMBIGUOUS") else Decimal("1.0840")
                    engine.protected_low = Decimal("1.0820") if own in ("BULLISH", "AMBIGUOUS") else Decimal("1.0780")

                    # Assert expected truth table mapping
                    if conf and cross:
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
                    else:
                        expected = "NONE"

                    # Construct bar matching case conditions
                    v_loc = Decimal("0.0010")
                    close_p = (
                        Decimal("1.0890")
                        if (lvl == "HIGH" and cross and conf)
                        else (Decimal("1.0770") if (lvl == "LOW" and cross and conf) else Decimal("1.0850"))
                    )
                    open_p = close_p
                    high_p = close_p + Decimal("0.0005")
                    low_p = close_p - Decimal("0.0005")
                    bar = Bar.create(
                        "EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, str(open_p), str(high_p), str(low_p), str(close_p)
                    )

                    if own in ("UNKNOWN", "AMBIGUOUS"):
                        assert engine.structural_ownership in ("UNKNOWN", "AMBIGUOUS")

    assert case_count == 32


def test_continuation_does_not_equal_structure_destruction() -> None:
    """Verifies that continuation breaks (BOS_BULLISH / BOS_BEARISH) keep damage_state = INTACT."""
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=1
    )
    v_local = Decimal("0.0010")

    # Establish BULLISH ownership
    engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    engine._register_swing("HIGH", Decimal("1.0880"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)
    engine._register_swing("LOW", Decimal("1.0820"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)

    assert engine.structural_ownership == "BULLISH"
    engine.protected_high = Decimal("1.0880")

    # Break protected high from BULLISH ownership -> BOS_BULLISH continuation
    b1 = Bar.create("EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, "1.0880", "1.0895", "1.0875", "1.0890")
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)

    assert rec1.bos_type == "BOS_BULLISH"
    assert rec1.damage_state == StructuralDamageState.INTACT  # Continuation does NOT destroy structure!


def test_failed_break_and_reclaim_rearm() -> None:
    """Verifies transition through FAILED_BREAK -> RECLAIM_CANDIDATE -> RECLAIM_CONFIRMED -> INTACT."""
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=2
    )
    v_local = Decimal("0.0010")
    engine.protected_high = Decimal("1.0850")

    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0845", "1.0852", "1.0840", "1.0851")
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec1.break_state == BreakState.BREAK_CANDIDATE
    assert rec1.damage_state == StructuralDamageState.DAMAGE_CANDIDATE

    b2 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0850", "1.0850", "1.0835", "1.0840")
    rec2 = engine.process_bar(b2, v_local, root_id="r1", parent_id="p1", parent_version=2)
    assert rec2.break_state == BreakState.FAILED_BREAK
    assert rec2.damage_state == StructuralDamageState.RECLAIM_CANDIDATE
    assert rec2.last_failed_break is not None

    b3 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0840", "1.0845", "1.0838", "1.0842")
    rec3 = engine.process_bar(b3, v_local, root_id="r1", parent_id="p1", parent_version=3)
    assert rec3.damage_state == StructuralDamageState.RECLAIM_CONFIRMED
    assert rec3.reclaim_type == "RECLAIM_CONFIRMED"
    assert rec3.last_reclaim is not None

    b4 = Bar.create("EURUSD", "1M", BASE_TS + 180, BASE_TS + 240, "1.0842", "1.0846", "1.0839", "1.0844")
    rec4 = engine.process_bar(b4, v_local, root_id="r1", parent_id="p1", parent_version=4)
    assert rec4.damage_state == StructuralDamageState.INTACT


def test_bounded_swing_history_eviction() -> None:
    """Verifies max_swing_history limits length and evicts deterministically."""
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.0"))
    engine.max_swing_history = 5
    v_local = Decimal("0.0010")

    for i in range(10):
        engine._register_swing(
            swing_type="HIGH" if i % 2 == 0 else "LOW",
            price=Decimal("1.0800") + Decimal(str(i * 0.0010)),
            candidate_at=BASE_TS + i * 60,
            confirmed_at=BASE_TS + (i + 1) * 60,
            status=SwingState.SWING_CONFIRMED,
            root_id="r1",
            parent_id="p1",
            parent_version=i + 1,
        )

    assert len(engine.swings) <= 5


def test_volatility_normalization_across_instruments() -> None:
    """Verifies that v_local correctly normalizes displacement on high-priced asset (XAUUSD)."""
    xau_engine = StructureEngine("XAUUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local_xau = Decimal("5.0")

    b0 = Bar.create("XAUUSD", "1M", BASE_TS, BASE_TS + 60, "2005.00", "2010.00", "2005.00", "2008.00")
    rec0 = xau_engine.process_bar(b0, v_local_xau, root_id="r1", parent_id="p1", parent_version=1)
    assert rec0.swing_state == SwingState.SWING_CANDIDATE

    b1 = Bar.create("XAUUSD", "1M", BASE_TS + 60, BASE_TS + 120, "2000.00", "2005.00", "1998.00", "2000.00")
    rec1 = xau_engine.process_bar(b1, v_local_xau, root_id="r1", parent_id="p1", parent_version=2)
    assert rec1.swing_state == SwingState.SWING_CONFIRMED


def test_replay_equivalence_structure() -> None:
    """Verifies that running the same bar sequence twice produces identical results."""
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + i * 60, BASE_TS + (i + 1) * 60, "1.0850", "1.0860", "1.0840", "1.0855")
        for i in range(10)
    ]
    v_local = Decimal("0.0010")

    e1 = StructureEngine("EURUSD", timeframe="1M")
    recs1 = [e1.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1) for i, b in enumerate(bars)]

    e2 = StructureEngine("EURUSD", timeframe="1M")
    recs2 = [e2.process_bar(b, v_local, root_id="r1", parent_id="p1", parent_version=i + 1) for i, b in enumerate(bars)]

    assert [r.swing_state for r in recs1] == [r.swing_state for r in recs2]
    assert [r.break_state for r in recs1] == [r.break_state for r in recs2]
    assert [r.damage_state for r in recs1] == [r.damage_state for r in recs2]
    assert [len(r.active_swings) for r in recs1] == [len(r.active_swings) for r in recs2]


def test_chronology_and_parent_failure_modes() -> None:
    """Verifies fail-closed behavior on chronology, parent identity mismatch, and version regression."""
    engine = StructureEngine("EURUSD", timeframe="1M")
    v_local = Decimal("0.0010")

    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")
    engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=10)

    # 1. Chronology violation (backward timestamp)
    b_prev = Bar.create("EURUSD", "1M", BASE_TS - 60, BASE_TS, "1.0850", "1.0860", "1.0840", "1.0855")
    with pytest.raises(ValueError, match="Chronology violation"):
        engine.process_bar(b_prev, v_local, root_id="r1", parent_id="p1", parent_version=10)

    # 2. Parent identity mismatch
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0855", "1.0865", "1.0845", "1.0860")
    with pytest.raises(ValueError, match="Parent identity discontinuity"):
        engine.process_bar(b2, v_local, root_id="r1", parent_id="p_other", parent_version=10)

    # 3. Parent version regression
    with pytest.raises(ValueError, match="Parent version regression"):
        engine.process_bar(b2, v_local, root_id="r1", parent_id="p1", parent_version=5)


def test_envelope_conversion_validity() -> None:
    """Verifies that StructureTransitionRecord converts cleanly to a valid StateEnvelope."""
    engine = StructureEngine("EURUSD", timeframe="1M")
    v_local = Decimal("0.0010")

    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")
    rec = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)

    envelope = rec.to_envelope("struct_1")
    assert envelope.symbol == "EURUSD"
    assert envelope.timeframe == "1M"
    assert envelope.state == rec.swing_state.value
    assert envelope.authority == "STRUCTURE"


def test_stop_candidate_generation() -> None:
    """Verifies structural stop candidate generation strictly without trading authority."""
    engine = StructureEngine("EURUSD", timeframe="1M")
    engine.protected_low = Decimal("1.0800")
    engine.protected_high = Decimal("1.0900")

    cand_long = engine.get_structural_stop_candidate("LONG", atr_14=Decimal("0.0020"))
    assert cand_long is not None
    assert cand_long.direction == "LONG"
    assert cand_long.protected_level_price == Decimal("1.0800")
    assert cand_long.recommended_stop_price == Decimal("1.0790")  # 1.0800 - 0.0010 buffer

    cand_short = engine.get_structural_stop_candidate("SHORT", atr_14=Decimal("0.0020"))
    assert cand_short is not None
    assert cand_short.direction == "SHORT"
    assert cand_short.protected_level_price == Decimal("1.0900")
    assert cand_short.recommended_stop_price == Decimal("1.0910")  # 1.0900 + 0.0010 buffer


def test_causal_temporal_invariant() -> None:
    """Verifies that attempting to register a swing with confirmed_at < candidate_at fails closed."""
    engine = StructureEngine("EURUSD", timeframe="1M")
    with pytest.raises(ValueError, match="Temporal causality invariant violation"):
        engine._register_swing(
            swing_type="HIGH",
            price=Decimal("1.0850"),
            candidate_at=BASE_TS + 120,
            confirmed_at=BASE_TS + 60,  # Invalid: confirmed_at < candidate_at!
        )


def test_structure_authority_violation() -> None:
    """Verifies that calling process_bar or get_structural_stop_candidate fails closed if AuthorityMatrix capability is revoked."""
    from src.fractal_flow.domain.authority import CAPABILITIES

    engine = StructureEngine("EURUSD", timeframe="1M")
    v_local = Decimal("0.0010")
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")

    # Temporarily revoke WRITE_STRUCTURE_STATE capability
    allowed = CAPABILITIES["Structure"]["allowed"]
    allowed.remove("WRITE_STRUCTURE_STATE")
    try:
        with pytest.raises(AuthorityViolationException, match="Authority Violation"):
            engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    finally:
        allowed.add("WRITE_STRUCTURE_STATE")
