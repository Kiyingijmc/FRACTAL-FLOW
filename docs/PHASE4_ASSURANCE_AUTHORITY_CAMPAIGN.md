# FRACTAL-FLOW Phase 4 — Assurance & Authority Integrity Campaign

## Objective

This campaign hardens the Phase 4 authority boundary against replay divergence, state-order defects, semantic safety-control removal, capability escalation, account-context interference, and authority revival after a negative state.

The campaign follows the ordering:

**replay → stateful differential testing → semantic mutation testing → capability / non-interference / monotonic-authority hardening → hostile re-audit**.

The security model is deliberately aligned with NIST least-privilege and separation-of-duties principles: authorization is explicit, scoped, deny-by-default, and distinct from the informational components that produce evidence. NIST describes least privilege as granting only the minimum authorization necessary for the assigned function and separation of duties as dividing duties so that a single role cannot abuse combined privileges. NIST's Zero Trust guidance likewise recommends discrete authorization, least privilege, separation of duties, and default denial. See NIST SP 800-171 Rev. 3 and SP 800-207.

## 1. Replay assurance

`src/fractal_flow/domain/phase4_assurance.py` adds:

- append-only `Phase4ReplayLog`;
- sequence validation;
- hash-chain integrity;
- deterministic stream fingerprinting;
- decision-outcome replay;
- `DecisionReplayFixture` capable of reconstructing Phase 4 domain inputs and rerunning the authoritative `make_decision()` path.

Replay tests prove that an identical serialized input fixture reconstructs the same decision fingerprint and authority outcome. Semantic tampering of replayed EntryPlan data is rejected by the authoritative domain invariants rather than trusted as a recorded result.

## 2. Stateful differential assurance

`tests/phase4_assurance/test_stateful_differential.py` exercises ordered state mutations and all gate permutations against an independently written reference predicate.

Covered properties include:

- lifecycle-state changes cannot create authorization;
- failed states cannot be upgraded by gate ordering;
- all gate permutations yield one canonical decision fingerprint;
- negative gate states cannot be upgraded by adding a duplicate positive claim;
- account metadata does not become Phase 4 authority or alter the canonical decision identity.

This is a deterministic state-machine campaign rather than a claim of Hypothesis-based property testing; no new third-party property-testing dependency was introduced.

## 3. Semantic mutation testing

`tools/phase4_semantic_mutation.py` applies eight targeted authority mutants to isolated temporary copies of `phase4.py` and runs the hostile plus assurance suites.

Mutants cover:

1. opportunity lifecycle bypass;
2. tradeability status bypass;
3. future-evidence bypass;
4. confidence escalation bypass;
5. mandatory-gate-set bypass;
6. gate temporal bypass;
7. direct authority-proof bypass;
8. decision-fingerprint bypass.

**Result: 8/8 killed, 0 survived, 0 invalid. Mutation kill rate: 100%.**

The campaign intentionally uses semantic authority mutants rather than treating line coverage as a proxy for safety assurance.

## 4. Capability hardening

`Phase4Capability` is a least-privilege, immutable capability bound to:

- one decision ID;
- one opportunity ID;
- one explicit scope (`PHASE4_HANDOFF`);
- the issuance timestamp;
- an opaque internal proof.

It cannot authorize `SUBMIT_ORDER`, `CREATE_EXECUTION_INTENT`, `ALLOCATE_RISK`, `SIZE_TRADE`, or `MODIFY_POSITION`.

Capability use also requires the authoritative opportunity context to remain live. An invalidated, stale, degraded, or expired opportunity therefore revokes the capability at use time rather than allowing a stale handoff to be treated as current authority.

## 5. Non-interference and separation of duties

The Phase 4 decision remains account-free and risk-free. Account identity is not an input to the decision fingerprint, EntryPlan geometry, or Phase 4 handoff capability.

The campaign explicitly verifies that account metadata cannot expand Phase 4 authority and that the handoff capability contains no execution or risk allocation authority.

This preserves the architectural split:

**analysis / evidence → Phase 4 decision handoff → later risk / portfolio / execution authority**.

No Phase 4 capability can cross that boundary by changing account metadata or gate ordering.

## 6. Monotonic authority

Authority is fail-closed and non-revivable within a decision instance:

- a failed gate yields a non-authoritative decision;
- adding a contradictory positive duplicate is rejected;
- an invalidated opportunity cannot manufacture a capability;
- an already-issued capability is revoked when its authoritative opportunity is no longer live;
- capability scope cannot be widened through normal construction.

This is a monotonicity property of the authority state, not a claim that all later execution-layer revocation semantics are already implemented.

## 7. Hostile re-audit result

Post-campaign verification:

- full regression: **614 passed, 0 failed, 0 skipped**;
- configured coverage: **88.85%**, above the 85% floor;
- Phase 4 hostile authority suite: **17 passed**;
- Phase 4 assurance suite: **12 passed**;
- semantic mutation campaign: **8/8 killed**;
- `python -m compileall -q src tests`: **PASS**;
- Ruff: **OWNER-APPROVED ENVIRONMENTAL EXCEPTION** — executable unavailable;
- Mypy: **OWNER-APPROVED ENVIRONMENTAL EXCEPTION** — executable unavailable.

The hostile re-audit found no surviving targeted authority mutant and no regression in the existing Phase 4 authority attack matrix.

## Boundary

This campaign materially closes the previously deferred Phase 4 assurance extensions for replay, deterministic stateful differential testing, targeted semantic mutation, least-privilege capability scoping, account-context non-interference, and monotonic opportunity-bound authority.

It does **not** promote Phase 4 into broker/execution authority and does not implement the deferred Phase 5 Risk, Portfolio, News Shield, broker execution/fill, or advanced statistical/Gyroscope authority surfaces.
