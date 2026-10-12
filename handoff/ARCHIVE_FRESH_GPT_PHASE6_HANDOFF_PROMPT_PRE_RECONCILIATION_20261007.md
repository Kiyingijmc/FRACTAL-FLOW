# FRACTAL-FLOW — PHASE 6 FRESH GPT SESSION MASTER HANDOFF

**Date:** 2026-10-07
**Mission:** Continue the existing FRACTAL-FLOW Phase 6 forensic engineering effort from the exact current boundary. Do not restart Phase 6, redesign it casually, or assume prior claims are correct without evidence.

---

## 0. FIRST INSTRUCTION — READ THE BUNDLE BEFORE ACTING

You are taking over a serious, multi-phase forensic software-engineering effort. The attached ZIP is the current working handoff package.

Before modifying anything:

1. Inventory the ZIP/tree.
2. Read:
   - `artifacts/phase6/CURRENT_RUNTIME_STATE_20261007.md`
   - `artifacts/phase6/UPDATED_PHASE6_HPL_20261007.md`
   - `artifacts/phase6/PHASE6_IMPLEMENTATION_HPL.md`
   - `artifacts/phase6/PHASE6_SESSION_BOUNDARY_IMPLEMENTATION_EVIDENCE.md`
   - `reference/PHASE6_IMPLEMENTATION_HPL-PRIOR.md`
   - `reference/FRACTAL-FLOW-PHASE6-CANONICAL-RESEARCH-HPL.md`
   - all files under `reference/FRACTAL-FLOW-PHASE6-DESIGN-SPECIFICATIONS/`
   - `artifacts/phase6/evidence/MT5_RUNTIME_LOG_20261007-171016.txt`
   - `artifacts/phase6/evidence/WIRE_JSON_DECODE_FAILURE_20261007.txt`
3. Fingerprint the source tree and relevant protocol files.
4. Inspect the actual implementation before proposing any patch.
5. Re-run the smallest relevant test(s) before changing code.

Do not treat the handoff documents as infallible. They are evidence and control artifacts. Reconcile them against source.

---

# 1. PROJECT IDENTITY

FRACTAL-FLOW is a survival-first, deterministic, auditable trading system. Phase 6 extends it across the Python ↔ MetaTrader 5 execution boundary.

The Phase 6 mission is NOT merely “make MT5 talk to Python.” It is to establish a deterministic, authenticated, durable, reconciliable execution boundary that preserves explicit authority and survives ambiguity, restart, broker inconsistency, and process/network failure.

Governing priority:

`SURVIVAL > CORRECTNESS > AUDITABILITY > DETERMINISM > EXPLICIT AUTHORITY > RECOVERY > SECURITY > PERFORMANCE > PnL`

No hidden ML/strategy authority may be introduced.

---

# 2. LOCAL DEVELOPMENT ENVIRONMENT

The active WSL working environment used during this phase is:

```text
/home/kiyingijmc/projects/phase6-work
```

Windows source/download location used during the MT5 campaign:

```text
C:\Users\danie\Downloads\FRACTAL-FLOW-PHASE6-LOCAL-WSL-MT5-SESSION-GATE-20261007.zip
```

Typical WSL commands used:

```bash
cd /home/kiyingijmc/projects/phase6-work
python -m pytest -q -o addopts= tests/test_ffbp_protocol.py tests/test_ffbp_session.py tests/test_ffbp_interop_vector.py tests/test_command_ledger.py tests/test_broker_truth.py tests/test_protective_authority.py tests/test_ffbp_mt5_smoke_server.py
python -m compileall -q src tests tools
```

A focused campaign against the current package was previously observed at:

```text
23 passed in 8.54s
```

Do not claim that number unless you reproduce it or explicitly classify it as historical/owner-supplied evidence.

The Python smoke server is:

```text
tools/ffbp_mt5_session_smoke_server.py
```

The normal test listener is:

