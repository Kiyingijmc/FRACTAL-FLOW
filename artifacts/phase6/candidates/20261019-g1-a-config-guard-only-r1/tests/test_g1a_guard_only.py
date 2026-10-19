from pathlib import Path
import difflib
import re
import subprocess

REPO = Path(__file__).resolve().parents[5]
BASE = REPO / "mql5/Phase6Bridge/FractalFlowBridge/FractalFlowBridgeEA.mq5"
CAND = Path(__file__).resolve().parents[1] / "mql5/FractalFlowBridgeEA.G1A_CANDIDATE.mq5"


def test_candidate_diff_is_exactly_one_guard_line():
    base_lines = BASE.read_text(encoding="utf-8").splitlines()
    cand_lines = CAND.read_text(encoding="utf-8").splitlines()
    delta = list(difflib.unified_diff(base_lines, cand_lines, lineterm=""))
    changed = [line for line in delta if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
    assert changed == ["+      InpMaxFrameBytes>65536 ||"]


def test_guard_is_in_oninit_before_fence_load_and_connect():
    src = CAND.read_text(encoding="utf-8")
    oninit = src[src.index("int OnInit()"):src.index("void OnDeinit(", src.index("int OnInit()"))]
    match = re.search(r"InpMaxFrameBytes\s*>\s*65536", oninit)
    assert match is not None
    fence = oninit.index("FFBP_LoadFence(")
    connect = oninit.index("ConnectBridge()")
    assert match.start() < fence < connect


def test_existing_bounds_and_real_trading_default_are_preserved():
    src = CAND.read_text(encoding="utf-8")
    assert "input uint   InpMaxFrameBytes=65536;" in src
    assert "input bool   InpAllowReal=false;" in src
    assert "InpMaxFrameBytes<1024" in src
    assert "InpMaxFrameBytes>65536" in src
