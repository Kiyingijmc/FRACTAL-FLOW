"""Authoritative Reconciliation Engine comparing local intents against broker truth, preserving UNKNOWN semantics when evidence is non-authoritative."""

import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Dict, List, Optional, Any, Mapping, Tuple, Iterator

from src.fractal_flow.domain.models import ExecutionIntent, Position, BrokerOrder, BrokerDeal, DealEntryRole
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


@dataclass
class OrphanRecord:
    """Tracks orphaned broker positions or orders through explicit resolution lifecycle."""
    orphan_id: str
    object_type: str  # "POSITION" or "ORDER"
    object_id: str
    symbol: str
    volume: float
    status: OrphanStatus = OrphanStatus.DETECTED
    protective_monitoring_active: bool = True
    detected_at: int = 0
    updated_at: int = 0
    details: Dict[str, Any] = field(default_factory=dict)

    def is_resolved_or_quarantined(self) -> bool:
        """Returns True if the orphan is resolved or safely quarantined under protective monitoring."""
        return self.status in (
            OrphanStatus.REATTACHED,
            OrphanStatus.RECOVERED,
            OrphanStatus.QUARANTINED,
            OrphanStatus.EXPIRED,
        )


@unique
class BrokerQueryQuality(str, Enum):
    FOUND = "FOUND"
    NOT_FOUND_AUTHORITATIVE = "NOT_FOUND_AUTHORITATIVE"
    NOT_FOUND_NON_AUTHORITATIVE = "NOT_FOUND_NON_AUTHORITATIVE"
    QUERY_FAILED = "QUERY_FAILED"
    PARTIAL = "PARTIAL"
    STALE = "STALE"


@dataclass(frozen=True)
class BrokerQueryResult:
    """Encapsulates authoritative broker query response metadata and execution objects."""
    status: str = "SUCCESS"
    authority: BrokerQueryQuality = BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE
    query_timestamp: int = 0
    completeness: bool = True
    broker_orders: Mapping[str, BrokerOrder] = field(default_factory=dict)
    broker_positions: Mapping[str, Position] = field(default_factory=dict)
    broker_deals: Mapping[str, BrokerDeal] = field(default_factory=dict)
    provider_identity: str = "BrokerQueryProvider"
    details: Dict[str, Any] = field(default_factory=dict)


class BrokerQueryProvider:
    """Authoritative provider boundary responsible for issuing broker state queries and asserting query quality."""

    def __init__(
        self,
        orders: Optional[Dict[str, BrokerOrder]] = None,
        positions: Optional[Dict[str, Position]] = None,
        deals: Optional[Dict[str, BrokerDeal]] = None,
        authority: BrokerQueryQuality = BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE,
        max_age_seconds: int = 300,
        query_timestamp: int = 0,
        provider_identity: str = "BrokerQueryProvider",
    ) -> None:
        self._orders = orders or {}
        self._positions = positions or {}
        self._deals = deals or {}
        self._authority = authority
        self._max_age_seconds = max_age_seconds
        self._query_timestamp = query_timestamp
        self._provider_identity = provider_identity

    def query_broker_state(self, current_timestamp: int = 0) -> BrokerQueryResult:
        now = current_timestamp or self._query_timestamp
        authority = self._authority

        # Enforce temporal freshness check
        if self._max_age_seconds > 0 and self._query_timestamp > 0 and now > 0:
            if now - self._query_timestamp > self._max_age_seconds:
                authority = BrokerQueryQuality.STALE

        return BrokerQueryResult(
            status="SUCCESS" if authority in (BrokerQueryQuality.FOUND, BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE) else "NON_AUTHORITATIVE",
            authority=authority,
            query_timestamp=now,
            completeness=(authority in (BrokerQueryQuality.FOUND, BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE)),
            broker_orders=dict(self._orders),
            broker_positions=dict(self._positions),
            broker_deals=dict(self._deals),
            provider_identity=self._provider_identity,
        )


@dataclass(frozen=True)
class ReconciliationResult:
    intent_id: str
    mismatch_type: ReconciliationMismatchType
    resolved_execution_state: ExecutionState
    details: Dict[str, Any]


