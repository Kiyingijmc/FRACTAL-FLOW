"""Frame builders for the FFBP strict-UTF-8 runtime gate (test-only; no broker, no COMMANDs).

Why the frames are built this way
---------------------------------
A peer that closes the socket proves nothing about WHY. A frame with a bad MAC is also
rejected, so a close after a malformed frame is ambiguous. To make the UTF-8 guard the only
possible cause, each "differential" frame carries a MAC that is VALID for the lossy
interpretation of its bytes:

    1. build a normal authenticated HEARTBEAT whose correlation_id contains U+FFFD
       (wire bytes EF BF BD), MAC computed by the real encode_envelope();
    2. replace exactly that 3-byte run with a malformed byte sequence and fix the length prefix.

A receiver that decodes lossily (invalid byte -> U+FFFD), re-encodes, and then checks the MAC
sees the ORIGINAL authenticated text and ACCEPTS the frame. Only a receiver that validates the
raw bytes first can reject it. => ACK received = guard absent/bypassed; peer close + the EA
log line `reason=UTF8_INVALID` = guard effective.

"differential=True" is claimed only for single-byte defects, where every lossy decoder maps the
byte to exactly one U+FFFD. Multi-byte defects are still expected to be rejected, but a lossy
decoder may emit one or several U+FFFD, so the MAC may or may not verify on a non-strict EA.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from src.fractal_flow.execution.ffbp_protocol import Channel, ProtocolEnvelope, encode_envelope

FFFD = "\ufffd"
FFFD_BYTES = FFFD.encode("utf-8")           # EF BF BD
VALID_CASE = "utf8-valid-multibyte"
VALID_TEXT = "caf\u00e9-\u20ac-\U0001d11e"  # 2-, 3- and 4-byte sequences


@dataclass(frozen=True)
class Utf8Case:
    name: str
    replacement: bytes
    differential: bool
    note: str


MALFORMED: dict[str, Utf8Case] = {c.name: c for c in (
    Utf8Case("utf8-lone-continuation", b"\x80", True, "stray continuation byte"),
    Utf8Case("utf8-invalid-lead-ff", b"\xff", True, "0xFF never occurs in UTF-8"),
    Utf8Case("utf8-invalid-lead-c0", b"\xc0", True, "C0 can only start an overlong form"),
    Utf8Case("utf8-overlong-c0af", b"\xc0\xaf", False, "overlong '/'"),
    Utf8Case("utf8-surrogate-eda080", b"\xed\xa0\x80", False, "UTF-16 surrogate U+D800"),
    Utf8Case("utf8-over-max-f4908080", b"\xf4\x90\x80\x80", False, "code point above U+10FFFF"),
    Utf8Case("utf8-truncated-e282", b"\xe2\x82", False, "3-byte sequence cut short"),
    Utf8Case("utf8-nul", b"\x00", False, "raw NUL (policy: MQL5 strings are NUL-terminated)"),
)}
ALL_CASE_NAMES = [*MALFORMED, VALID_CASE]


def _heartbeat(account: str, session: str, seq: int, correlation: str) -> ProtocolEnvelope:
    return ProtocolEnvelope(
        message_type="HEARTBEAT", account_id=account, session_id=session, channel=Channel.CONTROL,
        sequence=seq, correlation_id=correlation, sent_at_ms=int(time.time() * 1000), payload={},
    )


def build_utf8_frame(name: str, account: str, session: str, seq: int, key: bytes) -> bytes:
    """Return a complete length-prefixed frame for `name` (see module docstring)."""
    if name == VALID_CASE:
        env = _heartbeat(account, session, seq, f"ffbp-{name}-{VALID_TEXT}")
        return encode_envelope(env, key)
    case = MALFORMED[name]
    env = _heartbeat(account, session, seq, f"ffbp-{name}-{FFFD}")
    wire = encode_envelope(env, key)
    body = wire[4:]
    if body.count(FFFD_BYTES) != 1:
        raise AssertionError("expected exactly one U+FFFD marker in the authenticated body")
    body = body.replace(FFFD_BYTES, case.replacement)
    return len(body).to_bytes(4, "big") + body
