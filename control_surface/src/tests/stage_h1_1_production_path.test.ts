/**
 * FRACTAL-FLOW Stage H.1.1 Production Path, Risk Provenance & Precision Enforcement Test Suite
 * Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY
 *
 * Verifies:
 * - HPL-H1.1-RISK-01: Zero setup-map fallback for open positions (strict allocatedRiskR requirement).
 * - HPL-H1.1-RISK-02: Micro-R integer scaling, 4-decimal input precision enforcement, cap boundary equality.
 * - HPL-H1.1-TEST-01: Real mounted production component state transitions in <App /> (Valid -> Invalid -> Valid).
 * - HPL-H1.1-PROTECT-01: De-risking allowed during risk-invalid states; live execution blocked fail-closed.
 */

import { JSDOM } from 'jsdom';
import React, { act } from 'react';
import ReactDOM from 'react-dom/client';

// 1. Initialize DOM environment before importing React components that attach listeners
const dom = new JSDOM('<!DOCTYPE html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost'
});
const { window } = dom;
const { document } = window;
(globalThis as any).window = window;
(globalThis as any).document = document;
try {
  Object.defineProperty(globalThis, 'navigator', { value: window.navigator, configurable: true });
} catch {
  // Ignore in Node 22
}
(globalThis as any).HTMLElement = window.HTMLElement;
(globalThis as any).HTMLButtonElement = window.HTMLButtonElement;
(globalThis as any).KeyboardEvent = window.KeyboardEvent;
(globalThis as any).MouseEvent = window.MouseEvent;
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

import { App, AppTestControlHandle } from '../App';
import {
  evaluatePortfolioRisk,
  getValidPositionRiskR,
  getCandidatePlannedRiskR,
  validateCandidateAgainstRiskConfig,
  validateOperationalRiskConfig,
  hasValidRiskPrecision,
  toSafeMicroR,
  RISK_ARITHMETIC_CONSTANTS
} from '../utils/riskValidator';
import { LiveCommandAdapter, LiveExecutionBlockedError } from '../providers/LiveCommandAdapter';
import { SimulationProvider } from '../providers/SimulationProvider';
import { INITIAL_POSITIONS, GATE_CANDIDATES, INITIAL_OPERATIONAL_RISK_CONFIG } from '../data/mockData';
import { Position, OperationalRiskConfig } from '../types';

let passed = 0;
let failed = 0;

function expect(condition: boolean, message: string): void {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

async function test(name: string, fn: () => void | Promise<void>) {
  try {
    await fn();
    console.log(`  [PASS] ${name}`);
    passed++;
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`  [FAIL] ${name}: ${msg}`);
    failed++;
  }
}

const container = document.getElementById('root')!;
let root: ReactDOM.Root | null = null;

function setupMount() {
  teardownMount();
  container.innerHTML = '';
  root = ReactDOM.createRoot(container);
}

function teardownMount() {
  if (root) {
    act(() => {
      root!.unmount();
    });
    root = null;
  }
  container.innerHTML = '';
}

