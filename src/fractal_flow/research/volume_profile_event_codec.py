"""Canonical Event codec for Volume Profile revisions (G3b Unit 1).

Pure conversion only: this module never appends to a journal or mutates a store.
All causal decisions retain nanosecond precision in the payload. Canonical Event
timestamps are envelope metadata in seconds, consistent with the existing bar
convention. Authority remains ANALYTICAL_ONLY.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any, Mapping

from src.fractal_flow.domain.event import Event
from src.fractal_flow.research.volume_profile import ProfileEvent
from src.fractal_flow.research.volume_profile_revisions import ProfileRevision, RevisionOperation

NS_PER_SECOND = 1_000_000_000
VP_REVISION_EVENT_TYPE = "VP_PROFILE_REVISION_RECORDED"
VP_REVISION_AGGREGATE_TYPE = "VP_PROFILE_REVISION_CHAIN"
VP_REVISION_SCHEMA_VERSION = 1
VP_ROOT_PARENT_ID = "VP_REVISION_CHAIN_ROOT"
VP_AUTHORITY = "ANALYTICAL_ONLY"


class ProfileRevisionCodecError(ValueError):
    """Canonical event conversion failed closed."""


@dataclass(frozen=True, slots=True)
class ProfileRevisionContext:
    """Identity and prior observation context needed to encode any chain member.

    CANCEL has no embedded ProfileEvent, so identity must be supplied from the
    validated chain/store context rather than guessed. For CANCEL,
    prior_observation_event_time_ns must be the exact event time of the latest
    preceding UPSERT in the chain.
    """
    source_id: str
    symbol: str
    domain: str
    prior_observation_event_time_ns: int | None = None

    def __post_init__(self) -> None:
        for name in ("source_id", "symbol", "domain"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ProfileRevisionCodecError(f"{name} must be a non-empty string")
        if self.prior_observation_event_time_ns is not None:
            _require_nonnegative_int(
                self.prior_observation_event_time_ns,
                "prior_observation_event_time_ns",
            )


def _require_nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProfileRevisionCodecError(f"{name} must be a non-negative integer")
    return value


def _decimal_text(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ProfileRevisionCodecError("price and weight must be finite Decimal values")
    # Decimal's fixed-point format avoids exponent notation and binary float loss.
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if rendered in ("", "-0"):
        rendered = "0"
    return rendered


def _canonical_json(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ProfileRevisionCodecError("payload is not canonical JSON data") from exc


def _identity_payload(logical_event_id: str, context: ProfileRevisionContext) -> dict[str, str]:
    return {
        "logical_event_id": logical_event_id,
        "source_id": context.source_id,
        "symbol": context.symbol,
        "domain": context.domain,
    }


def _stable_id(prefix: str, material: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def encode_profile_revision(
    revision: ProfileRevision,
    *,
    context: ProfileRevisionContext | None = None,
    aggregate_version: int,
    parent_event_id: str | None,
    root_event_id: str | None = None,
) -> Event:
    """Encode one revision into the canonical Event envelope without persistence.

    Caller must supply the next aggregate version obtained from validated
    authoritative history. This function does not perform read/validate/append
    atomicity and must not be used as a journal transaction.
    """
    if not isinstance(revision, ProfileRevision):
        raise ProfileRevisionCodecError("revision must be ProfileRevision")
    if isinstance(aggregate_version, bool) or not isinstance(aggregate_version, int) or aggregate_version <= 0:
        raise ProfileRevisionCodecError("aggregate_version must be a positive integer")
    if parent_event_id is not None and (not isinstance(parent_event_id, str) or not parent_event_id):
        raise ProfileRevisionCodecError("parent_event_id must be non-empty or None")
    if root_event_id is not None and (not isinstance(root_event_id, str) or not root_event_id):
        raise ProfileRevisionCodecError("root_event_id must be non-empty or None")
    if (parent_event_id is None) != (revision.supersedes_revision_id is None):
        raise ProfileRevisionCodecError("parent_event_id presence must agree with predecessor revision identity")

    if revision.operation is RevisionOperation.UPSERT:
        event = revision.event
        if not isinstance(event, ProfileEvent):
            raise ProfileRevisionCodecError("UPSERT requires ProfileEvent")
        derived = ProfileRevisionContext(
            source_id=event.source_id, symbol=event.symbol, domain=event.domain.value,
            prior_observation_event_time_ns=event.event_time_ns,
        )
        if context is not None and (
            context.source_id != derived.source_id
            or context.symbol != derived.symbol
            or context.domain != derived.domain
        ):
            raise ProfileRevisionCodecError("supplied context conflicts with UPSERT event identity")
        context = derived
        observation_time_ns = event.event_time_ns
    elif revision.operation is RevisionOperation.CANCEL:
        if revision.event is not None:
            raise ProfileRevisionCodecError("CANCEL must not carry ProfileEvent")
        if context is None or context.prior_observation_event_time_ns is None:
            raise ProfileRevisionCodecError(
                "CANCEL requires chain context including prior UPSERT event time"
            )
        observation_time_ns = context.prior_observation_event_time_ns
    else:
        raise ProfileRevisionCodecError("unsupported revision operation")

    _require_nonnegative_int(revision.available_at_ns, "available_at_ns")
    _require_nonnegative_int(observation_time_ns, "observation_time_ns")
    if revision.available_at_ns < observation_time_ns:
        raise ProfileRevisionCodecError("revision availability precedes observation event time")

    identity = _identity_payload(revision.logical_event_id, context)
    aggregate_id = _stable_id("vp-aggregate-v1", identity)
    event_id = _stable_id("vp-revision-v1", {**identity, "revision_id": revision.revision_id})
    stable_root_id = _stable_id("vp-root-v1", identity)
    if root_event_id is not None and root_event_id != stable_root_id:
        raise ProfileRevisionCodecError(
            "root_event_id conflicts with deterministic chain root identity"
        )
    if revision.supersedes_revision_id is not None:
        expected_parent_id = _stable_id(
            "vp-revision-v1",
            {**identity, "revision_id": revision.supersedes_revision_id},
        )
        if parent_event_id != expected_parent_id:
            raise ProfileRevisionCodecError(
                "parent_event_id does not identify superseded revision"
            )
    parent_id = parent_event_id or VP_ROOT_PARENT_ID
    source_seconds = observation_time_ns // NS_PER_SECOND
    processing_seconds = max(source_seconds, revision.available_at_ns // NS_PER_SECOND)

    observation: dict[str, Any] | None = None
    if revision.operation is RevisionOperation.UPSERT:
        assert revision.event is not None
        observation = {
            "event_id": revision.event.event_id,
            "source_id": revision.event.source_id,
            "symbol": revision.event.symbol,
            "domain": revision.event.domain.value,
            "event_time_ns": revision.event.event_time_ns,
            "available_at_ns": revision.event.available_at_ns,
            "source_sequence": revision.event.source_sequence,
            "price": _decimal_text(revision.event.price),
            "weight": _decimal_text(revision.event.weight),
        }

    payload = {
        "payload_schema_version": VP_REVISION_SCHEMA_VERSION,
        "authority": VP_AUTHORITY,
        **identity,
        "revision_id": revision.revision_id,
        "supersedes_revision_id": revision.supersedes_revision_id,
        "operation": revision.operation.value,
        "available_at_ns": revision.available_at_ns,
        "observation": observation,
    }
    return Event(
        event_id=event_id,
        event_type=VP_REVISION_EVENT_TYPE,
        aggregate_type=VP_REVISION_AGGREGATE_TYPE,
        aggregate_id=aggregate_id,
        root_id=stable_root_id,
        parent_id=parent_id,
        aggregate_version=aggregate_version,
        source_timestamp=source_seconds,
        event_timestamp=source_seconds,
        processing_timestamp=processing_seconds,
        payload=payload,
        schema_version=VP_REVISION_SCHEMA_VERSION,
        configuration_version=1,
        data_version=1,
        feature_version=1,
        reason_codes=[],
        causation_id=parent_event_id,
        correlation_id=revision.logical_event_id,
        actor_id="VOLUME_PROFILE_RESEARCH",
        authority=VP_AUTHORITY,
        account_id=None,
    )


def decode_profile_revision(
    event: Event, *, context: ProfileRevisionContext | None = None
) -> tuple[ProfileRevision, ProfileRevisionContext]:
    """Validate envelope/payload agreement and reconstruct revision + context.

    This is a strict decoder, not a chain validator. Chain topology, aggregate
    sequence, journal checksum, and append/recovery consistency remain separate
    responsibilities.
    """
    if not isinstance(event, Event):
        raise ProfileRevisionCodecError("event must be canonical Event")
    if event.event_type != VP_REVISION_EVENT_TYPE or event.aggregate_type != VP_REVISION_AGGREGATE_TYPE:
        raise ProfileRevisionCodecError("unexpected canonical event/aggregate type")
    for field_name in (
        "schema_version", "aggregate_version", "configuration_version",
        "data_version", "feature_version", "source_timestamp",
        "event_timestamp", "processing_timestamp",
    ):
        value = getattr(event, field_name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ProfileRevisionCodecError(
                f"{field_name} must be an integer, not bool or another type"
            )
    if event.aggregate_version <= 0:
        raise ProfileRevisionCodecError("aggregate_version must be positive")
    if event.schema_version != VP_REVISION_SCHEMA_VERSION:
        raise ProfileRevisionCodecError("unsupported Event schema version")
    if event.authority != VP_AUTHORITY or event.actor_id != "VOLUME_PROFILE_RESEARCH":
        raise ProfileRevisionCodecError("unexpected authority or actor")
    if event.account_id is not None:
        raise ProfileRevisionCodecError("analytical VP event must not carry account identity")
    if (event.configuration_version, event.data_version, event.feature_version) != (1, 1, 1):
        raise ProfileRevisionCodecError("unsupported configuration/data/feature version")
    if event.root_id is None or not isinstance(event.root_id, str) or not event.root_id:
        raise ProfileRevisionCodecError("root_id must be non-empty")
    if not isinstance(event.parent_id, str) or not event.parent_id:
        raise ProfileRevisionCodecError("parent_id must be non-empty")
    if event.parent_id == VP_ROOT_PARENT_ID:
        if event.causation_id is not None:
            raise ProfileRevisionCodecError("root event must not carry causation_id")
    elif event.causation_id != event.parent_id:
        raise ProfileRevisionCodecError("parent_id and causation_id disagree")
    if not isinstance(event.correlation_id, str) or not event.correlation_id:
        raise ProfileRevisionCodecError("correlation_id must be non-empty")
    if event.reason_codes:
        raise ProfileRevisionCodecError("VP revision event must not carry reason codes")
    payload = dict(event.payload)
    required = {
        "payload_schema_version", "authority", "logical_event_id", "source_id",
        "symbol", "domain", "revision_id", "supersedes_revision_id",
        "operation", "available_at_ns", "observation",
    }
    if set(payload) != required:
        raise ProfileRevisionCodecError("payload keys differ from canonical schema")
    payload_schema_version = payload["payload_schema_version"]
    if isinstance(payload_schema_version, bool) or not isinstance(payload_schema_version, int):
        raise ProfileRevisionCodecError(
            "payload_schema_version must be an integer, not bool or another type"
        )
    if payload_schema_version != VP_REVISION_SCHEMA_VERSION or payload["authority"] != VP_AUTHORITY:
        raise ProfileRevisionCodecError("unsupported payload schema or authority")
    operation = payload["operation"]
    try:
        op = RevisionOperation(operation)
    except (TypeError, ValueError) as exc:
        raise ProfileRevisionCodecError("invalid operation") from exc
    available = _require_nonnegative_int(payload["available_at_ns"], "available_at_ns")
    for field_name in ("logical_event_id", "revision_id"):
        value = payload[field_name]
        if not isinstance(value, str) or not value.strip():
            raise ProfileRevisionCodecError(f"{field_name} must be a non-empty string")
    predecessor_id = payload["supersedes_revision_id"]
    if predecessor_id is not None and (not isinstance(predecessor_id, str) or not predecessor_id.strip()):
        raise ProfileRevisionCodecError("supersedes_revision_id must be None or a non-empty string")
    supplied_context = context
    context = ProfileRevisionContext(
        source_id=payload["source_id"], symbol=payload["symbol"], domain=payload["domain"],
        prior_observation_event_time_ns=(
            supplied_context.prior_observation_event_time_ns if supplied_context is not None else None
        ),
    )
    if supplied_context is not None and (
        supplied_context.source_id != context.source_id
        or supplied_context.symbol != context.symbol
        or supplied_context.domain != context.domain
    ):
        raise ProfileRevisionCodecError("supplied decode context conflicts with event identity")
    identity = _identity_payload(payload["logical_event_id"], context)
    if event.correlation_id != payload["logical_event_id"]:
        raise ProfileRevisionCodecError("correlation_id conflicts with logical_event_id")
    if event.aggregate_id != _stable_id("vp-aggregate-v1", identity):
        raise ProfileRevisionCodecError("aggregate identity mismatch")
    expected_root_id = _stable_id("vp-root-v1", identity)
    if event.root_id != expected_root_id:
        raise ProfileRevisionCodecError("root identity mismatch")
    expected_event_id = _stable_id("vp-revision-v1", {**identity, "revision_id": payload["revision_id"]})
    if event.event_id != expected_event_id:
        raise ProfileRevisionCodecError("event identity mismatch")

    obs = payload["observation"]
    profile_event = None
    observation_time_ns: int
    if op is RevisionOperation.UPSERT:
        if not isinstance(obs, Mapping):
            raise ProfileRevisionCodecError("UPSERT observation must be a mapping")
        obs_required = {"event_id", "source_id", "symbol", "domain", "event_time_ns",
                        "available_at_ns", "source_sequence", "price", "weight"}
        if set(obs) != obs_required:
            raise ProfileRevisionCodecError("observation keys differ from canonical schema")
        if any(not isinstance(obs[k], str) for k in ("price", "weight")):
            raise ProfileRevisionCodecError("price and weight must be canonical decimal strings")
        try:
            price, weight = Decimal(obs["price"]), Decimal(obs["weight"])
        except InvalidOperation as exc:
            raise ProfileRevisionCodecError("invalid decimal text") from exc
        if _decimal_text(price) != obs["price"] or _decimal_text(weight) != obs["weight"]:
            raise ProfileRevisionCodecError("non-canonical decimal representation")
        from src.fractal_flow.research.volume_profile import ProfileDomain
        try:
            domain = ProfileDomain(obs["domain"])
        except (TypeError, ValueError) as exc:
            raise ProfileRevisionCodecError("invalid observation domain") from exc
        profile_event = ProfileEvent(
            event_id=obs["event_id"], source_id=obs["source_id"], symbol=obs["symbol"],
            domain=domain,
            event_time_ns=_require_nonnegative_int(obs["event_time_ns"], "event_time_ns"),
            available_at_ns=_require_nonnegative_int(obs["available_at_ns"], "observation.available_at_ns"),
            source_sequence=_require_nonnegative_int(obs["source_sequence"], "source_sequence"),
            price=price, weight=weight,
        )
        if (profile_event.source_id, profile_event.symbol, profile_event.domain.value) != (
            context.source_id, context.symbol, context.domain
        ):
            raise ProfileRevisionCodecError("observation identity conflicts with payload identity")
        observation_time_ns = profile_event.event_time_ns
    else:
        if obs is not None:
            raise ProfileRevisionCodecError("CANCEL observation must be null")
        if context is None or context.prior_observation_event_time_ns is None:
            raise ProfileRevisionCodecError(
                "CANCEL decoding requires validated prior-chain observation-time context"
            )
        observation_time_ns = context.prior_observation_event_time_ns

    if available < observation_time_ns:
        raise ProfileRevisionCodecError("revision availability precedes observation event time")
    source_seconds = observation_time_ns // NS_PER_SECOND
    if (event.source_timestamp, event.event_timestamp) != (source_seconds, source_seconds):
        raise ProfileRevisionCodecError("Event timestamp envelope conflicts with payload")
    if event.processing_timestamp != max(source_seconds, available // NS_PER_SECOND):
        raise ProfileRevisionCodecError("processing timestamp envelope conflicts with payload")
    if event.parent_id == VP_ROOT_PARENT_ID:
        if payload["supersedes_revision_id"] is not None:
            raise ProfileRevisionCodecError("root envelope cannot supersede a revision")
    elif payload["supersedes_revision_id"] is None:
        raise ProfileRevisionCodecError("non-root envelope must identify a predecessor revision")
    else:
        expected_parent_id = _stable_id(
            "vp-revision-v1",
            {**identity, "revision_id": payload["supersedes_revision_id"]},
        )
        if event.parent_id != expected_parent_id:
            raise ProfileRevisionCodecError(
                "parent identity does not match superseded revision"
            )
    revision = ProfileRevision(
        logical_event_id=payload["logical_event_id"],
        revision_id=payload["revision_id"],
        supersedes_revision_id=payload["supersedes_revision_id"],
        operation=op,
        available_at_ns=available,
        event=profile_event,
    )
    if op is RevisionOperation.UPSERT:
        context = ProfileRevisionContext(
            source_id=context.source_id,
            symbol=context.symbol,
            domain=context.domain,
            prior_observation_event_time_ns=profile_event.event_time_ns if profile_event is not None else None,
        )
    return revision, context
