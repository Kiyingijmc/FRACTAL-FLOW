# FRACTAL-FLOW Volume Profile G3b — Canonical Persistence HPL (V4)

**Status:** Reconciled proof record; local verification is complete and owner review is pending.
**Authority:** VP output remains `ANALYTICAL_ONLY`.
**Rule:** Every PASS requires an identified test, observed output, and artifact/revision provenance. Environmental non-runs are `UNVERIFIED`, not PASS.

| ID | Hostile condition / proof obligation | Required evidence | Status |
|---|---|---|---|
| VP-P01 | Canonical Event round-trip preserves every required envelope field | Codec round-trip equality | PASS |
| VP-P02 | Canonical payload bytes are stable across process, timezone, and hash seed | Multi-process canonical digest test | PASS |
| VP-P03 | Decimal price/weight do not pass through binary float | Hostile Decimal precision test | PASS |
| VP-P04 | `available_at_ns` retains exact nanosecond value | Encode/decode exact integer equality | PASS |
| VP-P05 | Envelope timestamps use the repository's seconds convention | Boundary conversion tests and source-linked assertion | PASS |
| VP-P06 | Nanosecond floor conversion never controls causal visibility | Adjacent-nanosecond watermark tests | PASS |
| VP-P07 | Event IDs are deterministic, namespaced, and collision-safe | Scope/revision collision tests | PASS |
| VP-P08 | Same revision ID with changed payload fails closed | Identity conflict test | PASS |
| VP-P09 | Exact duplicate retry is idempotent and does not append twice | Sequence/count unchanged on retry | PASS |
| VP-P10 | Generic journal duplicate-ID guard remains active | Direct duplicate append rejection test | PASS |
| VP-P11 | Aggregate version is derived from durable history and increments exactly one | Version sequence and recovery tests | PASS |
| VP-P12 | Caller cannot select an arbitrary aggregate version | API/input hostile test | PASS |
| VP-P13 | Stale predecessor is rejected, not silently rebased | Stale-writer test | PASS |
| VP-P14 | Fork attempts are rejected before durable append | Two submissions from same head | PASS |
| VP-P15 | Single-process chain lock serializes append transaction | Concurrent threads race test | PASS |
| VP-P16 | Cross-process writer limitation is explicit and enforced/documented | Guard/architecture test or deployment contract | PASS |
| VP-P17 | UPSERT → correction → CANCEL → UPSERT reactivation replays identically | State-machine sequence test | PASS |
| VP-P18 | Root CANCEL and repeated CANCEL fail closed under frozen policy | Invalid operation-state tests | PASS |
| VP-P19 | CANCEL never fabricates an active observation | Payload contract and output inactivity tests | PASS |
| VP-P20 | Future revision cannot affect an earlier watermark | Causal leakage test at adjacent boundaries | PASS |
| VP-P21 | Corrupt future record cannot be hidden by earlier watermark | Full-history validation test | PASS |
| VP-P22 | Availability decreases along predecessor chain are rejected | Temporal inversion test | PASS |
| VP-P23 | Missing predecessor, cycle, fork, disconnected chain fail closed | Graph corruption tests | PASS |
| VP-P24 | Journal checksum corruption fails closed | Tamper/corrupt-record recovery test | PASS |
| VP-P25 | Established incomplete-tail recovery behavior is preserved | Crash-tail fixture/reopen test | PASS |
| VP-P26 | Failed append does not publish in-memory state | Injected append failure | PASS |
| VP-P27 | Failure after durable append requires replay before more writes | Post-append fault injection | PASS |
| VP-P28 | Restart rebuilds all VP revisions exclusively from journal | Close/reopen/reconstruct test | PASS |
| VP-P29 | Fresh replay and recovered replay match every observable | Deep equality incl. fingerprint, quality, reasons, provenance | PASS |
| VP-P30 | No VP checkpoint is required for correctness in Unit 1–4 | Replay test with no snapshot | PASS |
| VP-P31 | Phase 2 and generic journal contracts are unchanged | Regression tests and diff scope review | PASS |
| VP-P32 | No authority escalation reaches risk/execution/order/broker | Static boundary audit and negative tests | PASS |
| VP-P33 | Repository user changes and untracked artifacts are preserved | Before/after status and artifact checksums | PASS |
| VP-P34 | Full relevant regression suite passes | Captured commands, counts, exit codes | PASS |
| VP-P35 | Ruff/mypy results are reported accurately | Tool availability and exit codes; otherwise UNVERIFIED | PASS |

## Decision register

| Decision | V4 proposal | Approval/evidence status |
|---|---|---|
| Canonical Event timestamp unit | Seconds in envelope; exact nanoseconds remain in payload | Source convention supported; adapter tests still required |
| Causal visibility | `available_at_ns <= watermark_ns`, inclusive | Contract proposal; test required |
| Event identity | Deterministic namespaced identity from canonical chain scope + revision ID | Proposal |
| Retry | Exact existing canonical record = idempotent no-op; conflict = fail closed | Proposal |
| CANCEL | Must follow active UPSERT state; no root/repeated cancel; never embeds an active observation | Proposal |
| Concurrency | Single writer per process for initial slice; cross-process unsupported without atomic durable coordination | Proposal |
| History validation | Validate full durable history before watermark filtering | Proposal |
| Checkpoint | Omit from initial durable slice; journal is authority | Consistent with existing recovery pattern; integration tests required |

## Closure rules

- No HPL row is PASS without actual evidence.
- Any unrun, unavailable, or environment-blocked check remains NOT RUN/UNVERIFIED.
- Any failed obligation blocks closure.
- A clean focused test run does not imply full suite, lint, typing, cross-process safety, or runtime closure.
- This HPL is a plan, not a declaration that the implementation is complete.

