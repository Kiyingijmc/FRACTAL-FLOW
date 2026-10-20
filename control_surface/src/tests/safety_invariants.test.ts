import { LiveCommandAdapter } from '../providers/LiveCommandAdapter';
import { SimulationProvider } from '../providers/SimulationProvider';
import { 
  sha256Hex, 
  canonicalizeValue, 
  createIntentFingerprint, 
  createLogicalIntentId, 
  CanonicalizationError 
} from '../utils/idempotency';
import { 
  isSafeKeyboardShortcutTarget, 
  isValidShortcutEvent, 
  isKeyboardShortcutAllowed 
} from '../utils/keyboard';
import { evaluateTelemetryFreshness } from '../utils/telemetry';
import { LiveExecutionBlockedError, TelemetryProvenance } from '../types/contracts';

/**
 * FRACTAL-FLOW Control Surface — Adversarial Safety Invariant Test Suite
 * 
 * Protocol: Universal Forensic Engineering Protocol
 * Invariant Hierarchy: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY
 */
async function runAdversarialSafetyTests() {
  let passed = 0;
  let failed = 0;

  async function test(name: string, fn: () => void | Promise<void>) {
    try {
      await fn();
      console.log(`  [PASS] ${name}`);
      passed++;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`  [FAIL] ${name}`);
      console.error(`         Error: ${msg}`);
      failed++;
    }
  }

  console.log('========================================================');
  console.log('FRACTAL-FLOW GUI — Adversarial Safety Invariant Test Suite');
  console.log('Governing Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY');
  console.log('========================================================\n');

  // --- 1. Provider Isolation & Fail-Closed Live Gate ---
  console.log('--- 1. Provider Isolation & Fail-Closed Live Gate ---');

  await test('LiveCommandAdapter must fail-closed and throw LiveExecutionBlockedError on submitCommand', async () => {
    const adapter = new LiveCommandAdapter();
    const intent = createIntentFingerprint('operator_1', 'pos_01', 'EURUSD', 'CLOSE', {});
    
    let caught = false;
    try {
      await adapter.submitCommand(intent);
    } catch (err) {
      if (err instanceof LiveExecutionBlockedError) {
        caught = true;
      }
    }
    if (!caught) {
      throw new Error('Expected LiveExecutionBlockedError, but live command did not fail closed');
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
    
    const intent = createIntentFingerprint('daniel_operator', target.id, target.symbol, 'CLOSE', {});
    const progressUpdates: string[] = [];
    
    const result = await sim.submitCommand(intent, (prog) => {
      progressUpdates.push(prog.status);
      if (prog.authoritative !== false) {
        throw new Error('Progress update claimed authoritative = true');
      }
    });
    
    if (result.authoritative !== false) {
      throw new Error('Simulation command result must specify authoritative = false');
    }
    if (result.status !== 'CONFIRMED') {
      throw new Error(`Expected CONFIRMED status in sandbox, got ${result.status}`);
    }
    // Verify provider owned progression
    if (!progressUpdates.includes('ACCEPTED_BY_GATEWAY') || !progressUpdates.includes('DISPATCHED_TO_BROKER')) {
      throw new Error('SimulationProvider failed to emit intermediate non-authoritative lifecycle steps');
    }

    const updatedPositions = await sim.getPositions();
    if (updatedPositions.length !== initialPositions.length - 1) {
      throw new Error('Position was not removed from sandbox memory');
    }
    if (updatedPositions.some(p => p.id === target.id)) {
      throw new Error('Target position still exists in sandbox memory after CLOSE');
    }
  });

  await test('SimulationProvider simulated rejection leaves sandbox positions completely unmodified', async () => {
    const sim = new SimulationProvider();
    const initialPositions = await sim.getPositions();
    const target = initialPositions[0];

    const intent = createIntentFingerprint('op', target.id, target.symbol, 'CLOSE', { simulateRejection: true });
    const result = await sim.submitCommand(intent);

    if (result.status !== 'REJECTED') {
      throw new Error(`Expected REJECTED status, got ${result.status}`);
    }
    const afterPositions = await sim.getPositions();
    if (afterPositions.length !== initialPositions.length) {
      throw new Error('Sandbox positions were mutated during rejected command');
    }
  });

  // --- 2. Deterministic Intent Identity & Cryptographic SHA-256 Fingerprinting ---
  console.log('\n--- 2. Deterministic Intent Identity & SHA-256 Fingerprinting ---');

  await test('Standard NIST/RFC 6234 Known-Answer Vectors for SHA-256', () => {
    // Vector 1: Empty string
    const kat1 = sha256Hex('');
    const expected1 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
    if (kat1 !== expected1) {
      throw new Error(`KAT 1 failed: expected ${expected1}, got ${kat1}`);
    }

    // Vector 2: "abc"
    const kat2 = sha256Hex('abc');
    const expected2 = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad';
    if (kat2 !== expected2) {
      throw new Error(`KAT 2 failed: expected ${expected2}, got ${kat2}`);
    }

    // Vector 3: "The quick brown fox jumps over the lazy dog"
    const kat3 = sha256Hex('The quick brown fox jumps over the lazy dog');
    const expected3 = 'd7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592';
    if (kat3 !== expected3) {
      throw new Error(`KAT 3 failed: expected ${expected3}, got ${kat3}`);
    }
  });

  await test('Canonical serialization produces identical output regardless of nested key insertion order', () => {
    const obj1 = {
      z: 1,
      nested: { beta: 'two', alpha: 'one', deep: { y: 20, x: 10 } },
      a: [1, 2, { k: 'val', j: 'val' }]
    };
    const obj2 = {
      nested: { deep: { x: 10, y: 20 }, alpha: 'one', beta: 'two' },
      a: [1, 2, { j: 'val', k: 'val' }],
      z: 1
    };

    const str1 = canonicalizeValue(obj1);
    const str2 = canonicalizeValue(obj2);

    if (str1 !== str2) {
      throw new Error(`Canonical serialization differed:\n1: ${str1}\n2: ${str2}`);
    }
    if (sha256Hex(str1) !== sha256Hex(str2)) {
      throw new Error('SHA-256 hashes differed for equivalent canonical objects');
    }
  });

  await test('Canonical serialization preserves null and distinguishes from absent properties', () => {
    const objWithNull = { sl: null, tp: 1.09 };
    const objWithoutSl = { tp: 1.09 };

    const strNull = canonicalizeValue(objWithNull);
    const strWithout = canonicalizeValue(objWithoutSl);

    if (strNull === strWithout) {
      throw new Error('Explicit null was collapsed into absent property');
    }
    if (!strNull.includes('"sl":null')) {
      throw new Error(`Expected '"sl":null' in serialization, got: ${strNull}`);
    }
  });

  await test('Canonical serialization deterministically rejects unsupported and ambiguous types', () => {
    // 1. undefined
    let rejectedUndefined = false;
    try {
      canonicalizeValue({ invalid: undefined });
    } catch (e) {
      if (e instanceof CanonicalizationError) rejectedUndefined = true;
    }
    if (!rejectedUndefined) throw new Error('Failed to reject undefined in canonical payload');

    // 2. NaN
    let rejectedNaN = false;
    try {
      canonicalizeValue({ invalid: NaN });
    } catch (e) {
      if (e instanceof CanonicalizationError) rejectedNaN = true;
    }
    if (!rejectedNaN) throw new Error('Failed to reject NaN in canonical payload');

    // 3. Infinity
    let rejectedInf = false;
    try {
      canonicalizeValue({ invalid: Infinity });
    } catch (e) {
      if (e instanceof CanonicalizationError) rejectedInf = true;
    }
    if (!rejectedInf) throw new Error('Failed to reject Infinity in canonical payload');

    // 4. Function
    let rejectedFn = false;
    try {
      canonicalizeValue({ fn: () => {} });
    } catch (e) {
      if (e instanceof CanonicalizationError) rejectedFn = true;
    }
    if (!rejectedFn) throw new Error('Failed to reject Function in canonical payload');

    // 5. Cyclic structure
    const cycle: Record<string, unknown> = {};
    cycle.self = cycle;
    let rejectedCycle = false;
    try {
      canonicalizeValue(cycle);
    } catch (e) {
      if (e instanceof CanonicalizationError) rejectedCycle = true;
    }
    if (!rejectedCycle) throw new Error('Failed to reject cyclic object');
  });

  await test('Separate logical intent ID from payload fingerprint: Retries preserve intentId; new actions generate new intentId', () => {
    // Action 1: First operator command
    const firstIntent = createIntentFingerprint('op_1', 'pos_eurusd_01', 'EURUSD', 'TIGHTEN_STOP', { sl: 1.08420 });

    // Action 2: RETRY of the same intent (passes existingIntentId)
    const retryIntent = createIntentFingerprint(
      'op_1', 
      'pos_eurusd_01', 
      'EURUSD', 
      'TIGHTEN_STOP', 
      { sl: 1.08420 }, 
      firstIntent.intentId,
      2 // second transport attempt
    );

    if (retryIntent.intentId !== firstIntent.intentId) {
      throw new Error(`Retry changed intentId: ${retryIntent.intentId} !== ${firstIntent.intentId}`);
    }
    if (retryIntent.idempotencyKey !== firstIntent.idempotencyKey) {
      throw new Error(`Retry changed idempotencyKey: ${retryIntent.idempotencyKey} !== ${firstIntent.idempotencyKey}`);
    }

    // Action 3: A NEW intentional command for the same position and parameters (must receive a NEW intentId)
    const newIntent = createIntentFingerprint('op_1', 'pos_eurusd_01', 'EURUSD', 'TIGHTEN_STOP', { sl: 1.08420 });

    if (newIntent.intentId === firstIntent.intentId) {
      throw new Error('New operator action improperly reused previous intentId');
    }
    // But payload fingerprint remains identical because semantic payload is the same
    if (newIntent.payloadFingerprint !== firstIntent.payloadFingerprint) {
      throw new Error('Payload fingerprint differed for identical semantic parameters');
    }
  });

  await test('Altering parameters produces distinct payload fingerprints', () => {
    const intentA = createIntentFingerprint('op', 'pos_1', 'EURUSD', 'TIGHTEN_STOP', { sl: 1.0850 });
    const intentB = createIntentFingerprint('op', 'pos_1', 'EURUSD', 'TIGHTEN_STOP', { sl: 1.0860 });
    if (intentA.payloadFingerprint === intentB.payloadFingerprint) {
      throw new Error('Altered parameters generated identical payload fingerprint');
    }
    if (intentA.idempotencyKey === intentB.idempotencyKey) {
      throw new Error('Altered parameters generated identical idempotencyKey');
    }
  });

  // --- 3. Keyboard & Operator Interaction Safety ---
  console.log('\n--- 3. Keyboard & Operator Interaction Safety ---');

  await test('isSafeKeyboardShortcutTarget rejects all editable and textbox-role targets', () => {
    const targets = [
      { tagName: 'INPUT', isContentEditable: false, getAttribute: () => null },
      { tagName: 'TEXTAREA', isContentEditable: false, getAttribute: () => null },
      { tagName: 'SELECT', isContentEditable: false, getAttribute: () => null },
      { tagName: 'DIV', isContentEditable: true, getAttribute: () => null },
      { tagName: 'SPAN', isContentEditable: false, getAttribute: (attr: string) => attr === 'role' ? 'textbox' : null },
      { tagName: 'DIV', isContentEditable: false, getAttribute: (attr: string) => attr === 'role' ? 'searchbox' : null },
      { tagName: 'DIV', isContentEditable: false, getAttribute: (attr: string) => attr === 'role' ? 'combobox' : null },
    ];

    for (const t of targets) {
      const isSafe = isSafeKeyboardShortcutTarget({ target: t } as unknown as KeyboardEvent);
      if (isSafe !== false) {
        throw new Error(`Failed to reject editable target: ${t.tagName} (role: ${t.getAttribute('role')})`);
      }
    }

    // Normal non-editable container
    const safeDiv = { tagName: 'DIV', isContentEditable: false, getAttribute: () => null };
    if (!isSafeKeyboardShortcutTarget({ target: safeDiv } as unknown as KeyboardEvent)) {
      throw new Error('Incorrectly rejected non-editable DIV');
    }
  });

  await test('isValidShortcutEvent rejects IME composition and repeated key chatter', () => {
    const safeTarget = { tagName: 'DIV', isContentEditable: false, getAttribute: () => null };

    // 1. IME composition (isComposing = true)
    const imeEvent = {
      target: safeTarget,
      isComposing: true,
      keyCode: 229,
      repeat: false,
      ctrlKey: false,
      metaKey: false,
      altKey: false,
      shiftKey: false
    } as unknown as KeyboardEvent;

    if (isValidShortcutEvent(imeEvent) !== false) {
      throw new Error('Allowed shortcut during IME composition');
    }

    // 2. Repeated keydown (key chatter)
    const repeatEvent = {
      target: safeTarget,
      isComposing: false,
      keyCode: 67, // 'C'
      repeat: true,
      ctrlKey: false,
      metaKey: false,
      altKey: false,
      shiftKey: false
    } as unknown as KeyboardEvent;

    if (isValidShortcutEvent(repeatEvent, { allowRepeat: false }) !== false) {
      throw new Error('Allowed repeated keydown event without allowRepeat');
    }
  });

  await test('isValidShortcutEvent strictly enforces required and unwanted modifier keys', () => {
    const safeTarget = { tagName: 'DIV', isContentEditable: false, getAttribute: () => null };

    // Hotkey requires NO modifiers, but operator is holding Ctrl (e.g. Ctrl+C)
    const ctrlEvent = {
      target: safeTarget,
      isComposing: false,
      repeat: false,
      ctrlKey: true,
      metaKey: false,
      altKey: false,
      shiftKey: false
    } as unknown as KeyboardEvent;

    if (isValidShortcutEvent(ctrlEvent, { requireCtrlOrMeta: false }) !== false) {
      throw new Error('Unwanted Ctrl modifier was allowed');
    }

    // Hotkey requires NO modifiers, but operator is holding Alt (e.g. Alt+Tab)
    const altEvent = {
      target: safeTarget,
      isComposing: false,
      repeat: false,
      ctrlKey: false,
      metaKey: false,
      altKey: true,
      shiftKey: false
    } as unknown as KeyboardEvent;

    if (isValidShortcutEvent(altEvent, { requireAlt: false }) !== false) {
      throw new Error('Unwanted Alt modifier was allowed');
    }
  });

  await test('isKeyboardShortcutAllowed blocks shortcuts when modal is open or command is in flight', () => {
    const safeTarget = { tagName: 'DIV', isContentEditable: false, getAttribute: () => null };
    const nominalEvent = {
      target: safeTarget,
      isComposing: false,
      repeat: false,
      ctrlKey: false,
      metaKey: false,
      altKey: false,
      shiftKey: false
    } as unknown as KeyboardEvent;

    // Modal open
    if (isKeyboardShortcutAllowed(nominalEvent, { isModalOpen: true, isCommandInFlight: false }) !== false) {
      throw new Error('Allowed shortcut when confirmation modal was open');
    }

    // Command in flight
    if (isKeyboardShortcutAllowed(nominalEvent, { isModalOpen: false, isCommandInFlight: true }) !== false) {
      throw new Error('Allowed shortcut while an operator command was in flight');
    }

    // Both false
    if (isKeyboardShortcutAllowed(nominalEvent, { isModalOpen: false, isCommandInFlight: false }) !== true) {
      throw new Error('Rejected shortcut when safe and no modal/in-flight command');
    }
  });

  // --- 4. Production Telemetry Freshness & Provenance Evaluation ---
  console.log('\n--- 4. Telemetry Freshness & Provenance Evaluation ---');

  await test('evaluateTelemetryFreshness accurately evaluates fresh, threshold boundary, and expired telemetry', () => {
    const now = 100000;
    const baseTelemetry: TelemetryProvenance = {
      source: 'SIM_ENGINE',
      status: 'HEALTHY',
      freshnessTimestamp: now - 2000,
      isAuthoritative: false,
      staleThresholdMs: 5000,
      epoch: 418,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED'
    };

    // 1. Fresh (age 2000 < 5000)
    const freshEval = evaluateTelemetryFreshness(baseTelemetry, now);
    if (freshEval.status !== 'HEALTHY' || freshEval.isStale !== false) {
      throw new Error(`Expected HEALTHY, got ${freshEval.status} (stale: ${freshEval.isStale})`);
    }

    // 2. Exactly at threshold boundary (age 5000 == 5000) -> strictly STALE
    const boundaryTelemetry: TelemetryProvenance = { ...baseTelemetry, freshnessTimestamp: now - 5000 };
    const boundaryEval = evaluateTelemetryFreshness(boundaryTelemetry, now);
    if (boundaryEval.status !== 'STALE' || boundaryEval.isStale !== true) {
      throw new Error(`Expected STALE at exact threshold, got ${boundaryEval.status}`);
    }

    // 3. Expired (age 7000 > 5000) -> STALE
    const expiredTelemetry: TelemetryProvenance = { ...baseTelemetry, freshnessTimestamp: now - 7000 };
    const expiredEval = evaluateTelemetryFreshness(expiredTelemetry, now);
    if (expiredEval.status !== 'STALE' || expiredEval.isStale !== true) {
      throw new Error(`Expected STALE for expired telemetry, got ${expiredEval.status}`);
    }
  });

  await test('evaluateTelemetryFreshness handles missing/invalid timestamps and disconnected sources truthfully', () => {
    const now = 100000;

    // Missing / 0 / NaN timestamp
    const invalidTelemetry: TelemetryProvenance = {
      source: 'SIM_ENGINE',
      status: 'HEALTHY',
      freshnessTimestamp: 0,
      isAuthoritative: false,
      staleThresholdMs: 5000,
      epoch: 418,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED'
    };
    const invalidEval = evaluateTelemetryFreshness(invalidTelemetry, now);
    if (invalidEval.status !== 'UNKNOWN' || invalidEval.isStale !== true) {
      throw new Error(`Invalid timestamp must evaluate to UNKNOWN, got ${invalidEval.status}`);
    }

    // Disconnected source cannot be promoted to HEALTHY by recent timestamp
    const disconnectedTelemetry: TelemetryProvenance = {
      source: 'BROKER_FEED',
      status: 'DISCONNECTED',
      freshnessTimestamp: now - 50,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 418,
      bridgeStatus: 'DOWN',
      fenceStatus: 'ENFORCED'
    };
    const disconnectedEval = evaluateTelemetryFreshness(disconnectedTelemetry, now);
    if (disconnectedEval.status !== 'DISCONNECTED') {
      throw new Error(`DISCONNECTED source was improperly promoted to ${disconnectedEval.status}`);
    }
  });

  console.log('\n========================================================');
  console.log(`Results: ${passed} PASSED, ${failed} FAILED`);
  console.log('========================================================\n');

  if (failed > 0) {
    process.exit(1);
  }
}

runAdversarialSafetyTests().catch(err => {
  console.error('Fatal test runner error:', err);
  process.exit(1);
});
