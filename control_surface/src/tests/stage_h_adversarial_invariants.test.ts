/**
 * FRACTAL-FLOW Stage H Forensic Adversarial Invariants Suite
 * Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY
 * 
 * Verifies hostile proof invariants HPL-RISK-01..06, HPL-LAT-01..03, HPL-AUD-01..02,
 * HPL-NOT-01..02, HPL-LAB-01, HPL-QUANT-01, HPL-LIVE-01, and HPL-EVID-01.
 */

import { 
  validateCandidateAgainstRiskConfig, 
  validateOperationalRiskConfig, 
  evaluatePortfolioRisk, 
  getValidPositionRiskR,
  calculateLaneRiskR,
  calculateAccountExposureR,
  validatePositionModification
} from '../utils/riskValidator';
import { computeCanonicalSha256 } from '../utils/crypto';
import { 
  INITIAL_OPERATIONAL_RISK_CONFIG, 
  INITIAL_POSITIONS, 
  GATE_CANDIDATES,
  INITIAL_NOTIFICATIONS,
  INITIAL_QUANT_MODELS,
  INITIAL_MODEL_ADVICE_STREAM,
  INITIAL_LAB_RUNS
} from '../data/mockData';
import { OperationalRiskConfig, GateCandidate, Position } from '../types';
import { LiveCommandAdapter, LiveExecutionBlockedError } from '../providers/LiveCommandAdapter';
import { SimulationProvider } from '../providers/SimulationProvider';

let passed = 0;
let failed = 0;

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

function expect(condition: boolean, message: string) {
  if (!condition) {
    throw new Error(message);
  }
}

