# FRACTAL-FLOW Control Surface — Operator Instrument Panel

An ultra-dense, low-latency operator instrument panel and control surface for the **FRACTAL-FLOW** systematic multi-timeframe Forex trading system.

Built strictly in accordance with `spec/control_surface_v1.yaml` and `docs/24_CONTROL_SURFACE_DESIGN_SYSTEM.md`.

---

## 1. Safety Architecture & Operational Boundary

FRACTAL-FLOW enforces a non-negotiable architectural invariant: **The frontend is an observation and dispatch surface, never an independent trading authority.**

- **Simulation Mode Badge**: Displays prominent amber sandbox badge (`MODE: SIMULATION (OFF-BROKER SANDBOX)`) when running decoupled from live brokers. Simulated actions never dispatch broker commands.
- **Formal Command Lifecycle**: Gated actions transition through:
  `IDLE` → `REQUESTED` → `ACCEPTED` → `DISPATCHED` → `CONFIRMED` / `REJECTED`
- **Idempotency Protection**: Action buttons and hotkeys are strictly disabled while commands are in flight, preventing accidental duplicate execution.
- **Candidate vs Position Isolation**: Rejection candidate evaluation inspection is decoupled from open position management so operators cannot mistake a rejected setup for an active trade.

---

## 2. Signature Visual Devices

### 1. Eleven-Gate Chain Strip (`GateChainStrip`)
Evaluates candidate trade viability across 11 sequential, mandatory validity gates:
- **Q** (Data Quality & Spread Cost)
- **E** (Expansion & Volatility Threshold)
- **R** (Regime & Role Alignment)
- **P** (PDE Pullback Depth)
- **L** (Location & Structural Value)
- **O** (Opportunity Score)
- **T** (Tradeability & Fee Economics)
- **N** (News Shield & Embargo Fence)
- **K** (Account Risk & Sizing Feasibility)
- **A** (Portfolio & Currency Correlation Arbitration)
- **X** (Execution Gateway Readiness)

### 2. Timeframe Cascade Indicator (`ContextPanel`)
Displays multi-timeframe directional and structural ownership across the canonical hierarchy:
`4H` (Environment) → `1H` (Directional State) → `30M` (Structural Context) → `15M` (Primary Pullback) → `5M` (Confirmation) → `1M` (Execution).

---

## 3. Operator Keyboard Shortcuts

For rapid operator response without touching the mouse:
- **`T`**: Tighten Stop (Ratchet structural trail)
- **`B`**: Move to Breakeven
- **`C`** or **`X`**: Close Position
- **`Escape`** / **`Backspace`** / **`0`** / **`` ` ``**: Return to Positions (`POS`) view from any secondary tab
- **`Enter`**: Confirm modal action
- **`Escape`**: Cancel modal action

---

## 4. Feature Matrix

- **Active Instruments & Multi-Symbol Detection**: Compact symbol badge displaying current side. If a symbol has multiple open positions, an interactive `More` pill reveals a dropdown list of all active instances.
- **Dynamic Stats Tab**: Monospaced calculation of Win Rate, Total Realized R, Profit Factor, Average Win/Loss, Max Drawdown, and Duration metrics from audited closed trades.
- **Macroeconomic & System News Feed (`NEWS` tab)**: Curated economic calendar with High, Med, and Low impact indicators, embargo countdowns, and currency filters.
- **Decision Engine Logs (`DEC` tab)**: Inspection of recent trade candidates and reasons for rejection.
- **Risk & Lane Caps (`RISK` tab)**: Real-time lane drawdown, risk budgets, and portfolio correlation matrix.
- **Mode Profiles (`MODE` tab)**: Calibration and confidence states for FF-01 through FF-04.
- **System Health & Kill Switches (`HEALTH` tab)**: Bridge heartbeats, broker latency, tick freshness, and emergency safety latches.

---

## 5. Development & Build

### Prerequisites
- Node.js >= 18.0.0
- npm >= 9.0.0

### Run Locally
```bash
# Navigate to the GUI folder
cd control_surface

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

### Production Build & Linting
```bash
# Type check and lint
npm run lint

# Compile production bundle
npm run build
```
