# FFBP strict UTF-8 receive candidate — forensic note

Status: candidate only; NOT deployed and NOT MetaEditor-compiled.

## Change
Adds `FFBP_IsValidUtf8()` to `FractalFlowBridgeEA.mq5` candidate and validates the length-delimited frame body bytes before `CharArrayToString(..., CP_UTF8)`.

The validator rejects stray continuation bytes, invalid leading bytes, overlong encodings, UTF-16 surrogate encodings, truncated sequences, and code points above U+10FFFF. It leaves framing, authentication, sequence, ACK semantics, authority state, and reconnect behavior unchanged.

## Evidence
- UTF-8 oracle: 6 valid vectors and 10 invalid vectors passed against Python's strict UTF-8 decoder.
- Static source guard: validator invocation precedes MQL5 decoding.
- Existing receive-contract oracle: 8 cases passed (fragmentation, coalescing, trailing partial frame, deadline, partial close, zero length, oversized length, invalid UTF-8/JSON).

## Limitations
These are contract/oracle and source-placement checks, not execution of the MQL5 function. MetaEditor compilation and MT5 runtime tests remain mandatory. The candidate has not been copied into the canonical repository, any deployed EA directory, or any global/nested include directory. Keep `InpAllowReal=false`.

## Candidate SHA-256
`bc754db41b598f91e80613b7ff71dce86386b3b8ee186028bae2e79349fc2416`
