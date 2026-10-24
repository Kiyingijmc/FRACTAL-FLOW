/**
 * FRACTAL-FLOW Automated Risk Validator & Real-Time Latency Invariant Suite
 * Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY
 */

import React from 'react';
import { JSDOM } from 'jsdom';
import { renderToString } from 'react-dom/server';
import { 
  validateCandidateAgainstRiskConfig, 
  calculateLaneRiskR, 
  calculateAccountExposureR, 
  validatePositionModification 
} from '../utils/riskValidator';
import { 
  INITIAL_OPERATIONAL_RISK_CONFIG, 
  INITIAL_POSITIONS, 
  GATE_CANDIDATES 
} from '../data/mockData';
import { OperationalRiskConfig, GateCandidate, LatencyMetrics } from '../types';
import { AutomatedRiskValidatorBadge } from '../components/AutomatedRiskValidator';
import { Header } from '../components/Header';
import { GateChainStrip } from '../components/GateChainStrip';

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

async function runRiskAndLatencyVerification() {
  console.log('========================================================');
  console.log('FRACTAL-FLOW GUI — Automated Risk Validator & Latency Monitor');
  console.log('Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY');
  console.log('========================================================\n');

  // --- SECTION 1: AUTOMATED RISK VALIDATOR INVARIANT CHECKS ---
  console.log('--- RISK-VAL: Automated Risk Validator Against OperationalRiskConfig ---');

  await test('RISK-01: Detects Lane Risk Cap breach when candidate risk exceeds maxLaneRiskR', () => {
    const candidate = GATE_CANDIDATES[0]; // EURUSD, lane: ACT_PRIMARY
    const config: OperationalRiskConfig = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      maxLaneRiskR: 1.5, // Tightened lane limit
      maxAccountExposureR: 5.0,
    };

    const validation = validateCandidateAgainstRiskConfig(
      candidate,
      INITIAL_POSITIONS,
      config,
      312.5,
      0.8 // 0.8R candidate setup
    );

    if (validation.status !== 'BREACHED') {
      throw new Error(`Expected BREACHED status, got: ${validation.status}`);
    }

    const laneViolation = validation.violations.find((v) => v.code === 'MAX_LANE_RISK_EXCEEDED');
    if (!laneViolation) {
      throw new Error('Expected MAX_LANE_RISK_EXCEEDED violation to be flagged');
    }
    if (laneViolation.severity !== 'BLOCKING') {
      throw new Error('Lane risk limit breach must be BLOCKING');
    }
  });

  await test('RISK-02: Detects Total Account Exposure Cap breach when aggregate risk exceeds maxAccountExposureR', () => {
    const candidate = GATE_CANDIDATES[1]; // GBPUSD
    const config: OperationalRiskConfig = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      maxLaneRiskR: 10.0, // High lane limit to isolate account limit
      maxAccountExposureR: 2.0, // Strict account limit
    };

    const validation = validateCandidateAgainstRiskConfig(
      candidate,
      INITIAL_POSITIONS,
      config,
      312.5,
      0.6
    );

    if (validation.status !== 'BREACHED') {
      throw new Error(`Expected BREACHED status, got: ${validation.status}`);
    }

    const expViolation = validation.violations.find((v) => v.code === 'MAX_ACCOUNT_EXPOSURE_EXCEEDED');
    if (!expViolation) {
      throw new Error('Expected MAX_ACCOUNT_EXPOSURE_EXCEEDED violation to be flagged');
    }
  });

  await test('RISK-03: Detects Daily Loss Limit breach when daily PnL exceeds dailyLossLimitUsd', () => {
    const candidate = GATE_CANDIDATES[2]; // USDJPY
    const config: OperationalRiskConfig = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      dailyLossLimitUsd: 1000,
    };

    const validation = validateCandidateAgainstRiskConfig(
      candidate,
      INITIAL_POSITIONS,
      config,
      -1250.0 // Breached daily loss
    );

    if (validation.status !== 'BREACHED') {
      throw new Error(`Expected BREACHED status due to daily loss breach, got: ${validation.status}`);
    }

    const lossViolation = validation.violations.find((v) => v.code === 'DAILY_LOSS_LIMIT_EXCEEDED');
    if (!lossViolation) {
      throw new Error('Expected DAILY_LOSS_LIMIT_EXCEEDED violation to be flagged');
    }
  });

  await test('RISK-04: Returns CLEAR when candidate risk is strictly within all limits', () => {
    const candidate = GATE_CANDIDATES[2];
    const config: OperationalRiskConfig = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      maxLaneRiskR: 10.0,
      maxAccountExposureR: 10.0,
      dailyLossLimitUsd: 5000,
    };

    const validation = validateCandidateAgainstRiskConfig(
      candidate,
      INITIAL_POSITIONS,
      config,
      500.0,
      0.4
    );

    if (validation.status !== 'CLEAR') {
      throw new Error(`Expected CLEAR status for compliant candidate, got: ${validation.status}`);
    }
    if (validation.violations.length !== 0) {
      throw new Error(`Expected zero violations, got: ${validation.violations.length}`);
    }
  });

  await test('RISK-05: Warning badge renders on GateCandidate with correct data-testid and status', () => {
    const candidate = GATE_CANDIDATES[0];
    const config: OperationalRiskConfig = {
      ...INITIAL_OPERATIONAL_RISK_CONFIG,
      maxLaneRiskR: 1.0,
    };
    const validation = validateCandidateAgainstRiskConfig(candidate, INITIAL_POSITIONS, config, 300);

    const html = renderToString(
      React.createElement(AutomatedRiskValidatorBadge, {
        validation,
        candidate,
        onOpenDetails: () => {},
      })
    );

    const dom = new JSDOM(html);
    const badge = dom.window.document.querySelector(`[data-testid="risk-badge-${candidate.id}"]`);
    if (!badge) {
      throw new Error(`Badge with testid risk-badge-${candidate.id} not found in DOM`);
    }
    if (badge.getAttribute('data-risk-status') !== 'BREACHED') {
      throw new Error(`Expected data-risk-status to be BREACHED, got: ${badge.getAttribute('data-risk-status')}`);
    }
    if (!badge.textContent?.includes('BREACH') && !badge.textContent?.includes('⚠️')) {
      throw new Error(`Expected warning/breach text in badge, got: ${badge.textContent}`);
    }
  });

  // --- SECTION 2: REAL-TIME LATENCY MONITOR INVARIANTS ---
  console.log('\n--- LATENCY-MON: Real-Time Latency Monitor in Header ---');

  await test('LATENCY-01: Nominal latency status (<250ms) renders without critical warning banner', () => {
    const nominalLatency: LatencyMetrics = {
      lastRttMs: 145,
      avgRttMs: 160,
      minRttMs: 110,
      maxRttMs: 210,
      sampleCount: 15,
      warningThresholdMs: 250,
      criticalThresholdMs: 500,
      status: 'NOMINAL',
      lastMeasuredAt: Date.now(),
      injectedDelayMs: 0,
    };

    const html = renderToString(
      React.createElement(Header, {
        equity: 48250,
        dailyPnl: 312.5,
        openRiskR: 1.8,
        lane: 'ACT_PRIMARY',
        onLaneChange: () => {},
        isSimPaused: false,
        onToggleSimPause: () => {},
        telemetry: {
          source: 'SIM_ENGINE',
          status: 'HEALTHY',
          freshnessTimestamp: Date.now(),
          isAuthoritative: false,
          staleThresholdMs: 5000,
          epoch: 418,
          bridgeStatus: 'SIM_OK',
          fenceStatus: 'FENCE_OK',
        },
        applicationMode: 'SIMULATION_SANDBOX',
        latency: nominalLatency,
      })
    );

    const dom = new JSDOM(html);
    const desktopMonitor = dom.window.document.querySelector('[data-testid="latency-monitor"]');
    if (!desktopMonitor) {
      throw new Error('Desktop latency monitor not found in Header');
    }
    if (!desktopMonitor.textContent?.includes('145ms')) {
      throw new Error(`Expected 145ms in latency monitor, found: ${desktopMonitor.textContent}`);
    }
    if (!desktopMonitor.textContent?.includes('NOMINAL')) {
      throw new Error(`Expected NOMINAL status in latency monitor, found: ${desktopMonitor.textContent}`);
    }

    const warningBadge = dom.window.document.querySelector('[data-testid="latency-warning-badge"]');
    if (warningBadge) {
      throw new Error('Warning badge should not be present when latency is NOMINAL');
    }
  });

  await test('LATENCY-02: Elevated and exceeded delay thresholds display visual warning badge in Header', () => {
    const exceededLatency: LatencyMetrics = {
      lastRttMs: 620,
      avgRttMs: 480,
      minRttMs: 130,
      maxRttMs: 620,
      sampleCount: 20,
      warningThresholdMs: 250,
      criticalThresholdMs: 500,
      status: 'EXCEEDED',
      lastMeasuredAt: Date.now(),
      injectedDelayMs: 400,
    };

    const html = renderToString(
      React.createElement(Header, {
        equity: 48250,
        dailyPnl: 312.5,
        openRiskR: 1.8,
        lane: 'ACT_PRIMARY',
        onLaneChange: () => {},
        isSimPaused: false,
        onToggleSimPause: () => {},
        telemetry: {
          source: 'SIM_ENGINE',
          status: 'HEALTHY',
          freshnessTimestamp: Date.now(),
          isAuthoritative: false,
          staleThresholdMs: 5000,
          epoch: 418,
          bridgeStatus: 'SIM_OK',
          fenceStatus: 'FENCE_OK',
        },
        applicationMode: 'SIMULATION_SANDBOX',
        latency: exceededLatency,
      })
    );

    const dom = new JSDOM(html);
    const warningBadge = dom.window.document.querySelector('[data-testid="latency-warning-badge"]');
    if (!warningBadge) {
      throw new Error('Expected visual warning badge [data-testid="latency-warning-badge"] when latency is EXCEEDED');
    }
    if (!warningBadge.textContent?.includes('DELAY > 500ms')) {
      throw new Error(`Expected DELAY > 500ms in warning badge, got: ${warningBadge.textContent}`);
    }

    const mobileWarning = dom.window.document.querySelector('[data-testid="latency-warning-badge-mobile"]');
    if (!mobileWarning) {
      throw new Error('Expected mobile visual warning badge [data-testid="latency-warning-badge-mobile"]');
    }
  });

  await test('LATENCY-03: Mobile header implements accessible touch target for latency monitor', () => {
    const nominalLatency: LatencyMetrics = {
      lastRttMs: 180,
      avgRttMs: 175,
      minRttMs: 120,
      maxRttMs: 240,
      sampleCount: 10,
      warningThresholdMs: 250,
      criticalThresholdMs: 500,
      status: 'NOMINAL',
      lastMeasuredAt: Date.now(),
      injectedDelayMs: 0,
    };

    const html = renderToString(
      React.createElement(Header, {
        equity: 48250,
        dailyPnl: 312.5,
        openRiskR: 1.8,
        lane: 'ACT_PRIMARY',
        onLaneChange: () => {},
        isSimPaused: false,
        onToggleSimPause: () => {},
        telemetry: {
          source: 'SIM_ENGINE',
          status: 'HEALTHY',
          freshnessTimestamp: Date.now(),
          isAuthoritative: false,
          staleThresholdMs: 5000,
          epoch: 418,
          bridgeStatus: 'SIM_OK',
          fenceStatus: 'FENCE_OK',
        },
        applicationMode: 'SIMULATION_SANDBOX',
        latency: nominalLatency,
      })
    );

    const dom = new JSDOM(html);
    const mobileBtn = dom.window.document.querySelector('[data-testid="latency-monitor-mobile"]');
    if (!mobileBtn) {
      throw new Error('Mobile latency button [data-testid="latency-monitor-mobile"] not found');
    }
    if (!mobileBtn.className.includes('min-h-[44px]')) {
      throw new Error(`Mobile latency monitor button lacks min-h-[44px] touch target: ${mobileBtn.className}`);
    }
  });

  console.log('\n========================================================');
  console.log(`Risk & Latency Invariant Results: ${passed} PASSED, ${failed} FAILED`);
  console.log('========================================================\n');

  if (failed > 0) {
    process.exit(1);
  }
}

runRiskAndLatencyVerification().catch((err) => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
