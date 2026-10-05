# FRACTAL FLOW — DOC 20: MARKET UNIVERSE & RESOURCE GOVERNOR (MURG) SPECIFICATION
Version: 1.0
Status: Pass 4 Complete MURG Specification

---

## 1. Executive Summary & Architecture Pipeline

The Market Universe & Resource Governor (MURG) governs analytical resource allocation across broker instruments without granting trading permission or manufacturing direction.

Pipeline Position:
```
BROKER
    ↓
DISCOVERY & INSTRUMENT CATALOG
    ↓
ELIGIBILITY ENGINE
    ↓
USER MARKET UNIVERSE (Manual/Smart/Auto/Hybrid)
    ↓
RESOURCE GOVERNOR (Hard Caps & Account Resource Context)
    ↓
ACTIVE MARKET CONTEXT
    ↓
MARKET DATA → FEATURES → STATES → STRATEGY → OPPORTUNITY → ENTRY
```

The fundamental directive remains:
«MURG determines where analytical resources are spent; MURG NEVER determines trade direction or authorizes execution.»

---

## 2. Discovery, Instrument Catalog & Canonical Identity

- **InstrumentIdentity:** Maps canonical instrument symbol (`EURUSD`) to broker-specific symbol aliases (`EURUSD.a`, `EURUSDm`).
- **InstrumentDescriptor:** Stores contract size, tick size/value, min/max volume, volume step, stops level, freeze level, and supported order modes.
- **EligibilityEngine:** Fail-closed capability check rejecting disabled trade modes, invalid volume rules, or unsynchronized data streams.

---

## 3. User Universe & Market Groups

Supported Modes:
- `MANUAL`: Exact user-specified symbols.
- `SMART`: Broad preferred universe managed dynamically by MURG.
- `AUTO`: Dynamic discovery and filtering.
- `HYBRID`: Pinned priority symbols + dynamic capacity management.

---

## 4. Resource Governor, Account Context & Session Awareness

- **Hard Symbol Cap (`max_active_symbols`):** Enforces an absolute ceiling on active analytical markets.
- **Account Capacity Multiplier:** Scales analytical budget based on account equity, free margin, margin utilization, and drawdown state (`NORMAL` = 1.0x, `CONSTRAINED` = 0.5x, `CRITICAL` = 0.25x).
- **Session Context:** Closed sessions transition instruments to `DORMANT`.
- **CRITICAL INVARIANT (Position Protection):** When an instrument transitions to `DORMANT` or `SUSPENDED`, `entry_analysis_enabled` is set to `False`, BUT `position_monitoring_enabled` and `pending_order_monitoring_enabled` REMAINS `True`! Open positions and pending orders are NEVER abandoned.

---

## 5. Market States & Transitions

Canonical `MarketState` Progression:
`DISCOVERED -> CATALOGUED -> ELIGIBLE -> USER_SELECTED -> QUEUED -> WARMING_UP -> DATA_READY -> ACTIVE [-> DORMANT / SUSPENDED / BLOCKED / UNAVAILABLE]`
