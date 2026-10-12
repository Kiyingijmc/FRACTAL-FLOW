# FRACTAL-FLOW Phase 6 — Development, Design & Implementation Rules

## A. Architecture

- Extend existing FRACTAL-FLOW durable execution/recovery infrastructure; do not create parallel authorities.
- Keep informational, strategy, risk, portfolio, persistence, recovery, protective, and execution authority explicit.
- Transport is not strategy.
- MT5 is not strategy.
- Broker adapters observe/execute authorized intent; they do not manufacture intent.

## B. Determinism

- Canonical UTF-8 JSON.
- Stable field ordering.
- Explicit scalar normalization.
- Fixed 4-byte big-endian framing.
- Bounded frame size.
- Explicit sequence and acknowledgement semantics.
- Version all persistent/protocol state.
- Preserve replay equivalence.

## C. Security

- Shared secret is never logged.
- Derived session keys are never logged.
- Do not print full authenticated frames.
- Fresh nonces bind sessions.
- HKDF is domain-separated and directional.
- HMAC authenticates canonical bytes.
- Reject malformed/oversize frames.
- Fail closed on authentication/session mismatch.

## D. Execution correctness

- Order request ≠ order acknowledgement ≠ broker effect.
- ACK ≠ fill.
- `OrderSend()` ≠ fill.
- Transaction callback ≠ durable truth.
- Broker snapshot/history is required for uncertainty resolution.
- UNKNOWN persists.
- No blind resend.
- Partial fills are first-class.
- Netting/hedging semantics are explicit.

## E. Recovery

- Restart does not restore strategic authority automatically.
- Reconcile broker before re-enable.
- Sequence gaps trigger synchronization.
- Orphans are explicit.
- Corrupt persistence fails closed.
- Crash tails cannot fabricate broker effect.
- State reconstruction must be deterministic.

## F. Resource safety

- Bounded queues.
- Bounded retries.
- Explicit timeout/deadline behavior.
- Explicit overload/disconnect transitions.
- Never spin indefinitely on a failed/quarantined session.

## G. Verification

- Reproduce first.
- Instrument minimally.
- Prove the failing boundary.
- Patch the responsible layer only.
- Add a regression test.
- Re-run focused tests.
- Re-run cross-language/runtime evidence.
- Update HPL status only when evidence supports it.

## H. Change control

Every implementation change should answer:

1. What invariant does this protect?
2. Which authority owns the behavior?
3. What failure mode does it address?
4. What existing behavior could it alter?
5. What deterministic test proves it?
6. What runtime evidence is required?
7. What recovery/restart behavior changes?
8. What artifact/documentation must remain synchronized?

## I. Forbidden shortcuts

- No speculative protocol rewrites.
- No architecture replacement to avoid a local defect.
- No weakening assertions.
- No deleting tests.
- No hidden retries.
- No “best effort” effectful execution after uncertainty.
- No live trading.
- No final closure claims from unit tests alone.
