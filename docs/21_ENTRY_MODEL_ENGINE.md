# FRACTAL FLOW — DOC 21: ENTRY MODEL ENGINE SPECIFICATION
Version: 1.0
Status: Pass 4 Complete Entry Architecture Specification

## 1. Overview and Core Purpose

The Entry Model Engine translates authorized strategic trade decisions into actionable, conditionally executable entry plans. It bridges high-level direction (Opportunity, Tradeability, Risk) and low-level broker order submission.

```
OPPORTUNITY / DECISION (Direction & Intent)
    ↓
TRADEABILITY (Permission)
    ↓
ACTIVE MARKET CONTEXT (MURG Permission)
    ↓
ENTRY POLICY ENGINE (How to Enter)
    ↓
ENTRY PLAN (Conditional Execution)
```

## 2. Core Entry Models

1. `MARKET_CONFIRMATION`: Immediate execution upon trigger confirmation at prevailing market price.
2. `PULLBACK_LIMIT`: Passive limit placement waiting for intra-pullback re-pricing.
3. `RETEST_LIMIT`: Limit order placed at broken structural support/resistance.
4. `RECLAIM_LIMIT`: Limit order entering after a liquidity sweep reclaims level.
5. `BREAKOUT_STOP`: Stop order triggered when price breaks beyond key level.
6. `STOP_LIMIT_BREAKOUT`: Stop-limit order specifying price corridor limits on breakout.
7. `MOMENTUM_MARKET`: Urgent market execution upon high-velocity flow resumption.
8. `CONFIRMATION_REENTRY`: Secondary entry following partial scale or re-evaluation.
9. `HYBRID`: Multi-leg entry distributing risk across limit and market triggers.
10. `NO_ENTRY`: Fail-closed posture blocking entry submission.

## 3. ActiveMarketContext and Permission Rules

No entry plan may be constructed or armed without validating an `ActiveMarketContext` provided by the Market Universe & Resource Governor (MURG).

ActiveMarketContext must satisfy:
- `activation_state == "ACTIVE"`
- `entry_analysis_enabled == True`
- `is_tradable_session == True`
- Broker constraints satisfied (e.g. `min_volume`, `supported_order_types`).

## 4. Conditional Revalidation Engine

Armed entry plans are revalidated continuously prior to execution:
- Parent version equality (`plan.parent_version == authoritative_parent_version`)
- Expiry (`current_clock_ns < plan.expires_at`)
- News state (`current_news_state != "NEWS_LOCKDOWN"`)
- Tradeability state (`current_tradeability_state == "TRADEABILITY_PASS"`)

Failure of any condition transitions the entry plan to `ENTRY_INVALIDATED`, `ENTRY_EXPIRED`, or `ENTRY_STALE`.
