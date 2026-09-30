"""Authoritative Reconciliation Engine comparing local intents against broker truth, preserving UNKNOWN semantics when evidence is non-authoritative."""

import hashlib
import hmac
import json
import time
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import Enum, unique
from types import MappingProxyType
from typing import Any

from src.fractal_flow.domain.models import (
    BrokerDeal,
    BrokerOrder,
    DealEntryRole,
    ExecutionIntent,
    Position,
)
from src.fractal_flow.execution.execution_state import ExecutionState


@unique
class ReconciliationMismatchType(str, Enum):
    MATCH = "MATCH"
    LOCAL_ONLY = "LOCAL_ONLY"
    BROKER_ONLY = "BROKER_ONLY"
    STATE_MISMATCH = "STATE_MISMATCH"
    VOLUME_MISMATCH = "VOLUME_MISMATCH"
    DEAL_CONTRADICTION = "DEAL_CONTRADICTION"
    ORPHANED_BROKER = "ORPHANED_BROKER"
    UNKNOWN_UNRESOLVED = "UNKNOWN_UNRESOLVED"


@unique
class OrphanStatus(str, Enum):
    DETECTED = "DETECTED"
    RECONCILING = "RECONCILING"
    REATTACHED = "REATTACHED"
    RECOVERED = "RECOVERED"
    QUARANTINED = "QUARANTINED"
    EXPIRED = "EXPIRED"


# Legal transitions matrix for OrphanRecord state machine
_LEGAL_ORPHAN_TRANSITIONS = {
    OrphanStatus.DETECTED: {OrphanStatus.RECONCILING, OrphanStatus.QUARANTINED},
    OrphanStatus.RECONCILING: {
        OrphanStatus.REATTACHED,
        OrphanStatus.RECOVERED,
        OrphanStatus.QUARANTINED,
        OrphanStatus.EXPIRED,
    },
    OrphanStatus.REATTACHED: set(),
    OrphanStatus.RECOVERED: set(),
    OrphanStatus.QUARANTINED: {OrphanStatus.RECONCILING, OrphanStatus.EXPIRED},
    OrphanStatus.EXPIRED: set(),
}


def _deep_freeze(val: Any) -> Any:
    """Recursively converts dictionaries, lists, sets, and mappings to deeply immutable types."""
    if val is None or isinstance(val, (int, float, str, bool, Decimal, Enum, bytes)):
        return val
    if isinstance(val, (dict, MappingProxyType, Mapping)):
        return MappingProxyType({k: _deep_freeze(v) for k, v in val.items()})
    if isinstance(val, (list, tuple)):
        return tuple(_deep_freeze(x) for x in val)
    if isinstance(val, (set, frozenset)):
        return frozenset(_deep_freeze(x) for x in val)
    raise TypeError(
        f"Unsupported or mutable custom type '{type(val).__name__}' in OrphanRecord deep freeze."
    )


@dataclass(frozen=True)
class OrphanRecord:
    """Deeply immutable record tracking orphaned broker positions or orders through explicit resolution lifecycle."""

    orphan_id: str
    object_type: str  # "POSITION" or "ORDER"
    object_id: str
    symbol: str
    volume: float
    status: OrphanStatus = OrphanStatus.DETECTED
    protective_monitoring_active: bool = True
    detected_at: int = 0
    updated_at: int = 0
    details: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if isinstance(self.details, dict):
            object.__setattr__(self, "details", _deep_freeze(self.details))

    def is_resolved_or_quarantined(self) -> bool:
        """Returns True if the orphan is resolved or safely quarantined under protective monitoring."""
        return self.status in (
            OrphanStatus.REATTACHED,
            OrphanStatus.RECOVERED,
            OrphanStatus.QUARANTINED,
            OrphanStatus.EXPIRED,
        )

    def transition(
        self, new_status: OrphanStatus, reason: str = "", timestamp: int = 0
    ) -> "OrphanRecord":
        """Executes explicit legal orphan state transition returning a new immutable OrphanRecord."""
        if new_status not in _LEGAL_ORPHAN_TRANSITIONS.get(self.status, set()):
            raise ValueError(
                f"Illegal orphan status transition from '{self.status}' to '{new_status}' for orphan '{self.orphan_id}'"
            )

        now = timestamp or int(time.time())
        new_details = dict(self.details)
        new_details["last_transition_reason"] = reason
        new_details["previous_status"] = self.status.value

        return replace(
            self,
            status=new_status,
            updated_at=now,
            details=_deep_freeze(new_details),
        )


