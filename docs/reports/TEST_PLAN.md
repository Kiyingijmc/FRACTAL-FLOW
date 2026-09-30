# FRACTAL FLOW — COMPREHENSIVE TEST PLAN
Version: 1.1
Status: Implementation Test Plan
Scope: Derived from `docs/19_ADVERSARIAL_TESTING.md` and the 42 Invariants in `AGENTS.md`. Organized by Implementation Phases 1–8 (`CODEX_HANDOFF.md §3`).

---

## Phase 1 — Primitives, Lineage, Enums, State Envelopes & Invariants

### 1.1 Lineage & State Envelope Verification
* **Test Name:** `test_lineage_chain_integrity_validation`
  * **Objective:** Verify that every child object correctly anchors to `parent_id`, `parent_version`, and `root_id`.
  * **Assertions:**
    - `Assert(opportunity.root_id == regime.state_id)`
    - `Assert(opportunity.parent_id == pullback.state_id)`
    - `Assert(signal.parent_version == opportunity.version)`
* **Test Name:** `test_orphaned_signal_never_executes` (AGENTS.md Invariant #14)
  * **Objective:** Ensure a signal whose parent opportunity or setup state is invalidated before dispatch is rejected before MT5 gateway submission.
  * **Assertions:**
    - `Invalidate(parent_opportunity)`
    - `AssertRaises(LineageInvalidException, ValidateForExecution(child_signal))`
    - `Assert(mt5_gateway.order_count == 0)`
* **Test Name:** `test_invalid_parent_version_blocks_child_action` (AGENTS.md Invariant #13)
  * **Objective:** Ensure that when a parent object version increments, child requests with stale `parent_version` are rejected.
  * **Assertions:**
    - `UpdateParentState(parent_object)` -> `parent_object.version += 1`
    - `AssertFalse(ValidateChildState(child_object_stale_version))`

### 1.2 Automated State-Machine Transition Matrix Validation
* **Test Name:** `test_illegal_state_transitions_rejected`
  * **Objective:** Exhaustively test state transition matrix to verify illegal state transitions raise `InvalidStateTransitionException`.
  * **Assertions:**
    - `AssertRaises(InvalidStateTransitionException, Transition(PDE_INVALIDATED, PDE_PULLBACK_ACTIVE))`
    - `AssertRaises(InvalidStateTransitionException, Transition(OPP_EXPIRED, OPP_AUTHORIZED))`
    - `AssertRaises(InvalidStateTransitionException, Transition(EXEC_UNKNOWN, EXEC_FILLED))` -- Must pass through `EXEC_RECONCILING` first.
    - `AssertRaises(InvalidStateTransitionException, Transition(QUARANTINED, STRATEGIC_ENTRY))`

---

## Phase 2 — Market State (Data Quality, Volatility, Adaptive Structure)

### 2.1 Data Quality & Volatility Gates
* **Test Name:** `test_stale_or_corrupted_data_blocks_new_exposure` (AGENTS.md Invariant #17)
  * **Objective:** Verify that `DATA_STALE` or `DATA_CORRUPTED` immediately revokes tradeability.
  * **Assertions:**
    - `SetDataState(DATA_STALE)`
    - `AssertEqual(TradeabilityEngine.Evaluate(opportunity), FAIL_DATA_QUALITY)`
    - `AssertFalse(TradeDecision.entry_allowed)`

### 2.2 Adaptive Structure Verification
* **Test Name:** `test_fixed_three_candle_fractals_not_used_for_structure` (AGENTS.md Invariant #32)
  * **Objective:** Verify structure engine requires displacement and persistence confirmation, not naive 3-candle fractal logic.
  * **Assertions:**
    - `InjectCandlePattern(three_candle_fractal_without_displacement)`
    - `AssertEqual(StructureEngine.GetSwingState(), SWING_NONE)`
* **Test Name:** `test_structural_break_requires_displacement_and_persistence`
  * **Objective:** Confirm `LevelCross` alone produces `BREAK_CANDIDATE`, requiring calibrated displacement and persistence evidence for `BREAK_ESTABLISHED`.
  * **Assertions:**
    - `InjectLevelCrossOnly()` -> `AssertEqual(BreakState, BREAK_CANDIDATE)`
    - `InjectCalibratedDisplacement(fixture_config)` -> `AssertEqual(BreakState, BREAK_CONFIRMED)`
    - `InjectCalibratedPersistenceBars(fixture_config)` -> `AssertEqual(BreakState, BREAK_ESTABLISHED)`

---

## Phase 3 — Behavioral State (Flow, PDE, Regime, Role, Location)

### 3.1 Pullback Detection & Micro-Pullback Exception Handling
* **Test Name:** `test_m1_micro_pullback_not_treated_as_primary_pullback` (AGENTS.md Invariant #25, #26)
  * **Objective:** Ensure an M1 micro pullback cannot masquerade as a primary opportunity without an explicit setup exception.
  * **Assertions:**
    - `CreatePullback(timeframe="1M", tier="MICRO")`
    - `AssertFalse(OpportunityEngine.IsPrimaryOpportunity(m1_pullback))`
    - `AssertEqual(m1_pullback.primary_entry_allowed, FALSE)`

### 3.2 PDE Cannot Issue Direct Broker Orders
* **Test Name:** `test_pde_cannot_call_ordersend` (AGENTS.md Invariant #3)
  * **Objective:** Confirm PDE has no interface connection to MT5 `OrderSend`.
  * **Assertions:**
    - `AssertFalse(HasAttribute(PDEEngine, "OrderSend"))`
    - `AssertFalse(HasAttribute(PDEEngine, "mt5_gateway"))`

---

## Phase 4 — Opportunity & Tradeability Authorization

### 4.1 Mandatory Validity Gates
* **Test Name:** `test_confidence_score_cannot_bypass_invalid_gate` (AGENTS.md Invariant #9, #10)
  * **Objective:** Verify that an opportunity failing a mandatory validity gate (e.g. `FAIL_SPREAD`) cannot be authorized even if `Confidence = 1.0`.
  * **Assertions:**
    - `SetOpportunityConfidence(1.0)`
    - `SetSpread(ExcessiveSpreadFixture(fixture_config))` -> `Tradeability = FAIL_SPREAD`
    - `AssertFalse(DecisionAuthorization.Authorize(opportunity))`

---

## Phase 5 — Protection & Allocation (News, Risk, Portfolio)

### 5.1 News Lockdown Protection
* **Test Name:** `test_news_lockdown_blocks_new_exposure` (AGENTS.md Invariant #20)
  * **Objective:** Ensure zero strategic new orders are authorized during `NEWS_LOCKDOWN`.
  * **Assertions:**
    - `SetNewsState(NEWS_LOCKDOWN)`
    - `AssertEqual(NewsShield.CanOpenNewExposure(), FALSE)`
    - `AssertEqual(TradeDecision.authorized, FALSE)`

### 5.2 Stop Loss Never Loosened
* **Test Name:** `test_news_and_risk_overlays_never_loosen_stop` (AGENTS.md Invariant #19)
  * **Objective:** Ensure protective stops are strictly tightened or maintained, never widened.
  * **Assertions:**
    - `SetExistingStop(Long, 1.0800)`
    - `CalculateNewsStop(Long, 1.0750)` -> Wider stop proposed
    - `AssertEqual(NewsShield.ComputeFinalStop(Long, 1.0800, 1.0750), 1.0800)`

### 5.3 Currency Exposure & Portfolio Arbitration
* **Test Name:** `test_portfolio_currency_exposure_concentration_limits` (AGENTS.md Invariant #37)
  * **Objective:** Verify that correlated multi-pair entries (e.g., EURUSD Long + GBPUSD Long + USDCHF Short) are rejected or deferred when total USD short exposure cap is exceeded.
  * **Assertions:**
    - `EstablishExposure("USD", -10.0_lots)`
    - `SubmitOpportunity("GBPUSD", "LONG")` -> USD short exposure increased
    - `AssertEqual(PortfolioArbitration.Arbitrate(opportunity), REJECT)`

---

## Phase 6 — MT5 Execution Gateway & Reconciliation

### 6.1 Execution Idempotency & Pre-Submit Checks
* **Test Name:** `test_execution_pre_submit_state_revalidation`
  * **Objective:** Confirm execution layer re-reads latest state immediately prior to submission; aborts if state changed.
  * **Assertions:**
    - `StageTradeDecision(decision_id)`
    - `MutateState(NewsState = NEWS_LOCKDOWN)`
    - `AssertEqual(ExecutionGateway.Submit(decision_id), ABORT_STATE_CHANGED)`
    - `AssertEqual(mt5_gateway.orders_sent, 0)`

### 6.2 Execution Intent Idempotency on UNKNOWN Execution
* **Test Name:** `test_unknown_execution_never_retried_without_reconciliation`
  * **Objective:** Confirm an execution intent in `UNKNOWN` state triggers broker reconciliation by `client_order_id` rather than duplicate order submission.
  * **Assertions:**
    - `SetExecutionIntentStatus(intent_id, UNKNOWN)`
    - `AssertRaises(ExecutionIdempotencyException, ExecutionGateway.RetrySubmit(intent_id))`
    - `AssertTrue(ReconciliationEngine.IsReconciliationPending(intent_id))`

### 6.3 Reconciliation after Disconnect / Restart
* **Test Name:** `test_reconciliation_completes_before_strategy_authorization` (AGENTS.md Invariant #40)
  * **Objective:** Ensure system blocks new strategy authorization after restart until broker position matching and quarantine checks complete.
  * **Assertions:**
    - `TriggerSystemRestart()`
    - `AssertFalse(StrategyEngine.IsAuthorizedToTrade())`
    - `RunReconciliation()`
    - `AssertTrue(StrategyEngine.IsAuthorizedToTrade())`

---

## Phase 7 — Position Management, Trailing & TTL Decay

### 7.1 Structural Trailing Ratchet Only
* **Test Name:** `test_structural_trailing_ratchets_only`
  * **Objective:** Confirm trailing stops move only in the direction of profit protection.
  * **Assertions:**
    - `SetTrailStop(Long, 1.0850)`
    - `InjectLowerStructure(1.0820)`
    - `AssertEqual(PositionManagement.UpdateStop(Long, 1.0850, 1.0820), 1.0850)`

### 7.2 Trade TTL Expiry
* **Test Name:** `test_trade_ttl_forced_exit_on_expiry` (AGENTS.md Invariant #36)
  * **Objective:** Verify position triggers orderly protective closure when TTL trade decay reaches `EXPIRED`.
  * **Assertions:**
    - `InjectTimeElapsed(ttl_duration + 1_ns)`
    - `AssertEqual(TTLDecayEngine.GetState(), EXPIRED)`
    - `AssertEqual(PositionManagement.GetAction(), CLOSE_POSITION)`

---

## Phase 8 — Research, Replay & Adversarial Suite

### 8.1 Anti-Lookahead Research Integrity
* **Test Name:** `test_research_feature_store_no_lookahead` (AGENTS.md Invariant #23, #24)
  * **Objective:** Verify backtest decision at time `t` uses strictly data timestamped `<= t`.
  * **Assertions:**
    - `RunBacktestStep(t)`
    - `AssertTrue(FeatureStore.MaxTimestamp() <= t)`
