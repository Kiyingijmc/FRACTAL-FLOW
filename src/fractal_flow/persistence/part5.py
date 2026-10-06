"""Durable audit journal for Phase 5 protective/allocation decisions.

The Part-B engines remain deterministic/pure where possible. This journal is the
persistence authority for the resulting protective/allocation transition record:
no execution intent or market direction is created here. Every authoritative
outcome (ALLOW, REJECT, or DEFER) carries a canonical decision-input context so
forensic replay can explain the outcome without relying on volatile process state.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from src.fractal_flow.domain.event import Event
from src.fractal_flow.persistence.journal import DurableEventJournal, JournalCorruptionException


@dataclass(frozen=True)
class PartBDecisionRecord:
    event_id: str
    account_id: str
    decision_id: str
    observed_timestamp: int
    status: str
    reason: str
    allocation: dict[str, str] | None
    news_state_hash: str
    context: dict[str, object]
    context_fingerprint: str
    fingerprint: str


class PartBDecisionJournal:
    """Append-only, idempotent journal of authoritative Part-B outcomes."""

    AGGREGATE_TYPE = "PART_B_DECISION"
    EVENT_TYPE = "PART_B_DECISION_RECORDED"

    def __init__(self, journal: DurableEventJournal | None = None) -> None:
        self._journal = journal or DurableEventJournal()

    @staticmethod
    def _event_id(account_id: str, decision_id: str, observed_timestamp: int) -> str:
        seed = f"{account_id}|{decision_id}|{observed_timestamp}".encode("utf-8")
        return "partb-" + hashlib.sha256(seed).hexdigest()

    @staticmethod
    def _fingerprint(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def append(
        self,
        *,
        account_id: str,
        decision_id: str,
        observed_timestamp: int,
        status: str,
        reason: str,
        allocation: dict[str, str] | None,
        news_state_hash: str,
        context: dict[str, object] | None = None,
    ) -> PartBDecisionRecord:
        if not account_id or not decision_id or type(observed_timestamp) is not int or observed_timestamp < 0:
            raise ValueError("Part-B journal identity/timestamp is invalid")
        if status not in {"ALLOW", "REJECT", "DEFER"}:
            raise ValueError("Part-B journal status must be an authoritative outcome")
        payload: dict[str, Any] = {
            "account_id": account_id,
            "decision_id": decision_id,
            "observed_timestamp": str(observed_timestamp),
            "status": status,
            "reason": reason,
            "allocation": allocation,
            "news_state_hash": news_state_hash,
            "context": context or {},
        }
        context_fingerprint = self._fingerprint(payload["context"])
        payload["context_fingerprint"] = context_fingerprint
        fingerprint = self._fingerprint(payload)
        event_id = self._event_id(account_id, decision_id, observed_timestamp)
        existing = [event for event in self._journal.get_events_for_aggregate(self.AGGREGATE_TYPE, account_id) if event.event_id == event_id]
        if existing:
            prior = existing[0]
            prior_payload = dict(prior.payload)
            prior_fingerprint = str(prior_payload.get("fingerprint", ""))
            if prior_fingerprint != fingerprint:
                raise JournalCorruptionException("Part-B idempotency key reused with a different decision outcome")
            return self._record_from_event(prior)

        current = self._journal.get_events_for_aggregate(self.AGGREGATE_TYPE, account_id)
        version = len(current) + 1
        event = Event(
            event_id=event_id,
            event_type=self.EVENT_TYPE,
            aggregate_type=self.AGGREGATE_TYPE,
            aggregate_id=account_id,
            root_id=decision_id,
            parent_id=decision_id,
            aggregate_version=version,
            source_timestamp=observed_timestamp,
            event_timestamp=observed_timestamp,
            processing_timestamp=observed_timestamp,
            payload={**payload, "fingerprint": fingerprint},
            actor_id="SYSTEM",
            authority="PartB",
            account_id=account_id,
        )
        record = self._journal.append(event)
        return self._record_from_event(record.event)

    @staticmethod
    def _record_from_event(event: Event) -> PartBDecisionRecord:
        payload = dict(event.payload)
        allocation_raw = payload.get("allocation")
        allocation = dict(allocation_raw) if isinstance(allocation_raw, dict) else None
        return PartBDecisionRecord(
            event_id=event.event_id,
            account_id=str(payload["account_id"]),
            decision_id=str(payload["decision_id"]),
            observed_timestamp=int(payload["observed_timestamp"]),
            status=str(payload["status"]),
            reason=str(payload["reason"]),
            allocation=allocation,
            news_state_hash=str(payload["news_state_hash"]),
            context=dict(payload.get("context", {})),
            context_fingerprint=str(payload.get("context_fingerprint", "")),
            fingerprint=str(payload["fingerprint"]),
        )

    def authorized_for_opportunity(self, account_id: str, opportunity_id: str) -> tuple[PartBDecisionRecord, ...]:
        return tuple(
            record for record in self.replay()
            if record.account_id == account_id
            and record.status == "ALLOW"
            and record.decision_id
            and str(record.context.get("opportunity_id", "")) == opportunity_id
        )

    def replay(self) -> tuple[PartBDecisionRecord, ...]:
        events = [event for record in self._journal.get_all_records() if (event := record.event).aggregate_type == self.AGGREGATE_TYPE]
        return tuple(self._record_from_event(event) for event in events)

    def latest(self, account_id: str) -> PartBDecisionRecord | None:
        events = self._journal.get_events_for_aggregate(self.AGGREGATE_TYPE, account_id)
        return self._record_from_event(events[-1]) if events else None

    @property
    def journal(self) -> DurableEventJournal:
        return self._journal
