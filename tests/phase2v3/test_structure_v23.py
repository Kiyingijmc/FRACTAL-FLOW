from decimal import Decimal
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure_v23 import StructureEngineV23

def b(ts, o,h,l,c,seq):
    return Bar.create("EURUSD", "1M", ts, ts+60, o,h,l,c, sequence=seq)

def test_historical_projection_survives_future_mutation():
    a=StructureEngineV23("EURUSD")
    bars=[b(60,Decimal("1.1000"),Decimal("1.1020"),Decimal("1.0990"),Decimal("1.1015"),1),
          b(120,Decimal("1.1015"),Decimal("1.1040"),Decimal("1.1000"),Decimal("1.1030"),2),
          b(180,Decimal("1.1030"),Decimal("1.1035"),Decimal("1.1000"),Decimal("1.1005"),3)]
    for x in bars: a.process_bar(x, Decimal("0.001"), "r", "p", 1)
    before=a.authoritative_projection(120)
    for i in range(4,10):
        a.process_bar(b(i*60,Decimal("1.1005"),Decimal("1.1050"),Decimal("1.0990"),Decimal("1.1040"),i), Decimal("0.001"), "r", "p", i)
    after=a.authoritative_projection(120)
    assert before == after

def test_structure_truth_is_as_of_not_current_state():
    a=StructureEngineV23("EURUSD")
    a.process_bar(b(60,Decimal("1.1"),Decimal("1.102"),Decimal("1.099"),Decimal("1.101"),1),Decimal("0.001"),"r","p",1)
    a.process_bar(b(120,Decimal("1.101"),Decimal("1.103"),Decimal("1.100"),Decimal("1.102"),2),Decimal("0.001"),"r","p",2)
    truth=a.structural_truth(120)
    assert truth.as_of == 120
    assert all(s.effective_from <= 120 for s in truth.confirmed_swings)

def test_v23_snapshot_restores_historical_projection():
    a=StructureEngineV23("EURUSD")
    a.process_bar(b(60,Decimal("1.1"),Decimal("1.102"),Decimal("1.099"),Decimal("1.101"),1),Decimal("0.001"),"r","p",1)
    a.process_bar(b(120,Decimal("1.101"),Decimal("1.103"),Decimal("1.100"),Decimal("1.102"),2),Decimal("0.001"),"r","p",2)
    snap=a.snapshot_state()
    restored=StructureEngineV23.from_snapshot_state(snap)
    assert restored.authoritative_projection(120) == a.authoritative_projection(120)
