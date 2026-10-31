# FRACTAL-FLOW Backtesting Engine — B1 Authority and Interface Contract Map

**Status:** DRAFT / candidate-worktree contract freeze
**Work order:** B1 — Freeze authority and interfaces
**Target worktree:** `$HOME/projects/FractalFlow-backtester`
**Expected branch/base:** `work/backtester` / `719633433bebcf5b78b4dc31af93888e4325a66c`
**Disposition:** CONDITIONAL for continued isolated work; BLOCKED for canonical integration/release

## 1. Evidence and limits

The isolated candidate full test suite completed with **898 passed, 6 xfailed**, **89.27% coverage**, and pytest exit code **0**. This is candidate regression evidence only. It does not establish canonical strategy integration, production authority compatibility, durable crash recovery, broker behavior, or profitability.

The architecture requires reuse of existing FRACTAL-FLOW engines rather than a parallel strategy implementation, and simulation must never be treated as broker truth. The requirements traceability marks canonical strategy/gate integration, authority mapping, complete execution lifecycle, accounting, and durable recovery as incomplete or blocked.

This map is a contract proposal requiring source-level verification. A named module is not proof of authority ownership. Where an owner or adapter cannot be verified, status remains OPEN or BLOCKED.

## 2. Non-negotiable invariants

1. Simulation consumes canonical decisions and constraints; it is not a second production strategy, risk, portfolio, broker-truth, or execution authority.
2. Historical input is available only at its causal availability time. No future bar/tick or higher-timeframe value may influence an earlier decision.
3. Simulated events, fills, positions, and balances are labelled simulated and cannot be promoted to broker-confirmed truth.
4. Ambiguous outcomes remain `UNKNOWN` / reconciliation-required. Timeout, missing position, or absence of a matching observation is not proof of rejection.
5. Execution-relevant price, quantity, cash, fees, and PnL use Decimal/fixed-point semantics with explicit precision and rounding.
6. Account/lane/session/config identity is carried across intents, events, fills, positions, ledgers, reports, and recovery state where applicable.
7. Replay order, identifiers, seeds, serialization, and aggregation are deterministic; worker scheduling must not affect results.
8. Persistence or identity corruption fails closed: quarantine/reject recovery rather than manufacture state or authority.
9. Candidate test success is not canonical integration, remote CI, MT5, broker-runtime, or performance evidence.
10. No live execution, canonical repository mutation, staging, commit, push, merge, or deployment is authorized by this work order.

## 3. Authority and interface matrix

| Domain | Canonical owner required | Backtester consumer / boundary | Derived state allowed | Current status / proof needed |
|---|---|---|---|---|
| Strategy direction and setup family | Existing canonical strategy engines (Structure/Flow/Pullback/Regime/Opportunity as applicable) | Tier-2 adapter calls existing engines; no lookalike strategy function | Decision snapshots, candidate/rejection explanations | **BLOCKED** — canonical strategy adapters not integrated; identify exact call graph and contract |
| Multi-timeframe authority | Canonical MTF cascade and data-availability rules | Replay supplies only causally available timeframe state | Per-timeframe snapshots and migration events | **OPEN** — define availability, bar-close, synchronization and migration behavior |
| Decision/gate chain | Canonical eleven-gate chain (Q..X per architecture) | Record gate inputs/results and rejections without bypassing gates | Immutable decision/gate trace | **BLOCKED** — verify exact owner/schema; add gate-bypass negative tests |
| Risk authority | Canonical risk engine | Read-only request/decision adapter; simulation cannot authorize risk increases | Simulated risk observations and breach records | **BLOCKED** — canonical adapter and risk-limit invariants not proven |
| Portfolio allocation/exposure | Canonical portfolio/allocation authority | Consume allocation decisions; isolate each account/lane | Simulated balances and exposure attribution | **BLOCKED** — margin, concentration, correlation and portfolio integration absent |
| Exit/protective authority | Canonical exit rules, position policy, stop gate, protective authority | Consume authorized exit/stop updates; model market execution separately | Stop state and simulated exit intents | **OPEN** — verify precedence and missing/stale protective state behavior |
| Execution-intent ownership | Canonical intent/command contract; candidate ledger tracks simulation | Consume immutable intent identity and payload; namespace idempotency correctly | Simulated lifecycle events | **PARTIAL** — duplicate conflicting-payload, restart and namespace proofs required |
| Broker truth | Canonical broker-truth/reconciliation boundary, never the simulator | Simulator emits `SIMULATED` facts only | Simulated observations with provenance | **Integration unverified** — retain distinct truth provenance in event/report schemas |
| Order lifecycle | Typed candidate simulation lifecycle distinct from broker state | `ACCEPTED`, `PARTIALLY_FILLED`, `FILLED`, `REJECTED`, `CANCELED`, `EXPIRED`, `UNKNOWN/NEEDS_RECONCILIATION` | Deterministic transition ledger | **PARTIAL** — UNKNOWN fix exists; complete typed transition matrix remains open |
| Accounting/ledger | Explicit simulation accounting owner; production authority stays canonical | Apply fills/closes exactly once using Decimal and versioned assumptions | Open quantity, cash, realized/unrealized PnL, fees, equity | **PARTIAL** — latest regression tests pass; complete fees/FX/swap/margin reconciliation remains open |
| Market data/clock | Injected simulation clock and validated source; canonical feed defines production semantics | Ordered timestamped data with provenance | Replay clock and normalized events | **PARTIAL** — expand timezone/gap/MTF/tick semantics and malformed-data tests |
| Persistence/replay/recovery | Explicit versioned simulation journal/snapshot owner | Deterministic journal/checkpoint replay in simulation namespace | Reconstructible state and report | **BLOCKED** — report writer is not a durable replay journal; crash and restart-equivalence matrix absent |
| Identity/lane isolation | Canonical account/lane/session/config identity owners | Identity propagated through execution-relevant records | Per-lane isolated state and metrics | **PARTIAL** — two-account/two-lane collision and restart/recovery proof required |
| Configuration/version provenance | Versioned scenario, cost model, symbol map, timeframe/calendar and engine identity | Immutable run manifest/hash accompanies results | Reproducible config snapshot | **PARTIAL** — complete strategy/cost/data/code identity remains open |
| Research/report | Validation/reporting layer; no trading authority | Disclose splits, trials, costs, sample sizes, metrics and limitations | Research metrics with uncertainty/provenance | **PARTIAL** — leakage, multiple-testing and execution-fidelity gates remain open |

