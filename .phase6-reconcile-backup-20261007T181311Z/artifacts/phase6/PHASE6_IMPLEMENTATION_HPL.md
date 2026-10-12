# FRACTAL-FLOW — PHASE 6 CANONICAL IMPLEMENTATION HPL

**Status:** DESIGN GATE CLOSED / IMPLEMENTATION AUTHORIZED FOR NON-LIVE DEVELOPMENT
**Scope:** Python↔MT5 execution boundary, durable command lifecycle, broker-truth reconciliation, authentication/session, protection, restart/recovery, interoperability, and forensic verification.
**Live-trading authorization:** NONE.

## 0. Gate decision

The pre-implementation architecture challenge is complete.

**Decision: 🟢 IMPLEMENTATION GATE — SAFE TO BEGIN STAGED PHASE 6 IMPLEMENTATION**

This authorization is limited to development/test implementation. It is **not** a claim that any Phase 6 capability is implemented, verified, broker-proven, or safe for live trading.

The implementation must proceed through the HPL below. Effectful broker commands remain prohibited until their prerequisite gates are green.

---

## 1. Governing rules

1. Preserve the existing FRACTAL-FLOW architecture; extend rather than duplicate existing durable execution/recovery infrastructure.
2. Survival > Correctness > Auditability > Determinism > Explicit Authority > Recovery > Security > Performance > PnL.
3. No hidden strategy authority in transport, MT5, broker adapters, or position management.
4. `UNKNOWN` is a durable state, not an error to be erased.
5. No blind resend after uncertain dispatch.
6. `OrderSend()`/`OrderSendAsync()` success is dispatch/correlation evidence, not effect confirmation.
7. `OnTradeTransaction` is an observation/acceleration channel, not the authoritative durable broker ledger.
8. Broker snapshots/history are required to resolve uncertainty and reconstruct state.
9. Exactly-once broker effect is **not** claimed. The system proves durable command identity, duplicate/conflict handling, bounded dispatch semantics, and reconciliation-confirmed effect where evidence permits.
10. One authoritative application command ledger exists. MT5 command records are evidence/defensive deduplication, not a competing authority.
11. Recovery reconstructs state before authorizing new strategic execution.
12. Every required claim must be classified as OBSERVED, VERIFIED, IMPLEMENTED, PARTIAL, SPECIFIED, PROPOSED, UNVERIFIED, DEFERRED, BLOCKED, FAILED, INCORRECT, or OUT OF SCOPE.

---

## 2. Resolved architecture decisions

| Decision | Resolution | Rationale / invariant |
|---|---|---|
| Canonical serialization | Deterministic UTF-8 canonical JSON for protocol envelopes/payloads; fixed field ordering and normalized scalar encoding; cryptographic payload hashes operate on canonical bytes | MT5 already has JSON infrastructure; deterministic bytes are testable across Python/MQL5 |
| Framing | Existing 4-byte big-endian length prefix retained; bounded maximum frame/payload; exact-read/exact-write loops | Extends existing bridge instead of replacing it; TCP remains a byte stream |
| Protocol security | Application-layer challenge + HKDF-derived session keys + HMAC authentication; TLS remains optional future hardening, not a Phase 6 dependency | MT5 compatibility, deterministic interoperability, explicit replay/account/session binding, lower implementation complexity |
| Key schedule | Long-lived secret authenticates challenge; fresh nonces bind session; HKDF with domain-separated labels derives directional/control keys | Prevents key reuse across domains and binds keys to authenticated context |
| Command ledger authority | Python durable SQLite execution-command ledger is authoritative for application command identity/lifecycle | Existing durable substrate; avoids conflicting ledgers |
| MT5 command store | Defensive local evidence/dedupe cache only; never sole authority for command state | MT5 restart/terminal lifecycle cannot be allowed to manufacture durable application truth |
| Command identity | `(account_id, command_id)` is the stable application identity; `intent_id`, session ID, transport sequence, MT5 `request_id`, order/deal/position IDs remain distinct correlations | Prevents identity conflation and supports restart/reconciliation |
| Fingerprint conflict | Same command ID + same canonical fingerprint = duplicate/idempotent; same ID + different fingerprint = hard conflict/quarantine | Prevents semantic command mutation |
| Broker truth | Fresh authoritative broker query/snapshot/history outranks local ACK; transaction events accelerate reconciliation | Avoids false certainty |
| Position identity | Ticket and stable position identifier both retained; lineage uses stable identifier where broker semantics provide it | Handles ticket churn/reversal and avoids ticket-only identity |
| Netting/hedging | Explicit account-mode branch in normalized broker model and tests | Position semantics materially differ |
| Protection | Broker-native SL/TP is preferred for established protection; MT5 EA owns local protective continuity/TTL/dead-man enforcement where required; Python supplies authorized protective policy/intent | Protection must continue through Python outage without granting MT5 strategy authority |
| Recovery | Startup reconciliation precedes strategic re-enable; unresolved broker uncertainty leaves system quarantined/UNKNOWN | Prevents resurrection of stale execution authority |
| Sequence gaps | Gap is a synchronization condition, not an inferred missing event; state snapshot/history must repair the gap | Event order/completeness is not guaranteed |
| Backpressure | Bounded queues with explicit overload/disconnect behavior; no unbounded retry | Survival and resource safety dominate throughput |

