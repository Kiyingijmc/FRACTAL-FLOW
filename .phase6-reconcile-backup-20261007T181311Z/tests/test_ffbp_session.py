import hashlib
import hmac
from src.fractal_flow.execution.ffbp_session import Challenge, derive_session_keys, hkdf_expand, hkdf_extract


def test_hkdf_rfc5869_style_vector():
    ikm = bytes.fromhex("0b" * 22)
    salt = bytes.fromhex("000102030405060708090a0b0c")
    info = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9")
    prk = hkdf_extract(salt, ikm)
    okm = hkdf_expand(prk, info, 42)
    assert prk.hex() == "077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5"
    assert okm.hex() == "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"


def test_challenge_binds_account_session_and_fresh_nonces():
    secret = b"shared-secret"
    c = Challenge("A", "S", b"client", b"server")
    proof = c.proof(secret)
    assert c.verify(secret, proof)
    assert not Challenge("B", "S", b"client", b"server").verify(secret, proof)
    c2s, s2c = derive_session_keys(secret, "A", "S", b"client", b"server")
    assert c2s != s2c
    assert len(c2s) == len(s2c) == 32


def test_session_key_changes_with_nonce():
    secret = b"shared-secret"
    a = derive_session_keys(secret, "A", "S", b"c1", b"s1")
    b = derive_session_keys(secret, "A", "S", b"c2", b"s1")
    assert a != b
