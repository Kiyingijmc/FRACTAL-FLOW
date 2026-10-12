"""FFBP/1 challenge/session derivation without broker authority."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from src.fractal_flow.execution.ffbp_protocol import canonical_json


class SessionError(ValueError):
    pass


def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    if length < 0 or length > 255 * 32:
        raise ValueError("invalid HKDF output length")
    out = bytearray()
    previous = b""
    for counter in range(1, (length + 31) // 32 + 1):
        previous = hmac.new(prk, previous + info + bytes([counter]), hashlib.sha256).digest()
        out.extend(previous)
    return bytes(out[:length])


def derive_session_keys(secret: bytes, account_id: str, session_id: str, client_nonce: bytes, server_nonce: bytes) -> tuple[bytes, bytes]:
    if not secret or not client_nonce or not server_nonce:
        raise SessionError("secret and fresh nonces are mandatory")
    context = canonical_json({
        "account_id": account_id,
        "client_nonce": client_nonce.hex(),
        "session_id": session_id,
        "server_nonce": server_nonce.hex(),
        "v": "FFBP/1",
    })
    salt = hashlib.sha256(b"FRACTAL-FLOW/FFBP/1/SALT" + context).digest()
    prk = hkdf_extract(salt, secret)
    c2s = hkdf_expand(prk, b"FRACTAL-FLOW/FFBP/1/c2s/" + context, 32)
    s2c = hkdf_expand(prk, b"FRACTAL-FLOW/FFBP/1/s2c/" + context, 32)
    return c2s, s2c


@dataclass(frozen=True)
class Challenge:
    account_id: str
    session_id: str
    client_nonce: bytes
    server_nonce: bytes

    @classmethod
    def create(cls, account_id: str, session_id: str, client_nonce: bytes | None = None) -> "Challenge":
        return cls(account_id, session_id, client_nonce or secrets.token_bytes(32), secrets.token_bytes(32))

    def transcript(self) -> bytes:
        return canonical_json({
            "account_id": self.account_id,
            "client_nonce": self.client_nonce.hex(),
            "server_nonce": self.server_nonce.hex(),
            "session_id": self.session_id,
            "v": "FFBP/1",
        })

    def proof(self, secret: bytes) -> str:
        return hmac.new(secret, self.transcript(), hashlib.sha256).hexdigest()

    def verify(self, secret: bytes, proof: str) -> bool:
        return hmac.compare_digest(self.proof(secret), proof.lower())
