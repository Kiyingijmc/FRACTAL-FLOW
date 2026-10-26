# Stage H.1.1.2 — Corrective Design & Architecture Contract

**Timestamp:** 2026-10-26T21:11:00Z  
**Standard:** Universal Forensic Engineering Protocol  
**Guiding Mandate:** Implement the smallest safe correction that completely closes verified gaps without scope creep.

---

## 1. Production Authorization Boundary Architecture

The lifecycle of an operator command transitions across strict authority layers:

```
[Operator Interaction (Hotkey / ContextPanel Button / Table Action)]
                           │
                           ▼
              [handleTriggerAction(action, pos)]
                           │
                           ▼
          [ConfirmDialog (Confirmation Modal)]
       (Renders parameters, idempotency key, title)
                           │
        [Confirm Button Click / Enter Keypress]
                           │
                           ▼
              [handleConfirmAction(simulateRejection)]
                           │
                           ▼
        ┌────────────────────────────────────────────────────────┐
        │  PRODUCTION AUTHORIZATION GATEWAY (App.tsx)            │
        │                                                        │
        │  validatePositionModification(                         │
        │    action, targetPosition, riskConfig, dailyPnl, pos   │
        │  )                                                     │
        └────────────────────────────────────────────────────────┘
                   /                                \
      (isAllowed === false)                   (isAllowed === true)
                 /                                    \
                ▼                                      ▼
    [FAIL-CLOSED INTERCEPTION]                 [INTENT PREPARATION]
    - Set activeCommand to REJECTED            - createIntentFingerprint(...)
    - Source: PRODUCTION_RISK_GATE             - Idempotency registration
    - Audit: REJECTED_FAIL_CLOSED              - Log REQUESTED event
    - SystemEvent: LEVEL 'CRIT'                - Mode Gate: Live blocked
    - Early return (ZERO DISPATCH)             - Dispatch to Provider
    - Provider untouched                               │
                                                       ▼
                                            [SimulationProvider.submit]
                                            - State mutation if CONFIRMED
                                            - Emit CONFIRMED progress
```

---

## 2. Asymmetric Risk Modification Policy

In accordance with survival requirements, position modifications are segregated into two distinct risk profiles:

1. **Protective / De-risking Mutations (`tighten_stop`, `move_to_breakeven`, `close_position`):**
   - De-risking actions unconditionally reduce or eliminate exposure.
   - They are **always allowed** (`isAllowed: true`), even during portfolio-wide risk invalidity or daily loss limit breaches.
   - An operator must never be locked into market risk because of upstream telemetry corruption.

2. **Risk-Increasing / Expansion Mutations (`add_size`, `scale_in`):**
   - Require **active valid portfolio risk** (`evaluatePortfolioRisk(positions).status === 'VALID'`).
   - If any open position lacks valid explicit allocated risk (missing, `NaN`, non-positive, infinite), portfolio status is `INVALID` and the mutation is rejected fail-closed.
   - Require that total portfolio exposure has not reached or exceeded `maxAccountExposureR`.
   - Require that daily loss limit is not breached (`currentDailyPnlUsd >= -dailyLossLimitUsd`).

---

## 3. Test-Seam Isolation & Dead-Code Elimination Contract

To ensure zero production leakage of test control mechanisms:
1. `AppTestControlHandle` is only populated when `import.meta.env.DEV` is truthy:
   ```typescript
   if (import.meta.env.DEV && testRef) {
     testRef.current = { ... };
   }
   ```
2. In Vite production builds (`NODE_ENV=production vite build`), `import.meta.env.DEV` is statically replaced with boolean literal `false`.
3. Rollup / terser performs AST constant folding: `if (false && testRef)` evaluates to unreachable code and is stripped from the bundle during minification.
4. Production bundle inspection verifies that `testRef.current` assignment and test helper names (`AppTestControlHandle`, `getPortfolioRiskEval`, `getSimulationProvider`) have exactly 0 occurrences in `dist/assets/*.js`.
