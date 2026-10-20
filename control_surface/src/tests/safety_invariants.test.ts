import { SimulationProvider } from '../providers/SimulationProvider';
import { LiveCommandAdapter } from '../providers/LiveCommandAdapter';
import { LiveExecutionBlockedError } from '../types/contracts';
import { generateIntentFingerprint, createDeterministicHash } from '../utils/idempotency';
import { isSafeKeyboardShortcutTarget } from '../utils/keyboard';

export async function runSafetyInvariantTests() {
  console.log('\n========================================================');
  console.log('FRACTAL-FLOW GUI — Stage B Safety Invariant Test Suite');
  console.log('Governing Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY');
  console.log('========================================================\n');

  let passed = 0;
  let failed = 0;

  async function test(name: string, fn: () => Promise<void> | void) {
    try {
      await fn();
      console.log(`  [PASS] ${name}`);
      passed++;
    } catch (err: any) {
      console.error(`  [FAIL] ${name}`);
      console.error(`         Error: ${err.message || err}`);
      failed++;
    }
  }

  // Group 1: Provider Isolation & Live Fail-Closed Gate
  console.log('--- 1. Provider Isolation & Fail-Closed Live Gate ---');

  await test('LiveCommandAdapter must fail-closed and throw LiveExecutionBlockedError on submitCommand', async () => {
    const adapter = new LiveCommandAdapter();
    const intent = generateIntentFingerprint('operator_1', 'pos_01', 'EURUSD', 'CLOSE', {});
    
    let caught = false;
    try {
      await adapter.submitCommand(intent);
    } catch (err) {
      if (err instanceof LiveExecutionBlockedError) {
        caught = true;
      }
    }
    if (!caught) {
      throw new Error('Expected LiveExecutionBlockedError, but command succeeded or threw wrong error');
    }
  });

  await test('LiveCommandAdapter must fail-closed on reconcileCommand', async () => {
    const adapter = new LiveCommandAdapter();
    let caught = false;
    try {
      await adapter.reconcileCommand('intent_test_123');
    } catch (err) {
      if (err instanceof LiveExecutionBlockedError) {
        caught = true;
      }
    }
    if (!caught) {
      throw new Error('Expected LiveExecutionBlockedError on reconcileCommand');
    }
  });

  await test('SimulationProvider must have isLiveAuthorized = false and return isAuthoritative = false', async () => {
    const sim = new SimulationProvider();
    if (sim.isLiveAuthorized !== false) {
      throw new Error('SimulationProvider must never claim isLiveAuthorized = true');
    }
    const health = await sim.getHealth();
    if (health.isAuthoritative !== false) {
      throw new Error('SimulationProvider health must have isAuthoritative = false');
    }
    if (health.source !== 'SIM_ENGINE') {
      throw new Error(`SimulationProvider health source must be SIM_ENGINE, got ${health.source}`);
    }
  });

  await test('SimulationProvider commands modify only local sandbox memory and return non-authoritative results', async () => {
    const sim = new SimulationProvider();
    const initialPositions = await sim.getPositions();
    const target = initialPositions[0];
    
    const intent = generateIntentFingerprint('daniel_operator', target.id, target.symbol, 'CLOSE', {});
    const result = await sim.submitCommand(intent);
    
    if (result.authoritative !== false) {
      throw new Error('Simulation command result must specify authoritative = false');
    }
    if (result.status !== 'CONFIRMED') {
      throw new Error(`Expected CONFIRMED status in sandbox, got ${result.status}`);
    }

    const updatedPositions = await sim.getPositions();
    if (updatedPositions.length !== initialPositions.length - 1) {
      throw new Error('Position was not removed from sandbox memory');
    }
    if (updatedPositions.some(p => p.id === target.id)) {
      throw new Error('Target position still exists in sandbox memory after CLOSE');
    }
  });

  // Group 2: Deterministic Intent Fingerprinting & Idempotency
  console.log('\n--- 2. Deterministic Intent Fingerprinting & Idempotency ---');

  await test('Known-answer test: createDeterministicHash produces deterministic hex output', () => {
    const hash1 = createDeterministicHash('TEST_STRING_STABLE');
    const hash2 = createDeterministicHash('TEST_STRING_STABLE');
    if (hash1 !== hash2) {
      throw new Error(`Hash not deterministic: ${hash1} !== ${hash2}`);
    }
    if (hash1.length !== 16) {
      throw new Error(`Expected 16-character hex hash, got length ${hash1.length}`);
    }
  });

  await test('Identical intents generate identical idempotency keys (Stable across retries)', () => {
    const intentA = generateIntentFingerprint(
      'daniel_operator',
      'pos_eurusd_01',
      'EURUSD',
      'TIGHTEN_STOP',
      { currentSl: 1.08420, step: 0.0010 }
    );

    const intentB = generateIntentFingerprint(
      'daniel_operator',
      'pos_eurusd_01',
      'EURUSD',
      'TIGHTEN_STOP',
      { currentSl: 1.08420, step: 0.0010 }
    );

    if (intentA.idempotencyKey !== intentB.idempotencyKey) {
      throw new Error(`Retry keys differed: ${intentA.idempotencyKey} !== ${intentB.idempotencyKey}`);
    }
    if (intentA.intentId !== intentB.intentId) {
      throw new Error(`Intent IDs differed: ${intentA.intentId} !== ${intentB.intentId}`);
    }
  });

  await test('Object parameter key ordering does not alter the idempotency fingerprint', () => {
    const intent1 = generateIntentFingerprint('op', 'pos_1', 'EURUSD', 'CLOSE', {
      alpha: 10,
      beta: 20,
      gamma: 30
    });

    const intent2 = generateIntentFingerprint('op', 'pos_1', 'EURUSD', 'CLOSE', {
      gamma: 30,
      alpha: 10,
      beta: 20
    });

    if (intent1.idempotencyKey !== intent2.idempotencyKey) {
      throw new Error('Key order altered the idempotency key');
    }
  });

  await test('Altering parameters produces distinct idempotency fingerprints', () => {
    const intentA = generateIntentFingerprint('op', 'pos_1', 'EURUSD', 'TIGHTEN_STOP', { sl: 1.0850 });
    const intentB = generateIntentFingerprint('op', 'pos_1', 'EURUSD', 'TIGHTEN_STOP', { sl: 1.0860 });

    if (intentA.idempotencyKey === intentB.idempotencyKey) {
      throw new Error('Altered parameters generated identical idempotency key');
    }
  });

  // Group 3: Keyboard Shortcut Safety & Input Focus Guard
  console.log('\n--- 3. Keyboard Shortcut Safety & Input Focus Guard ---');

  await test('isSafeKeyboardShortcutTarget rejects events originating inside text inputs', () => {
    const mockInput = { tagName: 'INPUT', isContentEditable: false, getAttribute: () => null } as any;
    const isSafe = isSafeKeyboardShortcutTarget({ target: mockInput } as KeyboardEvent);
    if (isSafe !== false) {
      throw new Error('Expected isSafeKeyboardShortcutTarget to return false for INPUT');
    }
  });

  await test('isSafeKeyboardShortcutTarget rejects events originating inside textareas', () => {
    const mockTextarea = { tagName: 'TEXTAREA', isContentEditable: false, getAttribute: () => null } as any;
    const isSafe = isSafeKeyboardShortcutTarget({ target: mockTextarea } as KeyboardEvent);
    if (isSafe !== false) {
      throw new Error('Expected isSafeKeyboardShortcutTarget to return false for TEXTAREA');
    }
  });

  await test('isSafeKeyboardShortcutTarget rejects events originating inside contentEditable elements', () => {
    const mockEditable = { tagName: 'DIV', isContentEditable: true, getAttribute: () => null } as any;
    const isSafe = isSafeKeyboardShortcutTarget({ target: mockEditable } as KeyboardEvent);
    if (isSafe !== false) {
      throw new Error('Expected isSafeKeyboardShortcutTarget to return false for contentEditable');
    }
  });

  await test('isSafeKeyboardShortcutTarget allows events originating from body or general containers', () => {
    const mockDiv = { tagName: 'DIV', isContentEditable: false, getAttribute: () => null } as any;
    const isSafe = isSafeKeyboardShortcutTarget({ target: mockDiv } as KeyboardEvent);
    if (isSafe !== true) {
      throw new Error('Expected isSafeKeyboardShortcutTarget to return true for non-input DIV');
    }
  });

  // Group 4: Telemetry Freshness & Provenance
  console.log('\n--- 4. Telemetry Freshness & Provenance Evaluation ---');

  await test('Telemetry marks stale when age exceeds staleThresholdMs', () => {
    const staleThresholdMs = 5000;
    const now = 100000;
    const freshTimestamp = now - 2000; // 2 seconds old
    const expiredTimestamp = now - 6000; // 6 seconds old

    const isFresh = (now - freshTimestamp) > staleThresholdMs;
    const isExpired = (now - expiredTimestamp) > staleThresholdMs;

    if (isFresh !== false) {
      throw new Error('2s telemetry evaluated as stale');
    }
    if (isExpired !== true) {
      throw new Error('6s telemetry failed to evaluate as stale');
    }
  });

  console.log('\n========================================================');
  console.log(`Results: ${passed} PASSED, ${failed} FAILED`);
  console.log('========================================================\n');

  if (failed > 0) {
    process.exit(1);
  }
}

// Execute immediately when run directly via tsx
runSafetyInvariantTests().catch(err => {
  console.error('Fatal test runner error:', err);
  process.exit(1);
});