### Explicitly rejected

- Event-only broker truth.
- Ticket-only position identity.
- Treating `OrderSend` success as filled/confirmed.
- Treating terminal `request_id` as durable command identity.
- Two independent authoritative command ledgers.
- Blind retry of UNKNOWN.
- MT5 as strategy authority.
- Python process memory as durable authority.
- Unbounded queues/retries.
- Introducing TLS solely because it sounds stronger without an interoperability requirement.

---

## 3. Authority graph

```text
MARKET / BROKER OBSERVATIONS
        ↓
INFORMATIONAL AUTHORITY
        ↓
STRATEGY AUTHORITY
        ↓
RISK / PORTFOLIO AUTHORITY
        ↓
DURABLE EXECUTION INTENT
        ↓
EXECUTION AUTHORIZATION
        ↓
DURABLE COMMAND LEDGER (Python)
        ↓
AUTHENTICATED FFBP SESSION
        ↓
MT5 EXECUTION AUTHORITY
        ↓
BROKER EFFECT

BROKER TRUTH → RECONCILIATION → DURABLE STATE → RECOVERY/PROTECTION GATE

PROTECTIVE POLICY: Python/Risk
PROTECTIVE ENFORCEMENT: MT5/broker-native where configured
```

MT5 may execute an explicitly authorized command but may not invent direction, size, entry thesis, or strategy intent.

---

## 4. Canonical lifecycle

### Application intent

`INTENT_CREATED → AUTHORIZED → COMMAND_PERSISTED → DISPATCHABLE → SENT → BROKER_PENDING → RECONCILING → EFFECT_CONFIRMED`

Terminal/failure states:

`REJECTED | FAILED | UNKNOWN | EXPIRED | CANCELLED | QUARANTINED`

Rules:

- `UNKNOWN` persists across restart.
- `UNKNOWN` cannot transition to SENT merely because a retry timer fires.
- Resolution requires authoritative broker evidence or an explicitly safe expiry/cancellation decision that cannot erase possible broker effect.
- Partial fill is represented explicitly; it is not collapsed into binary success/failure.
- Protective commands use the same identity/fingerprint discipline.

---

## 5. Implementation HPL

### A. Existing foundation preservation

| ID | Requirement | Current baseline | Implementation | Required proof | Status |
|---|---|---|---|---|---|
| P6-001 | Preserve execution state model incl. UNKNOWN/RECONCILING | Exists | Extend minimally | State/invariant tests | 🟢 BASELINE VERIFIED |
| P6-002 | Reuse durable execution-intent repository | Exists | Integrate command ledger | Restart/idempotency tests | 🟢 BASELINE VERIFIED |
| P6-003 | Preserve recovery authority model | Exists | Connect broker recovery evidence | Recovery/adversarial tests | 🟢 BASELINE VERIFIED |
| P6-004 | No duplicate persistence authority | Python ledger established; MT5 remains non-authoritative evidence/cache | Authority + duplicate/conflict tests | 🟠 IMPLEMENTED + FOCUSED VERIFIED |

### B. Broker truth / normalized model