@dataclass(frozen=True)
class ReconciliationReport:
    """Typed, immutable reconciliation report deriving all counts and metrics internally."""
    results: Tuple[ReconciliationResult, ...]
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
    orphan_records: Tuple[OrphanRecord, ...] = field(default_factory=tuple)

    def __getitem__(self, index: Any) -> ReconciliationResult:
        return self.results[index]

    def __iter__(self) -> Iterator[ReconciliationResult]:
        return iter(self.results)

    def __len__(self) -> int:
        return len(self.results)


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
        broker_deals: Optional[Mapping[str, BrokerDeal]] = None,
        query_quality: BrokerQueryQuality = BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE,
        query_result: Optional[BrokerQueryResult] = None,
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
            target_order_id = matching_order.order_id if matching_order else (matching_pos.order_id if matching_pos else "")
            target_pos_id = matching_pos.position_id if matching_pos else ""

            related_deals = [
                d for d in broker_deals.values()
                if (target_order_id and d.order_id == target_order_id) or (target_pos_id and d.position_id == target_pos_id)
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

            # Check deal sequence and deal entry roles
            sorted_deals = sorted(related_deals, key=lambda x: getattr(x, 'timestamp', 0))
            seen_open = False
            for d in sorted_deals:
                role = cls._normalize_role(getattr(d, 'entry_role', DealEntryRole.UNKNOWN))
                if role == DealEntryRole.UNKNOWN:
                    return ReconciliationResult(
                        intent_id=local_intent.intent_id,
                        mismatch_type=ReconciliationMismatchType.DEAL_CONTRADICTION,
                        resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                        details={"note": f"Missing or unknown deal entry role for deal '{d.deal_id}'"},
                    )
                if role in (DealEntryRole.OPEN, DealEntryRole.INCREASE):
                    seen_open = True
                elif role in (DealEntryRole.CLOSE, DealEntryRole.DECREASE):
                    if not seen_open:
                        return ReconciliationResult(
                            intent_id=local_intent.intent_id,
                            mismatch_type=ReconciliationMismatchType.DEAL_CONTRADICTION,
                            resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                            details={"note": f"Contradictory deal sequence: CLOSE/DECREASE deal '{d.deal_id}' before OPEN"},
                        )

            if matching_pos:
                opening_vol = sum(
                    d.volume for d in related_deals
                    if cls._normalize_role(getattr(d, 'entry_role', DealEntryRole.UNKNOWN)) in (DealEntryRole.OPEN, DealEntryRole.INCREASE)
                )
                closing_vol = sum(
                    d.volume for d in related_deals
                    if cls._normalize_role(getattr(d, 'entry_role', DealEntryRole.UNKNOWN)) in (DealEntryRole.CLOSE, DealEntryRole.DECREASE)
                )
                net_deal_vol = opening_vol - closing_vol

                if closing_vol > opening_vol or net_deal_vol < 0 or abs(net_deal_vol - matching_pos.filled_volume) > 0.0001:
                    return ReconciliationResult(
                        intent_id=local_intent.intent_id,
                        mismatch_type=ReconciliationMismatchType.DEAL_CONTRADICTION,
                        resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                        details={
                            "note": f"Net deal volume ({net_deal_vol}) contradicts position filled volume ({matching_pos.filled_volume}) or over-close detected",
                            "position_id": matching_pos.position_id,
                            "opening_volume": opening_vol,
                            "closing_volume": closing_vol,
                        },
                    )

        if matching_pos:
            resolved_state = ExecutionState.EXEC_PARTIAL if matching_pos.remaining_volume > 0 else ExecutionState.EXEC_FILLED
            mismatch = ReconciliationMismatchType.MATCH if local_intent.status == resolved_state.value else ReconciliationMismatchType.STATE_MISMATCH
            return ReconciliationResult(
                intent_id=local_intent.intent_id,
                mismatch_type=mismatch,
                resolved_execution_state=resolved_state,
                details={"position_id": matching_pos.position_id, "filled_volume": matching_pos.filled_volume},
            )

        if matching_order:
            resolved_state = ExecutionState.EXEC_ACCEPTED if matching_order.status == "ACCEPTED" else ExecutionState.EXEC_FILLED
            mismatch = ReconciliationMismatchType.MATCH if local_intent.status == resolved_state.value else ReconciliationMismatchType.STATE_MISMATCH
            return ReconciliationResult(
                intent_id=local_intent.intent_id,
                mismatch_type=mismatch,
                resolved_execution_state=resolved_state,
                details={"order_id": matching_order.order_id, "order_status": matching_order.status},
            )

        # Broker has no record of order or position
        if query_quality == BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE:
            return ReconciliationResult(
                intent_id=local_intent.intent_id,
                mismatch_type=ReconciliationMismatchType.LOCAL_ONLY,
                resolved_execution_state=ExecutionState.EXEC_REJECTED,
                details={"note": "Broker authoritatively confirmed order non-existence / rejection."},
            )

        # Fail-closed: UNKNOWN != REJECTED without authoritative evidence!
        return ReconciliationResult(
            intent_id=local_intent.intent_id,
            mismatch_type=ReconciliationMismatchType.LOCAL_ONLY,
            resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
            details={"note": "Broker record absent but query is non-authoritative. Preserving EXEC_UNKNOWN."},
        )

    @classmethod
    def reconcile_broker_wide(
        cls,
        local_intents: Dict[str, ExecutionIntent],
        broker_orders: Optional[Mapping[str, BrokerOrder]] = None,
        broker_positions: Optional[Mapping[str, Position]] = None,
        broker_deals: Optional[Mapping[str, BrokerDeal]] = None,
        authoritative_rejections: Optional[set] = None,
        query_result: Optional[BrokerQueryResult] = None,
    ) -> ReconciliationReport:
        """Performs full broker-wide multi-directional reconciliation discovering local-only, matched, and orphaned broker objects.

        Returns an immutable ReconciliationReport with internally derived counts and orphan tracking.
        """
        now = int(time.time())
        q_timestamp = now
        q_quality = BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE
        q_complete = False

        if query_result is not None:
            broker_orders = query_result.broker_orders
            broker_positions = query_result.broker_positions
            broker_deals = query_result.broker_deals or broker_deals
            q_quality = query_result.authority
            q_timestamp = query_result.query_timestamp or now
            q_complete = query_result.completeness
        else:
            broker_orders = broker_orders or {}
            broker_positions = broker_positions or {}
            broker_deals = broker_deals or {}

        results_list: List[ReconciliationResult] = []
        orphan_records: List[OrphanRecord] = []

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
                        details={"position_id": pos.position_id, "symbol": pos.symbol, "volume": pos.filled_volume},
                    )
                )
                orphan_records.append(
                    OrphanRecord(
                        orphan_id=f"ORPHAN_POS_{pos.position_id}",
                        object_type="POSITION",
                        object_id=pos.position_id,
                        symbol=pos.symbol,
                        volume=pos.filled_volume,
                        status=OrphanStatus.DETECTED,
                        protective_monitoring_active=True,
                        detected_at=now,
                        updated_at=now,
                        details={"intent_id": pos.intent_id},
                    )
                )

        # Discover orphaned broker orders
        for ord_obj in broker_orders.values():
            if ord_obj.intent_id not in local_intents and not any(p.order_id == ord_obj.order_id for p in broker_positions.values()):
                results_list.append(
                    ReconciliationResult(
                        intent_id=ord_obj.intent_id or f"ORPHAN_ORD_{ord_obj.order_id}",
                        mismatch_type=ReconciliationMismatchType.ORPHANED_BROKER,
                        resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                        details={"order_id": ord_obj.order_id, "symbol": ord_obj.symbol, "volume": ord_obj.volume},
                    )
                )
                orphan_records.append(
                    OrphanRecord(
                        orphan_id=f"ORPHAN_ORD_{ord_obj.order_id}",
                        object_type="ORDER",
                        object_id=ord_obj.order_id,
                        symbol=ord_obj.symbol,
                        volume=ord_obj.volume,
                        status=OrphanStatus.DETECTED,
                        protective_monitoring_active=True,
                        detected_at=now,
                        updated_at=now,
                        details={"intent_id": ord_obj.intent_id},
                    )
                )

        results_tuple = tuple(results_list)

        # Derive counts internally from actual results tuple
        unknown_count = sum(
            1 for r in results_tuple if r.resolved_execution_state == ExecutionState.EXEC_UNKNOWN
        )
        orphaned_count = sum(
            1 for r in results_tuple if r.mismatch_type == ReconciliationMismatchType.ORPHANED_BROKER
        )

        authoritative = (q_quality in (BrokerQueryQuality.FOUND, BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE))

        report = ReconciliationReport(
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
            orphan_records=tuple(orphan_records),
        )

        return report
