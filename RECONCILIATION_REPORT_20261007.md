# FRACTAL-FLOW — PHASE 6 FORENSIC RECONCILIATION REPORT

**Date:** 2026-10-07  
**Inputs:**
- `FRACTAL-FLOW-PHASE6-FRESH-SESSION-HANDOFF-20261007.zip`
- `FRACTAL-FLOW-PHASE6-SESSION-FINAL-STATE-SNAPSHOT-20261007.zip`

## Executive decision

The two supplied packages are reconciled into this canonical package.

**Canonical project base:** the 383-file fresh-session handoff.

**Later source overlay accepted:** the MQL5 `FractalFlowBridgeEA.mq5` and `FFBP_Crypto.mqh` lineage from the session-final-state snapshot.

**Codex material:** omitted from the active canonical workflow at the user's direction.

**Final gate:** 🔴 BLOCKED.

## Why the packages could not simply be merged mechanically

The fresh-session handoff records the last observed live failure as:

```text
JSONDecodeError: Extra data: line 1 column 468 (char 467)
```

The later session-final-state snapshot says that a trailing-NUL framing defect was identified/remediated and that the remaining gate moved to AUTH/session-key interoperability.

Those statements are not equivalent to runtime proof. The later snapshot contains source artifacts but no corresponding post-remediation MT5 terminal trace establishing that the JSON boundary actually passed.

Therefore the canonical state must distinguish:

- **implementation evidence:** the later source contains the remediation;
- **runtime evidence:** the last preserved runtime observation is still the JSON decoder failure;
- **current live status:** unverified until the canonical source is actually run in MT5.

## Source reconciliation

### MQL5 EA

The later candidate EA was selected over the earlier packaged EA because it contains materially newer boundary-hardening work:

- exact UTF-8 serialization;
- explicit trailing-NUL rejection;
- canonical AUTH transcript serialization;
- corrected CHALLENGE dispatch flow avoiding duplicate envelope verification;
- local directional-key derivation verification;
- expanded fail-closed diagnostics.

The environment-specific account ID embedded in the candidate snapshot was removed from the canonical source and left as `InpAccountId=""`.

### MQL5 crypto

The later `FFBP_Crypto(2).mqh` was selected as the canonical `FFBP_Crypto.mqh` because it explicitly documents and implements the canonical session context and removes `StringToCharArray()` terminating NULs from cryptographic byte inputs.

The implementation still requires actual MetaEditor compilation and MT5 execution evidence.

### Python

No later Python implementation differing from the canonical handoff was identified in the session snapshot. The Python protocol/session implementation remains the canonical handoff version.

## Verification performed during reconciliation

The canonical Python tree was executed directly:

```text
22 focused Phase 6 tests: PASS
python -m compileall -q src tests tools: PASS
```

These are Python-side evidence only.

They do not prove:

- MetaEditor compilation of the overlaid MQL5 sources;
- MT5 terminal execution of the overlaid EA;
- Python↔MT5 live authentication;
- broker truth/reconciliation;
- protective continuity;
- effectful execution.

## Material contradictions resolved

| Issue | Earlier handoff | Later snapshot | Canonical decision |
|---|---|---|---|
| Live JSON boundary | observed failure | source says framing remediation | retain failure as last observed runtime evidence; source remediation = implemented/unverified |
| HKDF/session-key state | vectors verified; live handshake blocked | claims runtime gate moved later | fixed vectors remain VERIFIED; live session remains UNVERIFIED |
| MQL5 EA | earlier packaged candidate | newer canonicalized candidate | newer candidate selected |
| MQL5 crypto | earlier include | newer crypto lineage | newer lineage selected |
| Account ID | blank input | embedded environment-specific value | blank input restored |
| Codex | included | included | omitted from canonical active workflow |
| Final closure | blocked | snapshot is called "final-state" | final gate remains BLOCKED because required runtime proof is absent |

## Important audit finding

The most significant provenance defect in the supplied materials is not necessarily a code defect; it is **state-label drift**.

A "session final-state snapshot" can contain newer source than the "fresh-session handoff", while the runtime evidence still terminates at the earlier failure. The canonical package therefore must not infer runtime closure from source recency.

## Next proving action

Use the canonicalized MQL5 EA with the existing Python smoke server.

Instrument only bounded raw-frame diagnostics immediately before JSON decoding:

```text
FRAME_TOTAL
DECLARED
PAYLOAD_LEN
TAIL_HEX
TAIL_REPR
```

Then classify:

A. declared/actual mismatch → framing defect  
B. trailing NUL → sender serialization defect  
C. valid JSON + extra bytes → sender/assembly defect  
D. clean JSON + decoder failure → receiver/decoder defect

Only after classification should the next code change be selected.

## Safety gate

No crypto rewrite, ZMQ migration, COMMAND enablement, broker execution, or live trading is justified by the current evidence.
