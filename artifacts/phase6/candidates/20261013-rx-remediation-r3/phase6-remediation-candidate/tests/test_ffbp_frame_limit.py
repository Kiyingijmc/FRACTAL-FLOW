"""Source-level regression guard for FFBP/1 frame-size arithmetic bounds."""
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


def test_oninit_rejects_frame_limit_above_python_protocol_maximum():
    source = _source()
    init = _body(source, "OnInit")
    assert "InpMaxFrameBytes>65536" in init
    assert "InpMaxFrameBytes<1024" in init


def test_rx_capacity_arithmetic_has_protocol_upper_bound_guard():
    source = _source()
    init = _body(source, "OnInit")
    read = _body(source, "ReadFrame")
    assert init.index("InpMaxFrameBytes>65536") < source.index("int capacity=(int)InpMaxFrameBytes+4-buffered")
    assert "int capacity=(int)InpMaxFrameBytes+4-buffered" in read
