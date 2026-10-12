#!/usr/bin/env python3
"""Isolated FFBP test peer: authenticate, then send one invalid UTF-8 frame.

This is a controlled negative-test tool, not a production server. It never sends
COMMAND messages and never contacts a broker. It does not log secrets, proofs,
nonces, or session keys.
"""
from __future__ import annotations

import argparse
import os
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
    decode_envelope,
    encode_envelope,
)
from src.fractal_flow.execution.ffbp_session import Challenge, derive_session_keys


def recv_frame(conn: socket.socket) -> bytes:
    header = bytearray()
    while len(header) < 4:
        part = conn.recv(4 - len(header))
        if not part:
            raise RuntimeError("peer closed while reading frame header")
        header.extend(part)
    size = int.from_bytes(header, "big")
    if size <= 0 or size > 65_536:
        raise RuntimeError(f"invalid frame length {size}")
    body = bytearray()
    while len(body) < size:
        part = conn.recv(size - len(body))
        if not part:
            raise RuntimeError("peer closed while reading frame body")
        body.extend(part)
    return bytes(header + body)


def send(conn: socket.socket, envelope: ProtocolEnvelope, key: bytes) -> None:
    conn.sendall(encode_envelope(envelope, key))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=39001)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--secret-env", default="FFBP_TEST_SECRET")
    parser.add_argument("--close-timeout", type=float, default=8.0)
    args = parser.parse_args()

    secret_text = os.environ.get(args.secret_env, "")
    if not secret_text:
        parser.error(f"environment variable {args.secret_env} is empty or unset")
    if args.close_timeout <= 0:
        parser.error("--close-timeout must be positive")

    secret = secret_text.encode()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.host, args.port))
        server.listen(1)
        print(f"UTF8_TEST_LISTEN host={args.host} port={args.port}", flush=True)
        conn, peer = server.accept()
        print(f"UTF8_TEST_ACCEPT peer={peer[0]}:{peer[1]}", flush=True)
        try:
            with conn:
                conn.settimeout(10.0)
                hello = decode_envelope(recv_frame(conn), secret)
                if hello.message_type != "HELLO":
                    raise RuntimeError("expected HELLO")
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
                    secret,
                )

                auth = decode_envelope(recv_frame(conn), secret)
                if auth.message_type != "AUTH" or not isinstance(auth.payload, dict):
                    raise RuntimeError("expected AUTH")
                proof = str(auth.payload.get("proof", ""))
                if not challenge.verify(secret, proof):
                    raise RuntimeError("challenge proof verification failed")

                c2s, s2c = derive_session_keys(
                    secret,
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
                    secret,
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
                if ack.message_type != "ACK" or ack.sequence != 3:
                    raise RuntimeError("expected ACK sequence 3")
                print("UTF8_TEST_HANDSHAKE_PASS ack=validated", flush=True)

                # Overlong UTF-8 for "/" (C0 AF), forbidden by RFC 3629.
                invalid_body = b'{"test":"utf8-negative","value":"\xc0\xaf"}'
                conn.sendall(len(invalid_body).to_bytes(4, "big") + invalid_body)
                print("UTF8_TEST_INVALID_FRAME_SENT vector=overlong_c0af", flush=True)

                conn.settimeout(args.close_timeout)
                try:
                    received = conn.recv(1)
                    if received == b"":
                        print("UTF8_TEST_PEER_CLOSED", flush=True)
                        return 0
                    print("UTF8_TEST_INCONCLUSIVE peer_sent_data_after_invalid_frame", flush=True)
                    return 3
                except (ConnectionResetError, BrokenPipeError):
                    print("UTF8_TEST_PEER_RESET", flush=True)
                    return 0
                except socket.timeout:
                    print("UTF8_TEST_INCONCLUSIVE close_timeout_expired", flush=True)
                    return 3
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            print(f"UTF8_TEST_SERVER_ERROR type={type(exc).__name__}", flush=True)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
