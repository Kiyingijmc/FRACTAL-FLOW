import { LiveCommandAdapter } from '../providers/LiveCommandAdapter';
import { LiveExecutionBlockedError } from '../types/contracts';
import { SimulationProvider } from '../providers/SimulationProvider';
import { 
  sha256Hex, 
  canonicalizeValue, 
  computePayloadFingerprint, 
  createIntentFingerprint, 
  CanonicalizationError 
} from '../utils/idempotency';
import { 
  isSafeKeyboardShortcutTarget, 
  isValidShortcutEvent, 
  isKeyboardShortcutAllowed 
} from '../utils/keyboard';
import { 
  evaluateTelemetryFreshness, 
  updateTelemetryState 
} from '../utils/telemetry';
import { TelemetryProvenance } from '../types/contracts';

async function runAdversarialSafetyTests() {
  console.log('========================================================');
  console.log('FRACTAL-FLOW GUI — Adversarial Safety Invariant Test Suite');
  console.log('Governing Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY');
  console.log('========================================================\n');

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

  // --- 1. Provider Isolation & Fail-Closed Live Gate ---
  console.log('--- 1. Provider Isolation & Fail-Closed Live Gate ---');

  await test('LiveCommandAdapter must fail-closed and throw LiveExecutionBlockedError on submitCommand', async () => {
    const adapter = new LiveCommandAdapter();
    const intent = createIntentFingerprint('daniel_op', 'pos_01', 'EURUSD', 'CLOSE');

    let threw = false;
    try {
      await adapter.submitCommand(intent);
    } catch (err) {
      if (err instanceof LiveExecutionBlockedError) {
        threw = true;
      }
    }
    if (!threw) {
      throw new Error('LiveCommandAdapter did NOT throw LiveExecutionBlockedError');
    }
  });

  await test('LiveCommandAdapter must fail-closed on reconcileCommand', async () => {
    const adapter = new LiveCommandAdapter();
    let threw = false;
    try {
      await adapter.reconcileCommand('intent_test_123');
    } catch (err) {
      if (err instanceof LiveExecutionBlockedError) {
        threw = true;
      }
    }
    if (!threw) {
      throw new Error('LiveCommandAdapter did NOT throw LiveExecutionBlockedError on reconcileCommand');
    }
  });

  await test('SimulationProvider must have isLiveAuthorized = false and return isAuthoritative = false', async () => {
    const sim = new SimulationProvider();
    if (sim.isLiveAuthorized !== false) {
      throw new Error(`Expected isLiveAuthorized === false, got ${sim.isLiveAuthorized}`);
    }
    const health = await sim.getHealth();
    if (health.isAuthoritative !== false) {
      throw new Error(`Expected health.isAuthoritative === false, got ${health.isAuthoritative}`);
    }
  });

  await test('SimulationProvider commands modify only local sandbox memory and return non-authoritative results', async () => {
    const sim = new SimulationProvider();
    const positions = await sim.getPositions();
    if (positions.length === 0) throw new Error('Sandbox has no positions');

    const targetPos = positions[0];
    const intent = createIntentFingerprint('test_operator', targetPos.id, targetPos.symbol, 'MOVE_TO_BREAKEVEN');

    const res = await sim.submitCommand(intent);
    if (res.authoritative !== false) {
      throw new Error('Simulation command claimed authority');
    }
    if (res.status !== 'CONFIRMED') {
      throw new Error(`Expected simulation CONFIRMED, got ${res.status}`);
    }

    const updated = await sim.getPositions();
    const updatedTarget = updated.find(p => p.id === targetPos.id);
    if (!updatedTarget || !updatedTarget.breakevenStatus.includes('confirmed @ BE (sim)')) {
      throw new Error('Local sandbox mutation was not applied');
    }
  });

  // SC-08: Sandbox simulated rejection leaves positions completely unmodified
  await test('SC-08: SimulationProvider simulated rejection leaves sandbox positions completely unmodified', async () => {
    const sim = new SimulationProvider();
    const initialPositions = await sim.getPositions();
    const targetPos = initialPositions[0];

    const intent = createIntentFingerprint(
      'test_operator', 
      targetPos.id, 
      targetPos.symbol, 
      'CLOSE', 
      { simulateRejection: true }
    );

    const res = await sim.submitCommand(intent);
    if (res.status !== 'REJECTED') {
      throw new Error(`Expected REJECTED, got ${res.status}`);
    }

    const afterPositions = await sim.getPositions();
    if (afterPositions.length !== initialPositions.length) {
      throw new Error('Position count modified during rejected command');
    }

    // Verify deep state invariance
    if (JSON.stringify(afterPositions) !== JSON.stringify(initialPositions)) {
      throw new Error('Position state mutated during rejected command');
    }
  });

  // SC-07: SimulationProvider.reconcileCommand validates against recorded intents
  await test('SC-07: SimulationProvider.reconcileCommand validates against recorded intents and rejects unknown intents', async () => {
    const sim = new SimulationProvider();
    const positions = await sim.getPositions();
    const targetPos = positions[0];

    const intent = createIntentFingerprint('op_recon', targetPos.id, targetPos.symbol, 'TIGHTEN_STOP');
    await sim.submitCommand(intent);

    // Reconcile recorded intent
    const recordedRes = await sim.reconcileCommand(intent.intentId);
    if (recordedRes.status !== 'CONFIRMED' || recordedRes.intentId !== intent.intentId) {
      throw new Error(`Failed to reconcile recorded intent: ${recordedRes.status}`);
    }

    // Reconcile unknown intent -> MUST reject
    const unknownRes = await sim.reconcileCommand('unknown_intent_99999');
    if (unknownRes.status !== 'REJECTED' || unknownRes.rejectionReason !== 'INTENT_NOT_RECORDED') {
      throw new Error(`Unknown intent must be REJECTED, got: ${unknownRes.status}`);
    }
  });

  // --- 2. Deterministic Intent Identity & SHA-256 Fingerprinting ---
  console.log('\n--- 2. Deterministic Intent Identity & SHA-256 Fingerprinting ---');

  await test('Standard NIST/RFC 6234 Known-Answer Vectors for SHA-256', () => {
    // Vector 1: Empty string
    if (sha256Hex('') !== 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855') {
      throw new Error('SHA-256 failed on empty string');
    }
    // Vector 2: "abc"
    if (sha256Hex('abc') !== 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad') {
      throw new Error('SHA-256 failed on "abc"');
    }
  });

  await test('Canonical serialization produces identical output regardless of nested key insertion order', () => {
    const objA = { z: 1, a: { y: 2, b: 3 }, m: [1, 2] };
    const objB = { a: { b: 3, y: 2 }, m: [1, 2], z: 1 };
    const serA = canonicalizeValue(objA);
    const serB = canonicalizeValue(objB);
    if (serA !== serB) {
      throw new Error(`Canonical strings differed:\nA: ${serA}\nB: ${serB}`);
    }
  });

  await test('Canonical serialization preserves null and distinguishes from absent properties', () => {
    const objWithNull = { a: null };
    const objEmpty = {};
    if (canonicalizeValue(objWithNull) === canonicalizeValue(objEmpty)) {
      throw new Error('null was confounded with absent property');
    }
  });

  // SC-02: Canonical serialization deterministically rejects unsupported and ambiguous types
  await test('SC-02: Canonical serialization deterministically rejects sparse arrays, non-plain objects, BigInt, NaN, and cycles', () => {
    // NaN
    let threw = false;
    try { canonicalizeValue({ val: NaN }); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed NaN');

    // Infinity
    threw = false;
    try { canonicalizeValue({ val: Infinity }); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed Infinity');

    // BigInt
    threw = false;
    try { canonicalizeValue({ val: BigInt(123) }); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed BigInt');

    // Sparse Array (e.g. [1, , 3])
    threw = false;
    try { 
      const sparse = [1]; 
      sparse[3] = 4; 
      canonicalizeValue({ list: sparse }); 
    } catch (e) { 
      if (e instanceof CanonicalizationError) threw = true; 
    }
    if (!threw) throw new Error('Allowed sparse array');

    // Non-plain object instance (Date, RegExp, Map, Set)
    threw = false;
    try { canonicalizeValue({ date: new Date() }); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed Date object instance');

    threw = false;
    try { canonicalizeValue({ map: new Map() }); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed Map instance');

    // Cyclic structure
    threw = false;
    const cycle: Record<string, unknown> = { a: 1 };
    cycle.self = cycle;
    try { canonicalizeValue(cycle); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed cyclic object structure');
  });

  // SC-01: Idempotency key explicitly binds intentId
  await test('SC-01: Idempotency key binds intentId so distinct operator actions with identical payloads never collide', () => {
    const actionA = createIntentFingerprint('operator_1', 'pos_01', 'EURUSD', 'CLOSE', { lots: 1.0 });
    const actionB = createIntentFingerprint('operator_1', 'pos_01', 'EURUSD', 'CLOSE', { lots: 1.0 });

    // Distinct operator actions MUST have different intent IDs
    if (actionA.intentId === actionB.intentId) {
      throw new Error('Distinct actions produced identical intentId');
    }

    // SC-01: Idempotency keys MUST NOT collide
    if (actionA.idempotencyKey === actionB.idempotencyKey) {
      throw new Error(`Distinct actions produced colliding idempotencyKey: ${actionA.idempotencyKey}`);
    }

    // But retrying the SAME action preserving existingIntentId MUST preserve idempotencyKey
    const retryA = createIntentFingerprint(
      'operator_1', 
      'pos_01', 
      'EURUSD', 
      'CLOSE', 
      { lots: 1.0 }, 
      actionA.intentId, 
      2
    );
    if (retryA.idempotencyKey !== actionA.idempotencyKey) {
      throw new Error('Retry did not preserve idempotencyKey');
    }
  });

  await test('Altering parameters produces distinct payload fingerprints', () => {
    const intentA = createIntentFingerprint('op', 'pos_01', 'EURUSD', 'CLOSE', { lots: 1.0 });
    const intentB = createIntentFingerprint('op', 'pos_01', 'EURUSD', 'CLOSE', { lots: 1.5 });
    if (intentA.payloadFingerprint === intentB.payloadFingerprint) {
      throw new Error('Altered parameters generated identical payload fingerprint');
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
      throw new Error(`Expected HEALTHY, got ${freshEval.status}`);
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

  // SC-06: Non-positive, non-finite, or invalid staleThresholdMs evaluates strictly as DEGRADED (never false HEALTHY)
  await test('SC-06: evaluateTelemetryFreshness treats non-positive or invalid staleThresholdMs as DEGRADED', () => {
    const now = 100000;
    const zeroThreshold: TelemetryProvenance = {
      source: 'SIM_ENGINE',
      status: 'HEALTHY',
      freshnessTimestamp: now - 10,
      isAuthoritative: false,
      staleThresholdMs: 0,
      epoch: 418,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED'
    };
    const zeroEval = evaluateTelemetryFreshness(zeroThreshold, now);
    if (zeroEval.status !== 'DEGRADED') {
      throw new Error(`Expected DEGRADED for staleThresholdMs=0, got ${zeroEval.status}`);
    }

    const negativeThreshold: TelemetryProvenance = {
      ...zeroThreshold,
      staleThresholdMs: -100
    };
    const negEval = evaluateTelemetryFreshness(negativeThreshold, now);
    if (negEval.status !== 'DEGRADED') {
      throw new Error(`Expected DEGRADED for negative staleThresholdMs, got ${negEval.status}`);
    }

    const nonFiniteThreshold: TelemetryProvenance = {
      ...zeroThreshold,
      staleThresholdMs: Infinity
    };
    const infEval = evaluateTelemetryFreshness(nonFiniteThreshold, now);
    if (infEval.status !== 'DEGRADED') {
      throw new Error(`Expected DEGRADED for non-finite staleThresholdMs, got ${infEval.status}`);
    }
  });

  // SC-05: updateTelemetryState merges safely without clobbering other sources or clearing DISCONNECTED state
  await test('SC-05: updateTelemetryState preserves DISCONNECTED state and protects source provenance', () => {
    const disconnectedTelemetry: TelemetryProvenance = {
      source: 'CONTROL_SERVICE',
      status: 'DISCONNECTED',
      freshnessTimestamp: 1000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 418,
      bridgeStatus: 'DISCONNECTED',
      fenceStatus: 'ENFORCED'
    };

    // Attempting to clear DISCONNECTED without advancing epoch MUST preserve DISCONNECTED
    const unverifiedUpdate = updateTelemetryState(disconnectedTelemetry, {
      status: 'HEALTHY',
      freshnessTimestamp: 2000
    });
    if (unverifiedUpdate.status !== 'DISCONNECTED') {
      throw new Error(`DISCONNECTED was improperly cleared without epoch advance, got ${unverifiedUpdate.status}`);
    }
    if (unverifiedUpdate.source !== 'CONTROL_SERVICE') {
      throw new Error('Source provenance was clobbered');
    }

    // Verified epoch advance permits reconnection
    const verifiedUpdate = updateTelemetryState(disconnectedTelemetry, {
      status: 'HEALTHY',
      epoch: 419,
      bridgeStatus: 'CONNECTED'
    });
    if (verifiedUpdate.status !== "HEALTHY") {
      throw new Error(`Failed to advance epoch and reconnect, got ${verifiedUpdate.status}`);
    }
  });

  // SC-09: Session and simulated events must never claim false durable persistence
  await test("SC-09: In-memory/session events are labeled SESSION/SIMULATED without false PERSISTED claim", async () => {
    const sim = new SimulationProvider();
    const positions = await sim.getPositions();
    const target = positions[0];
    const intent = createIntentFingerprint("op_audit", target.id, target.symbol, "MOVE_TO_BREAKEVEN");
    await sim.submitCommand(intent);

    const events = await sim.getSystemEvents();
    const latestEvent = events[0];
    if (latestEvent.status === "PERSISTED") {
      throw new Error("In-memory simulated command event falsely claimed PERSISTED status");
    }
    if (latestEvent.status !== "SIMULATED" && latestEvent.status !== "SESSION" && latestEvent.status !== "IN_MEMORY") {
      throw new Error(`Unexpected event status: ${latestEvent.status}`);
    }
    if (latestEvent.isAuthoritative !== false) {
      throw new Error("Event falsely claimed authoritative status");
    }
  });

  await test("evaluateTelemetryFreshness handles missing/invalid timestamps and disconnected sources truthfully", () => {
    const now = 100000;
    const invalidTelemetry: TelemetryProvenance = {
      source: "SIM_ENGINE",
      status: "HEALTHY",
      freshnessTimestamp: 0,
      isAuthoritative: false,
      staleThresholdMs: 5000,
      epoch: 418,
      bridgeStatus: "OK",
      fenceStatus: "ENFORCED"
    };
    const invalidEval = evaluateTelemetryFreshness(invalidTelemetry, now);
    if (invalidEval.status !== "UNKNOWN" || invalidEval.isStale !== true) {
      throw new Error(`Invalid timestamp must evaluate to UNKNOWN, got ${invalidEval.status}`);
    }

    const disconnectedTelemetry: TelemetryProvenance = {
      source: "BROKER_FEED",
      status: "DISCONNECTED",
      freshnessTimestamp: now - 50,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 418,
      bridgeStatus: "DOWN",
      fenceStatus: "ENFORCED"
    };
    const disconnectedEval = evaluateTelemetryFreshness(disconnectedTelemetry, now);
    if (disconnectedEval.status !== "DISCONNECTED") {
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
