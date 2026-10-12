# FRACTAL-FLOW — PHASE 6 UPDATED FORENSIC HPL

**As-of:** 2026-10-07
**Scope:** Python ↔ MT5 FFBP/1 execution boundary, broker truth, authentication/session, durable command lifecycle, protective authority, recovery, interoperability, and adversarial verification.
**Live authorization:** NONE.
**Current gate:** **🔴 FINAL GATE BLOCKED — DO NOT GENERATE ARTIFACT.**

## 1. Governing priority

`SURVIVAL > CORRECTNESS > AUDITABILITY > DETERMINISM > EXPLICIT AUTHORITY > RECOVERY > SECURITY > PERFORMANCE > PnL`

## 2. Non-negotiable process rules

1. Never equate implemented with verified.
2. Never equate tests passing with system correctness or closure.
3. Never treat a local simulation as broker/terminal runtime proof.
4. UNKNOWN is a first-class durable state; it must never be silently converted into success or safely retryable state.
5. Never blindly resend after uncertain dispatch.
6. `OrderSend()`/`OrderSendAsync()` is dispatch evidence, not effect confirmation.
7. `OnTradeTransaction` is an observation/acceleration channel, not the authoritative durable broker ledger.
8. Fresh broker snapshot/history/query evidence outranks local ACK/expectation.
9. Python durable command identity is authoritative; MT5 evidence stores must not become a competing authority.
10. No hidden strategy authority may be added to transport, MT5, broker adapters, or protective enforcement.
11. Every claim must carry an evidence status: OBSERVED, VERIFIED, IMPLEMENTED, PARTIAL, SPECIFIED, PROPOSED, UNVERIFIED, DEFERRED, BLOCKED, FAILED, INCORRECT, or OUT OF SCOPE.
12. Environmental exceptions such as unavailable Ruff/mypy/Git must be recorded as UNVERIFIED/ENVIRONMENTAL EXCEPTION; never claimed as passed.
13. Do not weaken tests, broaden acceptance criteria, delete failing tests, or change specifications solely to obtain green output.
14. Preserve deterministic canonical bytes, explicit sequence semantics, bounded resources, and fail-closed behavior.
15. No live trading. Keep `InpAllowReal=false`.

## 3. Authority model

```text
MARKET/BROKER OBSERVATIONS
        ↓
INFORMATIONAL AUTHORITY
        ↓
STRATEGY AUTHORITY
        ↓
RISK/PORTFOLIO AUTHORITY
        ↓
DURABLE EXECUTION INTENT
        ↓
EXECUTION AUTHORIZATION
        ↓
PYTHON DURABLE COMMAND LEDGER
        ↓
AUTHENTICATED FFBP/1 SESSION
        ↓
MT5 EXECUTION AUTHORITY
        ↓
BROKER EFFECT

BROKER TRUTH → RECONCILIATION → DURABLE STATE → RECOVERY/PROTECTION GATE
```

MT5 must not invent strategy direction, size, entry thesis, or command intent.

## 4. Current HPL status