@unique
class BrokerQueryQuality(str, Enum):
    FOUND = "FOUND"
    NOT_FOUND_AUTHORITATIVE = "NOT_FOUND_AUTHORITATIVE"
    NOT_FOUND_NON_AUTHORITATIVE = "NOT_FOUND_NON_AUTHORITATIVE"
    QUERY_FAILED = "QUERY_FAILED"
    PARTIAL = "PARTIAL"
    STALE = "STALE"


_BROKER_ISSUANCE_KEY = object()


@dataclass(frozen=True)
class BrokerQueryResult:
    """Encapsulates authoritative broker query response metadata and execution objects."""

    status: str = "SUCCESS"
    authority: BrokerQueryQuality = BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE
    query_timestamp: int = 0
    completeness: bool = False
    broker_orders: Mapping[str, BrokerOrder] = field(default_factory=dict)
    broker_positions: Mapping[str, Position] = field(default_factory=dict)
    broker_deals: Mapping[str, BrokerDeal] = field(default_factory=dict)
    provider_identity: str = "BrokerQueryProvider"
    account_id: str = ""
    session_id: str = ""
    observation_digest: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    _observation: Any | None = field(default=None, repr=False, compare=False)
    _issuance_key: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            self.authority
            in (
                BrokerQueryQuality.FOUND,
                BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE,
            )
            and self._issuance_key is not _BROKER_ISSUANCE_KEY
        ):
            # Direct construction claiming FOUND / NOT_FOUND_AUTHORITATIVE without issuance key is downgraded to non-authoritative!
            object.__setattr__(
                self, "authority", BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE
            )
            object.__setattr__(self, "completeness", False)
            object.__setattr__(self, "status", "NON_AUTHORITATIVE")

    @property
    def authoritative(self) -> bool:
        return self.authority in (
            BrokerQueryQuality.FOUND,
            BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE,
        )

    @classmethod
    def from_observation(
        cls,
        observation: Any,
        producer_capability: Any,
        session_id: str,
    ) -> "BrokerQueryResult":
        from src.fractal_flow.execution.recovery import (
            CapabilityRole,
            ProducerCapability,
            RecoveryEvidenceError,
            SealedObservation,
        )

        if (
            not isinstance(producer_capability, ProducerCapability)
            or producer_capability.role != CapabilityRole.BROKER_QUERY
        ):
            raise RecoveryEvidenceError(
                "BrokerQueryResult requires a valid BROKER_QUERY ProducerCapability."
            )

        if not isinstance(observation, SealedObservation) or not observation.verify(
            producer_capability.authority_domain_id,
            CapabilityRole.BROKER_QUERY,
            session_id,
            producer_capability._role_key,
        ):
            raise RecoveryEvidenceError(
                "SealedObservation verification failed for BrokerQueryResult."
            )

        if observation.producer_id != producer_capability.producer_id:
            raise RecoveryEvidenceError(
                "Producer ID mismatch in SealedObservation for BrokerQueryResult."
            )

        payload = observation.frozen_payload
        quality = BrokerQueryQuality(
            payload.get(
                "query_quality", BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE.value
            )
        )
        completeness = bool(payload.get("completeness", False))
        q_timestamp = int(payload.get("query_timestamp", 0))
        provider_id = str(
            payload.get("provider_identity", producer_capability.producer_id)
        )
        acc_id = str(payload.get("account_id", ""))

        orders = dict(payload.get("broker_orders", {}))
        positions = dict(payload.get("broker_positions", {}))
        deals = dict(payload.get("broker_deals", {}))

        res: BrokerQueryResult = cls(
            status="SUCCESS"
            if quality
            in (BrokerQueryQuality.FOUND, BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE)
            else "NON_AUTHORITATIVE",
            authority=quality,
            query_timestamp=q_timestamp,
            completeness=completeness,
            broker_orders=orders,
            broker_positions=positions,
            broker_deals=deals,
            provider_identity=provider_id,
            account_id=acc_id,
            session_id=session_id,
            observation_digest=observation.payload_digest,
            details=dict(payload.get("details", {})),
            _issuance_key=_BROKER_ISSUANCE_KEY,
        )
        object.__setattr__(res, "_observation", observation)
        return res


