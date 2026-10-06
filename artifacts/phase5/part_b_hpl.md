# FRACTAL-FLOW — Phase 5 Part B HPL

## Canonical implementation gate reconciliation — 2026-10-06

> **HISTORICAL / SUPERSEDED:** Earlier working-tree evidence reported 725 passed / 89.43% coverage. Those values are retained only for provenance and are not current verification results.

> **CANONICAL CURRENT VERIFICATION:** The current final-gate baseline is the exact command/result recorded in the final verification section below.


| ID | Capability / Requirement | Current State | Intended State | Gap | Implementation | Verification | Risk | Authority | Status |
|---|---|---|---|---|---|---|---|---|---|
| B-01 | News state machine | Explicit deterministic state machine | Canonical NewsState lifecycle | None identified | `domain/news_shield.py` | News suite + spec parity | Low | News | 🟢 VERIFIED CLOSED |
| B-02 | Scheduled vs observed news | Separate event/observation stores | Never conflate calendar with shock | None | Separate `NewsEvent` / `NewsObservation` | invariant 21 + adversarial | Low | News | 🟢 VERIFIED CLOSED |
| B-03 | Unknown shock lockdown | Unknown SHOCK/EXTREME enters extended protection | Fail closed on unannounced shock | None identified | `observe()` protective path | News/adversarial suite | Low | News | 🟢 VERIFIED CLOSED |
| B-04 | Post-news validation | Explicit normalization checkpoint; no automatic restart | Validation required before re-entry | None | `validate_normalization()` | invariant 22 + replay campaign | Low | News | 🟢 VERIFIED CLOSED |
| B-05 | Account feasibility | Typed fresh feasibility result | Feasibility before sizing | None | `AccountFeasibilityEngine` | invariant 38 + integration | Low | Feasibility | 🟢 VERIFIED CLOSED |
| B-06 | Fixed fractional risk | Decimal fixed-fraction allocation | Deterministic allocation | None identified | `RiskEngine.size()` | risk suite + real campaign | Low | Risk | 🟢 VERIFIED CLOSED |
| B-07 | Hard risk caps | Per-trade/open/daily/drawdown/trade-count caps | Cannot exceed configured limits | None identified | `RiskConfig` + allocation clamps | risk/adversarial suite | Low | Risk | 🟢 VERIFIED CLOSED |
| B-08 | Risk throttles | Drawdown, news, portfolio and cooldown throttles | Throttles only reduce risk | None identified | Decimal multipliers + `cooldown_until` | risk suite | Low | Risk | 🟢 VERIFIED CLOSED |
| B-09 | Currency exposure | Deterministic signed currency vector | Aggregate currency limits | None identified | `PortfolioArbitrator._vector()` | portfolio suite | Low | Portfolio | 🟢 VERIFIED CLOSED |
| B-10 | Correlation exposure | Correlation-aware risk cap with finite/bounded input validation | No malformed correlation bypass | None | `_correlated_risk()` + input validation | portfolio/adversarial suite | Low | Portfolio | 🟢 VERIFIED CLOSED |
| B-11 | Portfolio arbitration | Deterministic rank + ALLOW/DEFER/MERGE/REJECT | Aggregate exposure authority | None identified | `PortfolioArbitrator` | portfolio suite + adversarial campaign | Low | Portfolio | 🟢 VERIFIED CLOSED |
| B-12 | Flip protection | Opposite direction requires independent structural reversal evidence | No immediate loss-to-opposite flip | None | `StructuralReversalEvidence` | invariant 28 + adversarial | Low | Portfolio | 🟢 VERIFIED CLOSED |
| B-13 | Group caps | Hard pre-exposure group risk cap | Cap checked before authorization | None | `LanePipeline` | lane suite + composition | Low | Group | 🟢 VERIFIED CLOSED |
| B-14 | LanePipeline | Deterministic lane risk/count arbitration | Lane/group controls precede authorization | None | `LanePipeline` | lane suite + composition | Low | Lane | 🟢 VERIFIED CLOSED |
| B-15 | Durable Part-B decision state | Append-only event journal for authoritative outcomes; News state snapshot/recovery | Restartable/replayable protective/allocation evidence | Risk state itself is stateless/pure and reconstructed from inputs; journal records outcomes | `persistence/part5.py` + pipeline journal hook | journal roundtrip/idempotency + complete-outcome context/replay tests + News replay | Low | Persistence | 🟢 VERIFIED CLOSED for Part-B state/evidence boundary |
| B-16 | Authority registry | News/Risk/Portfolio authorities explicitly registered | No silent cross-authority capability | None identified | `authority.py`, `spec/engines.yaml` | invariant relevance/parity | Low | Authority | 🟢 VERIFIED CLOSED |
| B-17 | Decimal-only Part-B boundary | Part-B risk/news/portfolio/lane surfaces use Decimal | No float arithmetic in Part-B authority path | Legacy MURG resource surfaces remain outside Part-B authority | Part-B typed models + Decimal arithmetic | source review + full regression | Low | Risk/Portfolio | 🟢 VERIFIED CLOSED for Part-B boundary; legacy MURG explicitly out of scope |
| B-18 | Causal/no-lookahead | Calendar/observation timestamps cannot be from the future relative to evaluation | Future evidence must fail closed | None identified | `NEWS_FUTURE_CALENDAR` / `NEWS_FUTURE_OBSERVATION` guards | causal/news tests | Low | News | 🟢 VERIFIED CLOSED |
| B-19 | Restart equivalence | News snapshot hash equivalence + journal replay; stateless Risk/Portfolio recompute deterministically | Same evidence prefix => same semantic result | No unresolved Part-B semantic mismatch identified | Snapshot/replay + pure engines + journal | News replay + journal tests + current canonical regression | Low | Recovery | 🟢 VERIFIED CLOSED for implemented Part-B state boundary |
| B-20 | Adversarial campaign | Real Phase3 candidates exercised against protective failure scenarios | Fail closed under hostile inputs | None identified within declared campaign | Adversarial worker | 72/72 scenario evaluations; zero unexpected | Low | All protective authorities | 🟢 VERIFIED CLOSED |