| ID | Requirement | Status | Current evidence / blocker |
|---|---|---|---|
| P6-001 | Preserve existing execution/recovery substrate | 🟢 BASELINE VERIFIED | Phase 5/R5 verified baseline retained |
| P6-002 | Durable execution intent substrate reused | 🟢 BASELINE VERIFIED | Existing repository/ledger infrastructure |
| P6-003 | Recovery authority preserved | 🟢 BASELINE VERIFIED | Phase 5/R5 recovery evidence |
| P6-004 | Single command authority | 🟢 FOCUSED VERIFIED | Python ledger authoritative; MT5 non-authoritative |
| P6-010 | Canonical account context | 🟢 FOCUSED VERIFIED | Python broker-truth tests |
| P6-011 | Canonical order model | 🟢 FOCUSED VERIFIED | Python focused tests; live broker pending |
| P6-012 | Canonical deal model | 🟢 FOCUSED VERIFIED | Python focused tests; live broker pending |
| P6-013 | Canonical position model | 🟢 FOCUSED VERIFIED | Netting/hedging runtime still pending |
| P6-014 | Observation provenance | 🟢 FOCUSED VERIFIED | Python model/tests |
| P6-015 | Reconciliation result contract | 🟢 FOCUSED VERIFIED | Python model/tests |
| P6-016 | Event-order independence | 🔴 OPEN | adversarial permutation campaign pending |
| P6-020 | Deterministic FFBP/1 envelope | 🟢 FOCUSED VERIFIED | Python protocol tests |
| P6-021 | Canonical UTF-8 JSON | 🟢 VECTOR VERIFIED / 🔴 LIVE FRAME BLOCKED | MT5 fixed vectors pass; live HELLO JSON currently fails |
| P6-022 | 4-byte BE framing | 🟠 IMPLEMENTED / 🔴 LIVE FRAME BLOCKED | TCP connection works; raw frame inspection required |
| P6-023 | Exact read/write and size bounds | 🟠 IMPLEMENTED | live raw-frame evidence still required |
| P6-024 | Malformed JSON rejection | 🟢 FOCUSED VERIFIED | Python negative tests |
| P6-025 | Protocol versioning | 🟠 SPECIFIED/IMPLEMENTED | runtime interoperability pending |
| P6-030 | Challenge/auth handshake | 🟠 PYTHON + MT5 CRYPTO VERIFIED / 🔴 LIVE HANDSHAKE BLOCKED | JSON failure precedes HMAC |
| P6-031 | HKDF directional keys | 🟢 VECTOR VERIFIED | Exact c2s/s2c vectors match |
| P6-032 | Challenge proof | 🟢 VECTOR VERIFIED | Exact fixed proof vector matches |
| P6-033 | Session key installation | 🟠 IMPLEMENTED / 🔴 LIVE UNVERIFIED | requires live challenge/auth |
| P6-034 | Post-session directional HMAC | 🟠 IMPLEMENTED / 🔴 LIVE UNVERIFIED | requires live session |
| P6-040 | Stable command identity | 🟢 FOCUSED VERIFIED | `(account_id, command_id)` |
| P6-041 | Fingerprint conflict | 🟢 FOCUSED VERIFIED | duplicate/conflict tests |
| P6-042 | Durable command lifecycle | 🟢 FOCUSED VERIFIED | SQLite ledger tests |
| P6-043 | MT5 command correlation | 🔴 OPEN | runtime command path not implemented |
| P6-044 | Durable UNKNOWN | 🟢 FOCUSED VERIFIED | ledger tests |
| P6-045 | No blind resend | 🟢 FOCUSED VERIFIED | negative transition tests |
| P6-046 | Partial fill semantics | 🟢 FOCUSED VERIFIED | normalized model; live integration pending |
| P6-047 | Expiry enforcement | 🔴 OPEN | automatic enforcement pending |
| P6-050 | MT5 transaction observation queue | 🔴 OPEN | runtime implementation pending |
| P6-051 | Broker snapshot sync | 🔴 OPEN | runtime implementation pending |
| P6-052 | Broker history sync | 🔴 OPEN | runtime implementation pending |
| P6-053 | Sequence-gap recovery | 🔴 OPEN | runtime implementation pending |
| P6-054 | Broker-query authority | 🔴 OPEN | runtime implementation pending |
| P6-055 | Orphan handling | 🔴 OPEN | runtime implementation pending |
| P6-060 | Protective authority separation | 🔴 OPEN | runtime implementation pending |
| P6-061 | Protective-state confirmation | 🔴 OPEN | runtime implementation pending |
| P6-062 | Python outage protection continuity | 🔴 OPEN | runtime implementation pending |
| P6-063 | TTL/dead-man enforcement | 🔴 OPEN | runtime implementation pending |
| P6-064 | Protective uncertainty | 🔴 OPEN | runtime implementation pending |
| P6-065 | Strategy re-enable gate | 🔴 OPEN | runtime implementation pending |
| P6-070 | Startup reconciliation | 🔴 OPEN | runtime implementation pending |
| P6-071 | Replay equivalence | 🔴 OPEN | adversarial/restart campaign pending |
| P6-072 | Crash-tail handling | 🔴 OPEN | injected crash campaign pending |
| P6-073 | Corruption handling | 🔴 OPEN | corruption campaign pending |
| P6-074 | Version compatibility | 🔴 OPEN | compatibility campaign pending |
| P6-080 | Malformed/oversize rejection | 🟢 FOCUSED VERIFIED | Python focused tests |
| P6-081 | Secret/log hygiene | 🔴 OPEN | final log/artifact audit required |
| P6-090 | Current MT5 source compile | 🟠 UNVERIFIED / SOURCE CHANGED | Earlier 0-error/0-warning evidence predates the reconciled MQL5 overlay; current source requires MetaEditor recompile |
| P6-091 | Fixed MT5 HKDF/proof vectors | 🟠 OBSERVED / CURRENT-SOURCE RECOMPILE REQUIRED | Later snapshot reports actual MT5 vector success, but the reconciled source lineage still requires current-source MetaEditor/self-test reproduction |
| P6-092 | Native MT5 socket connectivity | 🟠 HISTORICALLY OBSERVED / RE-RUN REQUIRED | Prior runtime trace established TCP connectivity; current reconciled source has not yet been rerun |
| P6-093 | MT5 HELLO reaches Python | 🟠 HISTORICALLY OBSERVED / RE-RUN REQUIRED | Prior runtime trace reached Python after HELLO; current reconciled source has not yet been rerun |
| P6-094 | Python decodes MT5 HELLO | 🔴 LAST OBSERVED FAILURE / RE-RUN REQUIRED | Preserved runtime trace: `JSONDecodeError: Extra data` at char 467; later source remediation has no post-change runtime trace |
| P6-095 | Live HMAC/auth | ⏳ NOT REACHED | last preserved run stopped at P6-094 |
| P6-096 | Live session establishment | ⏳ NOT REACHED | last preserved run stopped at P6-094 |
| P6-097 | Live broker reconciliation | 🔴 BLOCKED | prerequisite gates not green |
| P6-098 | Effectful execution | 🔒 LOCKED | prohibited until all prerequisites green |
| P6-099 | Phase 6 final closure | 🔴 BLOCKED | multiple red/open rows |

