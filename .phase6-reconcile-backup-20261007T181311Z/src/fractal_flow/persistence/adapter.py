"""Canonical Persistence Adapter for Decimal-bearing domain objects with typed Decimal encoding.

Provides lossless, typed, deterministic round-trip conversion between active Decimal-bearing domain dataclasses
and JSON-safe primitive representations without modifying frozen persistence files or relying on string-shape heuristics.
"""

from dataclasses import is_dataclass, fields
from decimal import Decimal
import hashlib
import json
from typing import Any, TypeVar

T = TypeVar("T")


def domain_to_primitive(obj: Any) -> Any:
    """Recursively converts Decimal objects and dataclasses into JSON-safe primitive dicts/lists/strings.

    - Decimal -> tagged dict structure {"__type__": "decimal", "value": str(obj)}
    - Dataclass -> dict with sorted keys
    - Enum / Unit wrapper -> underlying primitive or value
    - list/tuple/set/dict -> recursively converted with sorted keys and canonical set ordering
    """
    if obj is None:
        return None
    if isinstance(obj, Decimal):
        return {"__type__": "decimal", "value": str(obj)}
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
    if isinstance(obj, (set, frozenset)):
        # Deterministic sorting for sets/frozensets
        converted = [domain_to_primitive(item) for item in obj]
        return sorted(converted, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(obj, (list, tuple)):
        return [domain_to_primitive(item) for item in obj]
    return obj


def primitive_to_decimal(val: Any) -> Any:
    """Recursively decodes tagged Decimal objects {"__type__": "decimal", "value": "..."} back into Decimal instances without string heuristics."""
    if isinstance(val, dict):
        if val.get("__type__") == "decimal" and "value" in val and len(val) == 2:
            return Decimal(str(val["value"]))
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