| ID | Requirement | Implementation target | Verification | Status |
|---|---|---|---|---|
| P6-010 | Canonical account context | Python normalized model | serialization + mismatch tests | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-011 | Canonical order model | Python normalized model | fixture tests; runtime integration pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-012 | Canonical deal model | Python normalized model | fixture tests; runtime integration pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-013 | Canonical position model | Python normalized model | serialization tests; live netting/hedging pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-014 | Observation provenance | source/authority/observation/session/sequence model | deterministic serialization tests | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-015 | Reconciliation result | explicit confirmed/rejected/unknown/conflict/orphan/partial contract | broker fixture tests; runtime pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-016 | Event order independence | normalized truth is observation-based | permutation campaign still required | 🔴 |

### C. Protocol / transport

| ID | Requirement | Implementation target | Verification | Status |
|---|---|---|---|---|
| P6-020 | Deterministic envelope | Python FFBP/1 envelope with stable IDs/sequence/deadline/auth | Python vector tests; cross-language pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-021 | Canonical JSON | deterministic UTF-8 JSON implemented; supplied MQL5 vector reproduced exactly on Python side | HMAC/wire/length/prefix vector test; MT5 runtime still pending | 🟠 IMPLEMENTED + VECTOR VERIFIED |
| P6-022 | Framing | existing 4-byte BE framing preserved; Python encoder/decoder bounded | malformed/size tests; live socket pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-023 | Logical channels | channel enum implemented | protocol tests; end-to-end semantics pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-024 | Sequence protection | strict Python tracker with gap fencing | focused sequence tests; cross-boundary campaign pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-025 | Bounded transport | bounded Python queue; MT5 bounded timer drain exists | queue saturation test; runtime lifecycle pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-026 | Reconnect lifecycle | session fence primitive implemented; reconnect controller not yet complete | focused fence tests; restart pending | 🔴 |

### D. Authentication/session

| ID | Requirement | Implementation target | Verification | Status |
|---|---|---|---|---|
| P6-030 | Challenge-response | Python challenge transcript/proof implemented | positive/negative tests; MT5 completion pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-031 | Session key derivation | Python HKDF + directional domain separation | RFC5869 vector + nonce tests; MQL5 parity pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-032 | Account binding | protocol session fence binds account/session | negative binding tests; effectful path pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-033 | Replay resistance | sequence + session fencing + authenticated envelope foundation | focused tests; full replay campaign pending | 🔴 |
| P6-034 | Session fencing | Python account/session fence implemented | stale-session tests; reconnect integration pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-035 | Fail-closed auth | protocol decoder rejects auth/version/account violations | focused negative tests; effectful integration pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |

### E. Idempotency / UNKNOWN

| ID | Requirement | Implementation target | Verification | Status |
|---|---|---|---|---|
| P6-040 | Stable command identity | durable SQLite ledger keyed by `(account_id, command_id)` | restart/duplicate tests | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-041 | Fingerprint conflict | ledger conflict boundary plus existing intent fingerprint substrate | same-ID conflict tests | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-042 | Durable lifecycle | SQLite command transitions persisted | restart test; injected crash windows pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-043 | MT5 correlation | architecture specified; runtime correlation field integration pending | — | 🔴 |
| P6-044 | UNKNOWN persistence | durable UNKNOWN state in SQLite ledger | restart test | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-045 | No blind resend | UNKNOWN → SENT/BROKER_PENDING explicitly rejected | focused mutation test | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-046 | Partial fill | normalized broker truth carries filled/remaining volume | partial-fill fixture test; durable lifecycle integration pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-047 | Expiry | expiry field and terminal lifecycle contract established; automatic enforcement pending | — | 🔴 |

### F. MT5 observation/synchronization

| ID | Requirement | Implementation target | Verification | Status |
|---|---|---|---|---|
| P6-050 | OnTradeTransaction ingestion | bounded observation queue; no blocking network/reconciliation work in callback | overload/runtime tests | 🔴 |
| P6-051 | Snapshot sync | authoritative orders/deals/positions snapshot | integration tests | 🔴 |
| P6-052 | History sync | targeted order/deal/history recovery | missing-history tests | 🔴 |
| P6-053 | Sequence gap recovery | gap triggers sync, not guessed events | gap campaign | 🔴 |
| P6-054 | Broker query authority | fresh authoritative query stamped accordingly | truth-precedence tests | 🔴 |
| P6-055 | Orphan handling | broker-only/local-only objects quarantined/protected as appropriate | orphan tests | 🔴 |