## 5. Immediate next gate: wire-level frame diagnosis

**Do not change cryptography. Do not introduce ZMQ. Do not implement COMMAND.**

Instrument `tools/ffbp_mt5_session_smoke_server.py` immediately after `recv_frame(conn)` and before `decode_envelope()` to record:

- total frame length;
- declared big-endian payload length;
- actual payload length;
- final 16–32 payload bytes as hex;
- final 16–32 payload bytes as `repr()`.

Never log the full HELLO, secret, MAC, or derived keys.

Classify the raw result before editing code:

- **Declared ≠ actual:** receiver framing defect.
- **Exact payload ends in `00`:** trailing NUL/sender framing defect.
- **Exact payload contains valid JSON plus trailing bytes:** sender/envelope construction defect.
- **Exact payload is clean JSON but decoder still fails:** decoder/receive assembly defect.

Only then implement the smallest corrective change and add a regression test for the exact defect.

## 6. Runtime progression gates

The next gates are strictly ordered:

`P6-094 green → P6-095 green → P6-096 green → P6-050..055 green → P6-060..065 green → P6-070..074 green → adversarial/resource/security closure → effectful path review → final gate`

No gate skipping.

## 7. Final gate rule

The only acceptable final outcomes are:

`🟢 FINAL GREEN — ARTIFACT MAY BE GENERATED`

or

`🔴 FINAL GATE BLOCKED — DO NOT GENERATE ARTIFACT.`
