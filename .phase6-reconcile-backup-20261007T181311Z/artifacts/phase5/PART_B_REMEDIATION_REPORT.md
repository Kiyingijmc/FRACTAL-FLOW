# FRACTAL-FLOW Phase 5 Part B — Forensic Remediation Report

Date: 2026-10-06
Status at implementation start: `FINAL GATE BLOCKED`

## Research and design basis

The remediation followed a fail-closed authorization model: structural validity is distinct from authority, every protected boundary performs its own authorization check, and downstream components do not inherit authority merely because an upstream object contains a boolean `authorized` field.

Stateful/property-based testing was selected for the mutation-heavy surfaces because state-machine testing can generate sequences of actions rather than isolated examples and can assert invariants after every step. The project environment does not currently provide the Hypothesis package, so deterministic adversarial/state-machine-equivalent tests were retained as the executable fallback. Hypothesis documentation confirms the suitability of rule-based state machines and invariant checks for this class of sequence-dependent behavior.

Persistence design follows the existing append-only durable journal rather than introducing a second storage authority. Part-B context is recorded with a deterministic context fingerprint so a replay/audit process can reconstruct the decision inputs without trusting mutable process memory.

## Implementation sequence

1. Phase-4 authority closure.
2. Part-B current-authority/freshness boundary.
3. Portfolio hard-cap correctness and dynamic risk throttling.
4. News temporal integrity.
5. Part-B journal reconstruction context and idempotency evidence.
6. R5 stress-harness termination hardening.
7. Regression, adversarial and full-suite verification.

## Invariants closed by implementation

- Direct/public `TradeDecisionV4` construction cannot mint Phase-4 authority.
- Factory-issued Phase-4 authority is content-bound to the authoritative opportunity and current parent lineage for child opportunities.
- A stale, expired, invalidated, superseded or content-mismatched Phase-4 decision cannot cross into Part B.
- An opportunity cannot exceed its effective entry budget through repeated Part-B authorizations.
- MERGE cannot bypass portfolio hard caps.
- Portfolio exposure is explicit and unit-bound; raw volume is never silently substituted for missing notional.
- Portfolio correlation considers existing-position risk magnitude.
- Portfolio throttling can only reduce risk; final risk/volume remains Risk Engine authority.
- Scheduled news evidence before release is rejected.
- Part-B durable records retain deterministic reconstruction context and context fingerprints.
- R5 stress worker failures do not force unrelated thread-pool work to drain before the harness exits.

## Verification policy

Ruff, strict mypy and Git provenance remain environmental exceptions in this working artifact. They are never represented as passed. Compile/test/replay/adversarial evidence is independently recorded from executable source.
