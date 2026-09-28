# FRACTAL FLOW — RECONCILED STATE MACHINES
Version: 1.0
Status: Canonical State Machine Specification

This document provides the single source of truth for all state enums, valid transitions, and state envelopes across all FRACTAL FLOW engines. It resolves all state machine discrepancies previously identified across `docs/02_ENGINE_CONTRACTS.md`, `docs/03_STATE_MACHINE.md`, `docs/04_STRUCTURE_ENGINE.md`, `docs/06_PULLBACK_ENGINE.md`, `docs/10_NEWS_SHIELD.md`, `docs/13_EXECUTION.md`, `docs/14_RECONCILIATION.md`, and `docs/15_POSITION_MANAGEMENT.md`.

---

## 1. Universal State Envelope

Every state object emitted or persisted across all engines MUST wrap its state payload in this universal envelope:

```json
{
  "state_id": "UUIDv4 string",
  "object_id": "UUIDv4 string",
  "object_type": "string enum (e.g., PULLBACK, OPPORTUNITY, POSITION)",
  "symbol": "string (e.g., EURUSD)",
  "timeframe": "string enum (e.g., 15M, 5M, 1M)",
  "root_id": "UUIDv4 string (highest-level regime/environment ID)",
  "parent_id": "UUIDv4 string (immediate parent object ID)",
  "parent_version": "uint64",
  "state": "string enum",
  "sub_state": "optional string enum",
  "previous_state": "string enum",
  "version": "uint64",
  "timestamp": "uint64 (nanoseconds since UTC epoch)",
  "valid_until": "uint64 (nanoseconds since UTC epoch)",
  "last_seen": "uint64 (nanoseconds since UTC epoch)"
}
```

---

## 2. Pullback Detection Engine (PDE) Reconciled State Machine

### 2.1 Primary PDE States (`PDEState`)
- `PDE_NONE`: No active pullback activity or impulse.
- `PDE_IMPULSE`: Directional displacement detected; monitoring for counter-move.
- `PDE_PULLBACK_CANDIDATE`: Counter-move detected meeting minimum candidate threshold.
- `PDE_PULLBACK_ACTIVE`: Counter-move validated as an active pullback.
- `PDE_WEAKENING`: Pullback counter-momentum losing momentum; potential resumption setup.
- `PDE_STRENGTHENING`: Counter-move regaining momentum against impulse (deepening risk).
- `PDE_DEEPENING`: Pullback exceeding standard retracement depth; structural damage warning.
- `PDE_RESUMPTION_IN_PROGRESS`: Structural recovery initiated; executing resumption sub-lifecycle.
- `PDE_FOLLOW_THROUGH`: Resumption confirmed with directional follow-through displacement.
- `PDE_RESUMPTION_FAILED`: Resumption attempt failed to achieve continuation; thesis invalidated.
- `PDE_INVALIDATED`: Pullback exceeded maximum allowable structural boundary or expired.

### 2.2 Resumption Sub-Lifecycle States (`PDEResumptionState`)
- `RESUMPTION_NONE`: No resumption attempt active.
- `RECOVERY_CANDIDATE`: Lower-timeframe structural reclaim or reversal signal detected.
- `RECOVERY_CONFIRMED`: Structural reclaim confirmed on execution timeframe.
- `DISPLACEMENT_CANDIDATE`: Directional expansion candle in thesis direction.
- `RESUMPTION_CONFIRMED`: Break of pullback internal swing high/low confirmed.

### 2.3 PDE State Transition Diagram
```
[ PDE_NONE ]
     │ (Impulse displacement)
     ▼
[ PDE_IMPULSE ]
     │ (Counter-move detected)
     ▼
[ PDE_PULLBACK_CANDIDATE ]
     │ (Candidate threshold met)
     ▼
[ PDE_PULLBACK_ACTIVE ]
     │
     ├───► (Counter-momentum decay) ───► [ PDE_WEAKENING ]
     │                                        │
     │                                        ▼
     │                          [ PDE_RESUMPTION_IN_PROGRESS ]
     │                                   │          │
     │               (Follow-through)    │          │ (Resumption fails)
     │               ┌───────────────────┘          ▼
     │               ▼                    [ PDE_RESUMPTION_FAILED ] ──┐
     │      [ PDE_FOLLOW_THROUGH ]                  │                  │
     │                                              │                  │
     └───► (Counter-momentum surge) ──► [ PDE_STRENGTHENING ]          │
                                                │                      │
                                                ▼                      │
                                       [ PDE_DEEPENING ]               │
                                                │                      │
                                                ▼                      │
                                       [ PDE_INVALIDATED ] ◄───────────┘
```

---

## 3. Structure Engine Reconciled State Machine

Structure Engine publishes two synchronized state variables: `SwingState` and `BreakState`.

### 3.1 Swing States (`SwingState`)
- `SWING_NONE`: No swing extreme identified.
- `SWING_CANDIDATE`: Unconfirmed local high/low.
- `SWING_CONFIRMED`: Local extreme confirmed by minimum directional displacement.
- `SWING_PROTECTED`: High-significance structural swing anchor (e.g. key HTF low/high).
- `SWING_BROKEN`: Swing level breached by opposing price action.

### 3.2 Structural Break States (`BreakState`)
- `BREAK_NONE`: No breach of structural level.
- `BREAK_CANDIDATE`: Price cross above/below structural level (`LevelCross = TRUE`).
- `BREAK_CONFIRMED`: Penetration plus displacement confirmed (`DisplacementConfirmation = TRUE`).
- `BREAK_ESTABLISHED`: Persistence confirmed across time/bars (`PersistenceConfirmation = TRUE`).
- `FAILED_BREAK`: Price breached level but failed displacement/persistence (liquidity sweep / fakeout).

