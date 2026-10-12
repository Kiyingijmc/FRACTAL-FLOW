"""
FFBP/1 adversarial MT5 receive-framing test server.

Test-only transport/authentication harness. It never accepts COMMAND messages,
never submits trades, and never accesses a broker. Run one --case per EA session.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import socket
import sys
import time
from typing import Callable

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.fractal_flow.execution.ffbp_protocol import (
    Channel,
    ProtocolEnvelope,
    decode_envelope,
    encode_envelope,
)
from src.fractal_flow.execution.ffbp_session import Challenge, derive_session_keys


MAX_FRAME_DEFAULT = 65_536


def recv_exact(conn: socket.socket, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        data = conn.recv(count - len(chunks))
        if not data:
            raise RuntimeError("peer disconnected while reading frame")
        chunks.extend(data)
    return bytes(chunks)


def recv_frame(conn: socket.socket, max_frame: int = MAX_FRAME_DEFAULT) -> bytes:
    header = recv_exact(conn, 4)
    length = int.from_bytes(header, "big")
    if length <= 0 or length > max_frame:
        raise RuntimeError(f"invalid inbound frame length {length}")
    return header + recv_exact(conn, length)


def send_env(conn: socket.socket, env: ProtocolEnvelope, key: bytes) -> bytes:
    wire = encode_envelope(env, key)
    conn.sendall(wire)
    return wire


def make_heartbeat(account: str, session: str, seq: int, key: bytes) -> bytes:
    env = ProtocolEnvelope(
        message_type="HEARTBEAT",
        account_id=account,
        session_id=session,
        channel=Channel.CONTROL,
        sequence=seq,
        correlation_id=f"ffbp-test-heartbeat-{seq}",
        sent_at_ms=int(time.time() * 1000),
        payload={},
    )
    return encode_envelope(env, key)


def do_handshake(
    conn: socket.socket, account: str, secret: bytes
) -> tuple[str, bytes, bytes]:
    hello = decode_envelope(recv_frame(conn), secret)
    if hello.message_type != "HELLO":
        raise RuntimeError(f"expected HELLO, got {hello.message_type}")
    if hello.account_id != account:
        raise RuntimeError("HELLO account mismatch")
    if not isinstance(hello.payload, dict):
        raise RuntimeError("HELLO payload is not an object")

    client_nonce_hex = str(hello.payload["client_nonce"])
    client_nonce = bytes.fromhex(client_nonce_hex)
    challenge = Challenge.create(account, hello.session_id, client_nonce)

    send_env(
        conn,
        ProtocolEnvelope(
            message_type="CHALLENGE",
            account_id=account,
            session_id=hello.session_id,
            channel=Channel.CONTROL,
            sequence=1,
            sent_at_ms=int(time.time() * 1000),
            payload={"server_nonce": challenge.server_nonce.hex()},
        ),
        secret,
    )

    auth = decode_envelope(recv_frame(conn), secret)
    if auth.message_type != "AUTH" or not isinstance(auth.payload, dict):
        raise RuntimeError("expected AUTH envelope")
    proof = str(auth.payload.get("proof", ""))
    if not challenge.verify(secret, proof):
        raise RuntimeError("challenge proof verification failed")

    c2s, s2c = derive_session_keys(
        secret, account, hello.session_id, client_nonce, challenge.server_nonce
    )
    send_env(
        conn,
        ProtocolEnvelope(
            message_type="SESSION_ESTABLISHED",
            account_id=account,
            session_id=hello.session_id,
            channel=Channel.CONTROL,
            sequence=2,
            acknowledgement=auth.sequence,
            sent_at_ms=int(time.time() * 1000),
            payload={"c2s_key": c2s.hex(), "s2c_key": s2c.hex()},
        ),
        secret,
    )
    print("TEST_HANDSHAKE_PASS authenticated=true", flush=True)
    return hello.session_id, c2s, s2c


def wait_for_ack(
    conn: socket.socket,
    secret_c2s: bytes,
    account: str,
    session: str,
    expected_correlations: list[str],
    timeout: float,
) -> None:
    """Validate ACK identity/correlation and report ack-field semantics separately.

    The current MQL5 peer has emitted acknowledgement=0 in observed runs. This
    harness deliberately records that field without assuming its contract; it
    does enforce the correlation_id corresponding to each triggering heartbeat.
    """
    conn.settimeout(timeout)
    seen_ack_fields: list[int] = []
    seen_sequences: list[int] = []
    for expected_correlation in expected_correlations:
        env = decode_envelope(recv_frame(conn), secret_c2s)
        if env.message_type != "ACK":
            raise RuntimeError(f"expected ACK, got {env.message_type}")
        if env.account_id != account:
            raise RuntimeError("ACK account_id mismatch")
        if env.session_id != session:
            raise RuntimeError("ACK session_id mismatch")
        if env.channel is not Channel.CONTROL:
            raise RuntimeError(f"ACK channel mismatch: {env.channel}")
        if env.correlation_id != expected_correlation:
            raise RuntimeError(
                "ACK correlation_id mismatch: "
                f"expected={expected_correlation!r} actual={env.correlation_id!r}"
            )
        seen_ack_fields.append(int(env.acknowledgement))
        seen_sequences.append(int(env.sequence))
    if any(b <= a for a, b in zip(seen_sequences, seen_sequences[1:])):
        raise RuntimeError(f"ACK sequence values are not strictly increasing: {seen_sequences}")
    print(
        "TEST_ACKS_RECEIVED "
        f"count={len(seen_sequences)} ack_sequences={seen_sequences} "
        f"acknowledgement_values={seen_ack_fields} "
        "correlation_check=PASS identity_check=PASS",
        flush=True,
    )


def run_case(
    conn: socket.socket,
    case: str,
    account: str,
    session: str,
    c2s: bytes,
    s2c: bytes,
    max_frame: int,
    fragment_delay: float,
    deadline_seconds: float,
    ack_timeout: float,
) -> None:
    frame3 = make_heartbeat(account, session, 3, s2c)
    prefix3, body3 = frame3[:4], frame3[4:]

    if case == "fragmented-header":
        print("CASE_BEGIN fragmented-header", flush=True)
        for byte in prefix3:
            conn.sendall(bytes([byte]))
            time.sleep(fragment_delay)
        conn.sendall(body3)
        wait_for_ack(conn, c2s, account, session, ["ffbp-test-heartbeat-3"], ack_timeout)
        print("CASE_SERVER_PASS fragmented-header full-frame-acknowledged", flush=True)

    elif case == "fragmented-body":
        print("CASE_BEGIN fragmented-body", flush=True)
        conn.sendall(prefix3)
        # Split body into small chunks, with gaps shorter than the assembly deadline.
        chunk_size = max(1, min(32, len(body3) // 5 or 1))
        for offset in range(0, len(body3), chunk_size):
            conn.sendall(body3[offset:offset + chunk_size])
            time.sleep(fragment_delay)
        wait_for_ack(conn, c2s, account, session, ["ffbp-test-heartbeat-3"], ack_timeout)
        print("CASE_SERVER_PASS fragmented-body full-frame-acknowledged", flush=True)

    elif case == "coalesced":
        print("CASE_BEGIN coalesced", flush=True)
        frame4 = make_heartbeat(account, session, 4, s2c)
        conn.sendall(frame3 + frame4)  # Deliberately one write.
        wait_for_ack(conn, c2s, account, session, ["ffbp-test-heartbeat-3", "ffbp-test-heartbeat-4"], ack_timeout)
        print("CASE_SERVER_PASS coalesced two-acks-received", flush=True)

    elif case == "oversized":
        print(f"CASE_BEGIN oversized advertised_length={max_frame + 1}", flush=True)
        conn.sendall((max_frame + 1).to_bytes(4, "big"))
        conn.settimeout(ack_timeout)
        try:
            data = conn.recv(1)
            if data == b"":
                print("CASE_SERVER_OBSERVED peer_closed=true", flush=True)
            else:
                print("CASE_SERVER_OBSERVED peer_sent_data=true", flush=True)
        except socket.timeout:
            print("CASE_SERVER_OBSERVED no_close_before_timeout=true", flush=True)
        print("CASE_END oversized inspect EA quarantine log", flush=True)

    elif case == "partial-disconnect":
        print("CASE_BEGIN partial-disconnect", flush=True)
        conn.sendall(prefix3[:2])
        time.sleep(fragment_delay)
        conn.close()
        print("CASE_SERVER_ACTION closed_after_2_header_bytes=true", flush=True)

    elif case == "assembly-deadline":
        print(
            f"CASE_BEGIN assembly-deadline deadline_seconds={deadline_seconds:g}",
            flush=True,
        )
        conn.sendall(prefix3)
        conn.sendall(body3[: min(12, len(body3))])
        print("CASE_SERVER_ACTION partial-frame-sent=true; waiting", flush=True)
        time.sleep(deadline_seconds + 1.0)
        conn.settimeout(1.0)
        try:
            data = conn.recv(1)
            if data == b"":
                print("CASE_SERVER_OBSERVED peer_closed=true", flush=True)
            else:
                print("CASE_SERVER_OBSERVED peer_sent_data=true", flush=True)
        except socket.timeout:
            print("CASE_SERVER_OBSERVED no_close_after_deadline=true", flush=True)
        print("CASE_END assembly-deadline inspect EA quarantine log", flush=True)

    else:
        raise ValueError(f"unsupported case {case}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=39001)
    parser.add_argument("--account-id", required=True)
    parser.add_argument(
        "--secret-env",
        default="FFBP_TEST_SECRET",
        help="environment variable containing the test secret (default: FFBP_TEST_SECRET)",
    )
    parser.add_argument(
        "--case",
        required=True,
        choices=[
            "fragmented-header",
            "fragmented-body",
            "coalesced",
            "oversized",
            "partial-disconnect",
            "assembly-deadline",
        ],
    )
    parser.add_argument("--max-frame-bytes", type=int, default=MAX_FRAME_DEFAULT)
    parser.add_argument("--fragment-delay", type=float, default=0.08)
    parser.add_argument("--deadline-seconds", type=float, default=2.0)
    parser.add_argument("--ack-timeout", type=float, default=8.0)
    args = parser.parse_args()

    secret_text = os.environ.get(args.secret_env, "")
    if not secret_text:
        parser.error(f"environment variable {args.secret_env} is empty or unset")
    if args.max_frame_bytes < 1024:
        parser.error("--max-frame-bytes must be >= 1024")
    if args.fragment_delay < 0 or args.deadline_seconds <= 0 or args.ack_timeout <= 0:
        parser.error("delays/timeouts must be positive (fragment delay may be zero)")
    secret = secret_text.encode()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.host, args.port))
        server.listen(1)
        print(
            f"TEST_LISTEN host={args.host} port={args.port} case={args.case}",
            flush=True,
        )
        conn, peer = server.accept()
        print(f"TEST_ACCEPT peer={peer[0]}:{peer[1]}", flush=True)
        try:
            with conn:
                conn.settimeout(10.0)
                session, c2s, s2c = do_handshake(conn, args.account_id, secret)
                run_case(
                    conn,
                    args.case,
                    args.account_id,
                    session,
                    c2s,
                    s2c,
                    args.max_frame_bytes,
                    args.fragment_delay,
                    args.deadline_seconds,
                    args.ack_timeout,
                )
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            print(f"TEST_SERVER_ERROR type={type(exc).__name__}", flush=True)
            print(f"TEST_SERVER_ERROR_DETAIL {exc}", flush=True)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
