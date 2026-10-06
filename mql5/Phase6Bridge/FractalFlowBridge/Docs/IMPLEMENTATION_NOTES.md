# Phase 6 MQL5 Implementation Notes

## Implemented in this candidate

- Explicit account/lane identity; no account fallback.
- REAL-account startup guard unless explicitly enabled by input.
- TCP socket creation/connect/polling.
- Four-byte big-endian FFBP/1 frame envelope.
- Incremental exact-length socket reads.
- Maximum-frame enforcement before allocation.
- Canonical envelope generation in lexicographic key order.
- Explicit HMAC-SHA256 using MQL5 SHA-256 primitive.
- Canonical MAC insertion/removal.
- Monotonic receive sequence check.
- Durable session epoch file in `FILE_COMMON`.
- Append-only command evidence file boundary.
- Protective-only fail-closed behavior.
- O(1) `OnTradeTransaction` boundary.
- Bounded `OnTimer` drain loop.
- Demo-first / real-account fail-closed policy.

## Deliberately not enabled

Effectful broker COMMAND handling remains blocked in this candidate until the
following are separately implemented and verified:

1. Challenge/auth transcript and session-key installation.
2. Durable command dedupe lookup before any broker effect.
3. Broker request submission with stable command correlation.
4. Order/deal/position reconciliation.
5. UNKNOWN execution resolution.
6. Protective command authorization and monotonic stop policy.
7. Durable command result persistence.
8. Restart-equivalent state reconstruction.

This is intentional. A compile-clean adapter that can accidentally trade is
not a safe Phase 6 artifact.
