# FRACTAL FLOW — DOC 21: ENTRY MODEL ENGINE SPECIFICATION
Version: 1.0
Status: Pass 4 Complete Entry Architecture Specification

---

## 1. Executive Summary & Pipeline Position

The Entry Model Engine forms Layer 4A of the FRACTAL FLOW architecture. It acts as the bridge between Opportunity authorization (Layer 3/4) and Execution Intent submission (Layer 6).

Pipeline Position:
```
OPPORTUNITY (What/Where)
    ↓
TRADEABILITY (Permission)
    ↓
ACTIVE MARKET CONTEXT (MURG Permission)
    ↓
ENTRY POLICY ENGINE (How to Enter)
    ↓
ENTRY PLAN (Conditional Execution)
    ↓
RISK & PORTFOLIO (How Much)
    ↓
AUTHORIZATION EVIDENCE
    ↓
EXECUTION GATEWAY (Broker)
```

The fundamental directive remains:
«Entry Policy determines entry mechanisms; Execution Gateway determines broker dispatch; Broker determines execution truth.»

---

## 2. Canonical Entry Models

- `MARKET_CONFIRMATION`: Instant execution upon lower-timeframe confirmation trigger.
- `PULLBACK_LIMIT`: Pending limit order positioned at key structural retracement levels.
- `RETEST_LIMIT`: Pending limit order placed on broken structural swing retest.
- `RECLAIM_LIMIT`: Pending limit order positioned after structural level reclaim.
- `BREAKOUT_STOP`: Pending stop order positioned beyond structural swing extreme.
- `STOP_LIMIT_BREAKOUT`: Conditional stop-limit order requiring price breach before limit activation.
- `MOMENTUM_MARKET`: Market order dispatched on directional displacement acceleration.
- `CONFIRMATION_REENTRY`: Budgeted re-entry following structural recovery.
- `HYBRID`: Split-leg entry plan sharing a single opportunity risk budget.
- `NO_ENTRY`: Explicit policy decision concluding no valid entry mechanism exists.

---

## 3. Order Types & Capability Validation

Supported Order Types:
- `MARKET_BUY`, `MARKET_SELL`
- `BUY_LIMIT`, `SELL_LIMIT`
- `BUY_STOP`, `SELL_STOP`
- `BUY_STOP_LIMIT`, `SELL_STOP_LIMIT`

Every EntryPlan validates broker capability against `BrokerConstraints.supported_order_types` prior to arming. If an order type is unsupported, EntryPolicy re-evaluates explicit fallbacks or emits `NO_ENTRY`.

---

## 4. Conditional Order Lifecycle & State Machine

Entry Plans operate under the canonical `EntryState` machine:
`ENTRY_CREATED -> ENTRY_VALIDATING -> ENTRY_ARMED -> [STOP_TRIGGERED -> LIMIT_ACTIVATED] -> ENTRY_SUBMITTING -> PARTIAL_FILL -> ENTRY_FILLED`

Continuous Invalidation Gates:
- Parent opportunity version staleness (`parent_version != current_parent_version`)
- Strategy entry TTL expiration (`now >= expires_at`)
- Hard news lockdown (`NEWS_LOCKDOWN`)
- Spread expansion beyond threshold
- Broker freeze level breaches

---

## 5. Risk Allocation & Hybrid Entry Mechanics

- **Opportunity Risk Budget:** Single parent risk budget allocated across entry legs.
- **Invariants Enforced:**
  - `allocated_risk <= opportunity_risk_budget`
  - `remaining_risk >= 0`
  - `filled_volume <= approved_volume`
- **Contingent Exposure:** Pending orders contribute to `WORST_CASE_CONTINGENT_EXPOSURE` without converting pending orders into open positions.

---

## 6. Restart Recovery & Authorization Evidence

- **EntryAuthorizationEvidence:** Immutable provenance snapshot holding `decision_id`, `opportunity_version`, `effective_config_id`, and timestamps required before execution gateway submission.
- **Restart Reconciliation:** Strategic authorization is disabled upon system restart until `DeterministicBrokerSimulator.reconcile_intent()` matches pending plans against broker orders.
