# FRACTAL-FLOW — Stage H.1.1.3 State Consistency Evidence

## 1. Overview of State Guarantees

In accordance with:
- `HPL-H1.1.3-STATE-01`: Position mutations and allocated-risk semantics remain strictly consistent across the lifecycle.
- `HPL-H1.1.3-STATE-02`: Rejected actions cause zero unauthorized partial state mutation.
- `HPL-H1.1.3-RISK-07`: Position modifications cannot understate, double-count, or silently discard risk.

---

## 2. In-Memory Sandbox & React State Synchronization

### 2.1 Provider-Level Allocation Update
In `src/providers/SimulationProvider.ts`:
```typescript
} else if (intent.actionType === 'ADD_SIZE' || intent.actionType === 'SCALE_IN') {
  if (targetIdx >= 0) {
    this.positions[targetIdx].size = Number((this.positions[targetIdx].size * 1.5).toFixed(2));
    if (typeof this.positions[targetIdx].allocatedRiskR === 'number') {
      this.positions[targetIdx].allocatedRiskR = Number(
        (this.positions[targetIdx].allocatedRiskR * 1.5).toFixed(4)
      );
    }
  }
}
```
When size is increased by 50% (scaling factor 1.5), `allocatedRiskR` is scaled by 1.5 synchronously in sandbox memory.

### 2.2 React Ref State Freshness
In `src/App.tsx`:
- `positionsRef.current` and `riskConfigRef.current` mirror the latest state on every render, eliminating stale closures.
- `simulationProvider.setPositions(currentPositions)` is called immediately prior to `simulationProvider.submitCommand(intent)` to ensure the sandbox memory reflects authoritative state.
- Upon completion, `const updatedPositions = await simulationProvider.getPositions(); setPositions(updatedPositions);` updates React state, triggering recalculation of `portfolioRiskEval` and the DOM KPIs.

---

## 3. Sequential Multi-Operation Verification (`H1.1.3-AUTH-06`)

To prove that post-action risk metadata is updated and authoritative for subsequent operations:
1. **Initial Condition:**
   - Single position `pos_seq`: `size = 0.80`, `allocatedRiskR = 0.80 R`.
   - Account exposure cap: `1.5000 R`.
   - Total current risk: `0.8000 R`.
2. **First Operation (`add_size` #1):**
   - Delta: `+0.4000 R`.
   - Projected exposure: `0.8000 R + 0.4000 R = 1.2000 R <= 1.5000 R` (Authorized).
   - Execution: Confirmed and submitted to provider.
   - Result:
     - `pos_seq.size` scaled from `0.80` to `1.20`.
     - `pos_seq.allocatedRiskR` scaled from `0.80` to `1.20`.
     - `handle.getOpenRiskR()` updated from `0.8 R` to `1.2 R`.
3. **Second Operation (`add_size` #2):**
   - Evaluated against authoritative updated state (`allocatedRiskR = 1.20 R`, `openRiskR = 1.20 R`).
   - Incremental delta: `+50% of 1.20 R = +0.6000 R`.
   - Projected exposure: `1.2000 R + 0.6000 R = 1.8000 R > 1.5000 R` cap.
   - Execution: **REJECTED fail-closed**.
   - Result:
     - `activeCommand.status`: `'REJECTED'`
     - Provider simulated intent count: Unchanged (1 intent total).
     - `pos_seq.allocatedRiskR`: Remains exactly `1.20 R` (zero mutation).
     - `pos_seq.size`: Remains exactly `1.20` (zero mutation).

---

## 4. Rejection Zero-Side-Effect Invariant (`H1.1.3-STATE-02`)

For every rejected modification class:
1. `provider.getSimulatedIntents().size` does not increment.
2. `JSON.stringify(positions)` matches pre-action snapshot bit-for-bit.
3. No intent fingerprint is created for submission.
4. Downstream `liveCommandAdapter` receives zero invocations.
5. Audit trail records `outcome: 'REJECTED_FAIL_CLOSED'`.