### G. Protective authority

| ID | Requirement | Implementation target | Verification | Status |
|---|---|---|---|---|
| P6-060 | Protection separation | strategy/risk policy distinct from protective enforcement | authority mutation tests | 🔴 |
| P6-061 | SL/TP confirmation | broker truth confirms protective state | modify/reconcile tests | 🔴 |
| P6-062 | Python outage continuity | established broker-native/MT5-local protection remains active | terminal outage tests | 🔴 |
| P6-063 | TTL/dead-man | explicit durable expiry and enforcement authority | disconnect/restart tests | 🔴 |
| P6-064 | Protective uncertainty | failed/uncertain protection enters safe/quarantine state | failure tests | 🔴 |
| P6-065 | Strategy re-enable gate | strategy cannot resume while required protection/reconciliation is unresolved | recovery tests | 🔴 |

### H. Recovery / determinism

| ID | Requirement | Implementation target | Verification | Status |
|---|---|---|---|---|
| P6-070 | Startup reconciliation | broker state inspected before strategic enablement | restart tests | 🔴 |
| P6-071 | Replay equivalence | replayed persisted state matches clean execution semantics | deterministic hash/state comparison | 🔴 |
| P6-072 | Crash-tail handling | incomplete persistence cannot create false effect | injected crash tests | 🔴 |
| P6-073 | Corruption handling | checksum/schema/version failures fail closed | corruption campaign | 🔴 |
| P6-074 | Version compatibility | explicit protocol/state version policy | compatibility tests | 🔴 |

### I. Security / resource safety

| ID | Requirement | Implementation target | Verification | Status |
|---|---|---|---|---|
| P6-080 | Malformed/oversize input rejection | Python parser rejects malformed/oversize frames | focused mutation/size tests; fuzz campaign pending | 🟠 IMPLEMENTED + FOCUSED VERIFIED |
| P6-081 | Secret handling | no secret leakage into logs/artifacts | log inspection | 🔴 |
| P6-082 | Concurrent command control | deterministic serialization/conflict policy | race/adversarial tests | 🔴 |
| P6-083 | Retry bounds | bounded backoff, bounded attempts, no resurrection | time/failure tests | 🔴 |
| P6-084 | Resource cleanup | sockets/files/threads/timers cleaned after failure | lifecycle campaign | 🔴 |

### J. Interoperability / runtime

| ID | Requirement | Implementation target | Verification | Status |
|---|---|---|---|---|
| P6-090 | MQL5 compile | all includes/types/build paths valid | MetaEditor evidence | 🔴 |
| P6-091 | Python↔MQL5 vectors | exact serialization/auth vectors agree | cross-language campaign | 🔴 |
| P6-092 | MT5 terminal transport | connect/auth/session/reconnect | real terminal evidence | 🔴 |
| P6-093 | Effectful demo path | command→broker→truth→durable result | demo evidence | 🔴 |
| P6-094 | Netting campaign | actual account-mode behavior | broker/demo evidence | 🔴 |
| P6-095 | Hedging campaign | actual account-mode behavior | broker/demo evidence | 🔴 |
| P6-096 | Partial-fill campaign | actual broker/terminal behavior | broker/demo evidence | 🔴 |

### K. Adversarial verification

| ID | Requirement | Required cases | Status |
|---|---|---|---|
| P6-100 | Crash matrix | before/after persistence, authorization, send, ack, local result persistence | 🔴 |
| P6-101 | Uncertain broker effect | response lost after broker effect; delayed response; broker unavailable | 🔴 |
| P6-102 | Duplicate/conflict | duplicate command, reused ID with different fingerprint | 🔴 |
| P6-103 | Event faults | duplicate/reordered/missing event; sequence gap | 🔴 |
| P6-104 | Restart faults | Python, MT5, simultaneous restart | 🔴 |
| P6-105 | Position faults | partial fill, reversal, stale ticket, missing history, orphan | 🔴 |
| P6-106 | Protection faults | uncertain/rejected protection; TTL while disconnected | 🔴 |
| P6-107 | Security faults | stale session, replay, account mismatch, malformed/oversize, auth failure | 🔴 |
| P6-108 | Resource faults | queue saturation, reconnect storm, broker unavailable | 🔴 |

### L. Documentation / provenance / artifacts