class AuthoritativeBrokerAdapter:
    """Authoritative adapter for broker queries bound to a ProducerCapability."""

    def __init__(
        self,
        capability: Any,
        account_id: str = "ACT_PRIMARY",
        orders: dict[str, BrokerOrder] | None = None,
        positions: dict[str, Position] | None = None,
        deals: dict[str, BrokerDeal] | None = None,
        authority: BrokerQueryQuality = BrokerQueryQuality.FOUND,
        max_age_seconds: int = 300,
        provider_identity: str = "AuthoritativeBrokerAdapter",
    ) -> None:
        from src.fractal_flow.execution.recovery import (
            CapabilityRole,
            ProducerCapability,
            RecoveryEvidenceError,
        )

        if (
            not isinstance(capability, ProducerCapability)
            or capability.role != CapabilityRole.BROKER_QUERY
        ):
            raise RecoveryEvidenceError(
                "AuthoritativeBrokerAdapter requires a valid BROKER_QUERY ProducerCapability."
            )
        self.capability = capability
        self.account_id = account_id
        self._orders = orders or {}
        self._positions = positions or {}
        self._deals = deals or {}
        self._authority = authority
        self._max_age_seconds = max_age_seconds
        self._provider_identity = provider_identity

    def produce_broker_observation(
        self, session_id: str, current_timestamp: int = 0
    ) -> Any:
        from src.fractal_flow.execution.recovery import SealedObservation

        now = current_timestamp or int(time.time())
        authority = self._authority

        if (
            self._max_age_seconds > 0
            and self.capability
            and getattr(self, "_query_timestamp", 0) > 0
            and now > 0
        ) and now - getattr(self, "_query_timestamp", 0) > self._max_age_seconds:
            authority = BrokerQueryQuality.STALE

        payload = {
            "account_id": self.account_id,
            "provider_identity": self._provider_identity,
            "query_timestamp": now,
            "query_quality": authority.value,
            "completeness": authority
            in (BrokerQueryQuality.FOUND, BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE),
            "broker_orders": dict(self._orders),
            "broker_positions": dict(self._positions),
            "broker_deals": dict(self._deals),
            "details": {},
        }
        return SealedObservation.create(self.capability, session_id, now, payload)

    def query_broker_state(
        self, session_id: str, current_timestamp: int = 0
    ) -> BrokerQueryResult:
        obs = self.produce_broker_observation(session_id, current_timestamp)
        return BrokerQueryResult.from_observation(obs, self.capability, session_id)