## 4. Interface freeze rules

Dependent implementation must not:
- add a second strategy or gate-chain implementation;
- create a risk/portfolio authority that can approve orders;
- treat simulator output as broker truth;
- introduce live broker adapters or live side effects;
- silently default unsupported spread, commission, slippage, financing, FX, margin or session constraints to zero/permissive values;
- retry an `UNKNOWN` intent as though it were rejected;
- share mutable state across accounts, lanes, workers or scenarios;
- infer ownership from a module name alone.

Allowed candidate-side interfaces are limited to read-only adapters to verified canonical owners, injected clock/data boundaries, simulated execution/accounting, typed immutable events, and versioned report/provenance contracts. If a required canonical owner is missing or ambiguous, stop dependent changes and mark them BLOCKED.

## 5. Required contract record for each adapter

Record before implementation:
- contract ID and schema version;
- canonical owner module/class/function and source line(s);
- caller/consumer and allowed call direction;
- immutable inputs and identity namespace;
- output type and provenance (`CANONICAL_DECISION`, `SIMULATED`, `OBSERVED_MARKET_DATA`, or `BROKER_CONFIRMED`);
- permitted side effects (default: none);
- clock/data availability semantics;
- error/timeout/UNKNOWN behavior;
- idempotency and conflicting-duplicate behavior;
- persistence/replay behavior;
- HPL IDs and positive/negative tests;
- evidence status: `PASS`, `PARTIAL`, `OPEN`, `BLOCKED`, `NOT RUN`, or `ENVIRONMENTAL EXCEPTION`.

## 6. HPL additions mapped to B1

| HPL ID | Hostile condition | Required invariant | Minimum evidence | Status |
|---|---|---|---|---|
| B1-AUTH-01 | Candidate strategy differs from canonical engine | One strategy authority | Adapter/call-graph review and parity fixture | OPEN |
| B1-AUTH-02 | Gate bypass or rejected candidate reaches execution | Gate chain remains authoritative | Negative test for each terminal rejection class | OPEN |
| B1-RISK-01 | Simulator approves an order denied by canonical risk | Canonical risk remains authoritative | Adapter contract and risk-denial propagation test | BLOCKED |
| B1-PORT-01 | Same symbol in two accounts is netted or state is shared | Account/lane isolation | Two-account/two-lane colliding-ID test | OPEN |
| B1-EXIT-01 | Protective authority is missing, stale or contradictory | Fail closed; do not loosen protection | Stale/missing authority tests | OPEN |
| B1-EXEC-01 | Timeout or absent position is interpreted as rejection | Preserve UNKNOWN pending reconciliation | Lifecycle and retry-block tests | PARTIAL |
| B1-EXEC-02 | Duplicate intent ID has a different payload | No conflicting replay/idempotency | Conflicting-payload test before/after restart | OPEN |
| B1-TRUTH-01 | Simulated fill is represented as broker-confirmed | Provenance separation | Schema and report negative test | OPEN |
| B1-ACC-01 | Partial fills/closes create or destroy open quantity | Quantity conservation | Decimal property/adversarial tests | PARTIAL |
| B1-PER-01 | Crash between state mutation and durable write | No invented recovered authority | Fault injection at persistence boundaries | BLOCKED |
| B1-ID-01 | Stale session/config/fencing identity is replayed | Reject stale/mismatched identity | Stale-identity matrix across events/recovery | OPEN |
| B1-DET-01 | Worker completion order changes report bytes | Deterministic result independent of scheduling | Clean-process 1-vs-N worker digest comparison | PARTIAL |
| B1-DATA-01 | Future bar or higher-timeframe value is exposed early | Causal data availability | Future-mutation invariance and MTF tests | OPEN |
| B1-REP-01 | Unsupported cost is silently treated as zero | Honest assumption disclosure | Report rejects absent mandatory assumptions | OPEN |

## 7. B1 acceptance gate

B1 can be marked **PASS (candidate contract freeze)** only after:
1. actual source call sites and canonical owner symbols are cited for every authority row;
2. adapter input/output schemas, identity requirements, side effects and failure behavior are explicit;
3. HPL IDs map to concrete tests or a named missing dependency;
4. no duplicate strategy/risk/broker-truth authority is introduced;
5. changes are restricted to reviewed documentation/tests or explicitly authorized adapters;
6. baseline, worktree status, hashes, `git diff --check`, and focused checks are recorded.

Until then, this is a **draft contract map**, not proof that B1 is closed.

## 8. Next bounded task

Perform read-only source mapping in the isolated worktree. Capture class/function names and line ranges for strategy/MTF flow, the eleven-gate chain, risk/portfolio, exit/protective authority, broker truth and intent ownership, accounting/persistence/recovery, and account/lane/session/config identity.

Update this map with exact references and tests. If canonical strategy/gate/risk/portfolio owners are not reachable from the candidate, keep ARC-006 / RSK-001 blocked; do not fake compatibility with an example strategy.
