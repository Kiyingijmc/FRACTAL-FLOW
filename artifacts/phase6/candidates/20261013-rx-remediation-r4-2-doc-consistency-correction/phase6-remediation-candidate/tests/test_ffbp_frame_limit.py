"""Source-level regression guards for FFBP/1 frame-size arithmetic bounds.

These checks inspect source structure only; they do not replace MetaEditor or MT5 runtime tests.
"""
from __future__ import annotations
import os
import pathlib
import re


def _source() -> str:
    path = pathlib.Path(os.environ["FFBP_EA_UNDER_TEST"])
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def _body(text: str, name: str) -> str:
    m = re.search(rf"\n(?:int|bool|void|string)\s+{name}\s*\(", text)
    assert m, f"{name} not found"
    i = text.index("{", m.end())
    depth = 0
    for j in range(i, len(text)):
        depth += (text[j] == "{") - (text[j] == "}")
        if depth == 0:
            return text[i:j + 1]
    raise AssertionError(f"unterminated {name}")


def test_oninit_rejects_frame_limit_outside_supported_range():
    init = _body(_source(), "OnInit")
    assert "InpMaxFrameBytes>65536" in init
    assert "InpMaxFrameBytes<1024" in init


def test_frame_limit_validation_precedes_fence_load_and_socket_connect():
    """Compare all offsets within OnInit, not function-relative to file-relative offsets."""
    init = _body(_source(), "OnInit")
    guard = init.index("InpMaxFrameBytes>65536")
    fence_load = init.index("FFBP_LoadFence(")
    connect_bridge = init.index("ConnectBridge(")
    assert guard < fence_load, "frame limit must be rejected before fence loading"
    assert guard < connect_bridge, "frame limit must be rejected before invoking bridge connection"


def test_rx_capacity_arithmetic_is_followed_by_capacity_and_buffer_bounds():
    read = _body(_source(), "ReadFrame")
    capacity_expr = "int capacity=(int)InpMaxFrameBytes+4-buffered"
    assert capacity_expr in read
    capacity_at = read.index(capacity_expr)
    capacity_guard = read.index("if(capacity<=0)", capacity_at)
    assert capacity_at < capacity_guard
    assert "new_size>(int)InpMaxFrameBytes+4" in read
