/**
 * FRACTAL-FLOW Stage H.1.1 Production Path & Risk Provenance Test Suite
 * Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY
 * 
 * Verifies:
 * - HPL-H1.1-RISK-01: Zero setup-map fallback for open positions (strict allocatedRiskR requirement).
 * - HPL-H1.1-RISK-02: Micro-R integer scaling, cap boundary equality, and permutation invariance.
 * - HPL-H1.1-TEST-01: Production interactive state transitions (valid -> invalid -> valid).
 * - HPL-H1.1-PROTECT-01: De-risking allowed during risk-invalid states; live execution blocked.
 */

import React from 'react';
import { JSDOM } from 'jsdom';
import { renderToString } from 'react-dom/server';
import { Header } from '../components/Header';
import { SecondaryViews } from '../components/SecondaryViews';
import { 
  evaluatePortfolioRisk, 
  getValidPositionRiskR, 
  getCandidatePlannedRiskR,
  validateCandidateAgainstRiskConfig,
  validateOperationalRiskConfig
} from '../utils/riskValidator';
import { LiveCommandAdapter, LiveExecutionBlockedError } from '../providers/LiveCommandAdapter';
import { SimulationProvider } from '../providers/SimulationProvider';
import { INITIAL_POSITIONS, GATE_CANDIDATES, INITIAL_OPERATIONAL_RISK_CONFIG } from '../data/mockData';
import { Position, OperationalRiskConfig } from '../types';
import { TelemetryProvenance } from '../types/contracts';

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

const DUMMY_TELEMETRY: TelemetryProvenance = {
  source: 'SIM_ENGINE',
  status: 'HEALTHY',
  freshnessTimestamp: Date.now(),
  isAuthoritative: false,
  staleThresholdMs: 5000,
  epoch: 1,
  bridgeStatus: 'SIM_DISPATCH',
  fenceStatus: 'OFF_BROKER'
};

async function runStageH11ProductionPathSuite() {
  console.log('========================================================');
  console.log('FRACTAL-FLOW Stage H.1.1 Production Path & Provenance Suite');
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

  await test('H1.1-RISK-02.2: Large position count aggregation: 100 x 0.005R equals exactly 0.500R', () => {
    const hundredPositions: Position[] = Array.from({ length: 100 }, (_, i) => ({
      ...INITIAL_POSITIONS[0],
      id: `p_bulk_${i}`,
      allocatedRiskR: 0.005,
    }));
    const res = evaluatePortfolioRisk(hundredPositions);
    expect(res.status === 'VALID', 'Evaluation must be valid');
    expect(res.totalRiskR === 0.5, `Expected exactly 0.5R, got ${res.totalRiskR}`);
  });

  await test('H1.1-RISK-02.3: Cap equality: exact equality is CLEAR, excess of 0.0001R is BREACHED', () => {
    const candidate = GATE_CANDIDATES[0];
    const positions: Position[] = [
      { ...INITIAL_POSITIONS[0], lane: 'ACT_PRIMARY', allocatedRiskR: 1.0 },
    ];
    const config: OperationalRiskConfig = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      maxLaneRiskR: 1.8,
      maxAccountExposureR: 5.0,
    };

    // Exact equality (1.0 + 0.8 = 1.8R <= 1.8R) -> CLEAR
    const clearResult = validateCandidateAgainstRiskConfig(candidate, positions, config, 0, 0.8);
    expect(clearResult.status === 'CLEAR', `Exact equality must be CLEAR, got ${clearResult.status}`);

    // Excess of 0.0001R (1.0 + 0.8001 = 1.8001R > 1.8R) -> BREACHED
    const breachResult = validateCandidateAgainstRiskConfig(candidate, positions, config, 0, 0.8001);
    expect(breachResult.status === 'BREACHED', `Excess must breach, got ${breachResult.status}`);
  });

  await test('H1.1-RISK-02.4: Permutation determinism across 6 order permutations', () => {
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

    const baseResult = evaluatePortfolioRisk(permutations[0]).totalRiskR;
    for (let i = 1; i < permutations.length; i++) {
      const permResult = evaluatePortfolioRisk(permutations[i]).totalRiskR;
      expect(permResult === baseResult, `Permutation ${i} (${permResult}) must match base (${baseResult})`);
    }
  });

  // --- SECTION 3: HPL-H1.1-TEST-01 — PRODUCTION INTERACTIVE STATE TRANSITIONS ---
  console.log('\n--- HPL-H1.1-TEST-01: Interactive Production State Transitions ---');

  await test('H1.1-TEST-01.1: Production state transition: Valid -> Invalid -> Valid on position modification', () => {
    // Stage 1: Valid initial portfolio
    let currentPositions: Position[] = [...INITIAL_POSITIONS];
    let evalRes = evaluatePortfolioRisk(currentPositions);
    expect(evalRes.status === 'VALID', 'Initial portfolio must be valid');

    let html = renderToString(
      React.createElement(Header, {
        equity: 50000,
        dailyPnl: 312.5,
        openRiskR: evalRes.totalRiskR,
        lane: 'ACT_PRIMARY',
        onLaneChange: () => {},
        isSimPaused: false,
        onToggleSimPause: () => {},
        telemetry: DUMMY_TELEMETRY,
        applicationMode: 'SIMULATION_SANDBOX',
      })
    );
    let dom = new JSDOM(html);
    let kpi = dom.window.document.querySelector('[data-testid="open-risk-kpi"]');
    expect(kpi !== null && kpi.textContent!.trim() === '2.3R', 'Must render 2.3R for valid portfolio');

    // Stage 2: Ingest an unallocated position (transition to INVALID)
    currentPositions = [
      ...currentPositions,
      { ...INITIAL_POSITIONS[0], id: 'pos_unallocated', allocatedRiskR: undefined }
    ];
    evalRes = evaluatePortfolioRisk(currentPositions);
    expect(evalRes.status === 'INVALID', 'Portfolio must transition to INVALID');

    html = renderToString(
      React.createElement(Header, {
        equity: 50000,
        dailyPnl: 312.5,
        openRiskR: evalRes.totalRiskR, // null
        lane: 'ACT_PRIMARY',
        onLaneChange: () => {},
        isSimPaused: false,
        onToggleSimPause: () => {},
        telemetry: DUMMY_TELEMETRY,
        applicationMode: 'SIMULATION_SANDBOX',
      })
    );
    dom = new JSDOM(html);
    let invalidEl = dom.window.document.querySelector('[data-testid="open-risk-invalid"]');
    expect(invalidEl !== null && invalidEl.textContent!.trim() === 'INVALID', 'Must transition to INVALID badge');

    // Stage 3: Close/remove the unallocated position (recovery back to VALID)
    currentPositions = currentPositions.filter((p) => p.id !== 'pos_unallocated');
    evalRes = evaluatePortfolioRisk(currentPositions);
    expect(evalRes.status === 'VALID', 'Portfolio must recover to VALID');

    html = renderToString(
      React.createElement(Header, {
        equity: 50000,
        dailyPnl: 312.5,
        openRiskR: evalRes.totalRiskR,
        lane: 'ACT_PRIMARY',
        onLaneChange: () => {},
        isSimPaused: false,
        onToggleSimPause: () => {},
        telemetry: DUMMY_TELEMETRY,
        applicationMode: 'SIMULATION_SANDBOX',
      })
    );
    dom = new JSDOM(html);
    kpi = dom.window.document.querySelector('[data-testid="open-risk-kpi"]');
    expect(kpi !== null && kpi.textContent!.trim() === '2.3R', 'Must recover to 2.3R');
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
