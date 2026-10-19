"""Static guards over the EA under test (set FFBP_EA_UNDER_TEST=/path/to/FractalFlowBridgeEA.mq5).

These are SOURCE checks. They cannot prove MetaEditor compiles the file or how it behaves in the
terminal; they stop specific regressions (decode-before-validate, silent -1 returns, auth logging).
"""
from __future__ import annotations

import os
import pathlib
import re
import unittest

from tools import ffbp_log_hygiene_scan as scan


def _ea() -> tuple[pathlib.Path, str]:
    p = os.environ.get("FFBP_EA_UNDER_TEST")
    if not p:
        raise unittest.SkipTest("FFBP_EA_UNDER_TEST not set")
    path = pathlib.Path(p)
    return path, path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def _body(text: str, name: str) -> str:
    m = re.search(rf"\n(?:int|bool|void|string)\s+{name}\s*\(", text)
    assert m, f"{name} not found"
    i = text.index("{", m.end()); d = 0; j = i
    while True:
        d += (text[j] == "{") - (text[j] == "}"); j += 1
        if d == 0:
            return text[i:j]


def test_utf8_validation_precedes_every_lossy_decode_of_wire_bytes():
    _, t = _ea()
    fn = _body(t, "ExtractBufferedFrame")
    assert "FFBP_IsValidUtf8(" in fn, "no strict UTF-8 validation in the frame extractor"
    assert fn.index("FFBP_IsValidUtf8(") < fn.index("CharArrayToString(g_rx_buffer"), "decode happens before validation"
    assert len(re.findall(r"CharArrayToString\(\s*g_rx_buffer", t)) == 1, "another raw-buffer decode path exists"


def test_validation_failure_is_attributed_and_fatal():
    _, t = _ea()
    fn = _body(t, "ExtractBufferedFrame")
    start = fn.index("if(!FFBP_IsValidUtf8(")
    i = fn.index("{", start); depth = 0; j = i
    while True:                                   # brace-match; arguments contain `(int)` casts
        depth += (fn[j] == "{") - (fn[j] == "}"); j += 1
        if depth == 0:
            break
    block = fn[i:j]
    assert "FFBP_RX_UTF8_INVALID" in block and "return -1" in block


def test_every_negative_return_in_the_rx_path_records_a_reason():
    _, t = _ea()
    for name in ("ExtractBufferedFrame", "ReadFrame"):
        fn = _body(t, name)
        lines = fn.split("\n")
        for k, line in enumerate(lines):
            if re.search(r"\breturn\s+-1\s*;", line):
                window = "\n".join(lines[max(0, k - 4):k])
                assert "FFBP_RxReject(" in window, f"{name}: un-attributed `return -1` near: {line.strip()!r}"


def test_timer_quarantine_goes_through_the_structured_logger():
    _, t = _ea()
    fn = _body(t, "OnTimer")
    assert fn.count("FFBP_Quarantine(") >= 2
    assert "SocketClose(g_socket)" not in fn, "OnTimer closes the socket itself; use FFBP_Quarantine"


def test_build_id_defined_and_logged():
    _, t = _ea()
    assert re.search(r'#define\s+FFBP_BUILD_ID\s+"[^"]*"', t)
    assert "FFBP BUILD: id=%s" in t


def test_no_auth_material_in_log_statements():
    path, _ = _ea()
    bad = [f for f in scan.scan_path(path) if scan.SEV[f.severity] >= scan.SEV["MEDIUM"]]
    assert bad == [], [(f.line, f.why) for f in bad]
