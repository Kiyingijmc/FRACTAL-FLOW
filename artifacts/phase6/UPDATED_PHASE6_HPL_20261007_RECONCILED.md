# FRACTAL-FLOW --- PHASE 6

# UPDATED FORENSIC HPL --- RECONCILED CANONICAL BASELINE

**Document:** `UPDATED_PHASE6_HPL_20261007_RECONCILED.md`\
**As-of:** 2026-10-07\
**Status:** CANONICAL GOVERNANCE DOCUMENT\
**Scope:** Phase 6 execution boundary, FFBP/1 transport, MT5
interoperability, authentication/session establishment, durable command
lifecycle, broker truth, reconciliation, protective authority, recovery,
TTL, and adversarial verification.\
**Codex:** OUT OF SCOPE\
**Live authorization:** NONE\
**Current final gate:** 🔴 **BLOCKED**

------------------------------------------------------------------------

## 0. Authority of this HPL

This HPL governs Phase 6 engineering work from the reconciled canonical
package.

It supersedes conflicting or stale Phase 6 process/status claims in
earlier handoffs and session snapshots where those claims are not
supported by the latest evidence.

The HPL is a **governance and evidence standard**, not a substitute for
runtime proof.

### Evidence precedence

When sources disagree, resolve them in this order:

1.  Current directly observed runtime evidence.
2.  Reproducible current-source tests and compile evidence.
3.  Current source inspection.
4.  Fixed-vector/interoperability evidence.
5.  Versioned specifications and canonical design documents.
6.  Historical handoffs, session notes, and claims.

A later document date does **not** automatically outrank earlier runtime
evidence.

------------------------------------------------------------------------

# 1. Governing principles

Phase 6 is governed by:

> **SURVIVAL \> CORRECTNESS \> AUDITABILITY \> DETERMINISM \> EXPLICIT
> AUTHORITY \> RECOVERY \> SECURITY \> PERFORMANCE \> PnL**

Additional constitutional principles remain binding:

-   No live trading until Phase 6 closure is genuinely proven.
-   No effectful execution under unresolved uncertainty.
-   No silent conversion of `UNKNOWN` into success.
-   No architecture change merely to bypass a local defect.
-   No security weakening for interoperability convenience.
-   No source claim is promoted to runtime verification without
    evidence.

------------------------------------------------------------------------

# 2. Non-negotiable evidence rules

1.  **Implemented ≠ Verified.**
2.  **Passing tests ≠ system closure.**
3.  **Local simulation ≠ MT5 terminal runtime proof.**
4.  **Fixed vectors ≠ live session interoperability.**
5.  Historical failures remain historical observations; they must not be
    mislabeled as current failures after source changes.
6.  Conversely, source changes must not be treated as successful runtime
    remediation without a post-change trace.
7.  Every material claim must have an explicit evidence status.
8.  `UNKNOWN` is a first-class durable state.
9.  No blind resend after uncertain dispatch.
10. `OrderSend()` / `OrderSendAsync()` is dispatch evidence, not
    broker-effect confirmation.
11. `OnTradeTransaction` is an observation/acceleration mechanism, not
    the durable broker authority.
12. Fresh broker snapshot/history/query evidence outranks local
    expectation or ACK.
13. Python's durable command identity/ledger remains the authoritative
    command record.
14. MT5 must not become a competing strategic or command authority.
15. No full secrets, MACs, session keys, or authenticated frames may be
    logged.
16. Environmental exceptions such as unavailable Ruff, mypy, or Git
    metadata are recorded as **UNVERIFIED / ENVIRONMENTAL EXCEPTION**,
    never as passed.
17. Tests, assertions, and specifications may not be weakened to obtain
    green output.
18. Canonical bytes, sequence semantics, bounds, versioning, and
    fail-closed behavior must remain deterministic.
19. `InpAllowReal=false` remains mandatory during Phase 6 verification.

### Accepted evidence statuses

Use only explicit statuses such as:

`OBSERVED | VERIFIED | IMPLEMENTED | PARTIAL | SPECIFIED | PROPOSED | UNVERIFIED | DEFERRED | BLOCKED | FAILED | INCORRECT | OUT OF SCOPE`

------------------------------------------------------------------------

# 3. Authority model

The authority chain is:

``` text
MARKET / BROKER OBSERVATIONS
        ↓
INFORMATIONAL AUTHORITY
        ↓
STRATEGY AUTHORITY
        ↓
RISK / PORTFOLIO AUTHORITY
        ↓
DURABLE EXECUTION INTENT
        ↓
EXECUTION AUTHORIZATION
        ↓
PYTHON DURABLE COMMAND LEDGER
        ↓
AUTHENTICATED FFBP/1 SESSION
        ↓
MT5 EXECUTION AUTHORITY
        ↓
BROKER EFFECT
        ↓
BROKER TRUTH / RECONCILIATION
        ↓
DURABLE RECOVERY STATE
```

Rules:

-   MT5 cannot invent strategy direction, size, entry thesis, or command
    intent.
-   Transport cannot manufacture strategy authority.
-   Broker adapters cannot manufacture intent.
-   Protective authority is separate from strategy authority.
-   Recovery/reconciliation can block new exposure without fabricating
    strategy decisions.
-   Broker truth outranks local assumptions.

------------------------------------------------------------------------

