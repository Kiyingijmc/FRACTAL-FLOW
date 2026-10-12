# FRACTAL-FLOW Phase 6 — MT5 Source Identity Verification

Date: 2026-10-07
Branch: phase6-forensic-baseline
WSL HEAD: 0fe03629e96bb1b3ea1616ded1325fd6f344d408

## Result

The live MT5 MQL5 source tree was compared against the canonical WSL
Phase 6 source.

Raw SHA-256 differences were initially observed for:

- FractalFlowBridgeEA.mq5
- FFBP_Crypto.mqh

The differences were investigated for line-ending effects.

## Normalized Results

### FractalFlowBridgeEA.mq5

After CRLF/LF normalization, the files differ by exactly one substantive
source line:

MT5 deployment:
    input string InpAccountId="104838909";

Canonical WSL:
    input string InpAccountId="";

All other EA source content is identical after line-ending normalization.

The MT5 value is treated as deployment-specific account configuration.
The canonical repository intentionally contains no account-specific identity.

### FFBP_Crypto.mqh

After CRLF/LF normalization, SHA-256 matches exactly:

21b92b187a18a9f5ae96bb9f2ad5044544ca6ed13a72af60cb0c0aadb5545196

Therefore the live MT5 cryptographic implementation is source-identical
to the canonical WSL implementation.

### Other Phase 6 includes

The following files already matched by SHA-256:

FFBP_Json.mqh
165284fe70da929cd284011a912f3cbec063106b3353ad38b829aa3edc06cf51

FFBP_Broker.mqh
1075d5f59eba36f3511ae3e48b5971a76ef347a2df5966710eecf7f466ce9079

FFBP_Persistence.mqh
7229264d36c8332514231fd157527710aab71f23d234fa0e9281e376ad187aab

## Forensic Classification

MT5 source identity: VERIFIED
Cryptographic source identity: VERIFIED
Protocol implementation source identity: VERIFIED

EA account identity: DEPLOYMENT-SPECIFIC

No source synchronization is required at this point.

## Next Gate

Proceed to MetaEditor compilation and runtime wire verification.

Do not redesign HKDF/session cryptography unless live runtime evidence
demonstrates a cryptographic divergence.
