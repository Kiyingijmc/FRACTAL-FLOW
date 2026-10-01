# FRACTAL FLOW — TELEMETRY, NOTIFICATIONS, COMMAND & GUI ARCHITECTURE
Version: 1.0
Status: Pre-Implementation GUI & Telemetry Specification

This document specifies the institutional-grade notification, remote command-and-control, MT5 chart HUD, TradingView state mirror, and web dashboard architecture for FRACTAL FLOW.

---

## 1. Multi-Tier Telemetry & Notification Engine

Notifications are categorized into 4 severity levels with strict rate limiting and channel routing:

| Severity | Level Name | Target Channels | Escalation & Retention | Examples |
|---|---|---|---|---|
| `P0` | **CRITICAL_EMERGENCY** | PagerDuty, SMS, Telegram, MT5 Alert | Instant ring, repeat every 30s until ack | Broker disconnect, unknown execution state, drawdown cap breach, margin warning |
| `P1` | **TRADE_ACTION** | Telegram, Web GUI, Discord | Real-time push + rich chart image | Order fill, stop loss ratchet, partial profit hit, TTL forced exit, news freeze |
| `P2` | **STATE_TRANSITION** | Web GUI, Telegram (Digest) | Real-time WebSocket + 15m Telegram summary | HTF Regime transition, PDE resumption confirmed, News Watch activated |
| `P3` | **SYSTEM_INFO** | Web Log, Disk File | Daily log rotation | Heartbeats, data quality validation checks, latency measurements |

---

## 2. Remote Command & Control Interface (C2)

Remote command execution allows secure operational control via authenticated Telegram Bot commands or Web GUI REST/WebSocket endpoints.

### 2.1 Security & Authentication Contract
- Commands require HMAC-SHA256 signature verification or two-factor secret tokens.
- Strategic engines must reject commands if state integrity checks fail.

### 2.2 Command Registry

| Command | Arguments | Permission Level | Description |
|---|---|---|---|
| `/status` | `[symbol]` | Operator | Returns live regime state, active exposure, margin level, and engine health across all active pairs. |
| `/pause` | `[symbol\|ALL]` | Operator | Activates `SIGNAL_FREEZE`. Suspends new trade authorization while maintaining active protective management. |
| `/resume` | `[symbol\|ALL]` | Admin | Clears manual pause and performs full state reconciliation before re-authorizing new entries. |
| `/panic` | `[symbol\|ALL]` | Admin | Emergency execution: market closes specified positions immediately and cancels all pending orders. |
| `/mode` | `[STANDARD\|DEFENSIVE\|AGGRESSIVE]` | Admin | Updates global strategy operating mode dynamically with version increment. |
| `/trail` | `[ticket] [price]` | Admin | Overrides structural stop for a specific position (ratchet tighter only; loosening rejected). |
| `/news_override` | `[event_id]` | Admin | Manually forces news lockdown end if market conditions are confirmed normal post-release. |

---

## 3. MT5 Canvas & Chart HUD Interface

The MT5 terminal visualizer renders real-time structural state directly onto MT5 charts using native CCanvas / OBJ_RECTANGLE / OBJ_TEXT primitives.

### 3.1 Visual HUD Component Mapping
- **Header Status Bar:** Live Regime (`TREND_UP`), Flow Ownership (`LONG_DOMINANT`), News Shield Status (`NEWS_NORMAL`), Risk Level (`0.5%`).
- **Structure Overlays:**
  - Protected HTF Swings: Solid green/red horizontal ray bands (`SWING_PROTECTED`).
  - Active Pullback Corridor: Shaded semi-transparent channel highlighting `15M PRIMARY` or `5M SECONDARY` pullback zone.
  - Reclaim / Break Markers: Dynamic arrow markers on confirmed structural breaks with displacement metrics.
- **Trade Execution Card:** Interactive on-chart card showing calculated Position Size (Lots), Structural SL, TP1/TP2 targets, and current Trade TTL countdown timer.

---

## 4. TradingView Mirror & State Overlay Architecture

TradingView provides visual research and multi-timeframe state display via lightweight Pine Script indicators receiving Webhook state events.

### 4.1 Architecture
1. Core Strategy Engine emits `StateEnvelope` events on state changes.
2. Webhook Bridge formats payload into JSON arrays.
3. TradingView Pine Script Indicator parses state arrays to plot:
   - Color-coded background tinting for Regime state (e.g., Light Green = Trend Up, Gray = Transition).
   - Dynamic trailing stop lines synchronized with MT5 authoritative stop levels.
   - Opportunity quality scores rendered as table panels on top-right chart corner.

---

## 5. Web Control Center & Monitoring Dashboard

A lightweight Web GUI (React/Vue frontend + FastAPI/WebSockets backend) provides a single operational cockpit:

### 5.1 Dashboard Panels
1. **Executive Heatmap:** Live multi-pair matrix (EURUSD, XAUUSD, BTCUSD, ETHUSD, USOIL) showing 4H/1H/15M regime, flow, pullback state, and exposure.
2. **Lineage Inspector:** Tree view displaying active root-to-leaf lineage chains (`ROOT → REGIME → SETUP → PULLBACK → OPPORTUNITY → POSITION`).
3. **Risk & Drawdown Gauge:** Real-time equity curve, peak-to-trough drawdown meter, daily loss limit gauge, and currency risk vector breakdown.
4. **Order Book & Reconciliation Log:** Live MT5 position audit, orphan status indicator, order execution latency metrics, and broker spread elasticity graphs.