## Acceptance-scale evidence

Independent range-isolated runtime logs reconcile to exactly 100 unique seeds `0..99`, each with 10,000 M1 bars and 13,206 causal events. Aggregate: 1,000,000 M1 bars, 1,320,600 causal events, 53,862 Phase3 candidates, 100,002 ALLOW outcomes across three accounts, 61,584 blocked outcomes, zero unexpected worker failures. Zero-candidate seeds are treated as legitimate population behavior; the population contains candidates and all seeds completed successfully.

HISTORICAL / SUPERSEDED — the earlier working-tree non-stress gate reported 725 passed / 89.43% coverage. The current canonical result is recorded below.

Environmental exceptions remain unchanged and are not claimed as passes: Ruff unavailable, mypy unavailable, Git metadata absent from the working artifact.

## Final hardening HPL — 2026-10-06

| ID | Requirement | Gap | Implementation target | Verification | Status |
|---|---|---|---|---|---|
| H-01 | PortfolioCandidate exposure contract | `notional=None` could construct and later raise raw `TypeError` | Make `notional` mandatory and validate at domain boundary | Hostile missing/invalid notional tests + portfolio suite | 🟢 CLOSED after gate |
| H-02 | Complete authoritative outcome context | Some REJECT records lacked full reconstruction context | Persist canonical input context for every authoritative outcome, plus outcome metadata | Journal replay/context fingerprint/restart tests | 🟢 CLOSED after gate |
| H-03 | Evidence canonicalization | Historical 725/89.43 values could look current | Label historical values superseded; maintain one canonical current result | Evidence/HPL consistency test | 🟢 CLOSED after gate |
| H-04 | R5 cumulative lifecycle | Full R5 pytest module could exceed bounded execution window | Disposable bounded causal worker with explicit timeout/cleanup | Full R5 module + bounded worker gate | 🟢 CLOSED after gate |
| H-05 | Final artifact integrity | Release artifact must match verified source exactly | Extract, verify, compare, then package | ZIP test + source/artifact equivalence | 🟢 CLOSED after gate |


## CANONICAL CURRENT VERIFICATION — FINAL HARDENING GATE — 2026-10-06

Earlier numerical results in this HPL are historical/superseded. The following is the sole current verification record.

- Compile: `python -m compileall -q src tests` — PASS
- Ordinary repository regression excluding explicitly isolated R5/R6 stress modules: **744 passed, 6 xfailed**
- Coverage-enabled ordinary regression: **89.51%**, above the 85% floor
- Final-hardening + Part-B authority/portfolio/news/persistence/invariant/hostile suites: **83 passed**
- Complete R5 module under bounded ordinary configuration: **13 passed**
- R5 causal worker stress partition: **30/30 trials passed** (partition 0 of 10; complete stress census shape remains exactly 300)
- Historical population-scale Part-B campaign: **100/100 seeds**, retained as historical semantic evidence
- Ruff: **UNVERIFIED — ENVIRONMENTAL EXCEPTION**
- mypy strict: **UNVERIFIED — ENVIRONMENTAL EXCEPTION**
- Git provenance: **UNVERIFIED — ENVIRONMENTAL EXCEPTION**

**🟢 FINAL GREEN — ARTIFACT MAY BE GENERATED**