```text
0.0.0.0:39001
```

MT5 connects to:

```text
127.0.0.1:39001
```

The Windows-to-WSL TCP path was independently tested with:

```powershell
Test-NetConnection 127.0.0.1 -Port 39001
```

and succeeded.

---

# 3. MT5 TEST ACCOUNT / SAFETY

The MT5 campaign used a demo/hedging account. The exact account ID is present in the runtime evidence, but do not unnecessarily propagate account identifiers into logs or documentation.

Critical safety rule:

```text
InpAllowReal=false
```

Never enable real trading during this Phase 6 development campaign.

Never request or expose the shared secret. The secret must not appear in prompts, artifacts, logs, screenshots, source-control commits, or final reports.

---

# 4. WHAT IS ALREADY PROVEN

### Python

- FFBP protocol primitives exist.
- FFBP session primitives exist.
- Durable command ledger exists.
- Broker-truth normalized models exist.
- Protective-authority substrate exists.
- Focused protocol/session/broker/protection tests pass in the current development campaign.
- Python compileall passed.

### MQL5

- `FractalFlowBridgeEA.mq5` compiles in MetaEditor with 0 errors / 0 warnings based on owner-observed evidence.
- HMAC self-test passed in actual MT5.
- HKDF fixed vectors passed in actual MT5.
- Challenge proof vector passed in actual MT5.
- The prior HKDF mismatch was diagnosed as canonical context-key ordering; the source was corrected to match Python's deterministic ordering. Do not reopen this issue unless new evidence contradicts it.

Exact verified session vectors:

```text
c2s = 8b231877fc4595fd47d0168a27851888fd4b053bee31be2f565eabe9810ba169
s2c = 0c0814372cb1bbe4bdde66f0ee484b718b2989c7a850f3c16812c2e78c954727
proof = abc0a20abca417cc9c5d02b44ec0540accb43d9cea8a434c6ebd7a595420b1ed
```

### Native socket transport

A previous `SocketConnect` 4014 problem was resolved in the local MT5 environment. Current runtime evidence shows:

```text
TCP connection established
HELLO sent
```

Therefore the current blocker is no longer native TCP reachability.

---

# 5. EXACT CURRENT BLOCKER

The latest runtime sequence is:

```text
MT5
  ↓
SocketCreate                    GREEN
  ↓
SocketConnect                   GREEN
  ↓
Send HELLO                      GREEN
  ↓
Python accepts TCP connection  GREEN
  ↓
Python recv_frame               reaches decoder
  ↓
json.loads(...)                 RED
```

Python raises:

```text
JSONDecodeError: Extra data: line 1 column 468 (char 467)
```

The server then raises:

```text
ProtocolError: invalid UTF-8/JSON frame
```

This occurs BEFORE:

- HMAC verification;
- challenge validation;
- AUTH;
- session-key installation;
- SESSION_ESTABLISHED;
- post-session HMAC;
- broker reconciliation.

Therefore:

**DO NOT MODIFY HKDF, HMAC, challenge proof, session transcript, or command authorization to solve this failure.**

---

# 6. IMMEDIATE TASK — WIRE-LEVEL FORENSIC DIAGNOSIS

Your first implementation task is ONLY to establish exactly what bytes arrived at Python.

Inspect:

```text
tools/ffbp_mt5_session_smoke_server.py
src/fractal_flow/execution/ffbp_protocol.py
mql5/Phase6Bridge/FractalFlowBridge/FractalFlowBridgeEA.mq5
```

The current MQL5 sender contains logic that removes the terminating NUL from the UTF-8 byte array before transmitting and calculates the 4-byte big-endian frame length from the resulting byte count.

Do not assume that the `char 467` failure is a trailing NUL. Prove it.

Temporarily instrument the Python smoke server immediately after `recv_frame(conn)` and before `decode_envelope()` with ONLY bounded diagnostics:

