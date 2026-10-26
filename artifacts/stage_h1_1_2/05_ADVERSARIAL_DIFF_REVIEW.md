# Stage H.1.1.2 — Adversarial Diff Review & Scope Audit

**Timestamp:** 2026-10-26T21:11:00Z  
**Base Commit:** `3d29ea886b557439268b41c414848dfeb8c6014a`  
**Current Working Ref:** `work/stage-h1-1-2-remediation-20261026`  

---

## 1. Scope Boundary Certification

Every modified file and diff block was audited for strict compliance with the Stage H.1.1.2 remediation scope:
1. Did the change expand scope beyond Findings A, B, and C? **NO.**
2. Did the change weaken any existing Stage H.1 / H.1.1 guarantees? **NO.**
3. Are all new types and parameters backwards-compatible with existing consumers? **YES.**

---

## 2. File-by-File Diff Audit

### 1. `control_surface/package.json`
- **Diff:** Updated `"build": "vite build"` to `"build": "NODE_ENV=production vite build"`.
- **Rationale:** Ensures Vite consistently builds client bundles in production mode regardless of container environment defaults, enabling compile-time dead-code elimination of `import.meta.env.DEV`.

### 2. `control_surface/src/types.ts`
- **Diff:**
  - Expanded `ActionType` to include `'add_size' | 'scale_in'`.
  - Added `'PRODUCTION_RISK_GATE'` to `CommandExecutionRecord.source`.
- **Rationale:** Strongly types risk-increasing modifications and explicit authority gate rejections.

### 3. `control_surface/src/types/contracts.ts`
- **Diff:** Expanded `IntentFingerprint.actionType` to include `'ADD_SIZE' | 'SCALE_IN'`.
- **Rationale:** Ensures intent records match supported execution actions.

### 4. `control_surface/src/utils/riskValidator.ts`
- **Diff:**
  - Updated `validatePositionModification` signature to accept `portfolioPositions?: Position[]`.
  - Added gating: if `action === 'add_size' || action === 'scale_in'`, evaluates `evaluatePortfolioRisk(portfolioPositions)`. Rejects fail-closed if portfolio status !== `'VALID'` or if total risk >= `maxAccountExposureR`.
  - Preserved de-risking actions (`tighten_stop`, `move_to_breakeven`, `close_position`) as unconditionally allowed.
- **Rationale:** Implements the core production authorization boundary check for Finding A.

### 5. `control_surface/src/utils/idempotency.ts`
- **Diff:** Updated `createIntentFingerprint` and `computePayloadFingerprint` to type `actionType` as `IntentFingerprint['actionType']`.
- **Rationale:** Eliminates type narrowing mismatch when generating fingerprints for `ADD_SIZE` / `SCALE_IN`.

### 6. `control_surface/src/utils/keyboard.ts`
- **Diff:** In `isSafeKeyboardShortcutTarget`, added defensive guard `typeof target.getAttribute === 'function'`.
- **Rationale:** Prevents TypeError when keydown events are dispatched at non-Element targets (`window`/`document` in JSDOM).

### 7. `control_surface/src/App.tsx`
- **Diff:**
  - Added state refs (`positionsRef`, `riskConfigRef`, `confirmModalRef`, etc.) to guarantee latest state access.
  - In `handleConfirmAction`, inserted pre-submission gate calling `validatePositionModification`. If rejected, updates `activeCommand`, audit trail (`REJECTED_FAIL_CLOSED`), system event, and exits with ZERO dispatch.
  - Guarded test seam with `if (import.meta.env.DEV && testRef)`.
  - Added keyboard shortcut `+` / `=` for `add_size`.
- **Rationale:** Implements production authorization enforcement (Finding A) and test-seam elimination (Finding B).

### 8. `control_surface/src/components/ConfirmDialog.tsx`
- **Diff:** Added modal title, route, and detail text for `add_size` and `scale_in`; added `data-testid="confirm-dialog-confirm"` to confirm button.
- **Rationale:** Full production UI rendering for scale-in actions and clean testability.

### 9. `control_surface/src/components/ContextPanel.tsx`
- **Diff:** Added "Add size (+50%)" action button with `data-testid="context-btn-add-size"`.
- **Rationale:** Provides production UI interaction point for risk-increasing actions.

### 10. `control_surface/src/providers/SimulationProvider.ts`
- **Diff:** Added size scaling handler for `ADD_SIZE` / `SCALE_IN`; exposed `getSimulatedIntents()`.
- **Rationale:** Allows simulation sandbox execution when authorized, and verification that zero commands reach provider when rejected.

### 11. `control_surface/src/tests/stage_h1_1_production_path.test.ts`
- **Diff:** Added Section 5 adversarial test suite (`H1.1.2-AUTH-01` through `H1.1.2-AUTH-06` and `H1.1.2-SEAM-01`).
- **Rationale:** Full adversarial proof of all 6 cases and test seam isolation.