---

## 4. News Shield Engine Reconciled State Machine

### 4.1 Canonical News States (`NewsState`)
- `NEWS_NORMAL`: No active or upcoming scheduled news event within watch window.
- `NEWS_WATCH`: High-impact news event scheduled within pre-news watch window (e.g., 60 mins).
- `NEWS_PREP`: Pre-news lockdown approaching (e.g., 15 mins); position tightening active.
- `NEWS_LOCKDOWN`: Mandatory signal freeze window (e.g., -5 mins to +5 mins); no new exposure.
- `INITIAL_SHOCK`: High-volatility price discovery phase immediately following release.
- `VOLATILITY_DISCOVERY`: Post-release spread/volatility measurement phase.
- `POST_NEWS_VALIDATION`: Mandatory post-news validation checkpoint (10-min mark).
- `RESTRICTED_REENTRY`: Market stable but trading permitted only at reduced risk/strict parameters.
- `NORMAL_REENTRY`: Market metrics fully normalized; full trading authority restored.
- `EXTENDED_PROTECTION`: Shock/volatility exceeded acceptable bounds; restriction extended.

### 4.2 News State Transition Diagram
```
[ NEWS_NORMAL ] ──► [ NEWS_WATCH ] ──► [ NEWS_PREP ] ──► [ NEWS_LOCKDOWN ]
       ▲                                                        │
       │                                                        ▼
       │                                               [ INITIAL_SHOCK ]
       │                                                        │
       │                                                        ▼
   (Normal)                                           [ VOLATILITY_DISCOVERY ]
       │                                                        │
       │                                                        ▼
[ NORMAL_REENTRY ] ◄── [ RESTRICTED_REENTRY ] ◄── [ POST_NEWS_VALIDATION ]
       ▲                                                        │
       └────────────────── (Extreme shock) ─────────────────────┼──► [ EXTENDED_PROTECTION ]
```

---

## 5. MT5 Execution Engine Reconciled Order & Trade State Machine

### 5.1 Trade Decision Lifecycle States (`DecisionLifecycleState`)
- `DECISION_CANDIDATE`: Candidate signal evaluated for authorization.
- `DECISION_VALIDATING`: Signal undergoing gate validation.
- `DECISION_TRADEABILITY_CHECK`: Evaluating spread and market depth.
- `DECISION_RISK_CHECK`: Position sizing and drawdown checks.
- `DECISION_PORTFOLIO_CHECK`: Checking currency exposure limits.
- `DECISION_ARBITRATION`: Portfolio arbitration ranking.
- `DECISION_AUTHORIZED`: Decision authorized for execution submission.
- `DECISION_EXECUTED`: Order submitted to broker.
- `DECISION_REJECTED`: Decision failed validation gates.

### 5.2 Order & Execution Gateway States (`ExecutionState`)
- `EXEC_READY`: TradeDecision validated and ready for submission.
- `EXEC_SUBMITTING`: Dispatching order request to MT5 gateway.
- `EXEC_SUBMITTED`: Order acknowledged by MT5 server; awaiting execution.
- `EXEC_ACCEPTED`: Pending order placed on broker order book.
- `EXEC_PARTIAL`: Order partially filled.
- `EXEC_FILLED`: Order fully executed; position established.
- `EXEC_REJECTED`: Order rejected by broker or pre-trade gateway safety check.
- `EXEC_CANCELLED`: Pending order cancelled before execution.
- `EXEC_UNKNOWN`: Network/system disconnect during submission; state unconfirmed.
- `EXEC_RECONCILING`: Recovering order status after reconnect.

---

## 6. Position Management Reconciled State Machine

### 6.1 Lifecycle States (`PositionLifecycleState`)
- `POS_OPENING`: Execution filled; position being registered in state store.
- `POS_ACTIVE`: Open position operating under initial structural parameters.
- `POS_PROTECTED`: Stop-loss moved to breakeven or protected structural level.
- `POS_RUNNER`: Target 1 achieved; residual position trailing higher-timeframe structure.
- `POS_DECAYING`: Position progress stalled or trade TTL decaying; preparing early exit.
- `POS_EXPIRING`: TTL expired or structural thesis damaged; closing triggered.
- `POS_CLOSING`: Close order dispatched to broker.
- `POS_CLOSED`: Position fully closed and finalized.

### 6.2 Health States (`PositionHealthState`)
- `HEALTH_HEALTHY`: Trade progressing as expected along structural thesis.
- `HEALTH_STALLED`: Price movement stagnated near entry; trade decay accelerating.
- `HEALTH_DAMAGED`: Partial counter-structure formed; thesis weakened.
- `HEALTH_INVALID`: Parent setup/pullback invalidated; immediate protective exit required.
- `HEALTH_CRITICAL`: Account/drawdown or catastrophic market gap emergency.

---

## 7. Reconciliation Engine Reconciled State Machine

### 7.1 Orphan & Reconciliation States (`ReconciliationState`)
- `RECON_NORMAL`: Normal operational state; all objects reconciled.
- `RECON_SUSPECTED_ORPHAN`: Broker order/position detected without matching internal state object.
- `RECON_RECONCILING`: System actively matching broker state against local persistence history.
- `RECON_RECOVERED`: Lineage reconstructed; position re-attached to active strategy tracking.
- `RECON_QUARANTINED`: Lineage cannot be reconstructed; position placed under protective trailing management.
