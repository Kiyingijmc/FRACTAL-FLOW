import hashlib
import hmac
import json
import struct
from pathlib import Path


def test_supplied_mql5_interop_vector_matches_python_canonicalization():
    vector = json.loads(Path("mql5/Phase6Bridge/FractalFlowBridge/Docs/FFBP_INTEROP_VECTOR.json").read_text())
    body = vector["canonical_body_without_mac"].encode("utf-8")
    mac = hmac.new(vector["secret"].encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert mac == vector["hmac_sha256"]
    wire_obj = json.loads(vector["canonical_body_without_mac"])
    wire_obj["mac"] = mac
    wire = json.dumps(wire_obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    assert wire.decode("utf-8") == vector["canonical_wire_body"]
    assert len(wire) == vector["wire_body_bytes"]
    assert struct.pack(">I", len(wire)).hex() == vector["frame_prefix_hex"]
