# FRACTAL FLOW — CANONICAL SCHEMA TYPES & FIELD CONTRACTS
Version: 1.1
Status: Canonical Implementation Schema

This specification provides concrete data types, physical units, and validation ranges for every field across all canonical system objects in FRACTAL FLOW. It fixes all enum, ratio, session, mode, and broker volume constraints.

---

## 1. Type and Unit Conventions

| Primitive Identifier | Base Type | Unit / Format | Description / Range |
|---|---|---|---|
| `UUID` | `string` | UUIDv4 format | Unique object identifier |
| `Timestamp` | `uint64` | Nanoseconds | UTC timestamp since Unix epoch (`0` to `2^64-1`) |
| `Price` | `float64` | Absolute Price Quote | Absolute currency pair price (`> 0.0`) |
| `PricePips` | `float64` | Pips | Pip distance (1 pip = `0.0001` for EURUSD, `0.01` for USDJPY) |
| `PriceNormalized` | `float64` | Ratio / Multiplier | Price normalized by ATR or Swing Range (`>= 0.0`) |
| `BoundedRatio` | `float64` | Ratio `[0.0, 1.0]` | Normalized ratio bounded strictly between 0.0 and 1.0 |
| `PositiveRatio` | `float64` | Ratio `>= 0.0` | Ratio bounded to non-negative numbers (e.g. `duration_ratio`) |
| `UnboundedRatio` | `float64` | Ratio | Unbounded floating-point ratio |
| `Score` | `float64` | Unitless Score | Score range `[0.0, 1.0]` |
| `Volume` | `float64` | Lots | Order size validated dynamically against `BrokerConstraints` |
| `CurrencyAmount` | `float64` | Account Currency | Absolute money value (`>= 0.0`) |
| `DurationNs` | `uint64` | Nanoseconds | Time duration in nanoseconds |
| `Version` | `uint64` | Monotonic Counter | Incrementing version number (`>= 1`) |

---

## 2. Broker Constraints Object (`BrokerConstraints`)

Positions and orders MUST validate volume, stop distances, and price steps dynamically against `BrokerConstraints` rather than static global boundaries:

```json
{
  "symbol": "string (e.g. EURUSD)",
  "min_volume": "float64 (e.g. 0.01)",
  "max_volume": "float64 (e.g. 100.0)",
  "volume_step": "float64 (e.g. 0.01)",
  "contract_size": "float64 (e.g. 100000.0)",
  "tick_size": "float64 (e.g. 0.00001)",
  "tick_value": "float64 (e.g. 1.0)",
  "stops_level": "float64 (pips distance floor for SL/TP)",
  "freeze_level": "float64 (pips distance floor for modification)",
  "digits": "int32 (e.g. 5)"
}
```

---

## 3. Canonical Enums

### 3.1 Strategy Mode vs Operating Posture
`StrategyMode` (User strategy concept): `SCALPING`, `SMART_SCALPING`, `FLIPPING`, `SMART_OVERTRADING`, `SMALL_ACCOUNT`
`OperatingPosture` (Risk aggressiveness level): `STANDARD`, `DEFENSIVE`, `AGGRESSIVE`

### 3.2 Rich Session Enum
`Session`: `ASIA`, `LONDON`, `LONDON_NY_OVERLAP`, `NEW_YORK`, `LATE_NEW_YORK`, `ROLLOVER`, `TRANSITION`

### 3.3 Market Role Enum
`MarketRole`: `CONTINUATION`, `PULLBACK`, `COUNTERFLOW`, `RANGE_ROTATION`, `BREAKOUT`, `RECLAIM`, `TRANSITION`, `EXHAUSTION`, `NOISE`, `AMBIGUOUS`

### 3.4 Opportunity Lifecycle Enum
`OpportunityState`: `DISCOVERED`, `VALIDATING`, `VALID`, `TRIGGER_READY`, `AUTHORIZED`, `EXECUTED`, `DEGRADED`, `INVALIDATED`, `STALE`, `EXPIRED`

### 3.5 Portfolio Arbitration Result Enum
`ArbitrationResult`: `ALLOW`, `DEFER`, `MERGE`, `REJECT`

### 3.6 News State vs Policy
`NewsState`: `NEWS_NORMAL`, `NEWS_WATCH`, `NEWS_PREP`, `NEWS_LOCKDOWN`, `INITIAL_SHOCK`, `VOLATILITY_DISCOVERY`, `POST_NEWS_VALIDATION`, `RESTRICTED_REENTRY`, `NORMAL_REENTRY`, `EXTENDED_PROTECTION`
`NewsEventType`: `SCHEDULED_HIGH_IMPACT`, `SCHEDULED_MEDIUM_IMPACT`, `UNSCHEDULED_SHOCK`, `SYSTEM_PAUSE`
`NewsExposurePolicy`:
```json
{
  "strategic_entry_allowed": "bool",
  "reentry_allowed": "bool",
  "counterflow_allowed": "bool",
  "risk_multiplier": "float64 [0.0, 1.0]"
}
```

