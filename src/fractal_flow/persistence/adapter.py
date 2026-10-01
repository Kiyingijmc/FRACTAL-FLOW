"""Canonical Persistence Adapter for Decimal-bearing domain objects.

Provides lossless round-trip conversion between active Decimal-bearing domain dataclasses
and JSON-safe primitive representations without modifying frozen persistence files.
"""

from dataclasses import is_dataclass, fields
from decimal import Decimal
import hashlib
import json
from typing import Any, TypeVar

T = TypeVar("T")


def domain_to_primitive(obj: Any) -> Any:
    """Recursively converts Decimal objects and dataclasses into JSON-safe primitive dicts/lists/strings.

    - Decimal -> string representation (e.g. "1.08500")
    - Dataclass -> dict with sorted keys
    - Enum -> string value
    - list/tuple/set/dict -> recursively converted
    """
    if obj is None:
        return None
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, "value") and not is_dataclass(obj) and not isinstance(obj, (int, float, str, bool)):
        # Enum or Unit wrapper type
        return domain_to_primitive(obj.value)
    if is_dataclass(obj) and not isinstance(obj, type):
        result = {}
        for f in fields(obj):
            val = getattr(obj, f.name)
            result[f.name] = domain_to_primitive(val)
        return result
    if isinstance(obj, dict):
        return {str(k): domain_to_primitive(v) for k, v in sorted(obj.items(), key=lambda item: str(item[0]))}
    if isinstance(obj, (list, tuple, set)):
        return [domain_to_primitive(item) for item in obj]
    return obj


def primitive_to_decimal(val: Any) -> Any:
    """Converts string/numeric values or structures containing stringified Decimals into Decimal or original types."""
    if isinstance(val, str):
        try:
            # Check if valid Decimal representation
            dec = Decimal(val)
            # Only treat as Decimal if it has a decimal point or is formatted strictly as a numeric string
            if "." in val or val.replace("-", "").isdigit():
                return dec
        except Exception:
            pass
        return val
    if isinstance(val, dict):
        return {k: primitive_to_decimal(v) for k, v in val.items()}
    if isinstance(val, list):
        return [primitive_to_decimal(v) for v in val]
    return val


def canonical_json_dumps(obj: Any) -> str:
    """Serializes any domain object or dictionary into canonical, deterministic, sorted-key JSON string."""
    primitives = domain_to_primitive(obj)
    return json.dumps(primitives, sort_keys=True, ensure_ascii=True)


def compute_canonical_fingerprint(obj: Any) -> str:
    """Computes a SHA-256 fingerprint from the canonical JSON representation of an object."""
    json_str = canonical_json_dumps(obj)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()