| ID | Requirement | Required proof | Status |
|---|---|---|---|
| P6-110 | HPL parity | updated to reflect current source/test evidence and remaining runtime gaps | HPL/evidence reconciliation | 🟢 VERIFIED FOR CURRENT IMPLEMENTATION SLICE |
| P6-111 | Decision log parity | Phase 6 implementation decisions appended to decision log | document parity inspection | 🟢 VERIFIED FOR CURRENT IMPLEMENTATION SLICE |
| P6-112 | Evidence register | current Phase 6 evidence file records focused and regression campaigns | evidence-file inspection | 🟢 VERIFIED FOR CURRENT IMPLEMENTATION SLICE |
| P6-113 | Git provenance | verify only from actual Git repository; archive alone cannot prove it | 🟡 ENVIRONMENTAL / UNVERIFIED |
| P6-114 | Tool availability | unavailable Ruff/mypy/Git are recorded as environmental exceptions, never falsely claimed green | 🟡 ENVIRONMENTAL POLICY |
| P6-115 | Artifact extraction | generated package extracts cleanly and matches manifest/hash | 🔴 |
| P6-116 | Final re-verification | clean-environment or equivalent reproducible campaign | 🔴 |

---

## 6. Phase implementation order

### Phase 6A — Broker truth + canonical protocol foundations

Implement P6-010..026 without effectful broker execution.

### Phase 6B — Authentication/session

Implement P6-030..035 and cross-language cryptographic/serialization vectors.

### Phase 6C — Durable command ledger/idempotency

Implement P6-040..047 using the existing durable persistence substrate.

### Phase 6D — MT5 observation/synchronization

Implement P6-050..055 before effectful commands.

### Phase 6E — Effectful command path

Only when A–D focused gates are green. Implement broker adapter dispatch and reconciliation-confirmed lifecycle.

### Phase 6F — Protective authority

Implement P6-060..065 with Python outage and restart tests.

### Phase 6G — Recovery/adversarial hardening

Implement/run P6-070..108 and full restart/crash matrix.

### Phase 6H — Runtime interoperability and closure

P6-090..116; actual MT5/demo evidence; final artifact and provenance reconciliation.

Deviation from this order requires a documented dependency reason in the decision log.

---

## 7. Mandatory gate after each sub-phase

Every sub-phase must follow:

`Reconnaissance → HPL update → implementation → focused green → hardening → adversarial verification → regression → evidence reconciliation → gate decision`

A sub-phase cannot be called closed solely because its unit tests pass.

---

## 8. Final Phase 6 acceptance rule

Phase 6 may close only when:

- every required HPL row is classified;
- no required row is RED/MISSING/PARTIAL/FAILED/UNKNOWN;
- all unresolved UNKNOWN outcomes have explicit safe disposition;
- all effectful lifecycle transitions are durable and reconstructible;
- broker truth has been verified at the required runtime layer;
- Python↔MQL5 interoperability is reproduced;
- netting/hedging/partial-fill behavior is evidenced where in scope;
- protection continuity is evidenced;
- restart/crash matrix is green;
- replay equivalence is demonstrated;
- security/resource adversarial tests are green;
- documentation and implementation parity is reconciled;
- Git provenance is separately verified or explicitly recorded as environmental exception;
- final artifact extraction/re-verification succeeds.

Only then may the final gate be one of:

**🟢 FINAL GREEN — ARTIFACT MAY BE GENERATED**

or

**🔴 FINAL GATE BLOCKED — DO NOT GENERATE ARTIFACT**

No Phase 6 development green is a live-trading authorization.

---

## 9. Immediate next action

Begin **Phase 6A reconnaissance/implementation preparation** from the actual repository. First establish exact file ownership and integration points for:

- existing `DurableExecutionIntentRepository`;
- execution state machine;
- reconciliation engine;
- recovery authority;
- existing MQL5 bridge framing/JSON/HMAC/session epoch;
- Python transport boundary (currently absent/incomplete in the supplied snapshot);
- command persistence schema;
- tests and artifact locations.

Do not implement effectful broker execution during this first pass.

**Current gate: 🟢 IMPLEMENTATION GATE — SAFE TO BEGIN STAGED PHASE 6 IMPLEMENTATION; EFFECTFUL BROKER PATH STILL LOCKED BEHIND PREREQUISITE GATES.**
