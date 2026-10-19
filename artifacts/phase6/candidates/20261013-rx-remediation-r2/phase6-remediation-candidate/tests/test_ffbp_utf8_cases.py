from __future__ import annotations

import hashlib
import hmac
import json
import os
import socket
import subprocess
import sys
import time
import unittest

from src.fractal_flow.execution.ffbp_protocol import (
    Channel, ProtocolEnvelope, ProtocolError, canonical_json, decode_envelope, encode_envelope,
)
from src.fractal_flow.execution.ffbp_session import Challenge, derive_session_keys
from tools import ffbp_utf8_cases as uc

KEY = bytes(range(32))
SECRET = b"ffbp-unit-test-secret-7f3a91"


def _frame(name: str, seq: int = 3) -> bytes:
    return uc.build_utf8_frame(name, "ACC", "S-1", seq, KEY)


def _lossy_mac_ok(frame: bytes, key: bytes) -> bool:
    """Model of a NON-strict receiver: lossy decode, strip MAC, re-encode, verify MAC."""
    wire = json.loads(frame[4:].decode("utf-8", errors="replace"))
    mac = wire.pop("mac")
    expected = hmac.new(key, canonical_json(wire), hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac.lower(), expected)


# ---------------------------------------------------------------- builders ------
def test_every_malformed_frame_is_rejected_by_the_strict_python_peer():
    for name in uc.MALFORMED:
        frame = _frame(name)
        assert int.from_bytes(frame[:4], "big") == len(frame) - 4, name
        try:
            decode_envelope(frame, KEY)
        except ProtocolError:
            continue
        raise AssertionError(f"{name}: strict decoder accepted a malformed frame")


def test_valid_multibyte_control_is_accepted_with_a_good_mac():
    frame = _frame(uc.VALID_CASE)
    env = decode_envelope(frame, KEY)                     # strict decode + MAC verification
    assert env.message_type == "HEARTBEAT" and uc.VALID_TEXT in (env.correlation_id or "")
    assert any(b >= 0xF0 for b in frame[4:]) and any(0xE0 <= b < 0xF0 for b in frame[4:])  # 3- and 4-byte present


def test_differential_cases_have_a_mac_valid_under_lossy_decoding():
    """This is what makes a close attributable to the UTF-8 guard rather than to the MAC check."""
    diff = [n for n, c in uc.MALFORMED.items() if c.differential]
    assert len(diff) >= 3
    for name in diff:
        assert _lossy_mac_ok(_frame(name), KEY), f"{name}: a lossy receiver would REJECT on MAC, test is ambiguous"


def test_a_wrong_key_breaks_the_lossy_mac_so_the_property_is_not_vacuous():
    assert not _lossy_mac_ok(_frame("utf8-invalid-lead-ff"), bytes(32))


def test_frames_are_bounded_and_contain_the_defect_exactly_once():
    for name, case in uc.MALFORMED.items():
        frame = _frame(name)
        assert len(frame) < 65_536
        assert uc.FFFD_BYTES not in frame[4:], f"{name}: marker not fully replaced"
        assert frame[4:].count(case.replacement) >= 1


# --------------------------------------------- end-to-end with the real server ----
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _recv_exact(c: socket.socket, n: int) -> bytes:
    b = bytearray()
    while len(b) < n:
        chunk = c.recv(n - len(b))
        if not chunk:
            raise ConnectionError("closed")
        b.extend(chunk)
    return bytes(b)


def _recv_frame(c: socket.socket) -> bytes:
    h = _recv_exact(c, 4)
    return h + _recv_exact(c, int.from_bytes(h, "big"))


def _run_server_vs_peer(case: str, peer: str) -> str:
    """peer: 'strict' closes on malformed UTF-8; 'lossy' ACKs whenever the lossy MAC verifies."""
    port = _free_port()
    env = {**os.environ, "FFBP_TEST_SECRET": SECRET.decode()}
    proc = subprocess.Popen(
        [sys.executable, "tools/ffbp_adversarial_rx_server.py", "--host", "127.0.0.1", "--port", str(port),
         "--account-id", "ACC", "--case", case, "--ack-timeout", "4"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    try:
        deadline, conn = time.time() + 10, None
        while conn is None and time.time() < deadline:
            try:
                conn = socket.create_connection(("127.0.0.1", port), timeout=1)
            except OSError:
                time.sleep(0.05)
        assert conn is not None, "server did not listen"
        with conn:
            sid, cn = "SESSION-utf8-case", bytes(range(32))
            conn.sendall(encode_envelope(ProtocolEnvelope(
                message_type="HELLO", account_id="ACC", session_id=sid, channel=Channel.CONTROL, sequence=1,
                sent_at_ms=1, payload={"account_id": "ACC", "client_nonce": cn.hex(), "lane_id": "test"}), SECRET))
            sn = bytes.fromhex(decode_envelope(_recv_frame(conn), SECRET).payload["server_nonce"])
            conn.sendall(encode_envelope(ProtocolEnvelope(
                message_type="AUTH", account_id="ACC", session_id=sid, channel=Channel.CONTROL, sequence=2,
                sent_at_ms=2, payload={"proof": Challenge("ACC", sid, cn, sn).proof(SECRET)}), SECRET))
            decode_envelope(_recv_frame(conn), SECRET)                       # SESSION_ESTABLISHED
            c2s, s2c = derive_session_keys(SECRET, "ACC", sid, cn, sn)
            frame = _recv_frame(conn)                                        # the case frame
            try:
                frame[4:].decode("utf-8")
                strict_ok = b"\x00" not in frame[4:]
            except UnicodeDecodeError:
                strict_ok = False
            accept = strict_ok if peer == "strict" else _lossy_mac_ok(frame, s2c)
            if accept:
                conn.sendall(encode_envelope(ProtocolEnvelope(
                    message_type="ACK", account_id="ACC", session_id=sid, channel=Channel.CONTROL, sequence=3,
                    sent_at_ms=3, payload={}, correlation_id=json.loads(frame[4:].decode("utf-8", "replace")).get("correlation_id")),
                    c2s))
                time.sleep(0.2)
        out = proc.communicate(timeout=15)[0]
        assert "TEST_SERVER_ERROR" not in out, out
        verdict = [l for l in out.splitlines() if l.startswith("CASE_SERVER_VERDICT")]
        assert len(verdict) == 1, out
        return verdict[0]
    finally:
        if proc.poll() is None:
            proc.kill(); proc.wait()


def test_server_verdict_for_a_strict_peer_on_every_malformed_case():
    for name in uc.MALFORMED:
        v = _run_server_vs_peer(name, "strict")
        assert "verdict=REJECTED_CAUSE_UNCONFIRMED" in v, (name, v)    # server alone can never confirm the cause
        assert "UTF8_INVALID" in v                                       # ...and says where to look


def test_server_flags_a_lossy_peer_as_guard_not_effective():
    v = _run_server_vs_peer("utf8-invalid-lead-ff", "lossy")
    assert "verdict=FAIL_GUARD_NOT_EFFECTIVE" in v, v


def test_server_passes_valid_multibyte_for_a_strict_peer():
    v = _run_server_vs_peer(uc.VALID_CASE, "strict")
    assert "verdict=PASS" in v, v