# 4. Canonical Phase 6 status

  ----------------------------------------------------------------------------------------
  ID                Requirement          Status            Evidence / blocker
  ----------------- -------------------- ----------------- -------------------------------
  P6-001            Preserve             🟢 VERIFIED       Existing Phase 5/R5 substrate
                    execution/recovery                     retained
                    substrate                              

  P6-002            Durable execution    🟢 VERIFIED       Existing durable
                    intent substrate                       repository/ledger

  P6-003            Recovery authority   🟢 VERIFIED       Existing recovery evidence

  P6-004            Single command       🟢 VERIFIED       Python durable ledger is
                    authority                              authoritative

  P6-010            Canonical account    🟢 FOCUSED        Python-side evidence
                    context              VERIFIED          

  P6-011            Canonical order      🟢 FOCUSED        Python-side evidence; live
                    model                VERIFIED          broker pending

  P6-012            Canonical deal model 🟢 FOCUSED        Python-side evidence; live
                                         VERIFIED          broker pending

  P6-013            Canonical position   🟢 FOCUSED        Model/tests present;
                    model                VERIFIED          netting/hedging runtime pending

  P6-014            Observation          🟢 FOCUSED        Python model/tests
                    provenance           VERIFIED          

  P6-015            Reconciliation       🟢 FOCUSED        Python model/tests
                    result contract      VERIFIED          

  P6-016            Event-order          🔴 OPEN           Adversarial permutation
                    independence                           campaign pending

  P6-020            Deterministic FFBP/1 🟢 FOCUSED        Python protocol tests
                    envelope             VERIFIED          

  P6-021            Canonical UTF-8 JSON 🟢 VECTOR         Fixed vectors pass; current MT5
                                         VERIFIED / 🟠     live boundary not re-proven
                                         LIVE UNVERIFIED   

  P6-022            4-byte BE framing    🟠 IMPLEMENTED /  TCP path historically observed;
                                         🟠 LIVE           current source requires rerun
                                         UNVERIFIED        

  P6-023            Exact read/write +   🟠 IMPLEMENTED /  Python-side evidence; current
                    size bounds          🟠 LIVE           MT5 boundary pending
                                         UNVERIFIED        

  P6-024            Malformed JSON       🟢 FOCUSED        Negative tests
                    rejection            VERIFIED          

  P6-025            Protocol versioning  🟠 SPECIFIED /    Runtime interoperability
                                         IMPLEMENTED       pending

  P6-030            Challenge/auth       🟠 CRYPTO/VECTOR  Live handshake has not been
                    handshake            VERIFIED / 🔴     re-proven after source overlay
                                         LIVE BLOCKED      

  P6-031            HKDF directional     🟢 FIXED-VECTOR   Exact deterministic vectors
                    keys                 VERIFIED          match

  P6-032            Challenge proof      🟢 FIXED-VECTOR   Exact deterministic proof
                                         VERIFIED          vector matches

  P6-033            Session-key          🟠 IMPLEMENTED /  Requires live authenticated
                    installation         🔴 LIVE           session
                                         UNVERIFIED        

  P6-034            Post-session         🟠 IMPLEMENTED /  Requires live session
                    directional HMAC     🔴 LIVE           
                                         UNVERIFIED        

  P6-040            Stable command       🟢 FOCUSED        `(account_id, command_id)`
                    identity             VERIFIED          

  P6-041            Fingerprint conflict 🟢 FOCUSED        Conflict tests
                                         VERIFIED          

  P6-042            Durable command      🟢 FOCUSED        SQLite ledger tests
                    lifecycle            VERIFIED          

  P6-043            MT5 command          🔴 OPEN           Runtime command path not yet
                    correlation                            closed

  P6-044            Durable UNKNOWN      🟢 FOCUSED        Ledger tests
                                         VERIFIED          

  P6-045            No blind resend      🟢 FOCUSED        Negative transition tests
                                         VERIFIED          

  P6-046            Partial fill         🟢 FOCUSED        Normalized model; live
                    semantics            VERIFIED          integration pending

  P6-047            Expiry enforcement   🔴 OPEN           Automatic enforcement pending

  P6-050            MT5 transaction      🔴 OPEN           Runtime implementation pending
                    observation queue                      

  P6-051            Broker snapshot sync 🔴 OPEN           Runtime implementation pending

  P6-052            Broker history sync  🔴 OPEN           Runtime implementation pending

  P6-053            Sequence-gap         🔴 OPEN           Runtime implementation pending
                    recovery                               

  P6-054            Broker-query         🔴 OPEN           Runtime implementation pending
                    authority                              

  P6-055            Orphan handling      🔴 OPEN           Runtime implementation pending

  P6-060            Protective authority 🔴 OPEN           Runtime implementation pending
                    separation                             

  P6-061            Protective-state     🔴 OPEN           Runtime implementation pending
                    confirmation                           

  P6-062            Python outage        🔴 OPEN           Runtime implementation pending
                    protection                             
                    continuity                             

  P6-063            TTL/dead-man         🔴 OPEN           Runtime implementation pending
                    enforcement                            

  P6-064            Protective           🔴 OPEN           Runtime implementation pending
                    uncertainty                            

  P6-065            Strategy re-enable   🔴 OPEN           Runtime implementation pending
                    gate                                   

  P6-070            Startup              🔴 OPEN           Runtime implementation pending
                    reconciliation                         

  P6-071            Replay equivalence   🔴 OPEN           Restart/adversarial campaign
                                                           pending

  P6-072            Crash-tail handling  🔴 OPEN           Injected crash campaign pending

  P6-073            Corruption handling  🔴 OPEN           Corruption campaign pending

  P6-074            Version              🔴 OPEN           Compatibility campaign pending
                    compatibility                          

  P6-080            Malformed/oversize   🟢 FOCUSED        Python negative tests
                    rejection            VERIFIED          

  P6-081            Secret/log hygiene   🔴 OPEN           Final artifact/log audit
                                                           required

  P6-090            Current MT5 source   🟠 UNVERIFIED     Reconciled MQL5 source changed;
                    compilation                            current MetaEditor proof
                                                           required

  P6-091            Current-source MT5   🟠 UNVERIFIED     Historical/later vector claim
                    fixed vectors                          exists; current reconciled
                                                           source must reproduce it

  P6-092            Current MT5 socket   🟠 HISTORICALLY   Prior TCP trace exists; current
                    connectivity         OBSERVED / RERUN  source not rerun
                                         REQUIRED          

  P6-093            Current MT5 HELLO    🟠 HISTORICALLY   Prior HELLO trace exists;
                    reaches Python       OBSERVED / RERUN  current source not rerun
                                         REQUIRED          

  P6-094            Python decodes       🟠 UNVERIFIED --- Prior trace failed at
                    current MT5 HELLO    LAST HISTORICAL   `JSONDecodeError: Extra data`
                                         FAILURE WAS JSON  char 467; post-overlay runtime
                                         DECODE            proof absent

  P6-095            Live HMAC/auth       ⏳ NOT REACHED    Depends on current-source HELLO
                                                           decode

  P6-096            Live session         ⏳ NOT REACHED    Depends on live auth
                    establishment                          

  P6-097            Live broker          🔴 BLOCKED        Earlier runtime prerequisites
                    reconciliation                         unresolved

  P6-098            Effectful execution  🔒 LOCKED         Prohibited until all gates are
                                                           green

  P6-099            Phase 6 final        🔴 BLOCKED        Multiple open/unverified
                    closure                                prerequisites
  ----------------------------------------------------------------------------------------

