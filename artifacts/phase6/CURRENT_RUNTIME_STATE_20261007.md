# FRACTAL-FLOW — PHASE 6 CANONICAL RECONCILED CURRENT STATE

**As-of:** 2026-10-07  
**Package purpose:** Canonical reconciliation of the Phase 6 fresh-session handoff and the later session-final-state snapshot.  
**Live trading:** NONE.  
**Codex:** OUT OF SCOPE / intentionally omitted from this canonical workflow.

## 1. Canonical gate

**🔴 FINAL GATE BLOCKED — DO NOT GENERATE FINAL PHASE 6 ARTIFACT.**

The package contains a later MQL5 candidate lineage that implements two source-level remediations:

1. exact UTF-8 byte serialization with explicit rejection of a trailing NUL in outbound FFBP payloads;
2. avoidance of duplicate CHALLENGE envelope verification after the outer frame has already advanced the receive sequence.

However, the later snapshot contains **no post-remediation MT5 runtime trace proving that the live Python↔MT5 boundary passed**. The last independently preserved runtime evidence remains the JSON decoder failure recorded in `artifacts/phase6/evidence/WIRE_JSON_DECODE_FAILURE_20261007.txt`.

Therefore:

- source remediation: **IMPLEMENTED / UNVERIFIED at live runtime**;
- prior JSON failure: **OBSERVED historical runtime failure**;
- current live interoperability: **UNVERIFIED / BLOCKED pending re-run**;
- HKDF/session-key vectors: **VERIFIED at fixed-vector level**;
- effectful execution: **LOCKED**.

## 2. Reconciliation decision

The larger fresh-session handoff is the canonical project base.

The later session snapshot contributes the newer MQL5 candidate EA and `FFBP_Crypto.mqh` lineage. Those files have been overlaid into this package.

The later snapshot's claim that the trailing-NUL defect was "identified and remediated" is retained only as a **source-level implementation claim** because no new MT5 runtime evidence accompanies it.

The later snapshot's "current unresolved interoperability gate is runtime AUTH/session-key boundary" is **not promoted** to the current blocker because the package does not contain runtime evidence proving that the JSON framing boundary was actually cleared. The canonical status remains: **re-run the live boundary and observe the first failure**.

## 3. Last observed runtime failure

The preserved MT5/Python trace shows:

```text
TCP connection established
HELLO sent
Python accepted the connection
json.decoder.JSONDecodeError: Extra data: line 1 column 468 (char 467)
ProtocolError: invalid UTF-8/JSON frame
```

This occurred before HMAC verification, CHALLENGE processing, AUTH, or session-key establishment.

This is the last known runtime observation, not a statement that the source-level remediation necessarily failed.

## 4. Source-level remediation now canonicalized

The canonical MQL5 EA now includes:

- exact UTF-8 serialization helper;
- explicit no-trailing-NUL defense on outbound payloads;
- canonical AUTH transcript generation;
- challenge handling without re-verifying the already-consumed CHALLENGE envelope;
- local verification of server-provided directional session keys against deterministic derivation;
- fail-closed session establishment;
- protective-only/reconciliation-required state.

The canonical crypto include now contains:

- explicit RFC 2104 HMAC-SHA256 construction;
- RFC 5869 HKDF extract/expand;
- canonical sorted session context;
- explicit removal of `StringToCharArray()` terminating NULs in cryptographic inputs;
- canonical direction-separated c2s/s2c derivation.

The account identifier from the supplied snapshot was not propagated into the canonical source; `InpAccountId` remains an input with no embedded account value.

## 5. Independently executed verification during reconciliation

Against the supplied Python project tree:

```text
22 focused Phase 6 tests: PASS
python -m compileall -q src tests tools: PASS
```

These prove the Python implementation slice only. They do not prove MetaEditor compilation or live MT5 interoperability.

The environment emitted an unrelated spreadsheet-runtime warmup diagnostic during Python startup; the requested test and compile commands nevertheless returned success.

## 6. Immediate next action

Do not change crypto or transport architecture yet.

Re-run the actual MT5 → Python session boundary using the canonicalized MQL5 EA and the existing smoke server with bounded wire diagnostics immediately before JSON decoding:

- total frame length;
- declared length;
- actual payload length;
- final 16–32 bytes in hex;
- final 16–32 bytes as repr.

Then classify the result before any further patch.

## 7. Safety

- `InpAllowReal=false`.
- No effectful COMMAND path.
- No live trading.
- No blind resend after UNKNOWN.
- No promotion of source claims to runtime verification.