class BrokerQueryProvider:
    """Provider boundary responsible for issuing broker state queries."""

    def __init__(
        self,
        orders: dict[str, BrokerOrder] | None = None,
        positions: dict[str, Position] | None = None,
        deals: dict[str, BrokerDeal] | None = None,
        authority: BrokerQueryQuality = BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE,
        max_age_seconds: int = 300,
        query_timestamp: int = 0,
        provider_identity: str = "BrokerQueryProvider",
        capability: Any | None = None,
    ) -> None:
        self._orders = orders or {}
        self._positions = positions or {}
        self._deals = deals or {}
        self._authority = authority
        self._max_age_seconds = max_age_seconds
        self._query_timestamp = query_timestamp
        self._provider_identity = provider_identity
        self._capability = capability

    def query_broker_state(
        self, session_id: str = "", current_timestamp: int = 0
    ) -> BrokerQueryResult:
        now = current_timestamp or self._query_timestamp or int(time.time())
        authority = self._authority

        if (
            self._max_age_seconds > 0
            and self._query_timestamp > 0
            and now > 0
            and now - self._query_timestamp > self._max_age_seconds
        ):
            authority = BrokerQueryQuality.STALE

        if self._capability is not None and session_id:
            adapter = AuthoritativeBrokerAdapter(
                capability=self._capability,
                orders=self._orders,
                positions=self._positions,
                deals=self._deals,
                authority=authority,
                max_age_seconds=self._max_age_seconds,
                provider_identity=self._provider_identity,
            )
            return adapter.query_broker_state(session_id, now)

        # Un-capability-backed provider queries are non-authoritative
        final_authority = (
            BrokerQueryQuality.STALE
            if authority == BrokerQueryQuality.STALE
            else BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE
        )

        return BrokerQueryResult(
            status="NON_AUTHORITATIVE",
            authority=final_authority,
            query_timestamp=now,
            completeness=False,
            broker_orders=dict(self._orders),
            broker_positions=dict(self._positions),
            broker_deals=dict(self._deals),
            provider_identity=self._provider_identity,
            session_id=session_id,
        )


_RECON_MODULE_SECRET: bytes = uuid.uuid4().bytes
_RECON_ENGINE_SECRET: object = object()