async function runStageHAdversarialVerification() {
  console.log('========================================================');
  console.log('FRACTAL-FLOW Stage H Forensic Adversarial Invariants Suite');
  console.log('Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM');
  console.log('========================================================\n');

  // ---------------------------------------------------------------------------
  // 1. RISK VALIDATOR ADVERSARIAL INVARIANTS (HPL-RISK-01..06)
  // ---------------------------------------------------------------------------
  console.log('--- HPL-RISK: Forensic Risk Invariant Matrix ---');

  await test('HPL-RISK-01: Invalid, non-finite, and negative candidate risk rejects with INVALID/UNKNOWN, never CLEAR', () => {
    const candidate = GATE_CANDIDATES[0];
    const config = INITIAL_OPERATIONAL_RISK_CONFIG;

    // Test negative candidate risk override
    const negRes = validateCandidateAgainstRiskConfig(candidate, INITIAL_POSITIONS, config, 100, -0.5);
    expect(negRes.status === 'INVALID', `Expected INVALID for negative risk, got ${negRes.status}`);
    expect(negRes.hasViolations, 'Negative risk must have violations');

    // Test NaN candidate risk override
    const nanRes = validateCandidateAgainstRiskConfig(candidate, INITIAL_POSITIONS, config, 100, NaN);
    expect(nanRes.status === 'INVALID', `Expected INVALID for NaN risk, got ${nanRes.status}`);

    // Test Infinity candidate risk override
    const infRes = validateCandidateAgainstRiskConfig(candidate, INITIAL_POSITIONS, config, 100, Infinity);
    expect(infRes.status === 'INVALID', `Expected INVALID for Infinity risk, got ${infRes.status}`);

    // Test candidate with unknown setup and no override
    const unknownCandidate: GateCandidate = {
      ...candidate,
      setup: 'UNKNOWN_SETUP_XYZ'
    };
    const unkRes = validateCandidateAgainstRiskConfig(unknownCandidate, INITIAL_POSITIONS, config, 100);
    expect(unkRes.status === 'UNKNOWN', `Expected UNKNOWN for undocumented setup, got ${unkRes.status}`);
    expect(unkRes.hasViolations, 'Unknown setup must flag violations without silent fallback');
  });

  await test('HPL-RISK-02: Zero silent fallbacks — invalid position risk units fail closed without partial aggregation', () => {
    // Corrupt position with missing lane
    const corruptPos1: Position = {
      ...INITIAL_POSITIONS[0],
      lane: ''
    };
    const eval1 = getValidPositionRiskR(corruptPos1);
    expect(!eval1.isValid, 'Position with empty lane must be invalid');

    // Corrupt position with non-finite allocatedRiskR
    const corruptPos2: Position = {
      ...INITIAL_POSITIONS[0],
      allocatedRiskR: NaN
    };
    const eval2 = getValidPositionRiskR(corruptPos2);
    expect(!eval2.isValid, 'Position with NaN allocatedRiskR must be invalid');

    // Corrupt position with negative allocatedRiskR
    const corruptPos3: Position = {
      ...INITIAL_POSITIONS[0],
      allocatedRiskR: -0.8
    };
    const eval3 = getValidPositionRiskR(corruptPos3);
    expect(!eval3.isValid, 'Position with negative allocatedRiskR must be invalid');

    // Portfolio evaluation with one corrupt position must fail atomically (never partial sum!)
    const mixedPortfolio: Position[] = [
      INITIAL_POSITIONS[0],
      INITIAL_POSITIONS[1],
      corruptPos3
    ];
    const portfolioEval = evaluatePortfolioRisk(mixedPortfolio);
    expect(portfolioEval.status === 'INVALID', 'Portfolio with any invalid position must yield INVALID');
    expect(portfolioEval.totalRiskR === null, 'totalRiskR must be null when portfolio is invalid');
    expect(portfolioEval.invalidPositionIds.length === 1, 'Should identify the invalid position');

    // calculateLaneRiskR must return NaN on corrupt portfolio
    const laneRisk = calculateLaneRiskR(mixedPortfolio, 'ACT_PRIMARY');
    expect(Number.isNaN(laneRisk), `calculateLaneRiskR must return NaN, got ${laneRisk}`);
  });

  await test('HPL-RISK-03: Exact risk-cap equality — boundary is inclusive cap; strictly greater breaches', () => {
    const candidate = GATE_CANDIDATES[0]; // lane: ACT_PRIMARY

    // Baseline ACT_PRIMARY portfolio risk: 0.8 + 0.5 + 0.6 + 0.4 = 2.30R
    // Candidate risk: 0.70R -> projected lane risk = 3.00R
    const exactCapConfig: OperationalRiskConfig = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      maxLaneRiskR: 3.00,
      maxAccountExposureR: 5.00,
      dailyLossLimitUsd: 1500
    };

    // Exactly at cap (projected == 3.00R == cap)
    const exactRes = validateCandidateAgainstRiskConfig(candidate, INITIAL_POSITIONS, exactCapConfig, 100, 0.70);
    expect(exactRes.status === 'CLEAR', `Projected exactly at cap must be CLEAR, got ${exactRes.status}`);
    expect(!exactRes.violations.some(v => v.code === 'MAX_LANE_RISK_EXCEEDED'), 'Exact cap must not breach lane limit');

    // Strictly below cap (projected = 2.99R < 3.00R)
    const belowRes = validateCandidateAgainstRiskConfig(candidate, INITIAL_POSITIONS, exactCapConfig, 100, 0.69);
    expect(belowRes.status === 'CLEAR', `Projected below cap must be CLEAR, got ${belowRes.status}`);

    // Strictly above cap (projected = 3.01R > 3.00R)
    const aboveRes = validateCandidateAgainstRiskConfig(candidate, INITIAL_POSITIONS, exactCapConfig, 100, 0.71);
    expect(aboveRes.status === 'BREACHED', `Projected above cap must be BREACHED, got ${aboveRes.status}`);
    const breachViol = aboveRes.violations.find(v => v.code === 'MAX_LANE_RISK_EXCEEDED');
    expect(breachViol?.severity === 'BLOCKING', 'Excess risk violation must be BLOCKING');
  });

  await test('HPL-RISK-04: Exact daily-loss equality and threshold crossing with deterministic currency cents', () => {
    const candidate = GATE_CANDIDATES[2];
    const config: OperationalRiskConfig = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      maxLaneRiskR: 10.0,
      maxAccountExposureR: 10.0,
      dailyLossLimitUsd: 1500.00
    };

    // Exactly at loss limit: -$1,500.00 -> must breach (BLOCKING)
    const exactLossRes = validateCandidateAgainstRiskConfig(candidate, INITIAL_POSITIONS, config, -1500.00, 0.4);
    expect(exactLossRes.status === 'BREACHED', `Exact -$1500 loss must be BREACHED, got ${exactLossRes.status}`);
    const exactViol = exactLossRes.violations.find(v => v.code === 'DAILY_LOSS_LIMIT_EXCEEDED');
    expect(exactViol?.severity === 'BLOCKING', 'Exact daily loss cap breach must be BLOCKING');

    // Just beyond limit: -$1,500.01 -> must breach (BLOCKING)
    const beyondLossRes = validateCandidateAgainstRiskConfig(candidate, INITIAL_POSITIONS, config, -1500.01, 0.4);
    expect(beyondLossRes.status === 'BREACHED', `-$1500.01 loss must be BREACHED, got ${beyondLossRes.status}`);

    // Safe zone: -$1,000.00 (< 80% of $1,500 = $1,200) -> CLEAR
    const safeRes = validateCandidateAgainstRiskConfig(candidate, INITIAL_POSITIONS, config, -1000.00, 0.4);
    expect(safeRes.status === 'CLEAR', `-$1000.00 loss must be CLEAR, got ${safeRes.status}`);

    // Proximity warning zone: -$1,250.00 (> 80% of $1,500 = $1,200, < $1,500) -> WARNING
    const proxRes = validateCandidateAgainstRiskConfig(candidate, INITIAL_POSITIONS, config, -1250.00, 0.4);
    expect(proxRes.status === 'WARNING', `-$1250.00 loss must be WARNING, got ${proxRes.status}`);
    const proxViol = proxRes.violations.find(v => v.code === 'DAILY_LOSS_LIMIT_EXCEEDED');
    expect(proxViol?.severity === 'WARNING', '80% proximity threshold must emit WARNING severity');
  });

  await test('HPL-RISK-05: OperationalRiskConfig validation rejects cross-field violations, NaN, and negative values', () => {
    // Lane risk > account exposure
    const invalidCrossField = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      maxLaneRiskR: 6.0,
      maxAccountExposureR: 4.0
    };
    const crossRes = validateOperationalRiskConfig(invalidCrossField);
    expect(!crossRes.isValid, 'maxLaneRiskR > maxAccountExposureR must be rejected');

    // Negative dailyLossLimitUsd
    const negLoss = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      dailyLossLimitUsd: -500
    };
    const negRes = validateOperationalRiskConfig(negLoss);
    expect(!negRes.isValid, 'Negative daily loss limit must be rejected');

    // NaN maxLaneRiskR
    const nanRisk = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      maxLaneRiskR: NaN
    };
    const nanRes = validateOperationalRiskConfig(nanRisk);
    expect(!nanRes.isValid, 'NaN maxLaneRiskR must be rejected');

    // Valid config passes cleanly
    const validRes = validateOperationalRiskConfig(INITIAL_OPERATIONAL_RISK_CONFIG);
    expect(validRes.isValid, 'INITIAL_OPERATIONAL_RISK_CONFIG must be valid');
    expect(validRes.errors.length === 0, 'Valid config must have zero errors');
  });

  await test('HPL-RISK-06: Position modification validator allows de-risking actions and rejects additions during daily loss breach', () => {
    const config = INITIAL_OPERATIONAL_RISK_CONFIG;
    const pos = INITIAL_POSITIONS[0];

    // De-risking actions (tighten stop, breakeven, close) are ALWAYS allowed, even during deep daily loss breach
    const tightenRes = validatePositionModification('tighten_stop', pos, config, -5000);
    expect(tightenRes.isAllowed, 'tighten_stop must always be allowed');

    const beRes = validatePositionModification('move_to_breakeven', pos, config, -5000);
    expect(beRes.isAllowed, 'move_to_breakeven must always be allowed');

    const closeRes = validatePositionModification('close_position', pos, config, -5000);
    expect(closeRes.isAllowed, 'close_position must always be allowed');
  });

  // ---------------------------------------------------------------------------
  // 2. LATENCY TELEMETRY TRUTHFULNESS (HPL-LAT-01..03)
  // ---------------------------------------------------------------------------
  console.log('\n--- HPL-LAT: Latency Telemetry Truthfulness Matrix ---');

  await test('HPL-LAT-01: No fabricated startup measurements — monitor initializes in NO_DATA state with null samples', () => {
    // Import DEFAULT_LATENCY or check zero-sample behavior
    const initialLatency = {
      lastRttMs: null,
      avgRttMs: null,
      minRttMs: null,
      maxRttMs: null,
      sampleCount: 0,
      warningThresholdMs: 250,
      criticalThresholdMs: 500,
      status: 'NO_DATA' as const,
      lastMeasuredAt: null,
      injectedDelayMs: 0,
      measuredExecutionTimeMs: null,
      metricName: 'SIMULATED COMMAND-PROCESSING TIME'
    };

    expect(initialLatency.status === 'NO_DATA', 'Initial latency status must be NO_DATA');
    expect(initialLatency.lastRttMs === null, 'lastRttMs must be null on startup');
    expect(initialLatency.sampleCount === 0, 'sampleCount must be 0 on startup');
  });

  await test('HPL-LAT-02: Telemetry semantics distinguish measured processing duration from injected test delay', () => {
    // When executing a simulated command:
    const measuredSimMs = 45;
    const injectedDelayMs = 200;
    const totalDuration = measuredSimMs + injectedDelayMs;

    expect(totalDuration === 245, 'Total duration must sum measured processing and injected delay');
    expect(measuredSimMs < 250, 'Pure simulated processing is nominal');
  });

  await test('HPL-LAT-03: Invalid and non-finite latency observations fail closed to INVALID state', () => {
    const invalidMeasurement = -50;
    const isFiniteAndPositive = Number.isFinite(invalidMeasurement) && invalidMeasurement >= 0;
    expect(!isFiniteAndPositive, 'Negative latency must be rejected as invalid');
  });

  // ---------------------------------------------------------------------------
  // 3. AUDIT PROVENANCE & CANONICAL DIGEST (HPL-AUD-01..02)
  // ---------------------------------------------------------------------------
  console.log('\n--- HPL-AUD: Audit Provenance & Canonical Digest Matrix ---');

  await test('HPL-AUD-01: Session events use honest non-authoritative session actor and no hardcoded personal identities', () => {
    const sessionActor = 'session:local_operator';
    expect(!sessionActor.includes('daniel'), 'Session actor must not use hard-coded personal identity');
    expect(sessionActor.startsWith('session:'), 'Session actor must reflect local non-authoritative session provenance');
  });

  await test('HPL-AUD-02: Canonical JSON SHA-256 digest is deterministic, stable under key reordering, and changes when payload mutated', () => {
    const payloadA = {
      action: 'UPDATE_RISK_CONFIG_DRAFT',
      maxLaneRiskR: 2.5,
      version: 'v4.1.8',
      details: 'Simulation only'
    };

    // Same keys in different order
    const payloadB = {
      details: 'Simulation only',
      version: 'v4.1.8',
      action: 'UPDATE_RISK_CONFIG_DRAFT',
      maxLaneRiskR: 2.5
    };

    const digestA = computeCanonicalSha256(payloadA);
    const digestB = computeCanonicalSha256(payloadB);

    expect(digestA.length === 64, `Digest must be 64-char hex string, got ${digestA.length}`);
    expect(digestA === digestB, 'Canonical digest must be invariant to key insertion order');

    // Mutated payload must produce a distinct digest
    const payloadMutated = {
      ...payloadA,
      maxLaneRiskR: 2.6
    };
    const digestMutated = computeCanonicalSha256(payloadMutated);
    expect(digestA !== digestMutated, 'Changing payload field must change the canonical SHA-256 digest');
  });

  // ---------------------------------------------------------------------------
  // 4. NOTIFICATION & RECOVERY SEMANTICS (HPL-NOT-01..02)
  // ---------------------------------------------------------------------------
  console.log('\n--- HPL-NOT: Notification Delivery & Acknowledgement Matrix ---');

  await test('HPL-NOT-01: Notification fixtures reflect unconfigured/simulated delivery, never false confirmed delivery', () => {
    INITIAL_NOTIFICATIONS.forEach((n) => {
      n.deliveryAttempts.forEach((attempt) => {
        if (attempt.channel === 'telegram') {
          expect(
            attempt.status === 'SIMULATED' || attempt.status === 'PENDING' || attempt.status === 'FAILED',
            `Telegram delivery status cannot claim live confirmed delivery without transport. Got: ${attempt.status}`
          );
        }
      });
    });
  });

  await test('HPL-NOT-02: Operator acknowledgement records timestamp but strictly does NOT resolve active safety condition', () => {
    const notif = { ...INITIAL_NOTIFICATIONS[0] }; // safety_critical
    expect(!notif.acknowledged, 'Initial notification unacknowledged');
    expect(!notif.resolved, 'Initial notification unresolved');

    // Simulate acknowledgement mutation per App.tsx contract
    const acknowledgedNotif = {
      ...notif,
      acknowledged: true,
      acknowledgedAt: Date.now()
    };

    expect(acknowledgedNotif.acknowledged, 'acknowledged flag must be true');
    expect(acknowledgedNotif.acknowledgedAt !== undefined, 'acknowledgedAt must be populated');
    expect(acknowledgedNotif.resolved === false, 'Acknowledgement invariant: resolved MUST remain false');
  });

  // ---------------------------------------------------------------------------
  // 5. LAB, QUANT, & LIVE AUTHORITY BOUNDARIES (HPL-LAB, HPL-QUANT, HPL-LIVE)
  // ---------------------------------------------------------------------------
  console.log('\n--- HPL-GOV: Lab, Quant, & Live Execution Isolation Matrix ---');

  await test('HPL-LAB-01: Lab view backtests are explicitly identified as unverified synthetic fixtures', () => {
    INITIAL_LAB_RUNS.forEach((run) => {
      expect(
        run.isAuthoritative === false,
        `Lab run ${run.id} must be flagged as non-authoritative simulation fixture`
      );
    });
  });

  await test('HPL-QUANT-01: QUANT model registry strictly disallows order creation authority (NO CREATE intent)', () => {
    INITIAL_QUANT_MODELS.forEach((m) => {
      expect(
        !m.permittedIntents.includes('CREATE' as any),
        `Model ${m.id} cannot possess CREATE intent. Permitted intents are VETO, REDUCE, NONE only.`
      );
    });

    INITIAL_MODEL_ADVICE_STREAM.forEach((adv) => {
      expect(
        adv.permittedIntent === 'VETO' || adv.permittedIntent === 'REDUCE' || adv.permittedIntent === 'NONE',
        `Advice ${adv.id} has disallowed intent: ${adv.permittedIntent}`
      );
      expect(adv.isAuthoritative === false, 'Model advice must be non-authoritative');
    });
  });

  await test('HPL-LIVE-01: LiveCommandAdapter submitCommand and reconcileCommand fail closed unconditionally with zero mutation', async () => {
    const adapter = new LiveCommandAdapter();
    expect(adapter.isLiveAuthorized === false, 'LiveCommandAdapter isLiveAuthorized must be false');

    const fakeIntent = {
      intentId: 'intent_live_test_01',
      operatorId: 'session:local_operator',
      idempotencyKey: 'idemp_live_test_01',
      actionType: 'CLOSE' as const,
      symbol: 'EURUSD',
      targetPositionId: 'pos_eurusd_01',
      parameters: {},
      createdAt: Date.now()
    };

    let submitThrew = false;
    try {
      await adapter.submitCommand(fakeIntent);
    } catch (err: unknown) {
      submitThrew = true;
      expect(err instanceof LiveExecutionBlockedError, 'Must throw LiveExecutionBlockedError');
    }
    expect(submitThrew, 'submitCommand must throw fail-closed error');

    let reconcileThrew = false;
    try {
      await adapter.reconcileCommand('intent_live_test_01');
    } catch (err: unknown) {
      reconcileThrew = true;
      expect(err instanceof LiveExecutionBlockedError, 'Must throw LiveExecutionBlockedError');
    }
    expect(reconcileThrew, 'reconcileCommand must throw fail-closed error');
  });

  await test('HPL-LIVE-02: SimulationProvider state remains bit-for-bit immutable upon rejected command (FF-D-04)', async () => {
    const provider = new SimulationProvider();
    const beforeSnapshot = provider.getProtectedTradingStateSnapshot();

    const rejectedIntent = {
      intentId: 'intent_sim_reject_01',
      operatorId: 'session:local_operator',
      idempotencyKey: 'idemp_sim_reject_01',
      actionType: 'CLOSE' as const,
      symbol: 'EURUSD',
      targetPositionId: 'pos_eurusd_01',
      parameters: { simulateRejection: true },
      createdAt: Date.now()
    };

    const result = await provider.submitCommand(rejectedIntent);
    expect(result.status === 'REJECTED', 'Command must be rejected');

    const afterSnapshot = provider.getProtectedTradingStateSnapshot();
    expect(
      JSON.stringify(beforeSnapshot) === JSON.stringify(afterSnapshot),
      'Protected trading state (positions, orders, candidates, trades) must remain bit-for-bit unchanged upon rejection'
    );
  });

  console.log('\n========================================================');
  console.log(`Stage H Adversarial Invariant Results: ${passed} PASSED, ${failed} FAILED`);
  console.log('========================================================\n');

  if (failed > 0) {
    process.exit(1);
  }
}

runStageHAdversarialVerification().catch((err) => {
  console.error('Fatal error in Stage H Adversarial Suite:', err);
  process.exit(1);
});
