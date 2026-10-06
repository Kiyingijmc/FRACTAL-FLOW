from decimal import Decimal
from src.fractal_flow.domain.context import InstrumentSpec
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.phase2 import Phase2Pipeline

def bar(ts, o, h, l, c, seq):
    return Bar.create("EURUSD", "1M", ts, ts+60, o, h, l, c, sequence=seq, data_version=1, is_closed=True)

def test_phase2_pipeline_is_causal_and_non_authoritative():
    p = Phase2Pipeline("EURUSD", "1M", InstrumentSpec("EURUSD", Decimal("0.00001"), 5))
    values = [
        ("1.10000","1.10100","1.09950","1.10080"),
        ("1.10080","1.10200","1.10050","1.10170"),
        ("1.10170","1.10300","1.10100","1.10250"),
        ("1.10250","1.10270","1.10080","1.10110"),
        ("1.10110","1.10200","1.10050","1.10180"),
    ]
    out = None
    for i, (o,h,l,c) in enumerate(values, 1):
        out = p.process_bar(bar(i*60, *(Decimal(x) for x in (o,h,l,c)), i))
    assert out is not None
    assert out.context.watermark.timestamp == 360
    assert out.context.structure_version == p.structure.state_version
    assert out.role.state.value in {x.value for x in __import__('src.fractal_flow.domain.role', fromlist=['RoleState']).RoleState}
    assert not hasattr(out, "order")