---

## 4. Canonical Pullback Object (`PullbackObject`)
Owner Engine: Pullback Detection Engine (PDE) — Layer 2

| Field Name | Type | Unit / Format | Range / Constraints | Description |
|---|---|---|---|---|
| `id` | `UUID` | UUIDv4 | Non-null | Unique pullback instance ID |
| `parent_id` | `UUID` | UUIDv4 | Non-null | Parent setup or HTF pullback ID |
| `root_id` | `UUID` | UUIDv4 | Non-null | Root regime ID |
| `symbol` | `string` | Symbol code | Standard Forex/Crypto/Commodity symbol | Pair symbol |
| `timeframe` | `string` | Enum | 15M, 5M, 1M | Pullback timeframe |
| `direction` | `string` | Enum | LONG, SHORT | Thesis direction |
| `parent_direction` | `string` | Enum | LONG, SHORT | Higher timeframe direction |
| `start_time` | `Timestamp` | Nanoseconds | <= current_time | Timestamp of pullback origin |
| `start_price` | `Price` | Price | > 0.0 | Price at pullback start |
| `impulse_high` | `Price` | Price | > 0.0 | High of parent impulse |
| `impulse_low` | `Price` | Price | > 0.0 | Low of parent impulse |
| `impulse_range` | `PricePips` | Pips | > 0.0 | Total range of parent impulse |
| `current_high` | `Price` | Price | > 0.0 | Highest high during pullback |
| `current_low` | `Price` | Price | > 0.0 | Lowest low during pullback |
| `counter_move` | `PricePips` | Pips | >= 0.0 | Absolute counter-move distance |
| `counter_move_norm` | `PositiveRatio` | Ratio | >= 0.0 | Counter-move relative to impulse range |
| `retracement_depth` | `BoundedRatio` | Ratio | [0.0, 1.0] | Counter-move / impulse_range |
| `duration` | `DurationNs` | Nanoseconds | >= 0 | Elapsed duration of pullback |
| `duration_ratio` | `PositiveRatio` | Ratio | >= 0.0 | Pullback duration / impulse duration |
| `velocity` | `float64` | Pips / sec | Undefined unit | Price speed during counter-move |
| `acceleration` | `float64` | Pips / sec^2 | Undefined unit | Price acceleration during counter-move |
| `efficiency` | `BoundedRatio` | Ratio | [0.0, 1.0] | Counter-move efficiency (Net/Gross) |
| `momentum` | `BoundedRatio` | Ratio | [0.0, 1.0] | Relative counter-momentum score |
| `range` | `PricePips` | Pips | >= 0.0 | High-low range of pullback |
| `structural_damage` | `Score` | Score | [0.0, 1.0] | Structural damage to parent impulse |
| `weakening_score` | `Score` | Score | [0.0, 1.0] | Counter-momentum decay score |
| `resumption_score` | `Score` | Score | [0.0, 1.0] | Reversal/resumption evidence score |
| `false_resumption_risk` | `Score` | Score | [0.0, 1.0] | Estimated risk of fake resumption |
| `maturity` | `string` | Enum | START, DEVELOPING, MATURING, EXHAUSTED | Pullback maturity state |
| `state` | `string` | Enum | PDEState enum | Primary PDE state |
| `sub_state` | `string` | Enum | PDEResumptionState enum | Resumption sub-state |
| `validity` | `bool` | Boolean | TRUE, FALSE | Overall structural validity |
| `confidence` | `Score` | Score | [0.0, 1.0] | Evidence confidence score |
| `protected_level` | `Price` | Price | > 0.0 | Structural invalidation price level |
| `primary_entry_allowed` | `bool` | Boolean | TRUE, FALSE | Policy: Primary entry allowed |
| `micro_entry_allowed` | `bool` | Boolean | TRUE, FALSE | Policy: Micro entry allowed |
| `reentry_allowed` | `bool` | Boolean | TRUE, FALSE | Policy: Smart Overtrading re-entry allowed |
| `runner_management_allowed` | `bool` | Boolean | TRUE, FALSE | Policy: Structural trailing runner allowed |

---

## 5. Canonical Opportunity Object (`OpportunityObject`)
Owner Engine: Opportunity Engine — Layer 3

