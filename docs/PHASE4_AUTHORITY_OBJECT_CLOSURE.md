# FRACTAL-FLOW Phase 4 — Authority-Object Closure

## Scope

This narrow remediation closes the second-order authority-construction flaw identified by the independent hostile audit. The prior `make_decision()` validation boundary remains intact; this pass prevents the resulting `TradeDecisionV4` value object from being mistaken for authority merely because its public dataclass fields look valid.

## Defect closed

Before this pass, `TradeDecisionV4` was a frozen public dataclass whose `authorized`/`phase4_ready` result could be derived from its fields without proving that the object had passed the authoritative `make_decision()` construction path. That created a second construction path around lifecycle, lineage, temporal and evidence checks.

## Remediation

1. `TradeDecisionV4` now verifies its canonical decision fingerprint during `__post_init__()`.
2. A direct constructor can create only a structurally valid, **non-authoritative** record.
3. `phase4_ready` requires an opaque module-local authority proof.
4. Only `make_decision()` can attach that proof, and only after the existing full authority validation completes.
5. `phase4_ready` rechecks the canonical fingerprint, preventing authority after object-level evidence mutation.
6. Forged `decision_id` values are rejected at object construction.

Python frozen dataclasses provide immutability semantics but do not make constructors private; therefore the design uses an explicit authority-bearing proof rather than relying on constructor visibility. Python's dataclass documentation confirms that generated constructors invoke `__post_init__()`, making constructor-time invariant enforcement appropriate here.

## Hostile tests

The dedicated hostile suite now verifies:

- direct valid-looking construction is non-authorizing;
- direct construction using an invalidated opportunity record is non-authorizing;
- direct construction with future evidence is non-authorizing;
- forged decision fingerprints are rejected;
- the canonical factory remains authoritative;
- the pre-existing Phase 4 attack matrix remains green.

## Verification

- Full pytest: **601 passed, 0 failed, 0 skipped**.
- Configured coverage: **88.83%**, above the 85% floor.
- Compileall: **PASS**.
- Dedicated hostile suite: **14 passed**.
- Ruff: **OWNER-APPROVED ENVIRONMENTAL EXCEPTION** — unavailable.
- Mypy: **OWNER-APPROVED ENVIRONMENTAL EXCEPTION** — unavailable.

## Boundary interpretation

The follow-on Phase 4 Assurance & Authority Integrity campaign is now implemented in `docs/PHASE4_ASSURANCE_AUTHORITY_CAMPAIGN.md`. It adds deterministic replay, stateful differential testing, targeted semantic mutation testing, a least-privilege capability boundary, account-context non-interference checks, and monotonic authority/revocation checks.

## Final status

**Authority-object closure: GREEN.**

**Phase 4 assurance & authority-integrity campaign: GREEN.**

This does not promote Phase 4 into broker/execution authority. Phase 5 Risk, Portfolio, News Shield, broker execution/fill, and advanced statistical/Gyroscope authority remain deferred.