```text
frame_total_length
frame_declared_length
payload_actual_length
payload_tail_hex
payload_tail_repr
```

For example, conceptually:

```python
frame = recv_frame(conn)
print(f"FRAME_TOTAL={len(frame)}")
print(f"DECLARED={int.from_bytes(frame[:4], 'big')}")
print(f"PAYLOAD_LEN={len(frame)-4}")
print(f"TAIL_HEX={frame[-32:].hex()}")
print(f"TAIL_REPR={frame[-32:]!r}")
```

Do NOT print the complete frame, shared secret, MAC, or derived keys.

Then determine which case actually occurred:

### Case A — length mismatch

```text
DECLARED != actual payload bytes
```

Receiver framing/assembly is wrong.

### Case B — trailing NUL

Exact-length payload ends with:

```text
00
```

and JSON is otherwise valid.

Then determine why the sender transmitted it despite source-level stripping.

### Case C — valid JSON followed by other bytes

The payload contains a complete JSON object and additional non-NUL bytes.

Investigate sender envelope construction or receive assembly.

### Case D — clean JSON but decoder still fails

Then inspect `decode_envelope()` and the exact `recv_frame()` contract.

Do not make a speculative patch before classification.

---

# 7. REQUIRED ENGINEERING METHOD FOR THE FIX

Once the byte defect is proven:

1. State the defect precisely.
2. Identify the authoritative layer responsible.
3. Make the smallest correct fix.
4. Add a regression test that reproduces the exact defect.
5. Run the focused FFBP tests.
6. Run compileall.
7. If Python changes affect the wire contract, regenerate/reconcile cross-language vectors.
8. Have the owner recompile the affected MQL5 source in MetaEditor.
9. Re-run actual MT5 runtime smoke test.
10. Only promote the HPL row if the evidence supports the promotion.

Never fix an application-layer problem by replacing the transport architecture without proving the transport is defective.

---

# 8. ZMQ / TITAN CONTEXT — IMPORTANT BUT NOT THE CURRENT FIX

The owner has another actively running MT5 system, Titan Gateway, that communicates through:

```text
MT5 EA → libzmq.dll → ZeroMQ/TCP → external process
```

Its source uses MQL5 `#import "libzmq.dll"` and ZeroMQ sockets.

This explains why Titan can communicate on the same PC while native MQL5 `SocketConnect()` previously returned 4014.

However, native FFBP TCP is now proven to establish a TCP connection and deliver HELLO to Python. Therefore **do not switch FFBP to ZMQ merely because Titan uses ZMQ**.

A future ZMQ transport adapter could be researched if native TCP proves structurally inadequate, but it would introduce:

- DLL deployment/security dependencies;
- another failure boundary;
- another transport implementation;
- new resource/shutdown semantics;
- new interoperability tests.

That decision requires a separate architecture review.

---

# 9. FFBP PROTOCOL / AUTHORITY RULES

Canonical wire model:

```text
4-byte big-endian length
        ↓
UTF-8 deterministic JSON envelope
        ↓
HMAC authentication
```

Session sequence:

```text
HELLO
  → CHALLENGE
  → AUTH
  → SESSION_ESTABLISHED
  → authenticated HEARTBEAT/ACK
```

Session keys:

- challenge uses long-lived shared secret;
- fresh client/server nonces bind the session;
- HKDF derives directional c2s/s2c keys;
- post-session traffic uses directional HMAC.

The MT5 bridge must independently derive and verify the keys supplied by the server before setting authenticated state.

The bridge must remain:

```text
protective_only = true
reconciliation_required = true
```

until all required authority/reconciliation gates are satisfied.

---

# 10. EXECUTION SAFETY RULES

The following are explicitly prohibited until the Phase 6 final HPL is green:

- live trading;
- enabling `InpAllowReal`;
- effectful COMMAND processing;
- blind retries after UNKNOWN;
- treating ACK as broker effect;
- treating OrderSend success as filled;
- using `OnTradeTransaction` as sole broker truth;
- allowing MT5 to invent strategy decisions;
- allowing process memory to be authoritative;
- unbounded retry/queue growth;
- bypassing reconciliation;
- bypassing startup recovery gates;
- deleting or weakening tests to make a gate green.

---

# 11. DURABLE COMMAND / UNKNOWN MODEL

Command identity:

```text
(account_id, command_id)
```

Same command ID + same canonical fingerprint:

```text
DUPLICATE / IDENTITY-PRESERVING
```

Same command ID + different fingerprint:

```text
CONFLICT → QUARANTINE
```

UNKNOWN means exactly that: the system cannot yet establish broker effect.

The correct response to UNKNOWN is reconciliation, not blind resend.

---

# 12. BROKER TRUTH RULES

The system must distinguish:

- order request;
- order acknowledgement/result;
- order;
- deal;
- position;
- transaction observation;
- broker snapshot;
- broker history;
- durable command intent.

Fresh broker truth outranks local expectation.

Position identity must not rely solely on a mutable ticket. Stable broker position identifiers and lineage must be preserved where available.

Netting and hedging must be explicit branches in the normalized model and runtime tests.

---

# 13. RECOVERY RULES

Startup:

```text
load durable state
→ validate persistence
→ reconstruct
→ query/reconcile broker
→ resolve uncertainty
→ establish protective state
→ only then permit strategic execution
```

A restart must not resurrect stale execution authority.

Replay must be deterministic.

Crash tails, corruption, schema/version mismatch, missing history, sequence gaps, orphan objects, and partial fills must have explicit states and fail-safe behavior.

---

# 14. TESTING RULES

Use the smallest proving test first.

Recommended sequence:

```text
wire-unit test
→ focused Python FFBP tests
→ compileall
→ MetaEditor compile
→ MT5 smoke
→ cross-language handshake
→ restart/crash tests
→ adversarial tests
→ full regression
```

A green focused test does not close an integration gate.

A green Python simulation does not prove MT5 behavior.

An MT5 compile does not prove Python interoperability.

A successful TCP connection does not prove authenticated protocol correctness.

An authenticated session does not prove broker truth or execution correctness.

---

# 15. EVIDENCE CLASSIFICATION

Use these statuses exactly:

```text
OBSERVED
VERIFIED
IMPLEMENTED
PARTIAL
SPECIFIED
PROPOSED
RESEARCH FINDING
AGREED DESIGN
UNVERIFIED
DEFERRED
BLOCKED
FAILED
INCORRECT
OUT OF SCOPE
```

For every material claim, state:

```text
claim → evidence → status → remaining gap
```

---

# 16. ARTIFACT RULE

Do not generate a “final” closure artifact while any required HPL row is red, unknown, partial, incorrect, or unsupported by an explicit owner-approved exception.

Final gate must be exactly one of:

```text
🟢 FINAL GREEN — ARTIFACT MAY BE GENERATED
```

or

```text
🔴 FINAL GATE BLOCKED — DO NOT GENERATE ARTIFACT.
```

The current session is definitively the second state.

---

# 17. WHAT NOT TO DO IN THE FIRST RESPONSE

Do NOT:

- rewrite the protocol;
- replace TCP with ZMQ;
- modify crypto;
- enable commands;
- implement broker execution;
- claim session authentication is complete;
- declare Phase 6 green;
- create a final release artifact;
- assume the trailing-NUL hypothesis is correct;
- ask the owner to repeat information already contained in this bundle.

Your first response should report:

1. what you found in the bundle;
2. what you independently verified;
3. the exact current blocker;
4. the exact wire-level diagnostic you will run;
5. what evidence will determine the next patch.

Then execute that forensic workflow.

---

# 18. START HERE

**Immediate mission:** prove the exact bytes received by Python for the MT5 HELLO frame.

Do not proceed to any later Phase 6 capability until that boundary is clean and independently verified.