@dataclass(frozen=True)
class _ReconciliationAuthorityStamp:
    """Opaque, unforgeable capability proving a ReconciliationReport was directly generated by ReconciliationEngine."""

    authority_domain_id: str
    engine_id: str
    session_id: str
    broker_observation_digest: str
    generated_at: int
    signature: str

    def __copy__(self) -> None:
        return None

    def __deepcopy__(self, memo: Any) -> None:
        return None

    @classmethod
    def _issue(
        cls,
        authority_domain_id: str,
        engine_id: str,
        session_id: str,
        broker_obs_digest: str,
        generated_at: int,
        report_digest: str,
        secret_key: object,
    ) -> "_ReconciliationAuthorityStamp":
        if secret_key is not _RECON_ENGINE_SECRET:
            raise ValueError(
                "Unauthorized reconciliation authority stamp issuance attempt rejected."
            )
        msg = f"{authority_domain_id}|{engine_id}|{session_id}|{broker_obs_digest}|{generated_at}|{report_digest}".encode()
        sig = hmac.new(_RECON_MODULE_SECRET, msg, hashlib.sha256).hexdigest()
        return cls(
            authority_domain_id=authority_domain_id,
            engine_id=engine_id,
            session_id=session_id,
            broker_observation_digest=broker_obs_digest,
            generated_at=generated_at,
            signature=sig,
        )

    def verify(self, report_digest: str, expected_session_id: str = "") -> bool:
        if expected_session_id and self.session_id != expected_session_id:
            return False
        msg = f"{self.authority_domain_id}|{self.engine_id}|{self.session_id}|{self.broker_observation_digest}|{self.generated_at}|{report_digest}".encode()
        expected_sig = hmac.new(_RECON_MODULE_SECRET, msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(self.signature, expected_sig)


@dataclass(frozen=True)
class ReconciliationResult:
    intent_id: str
    mismatch_type: ReconciliationMismatchType
    resolved_execution_state: ExecutionState
    details: dict[str, Any]


@dataclass(frozen=True)
class ReconciliationReport:
    """Typed, immutable reconciliation report deriving all counts and metrics internally."""

    results: tuple[ReconciliationResult, ...]
    unknown_count: int
    orphaned_count: int
    authoritative: bool
    complete: bool
    query_quality: BrokerQueryQuality
    query_timestamp: int
    temporal_boundary: int
    broker_orders_seen: int
    broker_positions_seen: int
    broker_deals_seen: int
    generated_at: int
    broker_observation_digest: str = ""
    session_id: str = ""
    orphan_records: tuple[OrphanRecord, ...] = field(default_factory=tuple)
    _authority_stamp: _ReconciliationAuthorityStamp | None = field(
        default=None, repr=False, compare=False
    )

    def __getitem__(self, index: int) -> ReconciliationResult:
        res: ReconciliationResult = self.results[index]
        return res

    def __iter__(self) -> Iterator[ReconciliationResult]:
        return iter(self.results)

    def __len__(self) -> int:
        return len(self.results)

    def compute_digest(self) -> str:
        """Computes deterministic SHA-256 hash over canonical fields of this report."""
        raw = {
            "results": [
                {
                    "intent_id": r.intent_id,
                    "mismatch_type": r.mismatch_type.value,
                    "resolved_execution_state": r.resolved_execution_state.value,
                    "details": dict(r.details),
                }
                for r in self.results
            ],
            "unknown_count": self.unknown_count,
            "orphaned_count": self.orphaned_count,
            "authoritative": self.authoritative,
            "complete": self.complete,
            "query_quality": self.query_quality.value,
            "query_timestamp": self.query_timestamp,
            "temporal_boundary": self.temporal_boundary,
            "broker_orders_seen": self.broker_orders_seen,
            "broker_positions_seen": self.broker_positions_seen,
            "broker_deals_seen": self.broker_deals_seen,
            "generated_at": self.generated_at,
            "broker_observation_digest": self.broker_observation_digest,
            "session_id": self.session_id,
            "orphan_records": [
                {
                    "orphan_id": o.orphan_id,
                    "object_type": o.object_type,
                    "object_id": o.object_id,
                    "symbol": o.symbol,
                    "volume": o.volume,
                    "status": o.status.value,
                    "protective_monitoring_active": o.protective_monitoring_active,
                    "detected_at": o.detected_at,
                    "updated_at": o.updated_at,
                    "details": dict(o.details),
                }
                for o in self.orphan_records
            ],
        }
        canonical_json = json.dumps(raw, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def has_valid_authority_stamp(self, expected_session_id: str = "") -> bool:
        if self._authority_stamp is None:
            return False
        return self._authority_stamp.verify(
            expected_session_id=expected_session_id, report_digest=self.compute_digest()
        )


class ReconciliationEngine:
    """Authoritative reconciliation engine comparing local execution intent state against broker-side order/position/deal truth."""

    @staticmethod
    def _normalize_role(role_val: Any) -> DealEntryRole:
        if isinstance(role_val, DealEntryRole):
            return role_val
        if isinstance(role_val, str):
            try:
                return DealEntryRole(role_val.upper())
            except ValueError:
                return DealEntryRole.UNKNOWN
        return DealEntryRole.UNKNOWN

    @classmethod
    def reconcile_intent(
        cls,
        local_intent: ExecutionIntent,
        broker_orders: Mapping[str, BrokerOrder],
        broker_positions: Mapping[str, Position],
        broker_deals: Mapping[str, BrokerDeal] | None = None,
        query_quality: BrokerQueryQuality = BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE,
        query_result: BrokerQueryResult | None = None,
    ) -> ReconciliationResult:
        if query_result:
            broker_orders = query_result.broker_orders
            broker_positions = query_result.broker_positions
            broker_deals = query_result.broker_deals or broker_deals
            query_quality = query_result.authority

        # Search broker positions directly
        matching_pos = None
        for pos in broker_positions.values():
            if pos.intent_id == local_intent.intent_id:
                matching_pos = pos
                break

        # Search broker orders directly
        matching_order = None
        for ord_obj in broker_orders.values():
            if ord_obj.intent_id == local_intent.intent_id:
                matching_order = ord_obj
                break

        # Validate Deal Chain taking into account explicit entry_role semantics and duplicate detection
        if broker_deals and (matching_pos or matching_order):
            target_order_id = (
                matching_order.order_id
                if matching_order
                else (matching_pos.order_id if matching_pos else "")
            )
            target_pos_id = matching_pos.position_id if matching_pos else ""

            related_deals = [
                d
                for d in broker_deals.values()
                if (target_order_id and d.order_id == target_order_id)
                or (target_pos_id and d.position_id == target_pos_id)
            ]

            # Detect duplicate deal IDs
            deal_ids = [d.deal_id for d in related_deals]
            if len(deal_ids) != len(set(deal_ids)):
                return ReconciliationResult(
                    intent_id=local_intent.intent_id,
                    mismatch_type=ReconciliationMismatchType.DEAL_CONTRADICTION,
                    resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                    details={"note": "Duplicate deal IDs detected in deal chain"},
                )

            # Sort deals chronologically and execute formal deal chain state transitions
            sorted_deals = sorted(
                related_deals, key=lambda x: getattr(x, "timestamp", 0)
            )
            v_net = 0.0
            side_net = None

            for d in sorted_deals:
                role = cls._normalize_role(
                    getattr(d, "entry_role", DealEntryRole.UNKNOWN)
                )
                if role == DealEntryRole.UNKNOWN:
                    return ReconciliationResult(
                        intent_id=local_intent.intent_id,
                        mismatch_type=ReconciliationMismatchType.DEAL_CONTRADICTION,
                        resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                        details={
                            "note": f"Missing or unknown deal entry role for deal '{d.deal_id}'"
                        },
                    )

                d_side = str(getattr(d, "side", "")).upper()

                if role in (DealEntryRole.OPEN, DealEntryRole.INCREASE):
                    if v_net == 0.0:
                        side_net = d_side
                        v_net = float(d.volume)
                    elif d_side == side_net:
                        v_net += float(d.volume)
                    else:
                        return ReconciliationResult(
                            intent_id=local_intent.intent_id,
                            mismatch_type=ReconciliationMismatchType.DEAL_CONTRADICTION,
                            resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                            details={
                                "note": f"Contradictory deal side '{d_side}' for OPEN/INCREASE deal '{d.deal_id}'"
                            },
                        )

                elif role in (DealEntryRole.CLOSE, DealEntryRole.DECREASE):
                    if v_net <= 0.0 or side_net is None:
                        return ReconciliationResult(
                            intent_id=local_intent.intent_id,
                            mismatch_type=ReconciliationMismatchType.DEAL_CONTRADICTION,
                            resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                            details={
                                "note": f"Contradictory deal sequence: CLOSE/DECREASE deal '{d.deal_id}' before OPEN"
                            },
                        )
                    if float(d.volume) > v_net + 0.0001:
                        return ReconciliationResult(
                            intent_id=local_intent.intent_id,
                            mismatch_type=ReconciliationMismatchType.DEAL_CONTRADICTION,
                            resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                            details={
                                "note": f"Over-close detected in deal '{d.deal_id}': close volume {d.volume} > net open volume {v_net}"
                            },
                        )
                    v_net -= float(d.volume)
                    if abs(v_net) < 0.0001:
                        v_net = 0.0
                        side_net = None

                elif role == DealEntryRole.REVERSAL:
                    if v_net <= 0.0 or side_net is None:
                        return ReconciliationResult(
                            intent_id=local_intent.intent_id,
                            mismatch_type=ReconciliationMismatchType.DEAL_CONTRADICTION,
                            resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                            details={
                                "note": f"Contradictory deal sequence: REVERSAL deal '{d.deal_id}' without prior OPEN exposure"
                            },
                        )
                    if d_side == side_net:
                        return ReconciliationResult(
                            intent_id=local_intent.intent_id,
                            mismatch_type=ReconciliationMismatchType.DEAL_CONTRADICTION,
                            resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                            details={
                                "note": f"Contradictory deal side '{d_side}' for REVERSAL deal '{d.deal_id}' (same as active exposure)"
                            },
                        )

                    v_close = min(float(d.volume), v_net)
                    v_opp = float(d.volume) - v_close
                    v_net -= v_close

                    if v_opp > 0.0:
                        side_net = d_side
                        v_net = v_opp
                    elif abs(v_net) < 0.0001:
                        v_net = 0.0
                        side_net = None

            if matching_pos:
                if abs(v_net - float(matching_pos.filled_volume)) > 0.0001:
                    return ReconciliationResult(
                        intent_id=local_intent.intent_id,
                        mismatch_type=ReconciliationMismatchType.DEAL_CONTRADICTION,
                        resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                        details={
                            "note": f"Net deal volume ({v_net}) contradicts position filled volume ({matching_pos.filled_volume})",
                            "position_id": matching_pos.position_id,
                        },
                    )
                if (
                    side_net
                    and matching_pos.side
                    and side_net != matching_pos.side.upper()
                ):
                    return ReconciliationResult(
                        intent_id=local_intent.intent_id,
                        mismatch_type=ReconciliationMismatchType.DEAL_CONTRADICTION,
                        resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                        details={
                            "note": f"Net deal side ({side_net}) contradicts position side ({matching_pos.side})",
                            "position_id": matching_pos.position_id,
                        },
                    )

        if matching_pos:
            resolved_state = (
                ExecutionState.EXEC_PARTIAL
                if matching_pos.remaining_volume > 0
                else ExecutionState.EXEC_FILLED
            )
            mismatch = (
                ReconciliationMismatchType.MATCH
                if local_intent.status == resolved_state.value
                else ReconciliationMismatchType.STATE_MISMATCH
            )
            return ReconciliationResult(
                intent_id=local_intent.intent_id,
                mismatch_type=mismatch,
                resolved_execution_state=resolved_state,
                details={
                    "position_id": matching_pos.position_id,
                    "filled_volume": matching_pos.filled_volume,
                },
            )

        if matching_order:
            resolved_state = (
                ExecutionState.EXEC_ACCEPTED
                if matching_order.status == "ACCEPTED"
                else ExecutionState.EXEC_FILLED
            )
            mismatch = (
                ReconciliationMismatchType.MATCH
                if local_intent.status == resolved_state.value
                else ReconciliationMismatchType.STATE_MISMATCH
            )
            return ReconciliationResult(
                intent_id=local_intent.intent_id,
                mismatch_type=mismatch,
                resolved_execution_state=resolved_state,
                details={
                    "order_id": matching_order.order_id,
                    "order_status": matching_order.status,
                },
            )

        # Broker has no record of order or position
        if query_quality == BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE:
            return ReconciliationResult(
                intent_id=local_intent.intent_id,
                mismatch_type=ReconciliationMismatchType.LOCAL_ONLY,
                resolved_execution_state=ExecutionState.EXEC_REJECTED,
                details={
                    "note": "Broker authoritatively confirmed order non-existence / rejection."
                },
            )

        # Fail-closed: UNKNOWN != REJECTED without authoritative evidence!
        return ReconciliationResult(
            intent_id=local_intent.intent_id,
            mismatch_type=ReconciliationMismatchType.LOCAL_ONLY,
            resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
            details={
                "note": "Broker record absent but query is non-authoritative. Preserving EXEC_UNKNOWN."
            },
        )

    @classmethod
    def reconcile_broker_wide(
        cls,
        local_intents: dict[str, ExecutionIntent],
        broker_orders: Mapping[str, BrokerOrder] | None = None,
        broker_positions: Mapping[str, Position] | None = None,
        broker_deals: Mapping[str, BrokerDeal] | None = None,
        authoritative_rejections: set[str] | None = None,
        query_result: BrokerQueryResult | None = None,
        session_id: str = "",
    ) -> ReconciliationReport:
        """Performs full broker-wide multi-directional reconciliation discovering local-only, matched, and orphaned broker objects.

        Returns an immutable ReconciliationReport signed with a sealed authority stamp.
        """
        now = int(time.time())
        q_timestamp = now
        q_quality = BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE
        q_complete = False
        broker_obs_digest = ""
        report_session_id = session_id

        if query_result is not None:
            broker_orders = query_result.broker_orders
            broker_positions = query_result.broker_positions
            broker_deals = query_result.broker_deals or broker_deals
            q_quality = query_result.authority
            q_timestamp = query_result.query_timestamp or now
            q_complete = query_result.completeness
            broker_obs_digest = query_result.observation_digest
            if query_result.session_id:
                report_session_id = query_result.session_id
        else:
            broker_orders = broker_orders or {}
            broker_positions = broker_positions or {}
            broker_deals = broker_deals or {}

        results_list: list[ReconciliationResult] = []
        orphan_records: list[OrphanRecord] = []

        # Reconcile local intents against broker truth
        for intent in local_intents.values():
            res = cls.reconcile_intent(
                local_intent=intent,
                broker_orders=broker_orders,
                broker_positions=broker_positions,
                broker_deals=broker_deals,
                query_quality=q_quality,
            )
            results_list.append(res)

        # Discover orphaned broker positions
        for pos in broker_positions.values():
            if pos.intent_id not in local_intents:
                results_list.append(
                    ReconciliationResult(
                        intent_id=pos.intent_id or f"ORPHAN_POS_{pos.position_id}",
                        mismatch_type=ReconciliationMismatchType.ORPHANED_BROKER,
                        resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                        details={
                            "position_id": pos.position_id,
                            "symbol": pos.symbol,
                            "volume": pos.filled_volume,
                        },
                    )
                )
                orphan_records.append(
                    OrphanRecord(
                        orphan_id=f"ORPHAN_POS_{pos.position_id}",
                        object_type="POSITION",
                        object_id=pos.position_id,
                        symbol=pos.symbol,
                        volume=float(pos.filled_volume),
                        status=OrphanStatus.DETECTED,
                        protective_monitoring_active=True,
                        detected_at=now,
                        updated_at=now,
                        details=_deep_freeze({"intent_id": pos.intent_id}),
                    )
                )

        # Discover orphaned broker orders
        for ord_obj in broker_orders.values():
            if ord_obj.intent_id not in local_intents and not any(
                p.order_id == ord_obj.order_id for p in broker_positions.values()
            ):
                results_list.append(
                    ReconciliationResult(
                        intent_id=ord_obj.intent_id or f"ORPHAN_ORD_{ord_obj.order_id}",
                        mismatch_type=ReconciliationMismatchType.ORPHANED_BROKER,
                        resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                        details={
                            "order_id": ord_obj.order_id,
                            "symbol": ord_obj.symbol,
                            "volume": ord_obj.volume,
                        },
                    )
                )
                orphan_records.append(
                    OrphanRecord(
                        orphan_id=f"ORPHAN_ORD_{ord_obj.order_id}",
                        object_type="ORDER",
                        object_id=ord_obj.order_id,
                        symbol=ord_obj.symbol,
                        volume=float(ord_obj.volume),
                        status=OrphanStatus.DETECTED,
                        protective_monitoring_active=True,
                        detected_at=now,
                        updated_at=now,
                        details=_deep_freeze({"intent_id": ord_obj.intent_id}),
                    )
                )

        results_tuple = tuple(results_list)

        # Derive counts internally from actual results tuple
        unknown_count = sum(
            1
            for r in results_tuple
            if r.resolved_execution_state == ExecutionState.EXEC_UNKNOWN
        )
        orphaned_count = sum(
            1
            for r in results_tuple
            if r.mismatch_type == ReconciliationMismatchType.ORPHANED_BROKER
        )

        authoritative = q_quality in (
            BrokerQueryQuality.FOUND,
            BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE,
        )

        unsealed_report = ReconciliationReport(
            results=results_tuple,
            unknown_count=unknown_count,
            orphaned_count=orphaned_count,
            authoritative=authoritative,
            complete=q_complete,
            query_quality=q_quality,
            query_timestamp=q_timestamp,
            temporal_boundary=q_timestamp,
            broker_orders_seen=len(broker_orders),
            broker_positions_seen=len(broker_positions),
            broker_deals_seen=len(broker_deals) if broker_deals else 0,
            generated_at=now,
            broker_observation_digest=broker_obs_digest,
            session_id=report_session_id,
            orphan_records=tuple(orphan_records),
        )

        domain_id = getattr(
            getattr(query_result, "_observation", None), "domain_id", "UNTRUSTED"
        )
        stamp = _ReconciliationAuthorityStamp._issue(
            domain_id,
            "ReconciliationEngine",
            report_session_id,
            broker_obs_digest,
            now,
            unsealed_report.compute_digest(),
            _RECON_ENGINE_SECRET,
        )
        return replace(unsealed_report, _authority_stamp=stamp)