------------------------------------------------------------------------

# 5. Critical forensic distinction: historical failure vs current state

The last preserved runtime trace contained:

``` text
TCP connection established
HELLO sent
Python accepted connection
JSONDecodeError: Extra data: line 1 column 468 (char 467)
```

This is **historical runtime evidence**.

A later source overlay contains framing-related remediation. Because no
post-overlay MT5 trace is present, the correct canonical statement is:

``` text
LAST OBSERVED RUNTIME FAILURE
    = JSON decoder Extra data at char 467

CURRENT SOURCE
    = contains framing remediation

POST-REMEDIATION RUNTIME
    = UNVERIFIED

CURRENT GATE
    = BLOCKED pending current-source runtime observation
```

Do **not** write:

> "The JSON framing bug is still present."

unless the current source is rerun and reproduces it.

Do **not** write:

> "The JSON framing bug is fixed."

unless the current source is rerun and the wire evidence proves it.

------------------------------------------------------------------------

# 6. Immediate proving gate

## Gate P6-WIRE-01 --- current-source MT5 → Python frame proof

Before changing cryptography, transport architecture, command execution,
or broker integration:

1.  Compile the reconciled MQL5 source in MetaEditor.
2.  Run the actual EA against the existing Python smoke server.
3.  Capture bounded raw-frame diagnostics immediately after
    `recv_frame()` and before JSON decoding.
4.  Do not print secrets or full authenticated frames.

Required diagnostics:

``` text
FRAME_TOTAL
DECLARED
PAYLOAD_LEN
TAIL_HEX
TAIL_REPR
```

Optional additional bounded diagnostic:

``` text
FIRST_16_HEX
```

Only if necessary to prove a framing offset.

### Classification

**A --- Declared length differs from actual payload length**

→ investigate framing/read/write boundary.

**B --- Exact payload terminates with `00`**

→ investigate sender serialization/trailing-NUL handling.

**C --- Payload is valid JSON followed by additional bytes**

→ investigate sender envelope assembly or framing.

**D --- Payload is clean JSON but decoder still fails**

→ investigate receiver accumulation/decoder logic.

**E --- HELLO decodes successfully**

→ advance to CHALLENGE/AUTH/session establishment; do not redesign
crypto without a new failure.

------------------------------------------------------------------------

# 7. Crypto gate

The current evidence does **not** justify an HKDF rewrite.

Fixed-vector evidence establishes that the deterministic cryptographic
construction has previously matched expected values.

However, live interoperability requires:

1.  current-source compilation;
2.  current-source vector reproduction;
3.  live CHALLENGE receipt;
4.  live AUTH transcript reproduction;
5.  live HMAC verification;
6.  directional session-key derivation;
7.  post-session directional message verification.

Therefore:

> **Do not modify HKDF/HMAC solely because the live session has not yet
> been proven.**

If a live failure reaches the cryptographic layer, instrument bounded
intermediate fingerprints---not secrets---and prove the **first
byte-level divergence** before changing the implementation.

------------------------------------------------------------------------

