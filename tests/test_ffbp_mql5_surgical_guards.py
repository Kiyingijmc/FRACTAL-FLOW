"""Source-level safety guards for the FFBP MQL5 candidate.

These tests prove only source invariants. They do not replace MetaEditor
compilation or MT5 terminal runtime/adversarial tests.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EA = ROOT / "mql5/Phase6Bridge/FractalFlowBridge/FractalFlowBridgeEA.mq5"
JSON = ROOT / "mql5/Phase6Bridge/FractalFlowBridge/Include/FFBP_Json.mqh"
CRYPTO = ROOT / "mql5/Phase6Bridge/FractalFlowBridge/Include/FFBP_Crypto.mqh"


def _function(source: str, signature: str, next_signature: str) -> str:
    start = source.index(signature)
    end = source.index(next_signature, start + len(signature))
    return source[start:end]


def test_authentication_logs_do_not_disclose_transcript_proof_or_nonce_values():
    source = EA.read_text(encoding="utf-8")
    forbidden = (
        "FFBP AUTH DIAG",
        "transcript=%s",
        "transcript_sha256=%s",
        "proof=%s",
        "client_nonce=%s",
        "server_nonce=%s",
        "g_client_nonce);",
        "g_server_nonce);",
    )
    for marker in forbidden:
        assert marker not in source, f"sensitive diagnostic marker remains: {marker}"


def test_configured_account_must_exactly_match_terminal_login():
    source = EA.read_text(encoding="utf-8")
    fn = _function(source, "bool ValidateIdentity()", "uint ReadBE32(")
    assert "AccountInfoInteger(ACCOUNT_LOGIN)" in fn
    assert 'InpAccountId!=StringFormat("%I64d",actual_login)' in fn
    assert "ACCOUNT_TRADE_MODE_REAL" in fn
    assert "InpAllowReal" in fn


def test_hello_failure_closes_and_invalidates_socket():
    source = EA.read_text(encoding="utf-8")
    fn = _function(source, "bool ConnectBridge()", "int OnInit()")
    failure = fn.index("if(!SendHello())")
    block = fn[failure:fn.index('Print("FFBP CONNECT: HELLO sent")', failure)]
    assert "SocketClose(g_socket)" in block
    assert "g_socket=INVALID_HANDLE" in block


def test_receive_framing_is_persistent_bounded_and_nonblocking():
    source = EA.read_text(encoding="utf-8")
    assert "int ExtractBufferedFrame(string &body)" in source
    assert "int ReadFrame(string &body)" in source
    assert "FFBP_FRAME_ASSEMBLY_TIMEOUT_MS 2000" in source
    assert "g_rx_buffer" in source
    assert "len==0 || len>InpMaxFrameBytes" in source
    assert "if(!SocketIsConnected(g_socket))" in source
    assert "new_size>(int)InpMaxFrameBytes+4" in source


def test_timer_quarantines_fatal_transport_and_processing_failures_without_reconnect():
    source = EA.read_text(encoding="utf-8")
    fn = _function(source, "void OnTimer()", "void MaintainProtectiveState()")
    assert "if(g_quarantined)" in fn
    assert "if(g_socket==INVALID_HANDLE)" in fn
    assert "if(frame_status==0)" in fn
    assert "if(frame_status<0)" in fn
    assert "if(!ProcessFrame(body))" in fn
    assert "SocketClose(g_socket)" in fn
    assert "ConnectBridge();" not in fn
    assert "attempting reconnect" not in fn.lower()


def test_numeric_parsers_keep_explicit_64_bit_range_checks():
    source = JSON.read_text(encoding="utf-8")
    uint_fn = _function(source, "bool FFBP_ParseUInt64(", "bool FFBP_ParseInt64OrNull(")
    int_fn = _function(source, "bool FFBP_ParseInt64OrNull(", "bool FFBP_ExtractPayloadObject(")
    assert "18446744073709551615" in uint_fn
    assert "digits>20" in uint_fn
    assert "acc=acc*(ulong)10+digit" in uint_fn
    assert "9223372036854775808" in int_fn
    assert "9223372036854775807" in int_fn
    assert "digits>19" in int_fn
    assert "StringToInteger" not in uint_fn + int_fn


def test_hex_decoder_rejects_invalid_nibbles_and_clears_partial_output():
    source = CRYPTO.read_text(encoding="utf-8")
    nibble_fn = _function(source, "int FFBP_HexNibble(", "bool FFBP_HexDecode(")
    decode_fn = _function(source, "bool FFBP_HexDecode(", "bool FFBP_SHA256(")
    assert "return -1;" in nibble_fn
    assert "if((n&1)!=0)" in decode_fn
    assert "if(high<0 || low<0)" in decode_fn
    assert "ArrayResize(out,0)" in decode_fn


def test_session_material_is_cleared_on_teardown_and_fatal_paths():
    source = EA.read_text(encoding="utf-8")
    clear = _function(source, "void ClearSessionMaterial()", "uint ReadBE32(")
    for marker in (
        "ArrayInitialize(g_session_key,0)",
        "ArrayInitialize(g_c2s_key,0)",
        "ArrayInitialize(g_s2c_key,0)",
        'g_session_id=""',
        'g_client_nonce=""',
        'g_server_nonce=""',
        "ArrayResize(g_rx_buffer,0)",
    ):
        assert marker in clear
    assert "ClearSessionMaterial();" in _function(source, "void OnDeinit(", "void OnTimer(")
    timer = _function(source, "void OnTimer()", "void MaintainProtectiveState()")
    assert timer.count("ClearSessionMaterial();") >= 3
PERSISTENCE = (
    ROOT / "mql5/Phase6Bridge/FractalFlowBridge/Include/FFBP_Persistence.mqh"
)


def test_fence_load_rejects_missing_state_without_implicit_reset():
    source = PERSISTENCE.read_text(encoding="utf-8")
    fn = _function(
        source,
        "bool FFBP_LoadFence(",
        "bool FFBP_AppendCommand(",
    )
    assert "if(!FileIsExist(path,FILE_COMMON))" in fn
    assert not re.search(r"epoch\s*=\s*0\s*;\s*return\s+true\s*;", fn)
    assert re.search(
        r"if\s*\(!FileIsExist\(path,FILE_COMMON\)\)\s*"
        r"\{\s*return\s+false\s*;\s*\}",
        fn,
    )


def test_fence_save_rejects_epochs_outside_signed_64_bit_range():
    source = PERSISTENCE.read_text(encoding="utf-8")
    fn = _function(
        source,
        "bool FFBP_SaveFence(",
        "bool FFBP_LoadFence(",
    )
    assert "0x7FFFFFFFFFFFFFFF" in fn
    assert re.search(
        r"if\s*\(\s*epoch\s*>\s*0x7FFFFFFFFFFFFFFF\s*\)\s*"
        r"return\s+false\s*;",
        fn,
    )


def test_fence_save_checks_complete_record_writes_before_success():
    source = PERSISTENCE.read_text(encoding="utf-8")
    fn = _function(
        source,
        "bool FFBP_SaveFence(",
        "bool FFBP_LoadFence(",
    )
    assert re.search(
        r"FileWriteInteger\s*\(\s*h\s*,\s*FFBP_STATE_MAGIC\s*,\s*INT_VALUE\s*\)\s*!=\s*4",
        fn,
    )
    assert re.search(
        r"FileWriteInteger\s*\(\s*h\s*,\s*FFBP_STATE_VERSION\s*,\s*INT_VALUE\s*\)\s*!=\s*4",
        fn,
    )
    assert re.search(
        r"FileWriteLong\s*\(\s*h\s*,\s*\(long\)epoch\s*\)\s*!=\s*8",
        fn,
    )
    assert "FileMove(tmp,FILE_COMMON,final_path,FILE_COMMON|FILE_REWRITE)" in fn


def test_ea_rejects_epoch_exhaustion_before_increment():
    source = EA.read_text(encoding="utf-8")
    fn = _function(source, "int OnInit()", "void OnDeinit(")
    guard = fn.find("if(g_session_epoch>=0x7FFFFFFFFFFFFFFF)")
    increment = fn.find("g_session_epoch++;")
    assert guard >= 0, "missing fail-closed epoch exhaustion guard"
    assert increment >= 0, "session epoch increment not found"
    assert guard < increment, "epoch exhaustion must be checked before increment"
    assert "return INIT_FAILED;" in fn[guard:increment]


def test_fence_epoch_range_guard_precedes_file_open():
    source = PERSISTENCE.read_text(encoding="utf-8")
    fn = _function(
        source,
        "bool FFBP_SaveFence(",
        "bool FFBP_LoadFence(",
    )
    guard = fn.find("if(epoch>0x7FFFFFFFFFFFFFFF) return false;")
    file_open = fn.find("FileOpen(tmp,FILE_WRITE|FILE_BIN|FILE_COMMON)")
    assert guard >= 0
    assert file_open >= 0
    assert guard < file_open, "reject invalid epoch before acquiring a file handle"

def test_fence_save_readback_verifies_record_before_replacement():
    source = PERSISTENCE.read_text(encoding="utf-8")
    fn = _function(
        source,
        "bool FFBP_SaveFence(",
        "bool FFBP_LoadFence(",
    )

    verify_open = fn.find("FileOpen(")
    verify_open = fn.find("tmp,FILE_READ|FILE_BIN|FILE_COMMON|FILE_SHARE_READ", verify_open)
    assert verify_open >= 0, "SaveFence must reopen the completed temporary record"

    writer_close = fn.rfind("FileClose(h);", 0, verify_open)
    assert writer_close >= 0, "writer must close before read-back verification"
    assert writer_close < verify_open

    size_check = fn.find("FileSize(verify_handle)!=16", verify_open)
    assert size_check >= 0, "read-back must reject records with a non-16-byte size"

    magic_read = fn.find("FileReadInteger(verify_handle,INT_VALUE)", verify_open)
    version_read = fn.find("FileReadInteger(verify_handle,INT_VALUE)", magic_read + 1)
    epoch_read = fn.find("FileReadLong(verify_handle)", version_read + 1)
    eof_check = fn.find("FileIsEnding(verify_handle)", epoch_read + 1)

    assert magic_read >= 0, "read-back must inspect the record magic"
    assert version_read > magic_read, "read-back must inspect the version after magic"
    assert epoch_read > version_read, "read-back must inspect the epoch after version"
    assert eof_check > epoch_read, "read-back must verify the exact record boundary"

    replace = fn.find(
        "FileMove(tmp,FILE_COMMON,final_path,FILE_COMMON|FILE_REWRITE)"
    )
    verify_close = fn.find("FileClose(verify_handle)", eof_check)
    assert verify_close > eof_check, "verification handle must be closed"
    assert replace > verify_close, "replacement must occur only after read-back and close"
    assert "verify_magic==FFBP_STATE_MAGIC" in fn
    assert "verify_version==FFBP_STATE_VERSION" in fn
    assert "verify_epoch==(long)epoch" in fn
    assert "verify_eof" in fn
    assert "if(!verify_ok)" in fn
