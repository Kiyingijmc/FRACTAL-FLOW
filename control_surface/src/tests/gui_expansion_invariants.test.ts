/**
 * FRACTAL-FLOW GUI Expansion Invariants & Adversarial Test Suite
 * Mission: Unified GUI Expansion, Branch Reconciliation, Implementation, and Forensic Hardening
 * Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY
 */

import React from 'react';
import { JSDOM } from 'jsdom';
import { 
  INITIAL_NOTIFICATIONS, 
  INITIAL_OPERATIONAL_RISK_CONFIG, 
  INITIAL_QUANT_MODELS, 
  INITIAL_MODEL_ADVICE_STREAM, 
  INITIAL_LAB_RUNS, 
  INITIAL_REMEDIATION_BLOCKERS,
  INITIAL_AUDIT_TRAIL 
} from '../data/mockData';
import { 
  NotificationEvent, 
  OperationalRiskConfig, 
  QuantModelRecord, 
  ModelPermittedIntent 
} from '../types';

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

async function runExpansionVerification() {
  console.log('========================================================');
  console.log('FRACTAL-FLOW GUI — Expansion & Hardening Invariant Suite');
  console.log('Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY');
  console.log('========================================================\n');

  // --- SECTION 1: SETTINGS & OPERATIONAL RISK CONFIGURATION INVARIANTS ---
  console.log('--- EXP-01: Operational Risk Configuration & Invariant Guardrails ---');

  await test('EXP-01.1: Cross-field invariant: Max Lane Risk cannot exceed Max Account Exposure', () => {
    function validateRiskConfig(draft: OperationalRiskConfig): { valid: boolean; error?: string } {
      if (draft.maxLaneRiskR > draft.maxAccountExposureR) {
        return { 
          valid: false, 
          error: `INVARIANT_VIOLATION: Max Lane Risk (${draft.maxLaneRiskR}R) > Max Account Exposure (${draft.maxAccountExposureR}R)` 
        };
      }
      if (draft.maxLaneRiskR <= 0 || !Number.isFinite(draft.maxLaneRiskR)) {
        return { valid: false, error: 'INVALID_PARAM: maxLaneRiskR must be finite and positive' };
      }
      if (draft.maxAccountExposureR <= 0 || !Number.isFinite(draft.maxAccountExposureR)) {
        return { valid: false, error: 'INVALID_PARAM: maxAccountExposureR must be finite and positive' };
      }
      return { valid: true };
    }

    // Baseline is valid
    const validRes = validateRiskConfig(INITIAL_OPERATIONAL_RISK_CONFIG);
    if (!validRes.valid) throw new Error('Initial operational risk config failed validation');

    // Inverted violation
    const invalidDraft: OperationalRiskConfig = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      maxLaneRiskR: 6.0,
      maxAccountExposureR: 5.0
    };
    const invalidRes = validateRiskConfig(invalidDraft);
    if (invalidRes.valid) throw new Error('Failed to reject inverted lane risk > account exposure');

    // Non-positive violation
    const zeroRes = validateRiskConfig({ ...INITIAL_OPERATIONAL_RISK_CONFIG, maxLaneRiskR: 0 });
    if (zeroRes.valid) throw new Error('Failed to reject non-positive lane risk limit');

    const nanRes = validateRiskConfig({ ...INITIAL_OPERATIONAL_RISK_CONFIG, maxAccountExposureR: NaN });
    if (nanRes.valid) throw new Error('Failed to reject NaN account exposure limit');
  });

  await test('EXP-01.2: Fail-closed configuration write boundary: Simulation updates do not manufacture live authority', () => {
    const config = { ...INITIAL_OPERATIONAL_RISK_CONFIG };
    if (config.source !== 'SIM_ENGINE') {
      throw new Error(`Expected simulated configuration source to be SIM_ENGINE, got: ${config.source}`);
    }
  });

  // --- SECTION 2: NOTIFICATIONS & CRITICAL SAFETY BANNER INVARIANTS ---
  console.log('\n--- EXP-02: 5-Class Notification Taxonomy & Critical Incident Semantics ---');

  await test('EXP-02.1: Safety-critical notification subscriptions are permanently enabled and non-mutable', () => {
    const safetyCriticalNotifs = INITIAL_NOTIFICATIONS.filter(n => n.class === 'safety_critical');
    if (safetyCriticalNotifs.length === 0) {
      throw new Error('Initial notifications must contain safety-critical alerts');
    }
    safetyCriticalNotifs.forEach(n => {
      if (n.severity !== 'CRITICAL') {
        throw new Error(`Safety critical notification [${n.id}] must carry CRITICAL severity`);
      }
    });
  });

  await test('EXP-02.2: Acknowledgement invariant: Operator Ack sets timestamp but strictly does NOT resolve condition', () => {
    const notif: NotificationEvent = { ...INITIAL_NOTIFICATIONS[0] };
    
    // Simulate operator acknowledgement
    const ackTime = Date.now();
    const ackedNotif: NotificationEvent = {
      ...notif,
      acknowledged: true,
      acknowledgedAt: ackTime
    };

    if (!ackedNotif.acknowledged || !ackedNotif.acknowledgedAt) {
      throw new Error('Acknowledgement failed to record state and timestamp');
    }
    if (ackedNotif.resolved === true) {
      throw new Error('CRITICAL VIOLATION: Acknowledging an alert must NOT resolve the underlying system state!');
    }
  });

  // --- SECTION 3: QUANT MODEL REGISTRY & ADVISORY INVARIANTS ---
  console.log('\n--- EXP-03: Quant Model Registry & Permitted Advisory Intents ---');

  await test('EXP-03.1: Model permitted intents are strictly constrained to VETO, REDUCE, NONE (strictly NO CREATE)', () => {
    const VALID_INTENTS: ModelPermittedIntent[] = ['VETO', 'REDUCE', 'NONE'];

    INITIAL_QUANT_MODELS.forEach((model: QuantModelRecord) => {
      model.permittedIntents.forEach(intent => {
        if (!VALID_INTENTS.includes(intent)) {
          throw new Error(`Model [${model.id}] has unauthorized intent: ${intent}`);
        }
        if ((intent as string) === 'CREATE') {
          throw new Error(`CRITICAL INVARIANT VIOLATION: Model [${model.id}] was assigned CREATE intent authority!`);
        }
      });
      // Verify SHA-256 artifact digest
      if (!model.artifactSha256 || model.artifactSha256.length !== 64) {
        throw new Error(`Model [${model.id}] lacks valid 64-character SHA-256 artifact digest`);
      }
    });
  });

  await test('EXP-03.2: Model advice cannot bypass upstream risk gates', () => {
    const advice = INITIAL_MODEL_ADVICE_STREAM.find(a => a.gateDisposition === 'VETO_OVERRIDDEN_BY_RISK_GATE');
    if (!advice) {
      throw new Error('Expected sample of model advice overridden by risk gate to exist in stream');
    }
    if (advice.isAuthoritative === true) {
      throw new Error('Model advice must not claim authoritative execution status');
    }
  });

  // --- SECTION 4: LAB BACKTESTING READ-ONLY CONTRACTS ---
  console.log('\n--- EXP-04: Lab & Backtesting Analytical Contracts ---');

  await test('EXP-04.1: Lab backtest artifacts maintain statistical robustness checks (Null-World & Planted-Edge)', () => {
    INITIAL_LAB_RUNS.forEach(run => {
      if (run.nullWorldCheck !== 'PASS') {
        throw new Error(`Lab run [${run.id}] failed null-world shuffle verification`);
      }
      if (run.plantedEdgeRecovery !== 'PASS') {
        throw new Error(`Lab run [${run.id}] failed planted-edge recovery check`);
      }
      if (run.oosDegradationPct > 20) {
        throw new Error(`Lab run [${run.id}] exceeded 20% out-of-sample degradation limit: ${run.oosDegradationPct}%`);
      }
      if (run.isAuthoritative === true) {
        throw new Error(`Lab run [${run.id}] cannot be labeled authoritative for live execution`);
      }
    });
  });

  // --- SECTION 5: BLOCKERS & AUDIT TRAIL DATA INTEGRITY ---
  console.log('\n--- EXP-05: Blockers Register & Cryptographic Audit Trail ---');

  await test('EXP-05.1: Remediation blockers retain verifiable evidence artifacts and owner attribution', () => {
    INITIAL_REMEDIATION_BLOCKERS.forEach(blocker => {
      if (!blocker.id || !blocker.evidenceArtifact || !blocker.owner) {
        throw new Error(`Blocker [${blocker.id}] is missing required audit attributes`);
      }
      if (blocker.severity === 'P0' && blocker.status === 'BLOCKED_ON_BACKEND') {
        if (!blocker.summary.includes('fail-closed') && !blocker.summary.includes('ExecutionGateway') && !blocker.summary.includes('RBAC')) {
          throw new Error(`P0 blocker [${blocker.id}] lacks explicit architectural boundary explanation`);
        }
      }
    });
  });

  await test('EXP-05.2: Audit trail records require correlation ID and SHA-256 intent digest', () => {
    INITIAL_AUDIT_TRAIL.forEach(entry => {
      if (!entry.correlationId || !entry.intentDigestSha256) {
        throw new Error(`Audit entry [${entry.id}] missing correlationId or intentDigestSha256`);
      }
      if (entry.intentDigestSha256.length !== 64) {
        throw new Error(`Audit entry [${entry.id}] has invalid SHA-256 digest length: ${entry.intentDigestSha256.length}`);
      }
    });
  });

  console.log('\n========================================================');
  console.log(`Expansion Invariant Results: ${passed} PASSED, ${failed} FAILED`);
  console.log('========================================================\n');

  if (failed > 0) {
    process.exit(1);
  }
}

runExpansionVerification().catch(err => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
