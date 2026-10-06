# Codex Bootstrap — FRACTAL-FLOW Phase 6

You are operating on a forensic trading-system repository. Do not rewrite or casually refactor.

## Governing order
SURVIVAL > CORRECTNESS > AUDITABILITY > DETERMINISM > EXPLICIT AUTHORITY > RECOVERY > SECURITY > PERFORMANCE > PnL

## First task: reconnaissance only
Do not implement until you have:

1. inventoried the repository;
2. fingerprinted the source/spec/docs/tests;
3. identified the Phase 5 baseline and its current test state;
4. inspected `artifacts/phase5/` and `docs/13_EXECUTION.md`, `docs/14_RECONCILIATION.md`, `docs/22_PERSISTENCE_AND_RECOVERY.md`, `docs/23_RECONCILIATION_AND_TEMPORAL_CONSISTENCY.md`;
5. inspected `mql5/Phase6Bridge/` and its implementation notes;
6. searched for any existing bridge/session/command/ledger/reconciliation implementations;
7. produced a current HPL with statuses VERIFIED / IMPLEMENTED / PARTIAL / MISSING / UNVERIFIED.

## MQL5 evidence already verified externally
- `FractalFlowBridgeEA.mq5`: 0 errors, 0 warnings.
- `FFBP_CryptoSelfTest.mq5`: 0 errors, 0 warnings.
- MT5 runtime HMAC known-answer test: PASS.

Do not reclassify these as Python-side tests. They are external MT5 evidence.

## Phase 6 objectives
Audit and implement incrementally:
- strict account identity;
- canonical FFBP/1 protocol;
- durable `(account_id, command_id)` command ledger;
- durable session fencing;
- bounded transport queues/backpressure;
- TCP bridge;
- FakeEA/test double;
- broker reconciliation;
- protective autonomy;
- crash/restart recovery;
- replay/determinism;
- adversarial transport and persistence testing.

## Mandatory rules
- No missing `account_id` fallback to `ACT_PRIMARY`.
- Unknown broker execution must never be blindly resent.
- Exactly-once means exactly-once effect, never exactly-once delivery.
- Cache is never execution authority.
- Recovery is non-executing until reconciliation completes.
- Protective authority survives strategy/process/network failure where designed.
- No secrets in logs or artifacts.
- No live execution authorization.
- Do not claim runtime verification that was not actually performed.

## Verification workflow
HPL -> dependency graph -> smallest safe implementation unit -> targeted green gate -> hardening -> adversarial tests -> full regression -> documentation reconciliation -> final HPL.

Start with reconnaissance and report findings before modifying source.
