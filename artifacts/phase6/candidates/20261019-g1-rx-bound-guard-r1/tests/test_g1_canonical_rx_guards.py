from pathlib import Path

EA = Path(__file__).parents[1] / "mql5" / "FractalFlowBridgeEA.G1_RX_CANDIDATE.mq5"
SRC = EA.read_text()


def section(start, end):
    return SRC[SRC.index(start):SRC.index(end, SRC.index(start))]


def test_identity_defaults_and_real_trading_fence_preserved():
    assert 'input string InpAccountId="";' in SRC
    assert 'input string InpLaneId="";' in SRC
    assert 'input bool   InpAllowReal=false;' in SRC
    assert 'InpAccountId!=StringFormat("%I64d",actual_login)' in SRC


def test_persistent_buffer_bounded_before_allocation_and_cast():
    body = section('int ExtractBufferedFrame(string &body)', 'int ReadFrame(string &body)')
    assert 'if(len==0)' in body
    assert 'if(len>InpMaxFrameBytes)' in body
    assert body.index('if(len>InpMaxFrameBytes)') < body.index('int frame_size=4+(int)len;')
    read = section('int ReadFrame(string &body)', 'void AppendBytes(')
    assert 'int capacity=(int)InpMaxFrameBytes+4-buffered;' in read
    assert 'if(capacity<=0)' in read
    assert 'new_size>(int)InpMaxFrameBytes+4' in read


def test_utf8_validation_precedes_decode_and_reports_first_bad_byte():
    body = section('bool FFBP_IsValidUtf8(', 'int ExtractBufferedFrame(string &body)')
    assert 'int &bad_offset' in body
    assert 'if(b0==0x00)' in body
    assert 'bad_offset=i-start;' in body
    extract = section('int ExtractBufferedFrame(string &body)', 'int ReadFrame(string &body)')
    assert extract.index('FFBP_IsValidUtf8(') < extract.index('CharArrayToString(')
    assert 'g_rx_failure_detail=bad_utf8_offset;' in extract


def test_fragment_timeout_disconnect_and_socket_errors_remain_distinct():
    read = section('int ReadFrame(string &body)', 'void AppendBytes(')
    for reason in ('FRAME_ASSEMBLY_TIMEOUT', 'PEER_DISCONNECTED_PARTIAL_FRAME',
                   'PEER_DISCONNECTED_EMPTY_BUFFER', 'SOCKET_READ_FAILURE',
                   'RX_BUFFER_CAPACITY_EXHAUSTED'):
        assert reason in read
    assert 'g_rx_failure_error=GetLastError();' in read


def test_failure_paths_still_close_socket_and_clear_session_material():
    assert 'void ClearSessionMaterial()' in SRC
    deinit = section('void OnDeinit(const int reason)', 'void OnTimer()')
    assert 'SocketClose(g_socket);' in deinit
    assert 'ClearSessionMaterial();' in deinit
    timer = section('void OnTimer()', 'void MaintainProtectiveState()')
    assert timer.count('ClearSessionMaterial();') >= 3
    assert 'g_authenticated=false;' in timer
    assert 'g_protective_only=true;' in timer
    assert 'g_reconciliation_required=true;' in timer


def test_rx_diagnostic_does_not_log_session_material_or_payload():
    timer = section('void OnTimer()', 'void MaintainProtectiveState()')
    diag_lines = [line for line in timer.splitlines() if 'FFBP_RX_DIAG:' in line]
    assert len(diag_lines) == 1
    assert 'session_id' not in diag_lines[0].lower()
    assert 'nonce' not in diag_lines[0].lower()
    assert 'secret' not in diag_lines[0].lower()
    assert 'body' not in diag_lines[0].lower()


def test_candidate_is_not_stamped_as_release_build():
    assert 'FFBP_BUILD_ID "UNSTAMPED"' not in SRC
    assert 'FFBP_BUILD_ID' not in SRC


def test_configured_frame_limit_is_capped_before_signed_arithmetic():
    import re

    init = section("int OnInit()", "void OnDeinit(")
    match = re.search(r"InpMaxFrameBytes\s*>\s*65536", init)
    assert match is not None, "OnInit must reject frame limits above the protocol maximum"
    fence_load = init.index("FFBP_LoadFence(")
    bridge_connect = init.index("ConnectBridge()")
    assert match.start() < fence_load < bridge_connect, (
        "frame-limit validation must precede fence load and bridge connection"
    )