| Field Name | Type | Unit / Format | Range / Constraints | Description |
|---|---|---|---|---|
| `opportunity_id` | `UUID` | UUIDv4 | Non-null | Unique opportunity ID |
| `parent_opportunity_id` | `UUID` | UUIDv4 | Optional UUID | Parent opportunity ID if child |
| `root_id` | `UUID` | UUIDv4 | Non-null | Root regime ID |
| `symbol` | `string` | Code | Standard symbol | Pair symbol |
| `session` | `string` | Enum | Session enum | Rich session context |
| `strategy_mode` | `string` | Enum | StrategyMode enum | Strategy mode |
| `posture` | `string` | Enum | OperatingPosture enum | Risk posture level |
| `environment` | `string` | Enum | TREND_UP, TREND_DOWN, RANGE, TRANSITION | 4H regime state |
| `environment_tf` | `string` | Enum | 4H | Environment timeframe |
| `location` | `string` | Enum | OPEN, FAVORABLE, CONGESTED, BLOCKED | Structural location quality |
| `location_tf` | `string` | Enum | 30M | Location timeframe |
| `dominant_flow` | `string` | Enum | LONG_DOMINANT, SHORT_DOMINANT, BALANCED | Flow ownership state |
| `local_flow` | `string` | Enum | LONG_EMERGING, SHORT_EMERGING, etc. | Execution timeframe flow |
| `market_role` | `string` | Enum | MarketRole enum | Setup classification |
| `primary_pullback_id` | `UUID` | UUIDv4 | Non-null | Originating primary pullback ID |
| `setup_type` | `string` | Enum | FF-01, FF-02, FF-03, FF-04 | Strategy family code |
| `direction` | `string` | Enum | LONG, SHORT | Opportunity direction |
| `structural_edge` | `Price` | Price | > 0.0 | Key structural level giving edge |
| `opportunity_space` | `Score` | Score | [0.0, 1.0] | Room to move before major structure |
| `tradeability` | `string` | Enum | PASS, MARGINAL, FAIL_SPREAD, etc. | Tradeability status |
| `execution_quality` | `Score` | Score | [0.0, 1.0] | Historical execution quality score |
| `entry_profile` | `string` | Enum | MARKET, LIMIT, STOP | Recommended entry order type |
| `risk_class` | `string` | Enum | FULL, HALF, REDUCED | Risk allocation class |
| `ttl_class` | `string` | Enum | SCALP_SHORT, STANDARD, RUNNER | TTL lifetime profile |
| `confidence` | `Score` | Score | [0.0, 1.0] | Combined opportunity score |
| `state` | `string` | Enum | OpportunityState enum | Opportunity state |
| `entry_allowed` | `bool` | Boolean | TRUE, FALSE | Final opportunity validity flag |

---

## 6. Unified Trade Decision Object (`TradeDecision`)
Owner Engine: Layer 5 Decision Authorization / Layer 6 MT5 Gateway

| Field Name | Type | Unit / Format | Range / Constraints | Description |
|---|---|---|---|---|
| `decision_id` | `UUID` | UUIDv4 | Non-null | Unique decision identifier |
| `opportunity_id` | `UUID` | UUIDv4 | Non-null | Linked opportunity ID |
| `direction` | `string` | Enum | BUY, SELL | Order direction |
| `symbol` | `string` | Code | Valid broker symbol | Symbol code |
| `environment` | `string` | Enum | Regime state | Environment regime |
| `role` | `string` | Enum | MarketRole enum | Market role |
| `setup` | `string` | Enum | FF-01 .. FF-04 | Setup code |
| `pullback` | `UUID` | UUIDv4 | Non-null | Primary pullback ID |
| `resumption` | `string` | Enum | PDEResumptionState enum | Resumption state at trigger |
| `location` | `string` | Enum | Location state | Structural location |
| `opportunity_space` | `Score` | Score | [0.0, 1.0] | Opportunity space score |
| `tradeability` | `string` | Enum | Tradeability status | Must be PASS |
| `news_state` | `string` | Enum | NewsState enum | Checked against NewsExposurePolicy |
| `risk_state` | `string` | Enum | RiskState enum | Must NOT be RISK_HALTED |
| `portfolio_state` | `string` | Enum | ArbitrationResult enum | Must be ALLOW |
| `entry_price` | `Price` | Price | > 0.0 | Target or current market entry price |
| `structural_sl` | `Price` | Price | > 0.0 | Mandatory structural stop price |
| `tp_plan` | `string` | JSON struct | Valid JSON | Multi-target TP configuration |
| `ttl` | `DurationNs` | Nanoseconds | > 0 | Maximum lifetime before forced exit |
| `requested_risk` | `CurrencyAmount` | Money | > 0.0 | Risk requested by strategy |
| `approved_risk` | `CurrencyAmount` | Money | > 0.0 | Risk approved by Portfolio/Risk |
| `position_size` | `Volume` | Lots | Validated against BrokerConstraints | Sized position in standard lots |
| `arbitration_result` | `string` | Enum | ArbitrationResult enum | Arbitration decision (ALLOW, DEFER, MERGE, REJECT) |
| `configuration_version` | `Version` | Monotonic | >= 1 | System configuration version ID |
| `lineage_version` | `Version` | Monotonic | >= 1 | Lineage schema version ID |
