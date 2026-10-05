# POSITION MANAGEMENT
Version 1.0

## 1. Lifecycle

OPENING
→ ACTIVE
→ PROTECTED
→ RUNNER
→ DECAYING
→ EXPIRING
→ CLOSING
→ CLOSED

Health:
HEALTHY
STALLED
DAMAGED
INVALID
CRITICAL

## 2. Initial stop

Structural stop:
- long: below protected structure/pullback
- short: above protected structure/pullback

Volatility may add a buffer.

## 3. Structural trailing

Long:
trail below protected pullback low.

Short:
trail above protected pullback high.

Stops ratchet only.

Hierarchy:
- early: M5 structure
- established: M5 protected pullback
- runner: 15M protected structure

Do not trail simply because ATR moved.

## 4. Dynamic TP

Modes:
STATIC
STRUCTURAL
VOLATILITY
MOMENTUM
LIQUIDITY
HYBRID
ADAPTIVE

Dynamic TP should account for:
- structure
- liquidity
- momentum
- volatility
- setup
- session
- expected resolution

TP can expand when:
- structure expands
- momentum persists
- opportunity corridor opens

TP can contract/protect when:
- momentum collapses
- structure weakens
- opportunity space shrinks

## 5. Partials

Candidate profiles:
25/25/50
33/67
40/30/30

These are examples only.

The system must make partial profiles configurable and researchable.

## 6. Runner

A runner is not an excuse to ignore structural deterioration.

Runner management can migrate from:
M5 protected structure
to
15M protected structure

Runner remains subject to:
news
TTL
structural invalidation
portfolio safety

## 7. News overlay

News may tighten protection.

It must never loosen an existing SL.

Profitable positions may target a percentage of current realizable profit protection, subject to constraints.

## 8. Losing positions

Health classification:
HEALTHY
STALLING
DAMAGED
INVALID
CRITICAL

Actions:
HOLD
TIGHTEN
REDUCE
CLOSE

Never manufacture an opposite trade simply because a position loses.

## 9. Trade decay

Management should recognize:
- time decay
- progress shortfall
- momentum decay
- structural damage
- volatility collapse
- opportunity decay

This feeds TTL.

## 10. Position state audit

Each position stores:
- lineage
- current SL
- current TP
- entry/fill details
- remaining volume
- realized/unrealized PnL
- risk state
- news state
- TTL state
- configuration version
- management reason