## 2026-11-07 forensic reconciliation disposition

**Provenance:** baseline `695650298a3d6639230407381d29c0017611eb12`; local branch
`reconcile/vp-g3b-unit1-20261107`; candidate file digests are recorded in
`evidence/vp-g3b-reconciliation-20261107T090207Z/candidate-sha256.txt`.
The original kit ZIP passed `unzip -t`, and every listed kit member passed
`SHA256SUMS` validation. The mandatory gate logs are in
`evidence/vp-g3b-reconciliation-20261107T090207Z/`. A later rerun after the
additional HPL tests is recorded in the most recent sibling reconciliation
evidence directory.

| ID | Disposition | Evidence and observed result |
|---|---|---|
| VP-P01 | PASS | Codec round-trip tests passed; decoded revision equals encoded revision. |
| VP-P02 | PASS | Cross-process fingerprint test runs with `PYTHONHASHSEED=1` and `8675309` plus two timezones; fingerprints match. |
| VP-P03 | PASS | Decimal canonicalization and exact mixed-scale aggregation tests passed without binary-float conversion. |
| VP-P04 | PASS | Nanosecond round-trip test passed; payload preserved `2_500_000_001` and `2_500_000_999` exactly. |
| VP-P05 | PASS | Envelope-boundary test passed: source/event/processing seconds floor to `2` while payload retains exact nanoseconds. |
| VP-P06 | PASS | Adjacent-watermark test passed: revision at `11ns` is invisible at `10ns` and visible at `11ns`. |
| VP-P07 | PASS | Stable-ID scope test passed: same scope is deterministic; same revision ID in another logical scope changes event and aggregate IDs. |
| VP-P08 | PASS | Changed payload for an existing revision ID raises `ProfilePersistenceConflict`; conflicting durable identity is rejected. |
| VP-P09 | PASS | Exact retry returns the original record and journal count remains unchanged. |
| VP-P10 | PASS | `test_journal_duplicate_event_id_append_rejection` and restart/conflict variants passed in `persistence_adversarial` (47 passed). |
| VP-P11 | PASS | Durable-derived sequence test observed aggregate versions `(1, 2)` and recovery retained two records. |
| VP-P12 | PASS | Persistence API derives aggregate version internally; the durable-chain version test passed. |
| VP-P13 | PASS | Stale/regressing predecessor submission is rejected before journal mutation. |
| VP-P14 | PASS | Competing successor test passed: exactly one successor append succeeds. |
| VP-P15 | PASS | Threaded adapter race test passed with one process-local chain lock, one winner, and two durable records including root. |
| VP-P16 | PASS | `VolumeProfilePersistence` explicitly documents one writer per process and no cross-process compare-and-append claim; no unsupported atomicity claim is made. |
| VP-P17 | PASS | UPSERT → CANCEL → UPSERT reactivation and recovered replay equality passed. |
| VP-P18 | PASS | Root/repeated invalid CANCEL lifecycle paths are rejected by revision and persistence tests. |
| VP-P19 | PASS | CANCEL carries no observation; resolution exposes no active observation until a valid later UPSERT. |
| VP-P20 | PASS | Future correction is absent before its watermark and appears only at its exact availability boundary. |
| VP-P21 | PASS | Checksum-valid but canonically corrupt future revision causes recovery failure before any watermark query. |
| VP-P22 | PASS | Availability regression is rejected before journal mutation and on full-history recovery. |
| VP-P23 | PASS | Missing predecessor, cycle, fork, cross-logical predecessor, and disconnected chain tests passed. |
| VP-P24 | PASS | Candidate corrupt-journal test and generic journal corruption tests passed fail-closed. |
| VP-P25 | PASS | Generic incomplete-tail recovery matrix passed in `persistence_adversarial`; VP recovery uses tail truncation disabled. |
| VP-P26 | PASS | Injected `BEFORE_JOURNAL_WRITE` failure leaves zero VP records, faults the adapter, and a fresh adapter resolves no active state. |
| VP-P27 | PASS | Injected post-fsync failure faults the stale adapter; fresh recovery recognizes the durable event and permits only recovered state. |
| VP-P28 | PASS | Close/reopen VP adapter reconstructs durable revisions exclusively from its journal. |
| VP-P29 | PASS | Fresh and recovered resolutions compare equal after UPSERT/CANCEL/reactivation. |
| VP-P30 | PASS | VP recovery tests reconstruct from journal only; no VP checkpoint/snapshot interface exists or is required. |
| VP-P31 | PASS | No generic journal or Phase 2 source was modified; Phase 1 crash points (3 passed), Phase 2 durable suite (13 passed), and staged scope review passed. |
| VP-P32 | PASS | Codec rejects authority/account tampering; static review confirms VP source remains `ANALYTICAL_ONLY` and has no risk/order/execution imports. |
| VP-P33 | PASS | Before/after status logs preserve the six original in-scope untracked candidate paths; generated evidence remains unstaged. |
| VP-P34 | PASS | Required matrix passed: focused and complete candidate suites, Ruff, strict mypy, compileall, persistence adversarial, Phase 1, Phase 2, and whitespace checks. |
| VP-P35 | PASS | Preflight observed Python 3.12.3, Ruff 0.16.10, and mypy 2.4.0; verification logged zero exits. |

### Reconciliation note

The external candidate patcher used a regex whose final function replacement
consumed the immediately following `@dataclass` decorator. Focused tests caught
the resulting `PriceGrid() takes no arguments` failure. The candidate source was
minimally repaired, the kit backup/manifest was retained under
`evidence/vp-g3b-patch-20261107T090100Z/`, and all gates were rerun. This is a
kit-safety finding, not a generic journal or Phase 2 contract change.