# 8. Required change discipline

Every implementation change must answer:

1.  What invariant does it protect?
2.  Which authority owns the behavior?
3.  What exact failure mode does it address?
4.  What existing behavior could it alter?
5.  What deterministic test proves it?
6.  What runtime evidence is required?
7.  What recovery/restart behavior changes?
8.  Which documents/manifests/evidence records must be updated?

The preferred remediation sequence is:

``` text
REPRODUCE
  ↓
BOUND THE FAILURE
  ↓
IDENTIFY FIRST DIVERGENCE
  ↓
PATCH RESPONSIBLE LAYER
  ↓
ADD REGRESSION TEST
  ↓
RUN FOCUSED TESTS
  ↓
RUN CURRENT CROSS-LANGUAGE RUNTIME TEST
  ↓
REASSESS HPL
```

------------------------------------------------------------------------

# 9. Forbidden shortcuts

The following are prohibited:

-   speculative protocol rewrites;
-   HKDF redesign without byte-level evidence;
-   ZMQ migration to avoid a TCP defect;
-   replacing the existing durable ledger with a parallel authority;
-   hidden retries;
-   blind resend after UNKNOWN;
-   weakening authentication or frame validation;
-   removing assertions/tests to obtain green output;
-   changing acceptance criteria to fit current behavior;
-   enabling effectful COMMAND before closure;
-   enabling live trading;
-   treating broker ACK as broker truth;
-   treating unit tests as live broker proof;
-   treating source recency as runtime proof;
-   generating a "final" Phase 6 artifact while mandatory gates remain
    unresolved.

------------------------------------------------------------------------

# 10. Runtime safety requirements

Until final closure:

-   `InpAllowReal=false`.
-   Effectful COMMAND path remains locked.
-   No new broker exposure may be authorized.
-   Protective behavior, where applicable, must remain fail-closed.
-   UNKNOWN remains durable.
-   Recovery requires reconciliation before strategic re-enable.
-   No strategic authority may be restored merely because a process
    restarted successfully.

------------------------------------------------------------------------

# 11. Verification matrix

A Phase 6 claim is not closed until the corresponding evidence class
exists.

  Evidence class                          Required
  --------------------------------------- ----------
  Source inspection                       Yes
  Deterministic unit tests                Yes
  Negative/adversarial tests              Yes
  Current MQL5 compilation                Yes
  Current MT5 fixed-vector reproduction   Yes
  Current MT5→Python wire proof           Yes
  Live authentication/session proof       Yes
  Durable command lifecycle proof         Yes
  Broker truth/reconciliation proof       Yes
  Protective continuity proof             Yes
  Restart/crash/corruption proof          Yes
  Sequence-gap/orphan proof               Yes
  Resource/timeout/oversize proof         Yes
  Secret/log hygiene audit                Yes
  Final artifact provenance               Yes

A missing required evidence class is a blocker or explicit environmental
exception only where the governing gate permits that exception.

------------------------------------------------------------------------

# 12. Current canonical next step

**STOP before further architectural or cryptographic changes.**

The next action is:

> **Run the reconciled MQL5 source against the existing Python smoke
> server and obtain bounded wire-level evidence for the current HELLO
> frame.**

The result determines whether the investigation:

-   remains at framing;
-   advances to JSON decoding;
-   advances to CHALLENGE/AUTH;
-   or, only if reached, enters live session-key interoperability.

No later-stage defect may be inferred before the earlier boundary is
proven.

------------------------------------------------------------------------

# 13. Final closure standard

Phase 6 may only be declared:

``` text
🟢 FINAL GREEN — ARTIFACT MAY BE GENERATED
```

when all mandatory gates are supported by current evidence.

Otherwise the only valid status is:

``` text
🔴 FINAL GATE BLOCKED — DO NOT GENERATE FINAL PHASE 6 ARTIFACT
```

Current status:

> **🔴 FINAL GATE BLOCKED --- CURRENT MT5 INTEROPERABILITY IS
> UNVERIFIED.**
