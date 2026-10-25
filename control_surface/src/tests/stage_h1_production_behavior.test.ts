/**
 * FRACTAL-FLOW Stage H.1 Production Behavior & Forensic Invariant Test Suite
 * Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY
 * 
 * Tests real production components rendered in JSDOM, verifies micro-R precision without
 * premature rounding, validates FIPS 180-4 SHA-256 standard known-answer vectors, and
 * enforces fail-closed live execution barriers and state immutability.
 */

import React from 'react';
import { JSDOM } from 'jsdom';
import { renderToString } from 'react-dom/server';
import { Header } from '../components/Header';
import { SecondaryViews } from '../components/SecondaryViews';
import { 
  evaluatePortfolioRisk, 
  getValidPositionRiskR, 
  validateCandidateAgainstRiskConfig,
  validateOperationalRiskConfig
} from '../utils/riskValidator';
import { sha256, canonicalJsonStringify, computeCanonicalSha256 } from '../utils/crypto';
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

async function runStageH1ProductionBehaviorSuite() {
  console.log('========================================================');
  console.log('FRACTAL-FLOW Stage H.1 Production Behavior & Invariant Suite');
  console.log('Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM');
  console.log('========================================================\n');

  // --- SECTION 1: HPL-H1-RISK-01 — PRODUCTION RISK KPI RENDERING ---
  console.log('--- HPL-H1-RISK-01: Production Risk KPI Rendering & Zero Fabricated Fallbacks ---');

  await test('H1-RISK-01.1: Production Header renders exact aggregate openRiskR when nominal', () => {
    const html = renderToString(
      React.createElement(Header, {
        equity: 50000,
        dailyPnl: 312.5,
        openRiskR: 1.80,
        lane: 'ACT_PRIMARY',
        onLaneChange: () => {},
        isSimPaused: false,
        onToggleSimPause: () => {},
        telemetry: DUMMY_TELEMETRY,
        applicationMode: 'SIMULATION_SANDBOX',
      })
    );

    const dom = new JSDOM(html);
    const desktopKpi = dom.window.document.querySelector('[data-testid="open-risk-kpi"]');
    const mobileKpi = dom.window.document.querySelector('[data-testid="open-risk-kpi-mobile"]');

    expect(desktopKpi !== null, 'Desktop open-risk KPI element must exist');
    expect(desktopKpi!.textContent!.trim() === '1.8R', `Expected '1.8R', got '${desktopKpi!.textContent!.trim()}'`);

    expect(mobileKpi !== null, 'Mobile open-risk KPI element must exist');
    expect(mobileKpi!.textContent!.trim() === '1.8R', `Expected '1.8R', got '${mobileKpi!.textContent!.trim()}'`);
  });

  await test('H1-RISK-01.2: Production Header renders explicit INVALID badge when openRiskR is null (zero numeric guess)', () => {
    const html = renderToString(
      React.createElement(Header, {
        equity: 50000,
        dailyPnl: 312.5,
        openRiskR: null, // Corrupted / unknown risk
        lane: 'ACT_PRIMARY',
        onLaneChange: () => {},
        isSimPaused: false,
        onToggleSimPause: () => {},
        telemetry: DUMMY_TELEMETRY,
        applicationMode: 'SIMULATION_SANDBOX',
      })
    );

    const dom = new JSDOM(html);
    const desktopInvalid = dom.window.document.querySelector('[data-testid="open-risk-invalid"]');
    const mobileInvalid = dom.window.document.querySelector('[data-testid="open-risk-invalid-mobile"]');

    expect(desktopInvalid !== null, 'Desktop open-risk invalid element must exist');
    expect(desktopInvalid!.textContent!.trim() === 'INVALID', `Expected 'INVALID', got '${desktopInvalid!.textContent!.trim()}'`);

    expect(mobileInvalid !== null, 'Mobile open-risk invalid element must exist');
    expect(mobileInvalid!.textContent!.trim() === 'INVALID', `Expected 'INVALID', got '${mobileInvalid!.textContent!.trim()}'`);

    // Verify no numeric total is rendered
    expect(!html.includes('0.0R') && !html.includes('2.4R'), 'Must not render fallback numeric estimate');
  });

  await test('H1-RISK-01.3: Empty portfolio evaluates to valid 0.0R and is distinct from invalid state', () => {
    const emptyEval = evaluatePortfolioRisk([]);
    expect(emptyEval.status === 'VALID', 'Empty portfolio must have status VALID');
    expect(emptyEval.totalRiskR === 0.0, 'Empty portfolio must have totalRiskR 0.0');

    const html = renderToString(
      React.createElement(Header, {
        equity: 50000,
        dailyPnl: 0,
        openRiskR: emptyEval.totalRiskR,
        lane: 'ACT_PRIMARY',
        onLaneChange: () => {},
        isSimPaused: false,
        onToggleSimPause: () => {},
        telemetry: DUMMY_TELEMETRY,
        applicationMode: 'SIMULATION_SANDBOX',
      })
    );

    const dom = new JSDOM(html);
    const desktopKpi = dom.window.document.querySelector('[data-testid="open-risk-kpi"]');
    expect(desktopKpi !== null, 'Desktop KPI must exist for empty portfolio');
    expect(desktopKpi!.textContent!.trim() === '0.0R', `Expected '0.0R', got '${desktopKpi!.textContent!.trim()}'`);
  });

  await test('H1-RISK-01.4: SecondaryViews RISK tab renders dynamic open risk and handles invalid portfolio fail-closed', () => {
    // Valid portfolio
    const validHtml = renderToString(
      React.createElement(SecondaryViews, {
        activeTab: 'RISK',
        onReturnToPositions: () => {},
        positions: INITIAL_POSITIONS,
        riskConfig: INITIAL_OPERATIONAL_RISK_CONFIG
      })
    );
    const validDom = new JSDOM(validHtml);
    const totalRiskEl = validDom.window.document.querySelector('[data-testid="secondary-total-open-risk"]');
    expect(totalRiskEl !== null, 'Secondary total open risk card must exist');
    expect(totalRiskEl!.textContent!.trim() === '2.30R', `Expected 2.30R, got ${totalRiskEl!.textContent!.trim()}`);

    // Corrupted portfolio (one position with negative risk)
    const corruptPositions: Position[] = [
      ...INITIAL_POSITIONS,
      {
        ...INITIAL_POSITIONS[0],
        id: 'pos_corrupt',
        allocatedRiskR: -0.5
      }
    ];
    const corruptHtml = renderToString(
      React.createElement(SecondaryViews, {
        activeTab: 'RISK',
        onReturnToPositions: () => {},
        positions: corruptPositions,
        riskConfig: INITIAL_OPERATIONAL_RISK_CONFIG
      })
    );
    const corruptDom = new JSDOM(corruptHtml);
    const corruptTotalEl = corruptDom.window.document.querySelector('[data-testid="secondary-total-open-risk"]');
    expect(corruptTotalEl !== null, 'Corrupt card must exist');
    expect(corruptTotalEl!.textContent!.trim() === 'INVALID', `Expected INVALID, got ${corruptTotalEl!.textContent!.trim()}`);
  });

  // --- SECTION 2: HPL-H1-RISK-02 — CANONICAL PRECISION & ARITHMETIC ---
  console.log('\n--- HPL-H1-RISK-02: Canonical Precision, Micro-R Scaling & Boundary Equality ---');

  await test('H1-RISK-02.1: Three 0.005R positions sum to 0.015R (proves zero premature per-position hundredth rounding)', () => {
    const testPositions: Position[] = [
      { ...INITIAL_POSITIONS[0], id: 'pos_micro_1', allocatedRiskR: 0.005 },
      { ...INITIAL_POSITIONS[1], id: 'pos_micro_2', allocatedRiskR: 0.005 },
      { ...INITIAL_POSITIONS[2], id: 'pos_micro_3', allocatedRiskR: 0.005 },
    ];

    const result = evaluatePortfolioRisk(testPositions);
    expect(result.status === 'VALID', 'Evaluation must be VALID');
    // If premature per-position Math.round(0.005 * 100) occurred, it would round to 0.01 each = 0.03.
    // Exact micro-R aggregation: 0.005 + 0.005 + 0.005 = 0.015.
    expect(result.totalRiskR === 0.015, `Expected exactly 0.015R, got: ${result.totalRiskR}`);
  });

  await test('H1-RISK-02.2: Aggregation order determinism under position permutations', () => {
    const p1: Position = { ...INITIAL_POSITIONS[0], id: 'p1', allocatedRiskR: 0.1234 };
    const p2: Position = { ...INITIAL_POSITIONS[1], id: 'p2', allocatedRiskR: 0.5678 };
    const p3: Position = { ...INITIAL_POSITIONS[2], id: 'p3', allocatedRiskR: 0.9012 };

    const order1 = evaluatePortfolioRisk([p1, p2, p3]);
    const order2 = evaluatePortfolioRisk([p3, p1, p2]);
    const order3 = evaluatePortfolioRisk([p2, p3, p1]);

    expect(order1.totalRiskR === order2.totalRiskR, 'Permutation 1 and 2 must match bit-for-bit');
    expect(order2.totalRiskR === order3.totalRiskR, 'Permutation 2 and 3 must match bit-for-bit');
  });

  await test('H1-RISK-02.3: Cap comparison boundary equality — exact equality is CLEAR, strictly greater breaches', () => {
    const candidate = GATE_CANDIDATES[0]; // lane: ACT_PRIMARY
    const positions: Position[] = [
      { ...INITIAL_POSITIONS[0], lane: 'ACT_PRIMARY', allocatedRiskR: 1.0 },
    ];
    const config: OperationalRiskConfig = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      maxLaneRiskR: 1.8, // 1.0 + 0.8 = exactly 1.8R
      maxAccountExposureR: 5.0,
    };

    // Exactly equal to cap (1.0 + 0.8 = 1.8000R <= 1.8R) -> CLEAR
    const equalValidation = validateCandidateAgainstRiskConfig(
      candidate,
      positions,
      config,
      312.5,
      0.8
    );
    expect(equalValidation.status === 'CLEAR', `Exact equality must be CLEAR, got: ${equalValidation.status}`);

    // Strictly greater than cap (1.0 + 0.8001 = 1.8001R > 1.8R) -> BREACHED
    const breachValidation = validateCandidateAgainstRiskConfig(
      candidate,
      positions,
      config,
      312.5,
      0.8001
    );
    expect(breachValidation.status === 'BREACHED', `Strictly greater must breach, got: ${breachValidation.status}`);
  });

  // --- SECTION 3: HPL-H1-RISK-03 — PROVENANCE & SEMANTICS ---
  console.log('\n--- HPL-H1-RISK-03: Risk Provenance & Semantics ---');

  await test('H1-RISK-03.1: Allocated risk takes precedence over setup map', () => {
    const pos: Position = {
      ...INITIAL_POSITIONS[0],
      setup: 'FF-01', // mapped to 0.8
      allocatedRiskR: 0.45, // explicit allocation
    };

    const evalResult = getValidPositionRiskR(pos);
    expect(evalResult.isValid, 'Must be valid');
    expect(evalResult.riskR === 0.45, `Expected 0.45, got: ${evalResult.riskR}`);
  });

  await test('H1-RISK-03.2: Missing allocated risk and unknown setup fails closed without guessing', () => {
    const pos: Position = {
      ...INITIAL_POSITIONS[0],
      setup: 'UNKNOWN_CUSTOM_SETUP',
      allocatedRiskR: undefined,
    };

    const evalResult = getValidPositionRiskR(pos);
    expect(!evalResult.isValid, 'Must fail closed');
    expect(evalResult.riskR === null, 'Risk must be null');
  });

  // --- SECTION 4: HPL-H1-CRYPTO-01 — STANDARD SHA-256 CONFORMANCE ---
  console.log('\n--- HPL-H1-CRYPTO-01: FIPS 180-4 Standard SHA-256 Conformance ---');

  await test('H1-CRYPTO-01.1: NIST Standard Vector 1 (Empty String)', () => {
    const expected = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
    const actual = sha256('');
    expect(actual === expected, `Expected ${expected}, got: ${actual}`);
  });

  await test('H1-CRYPTO-01.2: NIST Standard Vector 2 ("abc")', () => {
    const expected = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad';
    const actual = sha256('abc');
    expect(actual === expected, `Expected ${expected}, got: ${actual}`);
  });

  await test('H1-CRYPTO-01.3: Non-ASCII UTF-8 string with symbols, accents and emojis', () => {
    // Verified against independent Node.js crypto.createHash('sha256')
    const input = 'FRACTAL-FLOW © 2026 \u00e9\u00e8\u00e0 \ud83d\udd12';
    const expected = '1b2a2a22adc7dde79734069edb1febdc71d95f6a749cf5f371d87520f9aa8dbf';
    const actual = sha256(input);
    expect(actual === expected, `Expected ${expected}, got: ${actual}`);
  });

  await test('H1-CRYPTO-01.4: Multi-block message spanning >64 bytes across block boundary', () => {
    const input = 'The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog again and again!';
    const expected = '9266152c41917da2ea10371017d2e25c42216d796a3ff24d7985b442f3f35089';
    const actual = sha256(input);
    expect(actual === expected, `Expected ${expected}, got: ${actual}`);
  });

  await test('H1-CRYPTO-01.5: Canonical JSON key-order invariance and array-order sensitivity', () => {
    const obj1 = { z: 1, a: 2, m: { y: 'bar', b: 'foo' } };
    const obj2 = { a: 2, m: { b: 'foo', y: 'bar' }, z: 1 };
    expect(computeCanonicalSha256(obj1) === computeCanonicalSha256(obj2), 'Key reordering must yield identical SHA-256');

    const arr1 = [1, 2, 3];
    const arr2 = [3, 2, 1];
    expect(computeCanonicalSha256(arr1) !== computeCanonicalSha256(arr2), 'Array order permutation must alter SHA-256');
  });

  await test('H1-CRYPTO-01.6: Canonical JSON fails closed on unsupported non-finite numbers and circular refs', () => {
    let nanThrew = false;
    try {
      canonicalJsonStringify({ val: NaN });
    } catch (e) {
      nanThrew = true;
      expect(e instanceof TypeError, 'Must throw TypeError on NaN');
    }
    expect(nanThrew, 'NaN must be rejected fail-closed');

    let circularThrew = false;
    const circular: Record<string, unknown> = { name: 'loop' };
    circular.self = circular;
    try {
      canonicalJsonStringify(circular);
    } catch (e) {
      circularThrew = true;
      expect(e instanceof TypeError, 'Must throw TypeError on circular reference');
    }
    expect(circularThrew, 'Circular structure must be rejected fail-closed');
  });

  // --- SECTION 5: HPL-H1-AUTH-01 & PROTECT-01 — AUTHORITY & LIVE BARRIER ---
  console.log('\n--- HPL-H1-AUTH-01 & PROTECT-01: Authority & Live Execution Barrier ---');

  await test('H1-AUTH-01.1: LiveCommandAdapter unconditionally throws LiveExecutionBlockedError', async () => {
    const adapter = new LiveCommandAdapter();
    let submitThrew = false;
    try {
      await adapter.submitCommand({
        intentId: 'live_test_01',
        operatorId: 'session:local_operator',
        targetPositionId: 'pos_1',
        symbol: 'EURUSD',
        actionType: 'CLOSE',
        parameters: {},
        idempotencyKey: 'idemp_01',
        createdAt: Date.now()
      });
    } catch (err: unknown) {
      submitThrew = true;
      expect(err instanceof LiveExecutionBlockedError, 'Must be LiveExecutionBlockedError');
    }
    expect(submitThrew, 'submitCommand must throw fail-closed error');
  });

  await test('H1-AUTH-01.2: SimulationProvider state remains bit-for-bit immutable on command rejection', async () => {
    const provider = new SimulationProvider();
    const beforeState = provider.getProtectedTradingStateSnapshot();

    const result = await provider.submitCommand({
      intentId: 'reject_test_01',
      operatorId: 'session:local_operator',
      targetPositionId: 'pos_eurusd_01',
      symbol: 'EURUSD',
      actionType: 'CLOSE',
      parameters: { simulateRejection: true },
      idempotencyKey: 'idemp_reject',
      createdAt: Date.now()
    });

    expect(result.status === 'REJECTED', 'Must reject command');
    const afterState = provider.getProtectedTradingStateSnapshot();
    expect(
      JSON.stringify(beforeState) === JSON.stringify(afterState),
      'Simulation trading state must remain bit-for-bit unchanged upon command rejection'
    );
  });

  await test('H1-PROTECT-01.1: OperationalRiskConfig rejection on cross-field violation preserves state', () => {
    const invalidConfig = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      maxLaneRiskR: 10.0,
      maxAccountExposureR: 5.0, // lane > account violation
    };

    const validation = validateOperationalRiskConfig(invalidConfig);
    expect(!validation.isValid, 'Cross-field violation must be invalid');
    expect(validation.errors.some((e) => e.includes('Cross-field invariant violation')), 'Must report cross-field error');
  });

  console.log('\n========================================================');
  console.log(`Stage H.1 Production Behavior Results: ${passed} PASSED, ${failed} FAILED`);
  console.log('========================================================');

  if (failed > 0) {
    throw new Error(`Stage H.1 suite failed with ${failed} failure(s)`);
  }
}

runStageH1ProductionBehaviorSuite().catch((err) => {
  console.error('Test execution aborted:', err);
  process.exit(1);
});
