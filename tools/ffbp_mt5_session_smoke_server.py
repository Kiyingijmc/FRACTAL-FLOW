#!/usr/bin/env python3
"""Local FFBP/1 Python peer for non-effectful MT5 session verification.

This server proves only transport/authentication/session interoperability.
It never accepts COMMAND messages and never touches a broker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import socket
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.fractal_flow.execution.ffbp_protocol import (
    Channel,
    ProtocolEnvelope,
    canonical_json,
    decode_envelope,
    encode_envelope,
)
from src.fractal_flow.execution.ffbp_session import Challenge, derive_session_keys



def _log_hello_frame_diagnostics(frame: bytes) -> None:
    """Emit bounded, secret-conscious diagnostics before HELLO decoding."""
    total = len(frame)
    declared = int.from_bytes(frame[:4], "big") if total >= 4 else -1
    payload = frame[4:] if total >= 4 else b""
    nul_tail = payload.endswith(bytes([0]))

    json_status = "NOT_ATTEMPTED"
    sensitive_fields_present = False
    try:
        parsed = json.loads(payload.decode("utf-8", errors="strict"))
        unsigned = dict(parsed)
        unsigned.pop("mac", None)
        unsigned_bytes = canonical_json(unsigned)
        print(
            "FFBP_HELLO_CANONICAL_DIAG "
            f"UNSIGNED_BYTES={len(unsigned_bytes)} "
            f"UNSIGNED_SHA256={hashlib.sha256(unsigned_bytes).hexdigest()}",
            flush=True,
        )
        json_status = "PASS"
        sensitive_names = {
            "mac", "hmac", "proof", "signature", "secret",
            "shared_secret", "key", "c2s_key", "s2c_key",
            "token", "nonce", "client_nonce", "server_nonce",
        }

        def inspect(value):
            nonlocal sensitive_fields_present
            if isinstance(value, dict):
                for key, child in value.items():
                    if str(key).lower() in sensitive_names:
                        sensitive_fields_present = True
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)

        inspect(parsed)
    except (UnicodeDecodeError, json.JSONDecodeError):
        json_status = "FAIL"
    except Exception:
        json_status = "ERROR"

    # Never emit raw frame bytes or field values. A raw tail can overlap
    # authentication material; use an explicit redaction marker instead.
    print(
        "FFBP_HELLO_FRAME_DIAG "
        f"FRAME_TOTAL={total} "
        f"DECLARED={declared} "
        f"PAYLOAD_LEN={len(payload)} "
        f"TRAILING_NUL={int(nul_tail)} "
        f"JSON_BODY={json_status} "
        f"SENSITIVE_FIELDS_PRESENT={int(sensitive_fields_present)} "
        "TAIL_HEX=REDACTED "
        "TAIL_REPR=REDACTED",
        flush=True,
    )


def recv_frame(conn: socket.socket) -> bytes:
    header = b""
    while len(header) < 4:
        chunk = conn.recv(4 - len(header))
        if not chunk:
            raise RuntimeError("peer disconnected while reading frame header")
        header += chunk
    length = int.from_bytes(header, "big")
    if length <= 0 or length > 65_536:
        raise RuntimeError(f"invalid frame length {length}")
    body = bytearray()
    while len(body) < length:
        chunk = conn.recv(length - len(body))
        if not chunk:
            raise RuntimeError("peer disconnected while reading frame body")
        body.extend(chunk)
    return header + bytes(body)


def send(conn: socket.socket, env: ProtocolEnvelope, key: bytes) -> None:
    conn.sendall(encode_envelope(env, key))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=39001)
    ap.add_argument("--account-id", required=True)
    ap.add_argument("--shared-secret", required=True)
    ap.add_argument("--hold-seconds", type=float, default=30.0)
    ap.add_argument("--hold-open", action="store_true", help="keep the authenticated connection open until the peer closes")
    args = ap.parse_args()
    if args.hold_seconds < 0:
        ap.error("--hold-seconds must be non-negative")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.host, args.port))
        server.listen(1)
        print(f"FFBP_SMOKE_LISTEN host={args.host} port={args.port}", flush=True)
        conn, addr = server.accept()
        with conn:
            print(f"FFBP_SMOKE_ACCEPT peer={addr[0]}:{addr[1]}", flush=True)
            hello_frame = recv_frame(conn)
            _log_hello_frame_diagnostics(hello_frame)
            hello = decode_envelope(hello_frame, args.shared_secret.encode())
            if hello.message_type != "HELLO":
                raise RuntimeError(f"expected HELLO, got {hello.message_type}")
            if hello.account_id != args.account_id:
                raise RuntimeError("HELLO account mismatch")
            if not isinstance(hello.payload, dict):
                raise RuntimeError("HELLO payload is not an object")
            client_nonce_hex = str(hello.payload["client_nonce"])
            client_nonce = bytes.fromhex(client_nonce_hex)
            challenge = Challenge.create(args.account_id, hello.session_id, client_nonce)
            send(
                conn,
                ProtocolEnvelope(
                    message_type="CHALLENGE",
                    account_id=args.account_id,
                    session_id=hello.session_id,
                    channel=Channel.CONTROL,
                    sequence=1,
                    sent_at_ms=int(time.time() * 1000),
                    payload={"server_nonce": challenge.server_nonce.hex()},
                ),
                args.shared_secret.encode(),
            )
            auth = decode_envelope(recv_frame(conn), args.shared_secret.encode())
            if auth.message_type != "AUTH" or not isinstance(auth.payload, dict):
                raise RuntimeError("expected authenticated AUTH envelope")
            proof = str(auth.payload.get("proof", ""))
            if not challenge.verify(args.shared_secret.encode(), proof):
                raise RuntimeError("challenge proof verification failed")
            c2s, s2c = derive_session_keys(
                args.shared_secret.encode(),
                args.account_id,
                hello.session_id,
                client_nonce,
                challenge.server_nonce,
            )
            send(
                conn,
                ProtocolEnvelope(
                    message_type="SESSION_ESTABLISHED",
                    account_id=args.account_id,
                    session_id=hello.session_id,
                    channel=Channel.CONTROL,
                    sequence=2,
                    acknowledgement=auth.sequence,
                    sent_at_ms=int(time.time() * 1000),
                    payload={"c2s_key": c2s.hex(), "s2c_key": s2c.hex()},
                ),
                args.shared_secret.encode(),
            )
            send(
                conn,
                ProtocolEnvelope(
                    message_type="HEARTBEAT",
                    account_id=args.account_id,
                    session_id=hello.session_id,
                    channel=Channel.CONTROL,
                    sequence=3,
                    sent_at_ms=int(time.time() * 1000),
                    payload={},
                ),
                s2c,
            )
            ack = decode_envelope(recv_frame(conn), c2s)
            if ack.message_type != "ACK":
                raise RuntimeError(f"expected ACK, got {ack.message_type}")
            if ack.sequence != 3:
                raise RuntimeError(f"unexpected ACK sequence {ack.sequence}")
            print(
                "FFBP_SMOKE_PASS "
                f"account={args.account_id} handshake=authenticated ack=validated",
                flush=True,
            )
            if args.hold_open:
                print(
                    "FFBP_SMOKE_DIAG connection_hold_mode=until_peer_close",
                    flush=True,
                )
                conn.settimeout(1.0)
                while True:
                    try:
                        probe = conn.recv(1, socket.MSG_PEEK)
                    except socket.timeout:
                        continue

                    if not probe:
                        print("FFBP_SMOKE_PEER_CLOSED", flush=True)
                        return 0

                    print(
                        "FFBP_SMOKE_UNEXPECTED_POST_ACK_DATA "
                        "bytes_available=1",
                        flush=True,
                    )
                    return 2
            else:
                print(
                    f"FFBP_SMOKE_DIAG connection_hold_seconds={args.hold_seconds:g}",
                    flush=True,
                )
                if args.hold_seconds:
                    time.sleep(args.hold_seconds)
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
