from pathlib import Path
import re

EA = Path(__file__).parents[1] / "ea" / "FractalFlowBridgeEA.REMEDIATED.mq5"


def test_receive_path_persistent_bounded_and_strict_utf8():
    s = EA.read_text()
    assert "uchar g_rx_buffer[];" in s
    assert "FFBP_FRAME_ASSEMBLY_TIMEOUT_MS 2000" in s
    extract = s[s.index("int ExtractBufferedFrame("):s.index("int ReadFrame(")]
    assert extract.index("FFBP_IsValidUtf8(") < extract.index("CharArrayToString(g_rx_buffer")
    assert "FFBP_RX_LEN_ZERO" in extract and "FFBP_RX_LEN_OVER_MAX" in extract


def test_idle_is_nonfatal_but_terminal_failures_quarantine():
    s = EA.read_text()
    timer = s[s.index("void OnTimer()"):]
    assert "if(frame_status==0)" in timer
    assert "FFBP_Quarantine(\"RX_FRAME\"" in timer
    assert "FFBP_Quarantine(\"PROCESS_FRAME\"" in timer
    assert "attempting reconnect" not in timer.lower()


def test_identity_requires_canonical_decimal_account_string():
    s = EA.read_text()
    fn = s[s.index("bool ValidateIdentity()"):s.index("// -----------------------------------------------------------------------------\n// Framing")]
    assert "IntegerToString(actual_login)" in fn
    assert "InpAccountId!=actual_login_text" in fn
    assert "StringToInteger(InpAccountId)" not in fn


def test_epoch_cannot_wrap_signed_persistent_fence():
    s = EA.read_text()
    guard = s.index("if(g_session_epoch>=0x7FFFFFFFFFFFFFFF)")
    increment = s.index("g_session_epoch++;", guard)
    assert guard < increment


def test_no_auth_material_in_log_calls():
    # The scanner deliberately excludes LOW-only session identifiers from the fail threshold.
    from tools import ffbp_log_hygiene_scan as scan
    findings = [f for f in scan.scan_path(EA) if scan.SEV[f.severity] >= scan.SEV["MEDIUM"]]
    assert not findings, [(f.line, f.why, f.snippet) for f in findings]