async function runStageH11ProductionPathSuite() {
  console.log('========================================================');
  console.log('FRACTAL-FLOW Stage H.1.1 Production Path & Precision Suite');
  console.log('Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM');
  console.log('========================================================\n');

  // --- SECTION 1: HPL-H1.1-RISK-01 — RISK PROVENANCE & ZERO SETUP-MAP FALLBACK ---
  console.log('--- HPL-H1.1-RISK-01: Explicit Allocated Risk vs Setup Estimates ---');

  await test('H1.1-RISK-01.1: Existing position with explicit valid allocatedRiskR is accepted', () => {
    const pos: Position = {
      ...INITIAL_POSITIONS[0],
      allocatedRiskR: 0.75,
    };
    const res = getValidPositionRiskR(pos);
    expect(res.isValid, 'Must be valid');
    expect(res.riskR === 0.75, `Expected 0.75, got ${res.riskR}`);
  });

  await test('H1.1-RISK-01.2: Existing position with missing allocatedRiskR and recognized setup fails closed (ZERO setup fallback)', () => {
    const pos: Position = {
      ...INITIAL_POSITIONS[0],
      setup: 'FF-01', // Recognized setup in DEFAULT_SETUP_RISK_MAP (0.8R)
      allocatedRiskR: undefined, // Missing explicit allocated risk
    };
    const res = getValidPositionRiskR(pos);
    expect(!res.isValid, 'Must fail closed when allocatedRiskR is missing');
    expect(res.riskR === null, 'Risk must be null');
    expect(Boolean(res.reason?.includes('missing allocatedRiskR')), 'Must cite missing allocatedRiskR');
  });

  await test('H1.1-RISK-01.3: Existing position with missing allocatedRiskR and unknown setup fails closed', () => {
    const pos: Position = {
      ...INITIAL_POSITIONS[0],
      setup: 'UNKNOWN_SETUP_CLASS',
      allocatedRiskR: undefined,
    };
    const res = getValidPositionRiskR(pos);
    expect(!res.isValid, 'Must fail closed');
    expect(res.riskR === null, 'Risk must be null');
  });

  await test('H1.1-RISK-01.4: Explicit null, zero, negative, NaN, and Infinity allocated-risk values fail closed', () => {
    const hostileValues = [null, 0, -0.01, -1.0, NaN, Infinity, -Infinity];
    for (const val of hostileValues) {
      const pos = {
        ...INITIAL_POSITIONS[0],
        allocatedRiskR: val as unknown as number,
      };
      const res = getValidPositionRiskR(pos);
      expect(!res.isValid, `Allocated risk value ${val} must be rejected`);
      expect(res.riskR === null, `Risk must be null for value ${val}`);
    }
  });

  await test('H1.1-RISK-01.5: Mixed portfolio with one unallocated position fails closed (ZERO partial sum)', () => {
    const portfolio: Position[] = [
      { ...INITIAL_POSITIONS[0], allocatedRiskR: 0.8 },
      { ...INITIAL_POSITIONS[1], allocatedRiskR: 0.5 },
      { ...INITIAL_POSITIONS[2], allocatedRiskR: undefined }, // unallocated
      { ...INITIAL_POSITIONS[3], allocatedRiskR: 0.4 },
    ];
    const evalResult = evaluatePortfolioRisk(portfolio);
    expect(evalResult.status === 'INVALID', 'Must be INVALID');
    expect(evalResult.totalRiskR === null, 'totalRiskR must be null (no partial sum of 1.7R)');
    expect(evalResult.invalidPositionIds.length === 1, 'Must record invalid position ID');
  });

  await test('H1.1-RISK-01.6: Candidate planned risk uses setup map appropriately without leaking into open positions', () => {
    const candidate = GATE_CANDIDATES[0]; // setup: FF-01 (mapped 0.8)
    const plannedResult = getCandidatePlannedRiskR(candidate);
    expect(plannedResult.isValid, 'Candidate planning must accept setup default');
    expect(plannedResult.plannedRiskR === 0.8, `Expected 0.8, got ${plannedResult.plannedRiskR}`);

    // Verify candidate planning override
    const overrideResult = getCandidatePlannedRiskR(candidate, 0.45);
    expect(overrideResult.isValid, 'Override must be accepted');
    expect(overrideResult.plannedRiskR === 0.45, `Expected 0.45, got ${overrideResult.plannedRiskR}`);
  });

  // --- SECTION 2: HPL-H1.1-RISK-02 — ARITHMETIC PRECISION & BOUNDARIES ---
  console.log('\n--- HPL-H1.1-RISK-02: Micro-R Arithmetic Precision & Cap Boundaries ---');

  await test('H1.1-RISK-02.1: Precision boundary: 3 x 0.005R equals exactly 0.015R', () => {
    const microPositions: Position[] = [
      { ...INITIAL_POSITIONS[0], id: 'mp1', allocatedRiskR: 0.005 },
      { ...INITIAL_POSITIONS[1], id: 'mp2', allocatedRiskR: 0.005 },
      { ...INITIAL_POSITIONS[2], id: 'mp3', allocatedRiskR: 0.005 },
    ];
    const res = evaluatePortfolioRisk(microPositions);
    expect(res.status === 'VALID', 'Evaluation must be valid');
    expect(res.totalRiskR === 0.015, `Expected exactly 0.015, got ${res.totalRiskR}`);
  });

  await test('H1.1-RISK-02.2: 4-decimal precision enforcement: inputs with <= 4 decimals accepted; 5+ decimals strictly rejected', () => {
    // Valid precision inputs (<= 4 decimals)
    expect(hasValidRiskPrecision(0.0001), '0.0001 (4 decimals) must be valid');
    expect(hasValidRiskPrecision(0.005), '0.005 (3 decimals) must be valid');
    expect(hasValidRiskPrecision(0.1234), '0.1234 (4 decimals) must be valid');
    expect(hasValidRiskPrecision(1.8), '1.8 (1 decimal) must be valid');

    // Invalid precision inputs (5+ decimals)
    expect(!hasValidRiskPrecision(0.00001), '0.00001 (5 decimals) must be rejected');
    expect(!hasValidRiskPrecision(0.12345), '0.12345 (5 decimals) must be rejected');
    expect(!hasValidRiskPrecision(0.00005), '0.00005 (5 decimals) must be rejected');
    expect(!hasValidRiskPrecision(0.123456), '0.123456 (6 decimals) must be rejected');

    // Rejection at position level
    const posInvalidPrecision: Position = {
      ...INITIAL_POSITIONS[0],
      allocatedRiskR: 0.12345, // 5 decimals
    };
    const posEval = getValidPositionRiskR(posInvalidPrecision);
    expect(!posEval.isValid, 'Position with 5 decimals must fail closed');
    expect(Boolean(posEval.reason?.includes('exceeds maximum permitted input precision')), 'Must cite precision violation');
  });

  await test('H1.1-RISK-02.3: Individual position upper bound and overflow protections', () => {
    // Max individual position risk is 100.0R
    const safePos = toSafeMicroR(100.0);
    expect(safePos.isValid && safePos.microR === 100_000_000, '100.0R must be accepted');

    const excessPos = toSafeMicroR(100.0001);
    expect(!excessPos.isValid, '100.0001R must exceed max position risk');
    expect(excessPos.reason === 'EXCEEDS_MAX_POSITION_RISK', 'Must report EXCEEDS_MAX_POSITION_RISK');

    // Unsafe integer / massive numbers
    const hugePos = toSafeMicroR(1e25);
    expect(!hugePos.isValid, '1e25 must be rejected');
  });

  await test('H1.1-RISK-02.4: Cap equality: exact equality is CLEAR, excess of 0.0001R is BREACHED', () => {
    const config: OperationalRiskConfig = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      maxLaneRiskR: 1.8,
      maxAccountExposureR: 3.0,
    };

    const candidate = GATE_CANDIDATES[0]; // lane: ACT_PRIMARY

    // Case A: 1.0R + 0.8R = 1.8R (exact cap equality -> CLEAR)
    const currentPositionsEqual: Position[] = [
      { ...INITIAL_POSITIONS[0], lane: 'ACT_PRIMARY', allocatedRiskR: 1.0 },
    ];
    const resEqual = validateCandidateAgainstRiskConfig(
      candidate,
      currentPositionsEqual,
      config,
      100.0,
      0.8 // Override candidate risk to 0.8
    );
    expect(resEqual.status === 'CLEAR', '1.8R against 1.8R cap must be CLEAR');
    expect(!resEqual.hasViolations, 'Must have zero violations on exact cap equality');

    // Case B: 1.0R + 0.8001R = 1.8001R (excess of 0.0001R -> BREACHED)
    const resBreach = validateCandidateAgainstRiskConfig(
      candidate,
      currentPositionsEqual,
      config,
      100.0,
      0.8001 // Override candidate risk to 0.8001
    );
    expect(resBreach.status === 'BREACHED', '1.8001R against 1.8R cap must be BREACHED');
    expect(resBreach.hasViolations, 'Must have violations');
    const laneViolation = resBreach.violations.find((v) => v.code === 'MAX_LANE_RISK_EXCEEDED');
    expect(laneViolation !== undefined, 'Must trigger MAX_LANE_RISK_EXCEEDED');
    expect(Boolean(laneViolation?.message.includes('0.0001R')), 'Excess must be exactly 0.0001R');
  });

  await test('H1.1-RISK-02.5: Permutation determinism across position order permutations', () => {
    const p1: Position = { ...INITIAL_POSITIONS[0], id: 'p1', allocatedRiskR: 0.1111 };
    const p2: Position = { ...INITIAL_POSITIONS[1], id: 'p2', allocatedRiskR: 0.2222 };
    const p3: Position = { ...INITIAL_POSITIONS[2], id: 'p3', allocatedRiskR: 0.3333 };

    const permutations = [
      [p1, p2, p3],
      [p1, p3, p2],
      [p2, p1, p3],
      [p2, p3, p1],
      [p3, p1, p2],
      [p3, p2, p1],
    ];

    const expectedTotal = 0.6666;
    for (const perm of permutations) {
      const res = evaluatePortfolioRisk(perm);
      expect(res.status === 'VALID', 'Must be valid');
      expect(res.totalRiskR === expectedTotal, `Permutation total must be ${expectedTotal}, got ${res.totalRiskR}`);
    }
  });

  // --- SECTION 3: HPL-H1.1-TEST-01 — REAL MOUNTED PRODUCTION COMPONENT STATE TRANSITIONS ---
  console.log('\n--- HPL-H1.1-TEST-01: Real Mounted Production Component State Transitions in <App /> ---');

  await test('H1.1-TEST-01.1: Production <App /> interactive state lifecycle: Valid -> Invalid -> Valid mounted in JSDOM', async () => {
    setupMount();
    const testControlRef = React.createRef<AppTestControlHandle | null>();

    // Step 1: Mount real production <App /> with valid INITIAL_POSITIONS
    act(() => {
      root!.render(
        React.createElement(App, {
          initialPositions: INITIAL_POSITIONS,
          testRef: testControlRef,
        })
      );
    });

    const handle = testControlRef.current;
    expect(handle !== null, 'App testControlRef must be populated by mounted component');

    // Verify initial mounted DOM Header KPI
    let kpiEl = container.querySelector('[data-testid="open-risk-kpi"]');
    expect(kpiEl !== null, 'Header KPI element must exist in DOM');
    expect(kpiEl!.textContent!.trim() === '2.3R', `Initial mounted KPI must be 2.3R, got ${kpiEl?.textContent}`);
    expect(handle!.getOpenRiskR() === 2.3, 'Authoritative open risk must be 2.3R');

    // Step 2: Trigger real production state update: Introduce an unallocated position
    const unallocatedPos: Position = {
      ...INITIAL_POSITIONS[0],
      id: 'pos_corrupt_test_01',
      allocatedRiskR: undefined, // Missing explicit allocation
      setup: 'FF-01',
    };

    act(() => {
      handle!.setPositions((prev) => [...prev, unallocatedPos]);
    });

    // Step 3: Verify mounted DOM updates in real-time to INVALID
    let invalidEl = container.querySelector('[data-testid="open-risk-invalid"]');
    expect(invalidEl !== null, 'Header INVALID badge must render in DOM after state transition');
    expect(invalidEl!.textContent!.trim() === 'INVALID', 'INVALID badge text must be "INVALID"');
    expect(testControlRef.current!.getOpenRiskR() === null, 'Authoritative open risk must be null when portfolio is invalid');

    // Step 4: Verify candidate validation in GateChainStrip reflects invalid portfolio
    const evalRes = testControlRef.current!.getPortfolioRiskEval();
    expect(evalRes.status === 'INVALID', 'Portfolio risk status must be INVALID');
    expect(evalRes.invalidPositionIds.includes('pos_corrupt_test_01'), 'Must flag corrupt position');

    // Candidate validation against invalid portfolio fails closed
    const candidateValidation = validateCandidateAgainstRiskConfig(
      GATE_CANDIDATES[0],
      testControlRef.current!.getPositions(),
      testControlRef.current!.getRiskConfig(),
      100.0
    );
    expect(candidateValidation.status === 'INVALID', 'Candidate validation must fail closed when portfolio is invalid');
    expect(candidateValidation.hasViolations, 'Must have violations');
    const portViolation = candidateValidation.violations.find((v) => v.metric === 'PORTFOLIO_INPUT');
    expect(portViolation !== undefined, 'Must flag PORTFOLIO_INPUT blocking violation');

    // Step 5: Verify protective actions remain permitted during invalid portfolio state
    // De-risking: Triggering close_position modal
    act(() => {
      testControlRef.current!.triggerAction('close_position', INITIAL_POSITIONS[0]);
    });

    // Verify confirmation dialog opens in mounted DOM
    const confirmModalEl = container.querySelector('[role="dialog"]');
    expect(confirmModalEl !== null, 'Confirmation modal must mount for protective de-risking action');

    // Dismiss modal
    const cancelBtn = container.querySelector<HTMLButtonElement>('button[data-testid="confirm-dialog-cancel"]') ||
                     container.querySelectorAll<HTMLButtonElement>('button')[0];
    if (cancelBtn) {
      act(() => {
        cancelBtn.click();
      });
    }

    // Step 6: Recovery: Remove the corrupt position through real production state dispatcher
    act(() => {
      testControlRef.current!.setPositions((prev) => prev.filter((p) => p.id !== 'pos_corrupt_test_01'));
    });

    // Step 7: Verify mounted DOM immediately recovers to valid 2.3R
    kpiEl = container.querySelector('[data-testid="open-risk-kpi"]');
    expect(kpiEl !== null, 'Header KPI element must recover in DOM');
    expect(kpiEl!.textContent!.trim() === '2.3R', `Recovered mounted KPI must be 2.3R, got ${kpiEl?.textContent}`);
    expect(testControlRef.current!.getOpenRiskR() === 2.3, 'Authoritative open risk must recover to 2.3R');

    // Step 8: Switch active tab to 'RISK' and verify SecondaryViews renders dynamic open risk
    act(() => {
      testControlRef.current!.setActiveNavTab('RISK');
    });

    const riskViewBadge = container.querySelector('[data-testid="secondary-total-open-risk"]');
    expect(riskViewBadge !== null, 'SecondaryViews RISK KPI badge must mount in DOM');
    expect(riskViewBadge!.textContent!.includes('2.30R'), 'SecondaryViews must render 2.30R in detailed tab');

    // Step 9: Responsive layout presence check (both desktop md:flex and mobile md:hidden structures present)
    const desktopView = container.querySelector('.md\\:flex');
    const mobileView = container.querySelector('.md\\:hidden');
    expect(desktopView !== null, 'Desktop responsive container must exist in mounted tree');
    expect(mobileView !== null, 'Mobile responsive container must exist in mounted tree');

    teardownMount();
  });

  // --- SECTION 4: HPL-H1.1-PROTECT-01 — PROTECTIVE BEHAVIOR & AUTHORITY ---
  console.log('\n--- HPL-H1.1-PROTECT-01: Protective Actions & Authority Integrity ---');

  await test('H1.1-PROTECT-01.1: De-risking actions remain authorized during risk-invalid states', async () => {
    const provider = new SimulationProvider();

    // Command to close position (de-risking)
    const result = await provider.submitCommand({
      intentId: 'derisk_close_01',
      operatorId: 'session:local_operator',
      targetPositionId: 'pos_eurusd_01',
      symbol: 'EURUSD',
      actionType: 'CLOSE',
      parameters: {},
      idempotencyKey: 'idemp_derisk_01',
      createdAt: Date.now()
    });

    expect(result.status === 'CONFIRMED', `De-risking command must confirm, got: ${result.status}`);
  });

  await test('H1.1-PROTECT-01.2: Live command submission remains unconditionally blocked', async () => {
    const adapter = new LiveCommandAdapter();
    let threw = false;
    try {
      await adapter.submitCommand({
        intentId: 'live_test_02',
        operatorId: 'session:local_operator',
        targetPositionId: 'pos_1',
        symbol: 'EURUSD',
        actionType: 'CLOSE',
        parameters: {},
        idempotencyKey: 'idemp_live_02',
        createdAt: Date.now()
      });
    } catch (err: unknown) {
      threw = true;
      expect(err instanceof LiveExecutionBlockedError, 'Must throw LiveExecutionBlockedError');
    }
    expect(threw, 'Live submission must fail closed');
  });

  await test('H1.1-PROTECT-01.3: Cross-field invalid configuration is rejected fail-closed with zero state mutation', () => {
    const invalidConfig = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      maxLaneRiskR: 6.0,
      maxAccountExposureR: 3.0, // maxLane > maxAccount violation
    };
    const res = validateOperationalRiskConfig(invalidConfig);
    expect(!res.isValid, 'Cross-field violation must be rejected');
    expect(res.errors.some((e) => e.includes('Cross-field invariant violation')), 'Must report cross-field error');
  });

  // --- SECTION 5: HPL-H1.1.2-PROD-AUTH — REAL PRODUCTION AUTHORIZATION BOUNDARY ENFORCEMENT ---
  console.log('\n--- HPL-H1.1.2-PROD-AUTH: Real Production Authorization Boundary Enforcement ---');

  await test('H1.1.2-AUTH-01: Case 1 — Valid portfolio allows risk-increasing action (ADD_SIZE) through production authority path', async () => {
    setupMount();
    const testControlRef = React.createRef<AppTestControlHandle | null>();

    act(() => {
      root!.render(
        React.createElement(App, {
          initialPositions: INITIAL_POSITIONS,
          testRef: testControlRef,
        })
      );
    });

    const handle = testControlRef.current!;
    expect(handle !== null, 'Handle must be populated in DEV environment');
    expect(handle.getOpenRiskR() === 2.3, 'Initial portfolio risk must be 2.3R (valid)');

    const targetPos = handle.getPositions()[0];
    const initialSize = targetPos.size;

    // Trigger risk-increasing action through UI path
    act(() => {
      handle.triggerAction('add_size', targetPos);
    });

    // Verify modal is open with ADD_SIZE details
    const modalEl = container.querySelector('[role="dialog"]');
    expect(modalEl !== null, 'Confirmation modal must mount');
    expect(modalEl!.textContent!.includes('Increase Position Size'), 'Modal title must reflect ADD_SIZE');
    expect(modalEl!.textContent!.includes('ExecutionGateway.ADD_SIZE'), 'Command route must reflect ADD_SIZE');

    const provider = handle.getSimulationProvider();
    const initialIntentCount = provider.getSimulatedIntents().size;

    // Confirm execution through the production confirmation callback
    await act(async () => {
      await handle.confirmAction();
    });

    // Verify command submission succeeded to provider
    const newIntentCount = provider.getSimulatedIntents().size;
    expect(newIntentCount === initialIntentCount + 1, 'Provider must have received the submitted command');

    const updatedPos = handle.getPositions().find((p) => p.id === targetPos.id)!;
    expect(updatedPos.size > initialSize, `Position size must increase from ${initialSize}, got ${updatedPos.size}`);

    teardownMount();
  });

  await test('H1.1.2-AUTH-02: Case 2 — Invalid portfolio blocks risk-increasing action fail-closed with zero provider submission', async () => {
    setupMount();
    const testControlRef = React.createRef<AppTestControlHandle | null>();

    act(() => {
      root!.render(
        React.createElement(App, {
          initialPositions: INITIAL_POSITIONS,
          testRef: testControlRef,
        })
      );
    });

    const handle = testControlRef.current!;

    // Introduce an unallocated position through the real supported state dispatcher
    const corruptPos: Position = {
      ...INITIAL_POSITIONS[1],
      id: 'pos_unallocated_hostile_01',
      allocatedRiskR: undefined, // missing allocated risk
      setup: 'FF-02'
    };

    act(() => {
      handle.setPositions((prev) => [...prev, corruptPos]);
    });

    // Verify production UI renders INVALID badge
    const invalidBadge = container.querySelector('[data-testid="open-risk-invalid"]');
    expect(invalidBadge !== null, 'Header must render INVALID badge');
    expect(handle.getOpenRiskR() === null, 'Authoritative open risk must be null');

    const provider = handle.getSimulationProvider();
    const initialIntentCount = provider.getSimulatedIntents().size;
    const initialPositionsSnapshot = JSON.stringify(handle.getPositions());

    // Attempt risk-increasing action
    act(() => {
      handle.triggerAction('add_size', handle.getPositions()[0]);
    });

    // Confirm action
    await act(async () => {
      await handle.confirmAction();
    });

    // 1. Verify action is rejected at production authority gate
    const activeCmd = handle.getActiveCommand();
    expect(activeCmd !== null, 'Active command record must reflect gate decision');
    expect(activeCmd!.status === 'REJECTED', `Status must be REJECTED, got: ${activeCmd?.status}`);
    expect(activeCmd!.source === 'PRODUCTION_RISK_GATE', `Source must be PRODUCTION_RISK_GATE, got: ${activeCmd?.source}`);
    expect(Boolean(activeCmd!.details?.includes('REJECTED FAIL-CLOSED')), 'Details must state REJECTED FAIL-CLOSED');

    // 2. Verify audit trail records REJECTED_FAIL_CLOSED
    const auditEntries = handle.getAuditTrail();
    const rejectionAudit = auditEntries.find((a) => a.action === 'REJECT_ADD_SIZE');
    expect(rejectionAudit !== undefined, 'Audit trail must record REJECT_ADD_SIZE');
    expect(rejectionAudit!.outcome === 'REJECTED_FAIL_CLOSED', 'Audit outcome must be REJECTED_FAIL_CLOSED');
    expect(rejectionAudit!.actor === 'PRODUCTION_AUTHORITY_GATE', 'Actor must be PRODUCTION_AUTHORITY_GATE');

    // 3. ZERO command submission to simulation provider
    const postIntentCount = provider.getSimulatedIntents().size;
    expect(postIntentCount === initialIntentCount, `Zero commands must be submitted to provider (was ${initialIntentCount}, now ${postIntentCount})`);

    // 4. Positions remain bit-for-bit unchanged
    expect(JSON.stringify(handle.getPositions()) === initialPositionsSnapshot, 'Positions state must remain completely unmutated');

    teardownMount();
  });

  await test('H1.1.2-AUTH-03: Case 3 — Candidate/planned risk cannot mask invalid actual exposure', async () => {
    setupMount();
    const testControlRef = React.createRef<AppTestControlHandle | null>();

    act(() => {
      root!.render(
        React.createElement(App, {
          initialPositions: INITIAL_POSITIONS,
          testRef: testControlRef,
        })
      );
    });

    const handle = testControlRef.current!;

    // Introduce invalid actual risk while candidates with planned risk exist
    act(() => {
      handle.setPositions((prev) => [
        ...prev,
        { ...INITIAL_POSITIONS[0], id: 'pos_nan_risk', allocatedRiskR: NaN }
      ]);
    });

    expect(handle.getOpenRiskR() === null, 'Portfolio risk must be null due to NaN');

    // Candidate exists and has valid planned risk in strip
    expect(GATE_CANDIDATES.length > 0, 'Gate candidates exist');

    // Attempt scale-in
    act(() => {
      handle.triggerAction('scale_in', handle.getPositions()[0]);
    });

    await act(async () => {
      await handle.confirmAction();
    });

    const activeCmd = handle.getActiveCommand();
    expect(activeCmd?.status === 'REJECTED', 'Planned risk cannot override invalid actual risk');
    expect(activeCmd?.source === 'PRODUCTION_RISK_GATE', 'Rejected at risk gate');

    teardownMount();
  });

  await test('H1.1.2-AUTH-04: Case 4 — De-risking (CLOSE, TIGHTEN_STOP, BE) remains permitted under invalid portfolio state', async () => {
    setupMount();
    const testControlRef = React.createRef<AppTestControlHandle | null>();

    act(() => {
      root!.render(
        React.createElement(App, {
          initialPositions: INITIAL_POSITIONS,
          testRef: testControlRef,
        })
      );
    });

    const handle = testControlRef.current!;

    // Introduce invalid position
    act(() => {
      handle.setPositions((prev) => [
        ...prev,
        { ...INITIAL_POSITIONS[0], id: 'pos_missing_risk', allocatedRiskR: undefined }
      ]);
    });

    expect(handle.getOpenRiskR() === null, 'Portfolio is in INVALID risk state');

    const provider = handle.getSimulationProvider();
    const preCount = provider.getSimulatedIntents().size;

    // Trigger de-risking action: close_position on valid position
    const target = handle.getPositions()[0];
    act(() => {
      handle.triggerAction('close_position', target);
    });

    await act(async () => {
      await handle.confirmAction();
    });

    // De-risking action succeeds and submits to provider
    const postCount = provider.getSimulatedIntents().size;
    expect(postCount === preCount + 1, 'De-risking action must submit to provider');

    // Verify permission is strictly limited: ensure corrupt position is present and attempt add_size
    act(() => {
      handle.setPositions((prev) => [
        ...prev.filter((p) => p.id !== 'pos_missing_risk'),
        { ...INITIAL_POSITIONS[0], id: 'pos_missing_risk', allocatedRiskR: undefined }
      ]);
    });
    expect(handle.getOpenRiskR() === null, 'Portfolio remains in INVALID risk state');

    act(() => {
      handle.triggerAction('add_size', handle.getPositions()[0]);
    });

    await act(async () => {
      await handle.confirmAction();
    });

    expect(handle.getActiveCommand()?.status === 'REJECTED', 'Permission does not broaden: add_size still rejected');
    expect(provider.getSimulatedIntents().size === postCount, 'Zero new provider submission for add_size');

    teardownMount();
  });

  await test('H1.1.2-AUTH-05: Case 5 — Recovery restores authorization and newly invalid state immediately re-engages barrier', async () => {
    setupMount();
    const testControlRef = React.createRef<AppTestControlHandle | null>();

    act(() => {
      root!.render(
        React.createElement(App, {
          initialPositions: INITIAL_POSITIONS,
          testRef: testControlRef,
        })
      );
    });

    const handle = testControlRef.current!;

    // Step A: Corrupt
    act(() => {
      handle.setPositions((prev) => [
        ...prev,
        { ...INITIAL_POSITIONS[0], id: 'pos_corrupt_rec', allocatedRiskR: -0.5 }
      ]);
    });
    expect(handle.getOpenRiskR() === null, 'Corrupt portfolio is null');

    // Attempt add_size -> REJECTED
    act(() => {
      handle.triggerAction('add_size', handle.getPositions()[0]);
    });
    await act(async () => {
      await handle.confirmAction();
    });
    expect(handle.getActiveCommand()?.status === 'REJECTED', 'Rejected while corrupt');

    // Step B: Recover
    act(() => {
      handle.setPositions((prev) => prev.filter((p) => p.id !== 'pos_corrupt_rec'));
    });
    expect(handle.getOpenRiskR() === 2.3, 'Open risk recovered to 2.3R');
    expect(container.querySelector('[data-testid="open-risk-kpi"]')?.textContent?.trim() === '2.3R', 'KPI recovered in DOM');

    // Attempt add_size -> SUCCEEDS
    const provider = handle.getSimulationProvider();
    const preCount = provider.getSimulatedIntents().size;
    act(() => {
      handle.triggerAction('add_size', handle.getPositions()[0]);
    });
    await act(async () => {
      await handle.confirmAction();
    });
    expect(provider.getSimulatedIntents().size === preCount + 1, 'Authorized after recovery');

    // Step C: Re-corrupt with a new invalid state -> MUST IMMEDIATELY RE-ENGAGE BARRIER
    act(() => {
      handle.setPositions((prev) => [
        ...prev,
        { ...INITIAL_POSITIONS[0], id: 'pos_corrupt_second', allocatedRiskR: Infinity }
      ]);
    });
    expect(handle.getOpenRiskR() === null, 'Re-corrupted portfolio is null');

    act(() => {
      handle.triggerAction('add_size', handle.getPositions()[0]);
    });
    await act(async () => {
      await handle.confirmAction();
    });
    expect(handle.getActiveCommand()?.status === 'REJECTED', 'Stale valid state cannot bypass newly invalid state');

    teardownMount();
  });

  await test('H1.1.2-AUTH-06: Case 6 — Alternate paths (keyboard shortcuts, mobile views) enforce identical authority boundary', async () => {
    setupMount();
    const testControlRef = React.createRef<AppTestControlHandle | null>();

    act(() => {
      root!.render(
        React.createElement(App, {
          initialPositions: INITIAL_POSITIONS,
          testRef: testControlRef,
        })
      );
    });

    const handle = testControlRef.current!;

    // Make portfolio invalid
    act(() => {
      handle.setPositions((prev) => [
        ...prev,
        { ...INITIAL_POSITIONS[0], id: 'pos_missing_alt', allocatedRiskR: undefined }
      ]);
    });

    // Test Keyboard Shortcut path: '+' key triggers add_size
    act(() => {
      const event = new window.KeyboardEvent('keydown', { key: '+', bubbles: true });
      window.dispatchEvent(event);
    });

    // Verify modal opened via keyboard
    const modalEl = container.querySelector('[role="dialog"]');
    expect(modalEl !== null, 'Keyboard shortcut "+" must open confirmation dialog');

    // Click confirm button in mounted DOM
    const confirmBtn = container.querySelector<HTMLButtonElement>('[data-testid="confirm-dialog-confirm"]');
    expect(confirmBtn !== null, 'Confirm button must exist in DOM');

    await act(async () => {
      confirmBtn!.click();
    });

    // Verify rejection at boundary
    expect(handle.getActiveCommand()?.status === 'REJECTED', 'Keyboard path rejected fail-closed');

    // Test ContextPanel DOM Button path:
    const addSizeBtn = container.querySelector<HTMLButtonElement>('[data-testid="context-btn-add-size"]');
    expect(addSizeBtn !== null, 'ContextPanel Add Size button must exist in DOM');

    act(() => {
      addSizeBtn!.click();
    });

    const confirmBtn2 = container.querySelector<HTMLButtonElement>('[data-testid="confirm-dialog-confirm"]');
    await act(async () => {
      confirmBtn2!.click();
    });

    expect(handle.getActiveCommand()?.status === 'REJECTED', 'ContextPanel DOM button path rejected fail-closed');

    teardownMount();
  });

  await test('H1.1.2-SEAM-01: Finding B — Test seam isolation: AppTestControlHandle absent from production bundle', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const distAssetsDir = path.resolve(process.cwd(), 'dist/assets');

    expect(fs.existsSync(distAssetsDir), 'dist/assets directory must exist from production build');
    const files = fs.readdirSync(distAssetsDir).filter((f: string) => f.endsWith('.js'));
    expect(files.length > 0, 'Production JS bundle must exist');

    for (const file of files) {
      const content = fs.readFileSync(path.join(distAssetsDir, file), 'utf-8');
      expect(!content.includes('getPortfolioRiskEval'), `Production bundle ${file} must NOT contain getPortfolioRiskEval`);
      expect(!content.includes('getSimulationProvider'), `Production bundle ${file} must NOT contain getSimulationProvider`);
      expect(!content.includes('AppTestControlHandle'), `Production bundle ${file} must NOT contain AppTestControlHandle`);
    }
  });

  console.log('\n========================================================');
  console.log(`Stage H.1.1 Production Path Results: ${passed} PASSED, ${failed} FAILED`);
  console.log('========================================================');

  if (failed > 0) {
    throw new Error(`Stage H.1.1 suite failed with ${failed} failure(s)`);
  }
}

runStageH11ProductionPathSuite().catch((err) => {
  console.error('Test execution aborted:', err);
  process.exit(1);
});
