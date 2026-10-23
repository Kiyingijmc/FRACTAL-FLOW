import { LiveCommandAdapter } from '../providers/LiveCommandAdapter';
import { SimulationProvider } from '../providers/SimulationProvider';
import {
  sha256Hex,
  canonicalizeValue,
  computePayloadFingerprint,
  createIntentFingerprint,
  createLogicalIntentId,
  clearIntentRegistry,
  CanonicalizationError,
  IntentReplayMismatchError,
  IDEMPOTENCY_AUTHORITY_BOUNDARY
} from '../utils/idempotency';
import {
  isSafeKeyboardShortcutTarget,
  isValidShortcutEvent,
  isKeyboardShortcutAllowed
} from '../utils/keyboard';
import {
  evaluateTelemetryFreshness,
  updateTelemetryState,
  tryUpdateTelemetryState,
  createInitialTelemetry,
  VALID_SOURCES,
  VALID_STATUSES,
  VALID_ACTIVE_BRIDGE_STATUSES,
  MIGRATION_AUTHORITY_BOUNDARY,
  RECONNECT_AUTHORITY_BOUNDARY,
  DOCUMENTED_UNKNOWN_TELEMETRY,
  ReconnectAuthorizationProof
} from '../utils/telemetry';
import { LiveExecutionBlockedError, TelemetryProvenance } from '../types/contracts';

async function runStageDAdversarialTests() {
  console.log('========================================================');
  console.log('FRACTAL-FLOW GUI — Stage D Forensic Adversarial Test Suite');
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

  // =========================================================================
  // SC-01: Telemetry Source Integrity & Provenance
  // =========================================================================
  console.log('--- SC-01: Telemetry Source Integrity & Provenance ---');

  await test('SC-01.1: Simulation tick (SIM_ENGINE) CANNOT heal or overwrite a disconnected external source', () => {
    const disconnectedBroker: TelemetryProvenance = {
      source: 'BROKER_FEED',
      status: 'DISCONNECTED',
      freshnessTimestamp: 1000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 418,
      bridgeStatus: 'DISCONNECTED',
      fenceStatus: 'ENFORCED'
    };

    // A simulation tick arrives from SIM_ENGINE with status HEALTHY
    const updated = updateTelemetryState(disconnectedBroker, {
      source: 'SIM_ENGINE',
      status: 'HEALTHY',
      freshnessTimestamp: 2000
    });

    if (updated.status !== 'DISCONNECTED') {
      throw new Error(`Simulation tick improperly healed disconnected broker! Got: ${updated.status}`);
    }
    if (updated.source !== 'BROKER_FEED') {
      throw new Error(`Active source was clobbered by simulation tick! Got: ${updated.source}`);
    }
    if (updated.freshnessTimestamp !== 1000) {
      throw new Error('Freshness timestamp was overwritten by unrelated simulation tick');
    }
  });

  await test('SC-01.2: Events from a different source cannot refresh or overwrite the active source', () => {
    const activeControl: TelemetryProvenance = {
      source: 'CONTROL_SERVICE',
      status: 'HEALTHY',
      freshnessTimestamp: 5000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 418,
      bridgeStatus: 'CONNECTED',
      fenceStatus: 'ENFORCED'
    };

    const attempt = updateTelemetryState(activeControl, {
      source: 'SIM_ENGINE',
      freshnessTimestamp: 6000
    });

    if (attempt.source !== 'CONTROL_SERVICE' || attempt.freshnessTimestamp !== 5000) {
      throw new Error('Cross-source event refreshed active CONTROL_SERVICE source');
    }
  });

  await test('SC-01.3: Stale out-of-order events cannot overwrite newer valid telemetry state', () => {
    const nominal: TelemetryProvenance = {
      source: 'SIM_ENGINE',
      status: 'HEALTHY',
      freshnessTimestamp: 10000,
      isAuthoritative: false,
      staleThresholdMs: 5000,
      epoch: 418,
      bridgeStatus: 'SIM_VIRTUAL_OK',
      fenceStatus: 'SIM_FENCE_ENFORCED'
    };

    // Arrives late from network (timestamp 8000 < current 10000)
    const updated = updateTelemetryState(nominal, {
      source: 'SIM_ENGINE',
      freshnessTimestamp: 8000,
      status: 'DEGRADED'
    });

    if (updated.freshnessTimestamp !== 10000 || updated.status !== 'HEALTHY') {
      throw new Error('Stale out-of-order event overwrote newer telemetry state');
    }
  });

  await test('SC-01.4: Invalid, non-positive, or non-finite threshold values fail safely to DEGRADED', () => {
    const now = 100000;
    const base: TelemetryProvenance = {
      source: 'SIM_ENGINE',
      status: 'HEALTHY',
      freshnessTimestamp: now - 100,
      isAuthoritative: false,
      staleThresholdMs: 0, // non-positive
      epoch: 418,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED'
    };

    const evalZero = evaluateTelemetryFreshness(base, now);
    if (evalZero.status !== 'DEGRADED') {
      throw new Error(`Expected DEGRADED for staleThresholdMs=0, got ${evalZero.status}`);
    }

    const evalNeg = evaluateTelemetryFreshness({ ...base, staleThresholdMs: -500 }, now);
    if (evalNeg.status !== 'DEGRADED') {
      throw new Error(`Expected DEGRADED for negative threshold, got ${evalNeg.status}`);
    }

    const evalInf = evaluateTelemetryFreshness({ ...base, staleThresholdMs: Infinity }, now);
    if (evalInf.status !== 'DEGRADED') {
      throw new Error(`Expected DEGRADED for Infinity threshold, got ${evalInf.status}`);
    }
  });

  await test('SC-01.5: Missing, invalid, or non-finite timestamps fail safely to UNKNOWN/DEGRADED', () => {
    const now = 100000;
    const missingTs = evaluateTelemetryFreshness({
      source: 'SIM_ENGINE',
      status: 'HEALTHY',
      freshnessTimestamp: 0,
      isAuthoritative: false,
      staleThresholdMs: 5000,
      epoch: 418,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED'
    }, now);

    if (missingTs.status !== 'UNKNOWN' || missingTs.isStale !== true) {
      throw new Error(`Invalid timestamp must evaluate to UNKNOWN, got: ${missingTs.status}`);
    }

    // Future timestamp / clock skew -> DEGRADED
    const futureTs = evaluateTelemetryFreshness({
      source: 'SIM_ENGINE',
      status: 'HEALTHY',
      freshnessTimestamp: now + 5000,
      isAuthoritative: false,
      staleThresholdMs: 5000,
      epoch: 418,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED'
    }, now);

    if (futureTs.status !== 'DEGRADED') {
      throw new Error(`Future timestamp must evaluate to DEGRADED, got: ${futureTs.status}`);
    }
  });

  await test('SC-01.6: Correct-source healthy observation restores health under documented policy', () => {
    const degraded: TelemetryProvenance = {
      source: 'SIM_ENGINE',
      status: 'STALE',
      freshnessTimestamp: 5000,
      isAuthoritative: false,
      staleThresholdMs: 5000,
      epoch: 418,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED'
    };

    const now = 12000;
    const restored = updateTelemetryState(degraded, {
      source: 'SIM_ENGINE',
      freshnessTimestamp: now,
      status: 'HEALTHY'
    });

    if (restored.status !== 'HEALTHY' || restored.freshnessTimestamp !== now) {
      throw new Error('Correct-source healthy observation failed to restore health');
    }
  });

  await test('SC-01.7: Disconnected state timestamp refresh prevention (FF-D-01)', () => {
    const disconnectedFeed: TelemetryProvenance = {
      source: 'BROKER_FEED',
      status: 'DISCONNECTED',
      freshnessTimestamp: 5000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 10,
      bridgeStatus: 'DISCONNECTED',
      fenceStatus: 'ENFORCED'
    };

    // Incoming attempt with newer timestamp (8000) and HEALTHY status but same epoch (10)
    const blockedUpdate = updateTelemetryState(disconnectedFeed, {
      source: 'BROKER_FEED',
      status: 'HEALTHY',
      freshnessTimestamp: 8000,
      epoch: 10
    });

    if (blockedUpdate.status !== 'DISCONNECTED') {
      throw new Error(`Disconnected feed improperly cleared without advancing epoch! Got: ${blockedUpdate.status}`);
    }
    if (blockedUpdate.freshnessTimestamp !== 5000) {
      throw new Error(`Disconnected feed timestamp refreshed without authorized epoch advance! Got: ${blockedUpdate.freshnessTimestamp}`);
    }
  });

  await test('SC-01.8: Strict authorized handshake requirement and fail-closed reconnection gating (FF-D-01 / D2-A / D.2.1 / D.2.2)', () => {
    const disconnectedFeed: TelemetryProvenance = {
      source: 'BROKER_FEED',
      status: 'DISCONNECTED',
      freshnessTimestamp: 5000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 10,
      bridgeStatus: 'DISCONNECTED',
      fenceStatus: 'ENFORCED'
    };

    // 1. Reconnection attempt without independent auth proof is REJECTED fail-closed
    const rejectedNoAuth = updateTelemetryState(disconnectedFeed, {
      source: 'BROKER_FEED',
      status: 'HEALTHY',
      freshnessTimestamp: 9000,
      epoch: 11,
      bridgeStatus: 'CONNECTED'
    });
    if (rejectedNoAuth !== disconnectedFeed || rejectedNoAuth.status !== 'DISCONNECTED' || rejectedNoAuth.freshnessTimestamp !== 5000) {
      throw new Error('Reconnection was accepted without independent auth proof');
    }

    // 2. Forged caller-controlled boolean (reconnectAuthorized: true) MUST BE REJECTED fail-closed
    const diagForgedFlag = tryUpdateTelemetryState(disconnectedFeed, {
      source: 'BROKER_FEED',
      status: 'HEALTHY',
      freshnessTimestamp: 9000,
      epoch: 11,
      bridgeStatus: 'CONNECTED',
      reconnectAuthorized: true
    });
    if (diagForgedFlag.accepted || diagForgedFlag.state !== disconnectedFeed || diagForgedFlag.rejectionReason !== 'CALLER_RECONNECT_AUTHORITY_FORGERY') {
      throw new Error('Caller-controlled reconnectAuthorized boolean was improperly accepted');
    }

    // 3. Reconnection attempt with bridgeStatus UNKNOWN MUST BE REJECTED fail-closed
    const diagUnknownBridge = tryUpdateTelemetryState(disconnectedFeed, {
      source: 'BROKER_FEED',
      status: 'HEALTHY',
      freshnessTimestamp: 9000,
      epoch: 11,
      bridgeStatus: 'UNKNOWN'
    });
    if (diagUnknownBridge.accepted || diagUnknownBridge.state !== disconnectedFeed || diagUnknownBridge.rejectionReason !== 'DISCONNECTED_INACTIVE_BRIDGE_STATUS') {
      throw new Error('Reconnection was accepted with UNKNOWN bridge status');
    }

    // 4. Caller-supplied proof object with verify: () => true is REJECTED fail-closed
    const callerProof: ReconnectAuthorizationProof = {
      authority: 'CONTROL_SERVICE_HANDSHAKE',
      token: 'cs_proof_token_99182',
      issuedAt: 9000,
      nonce: 'nonce_8817a',
      verify: () => true
    };
    const diagCallerProof = tryUpdateTelemetryState(
      disconnectedFeed,
      {
        source: 'BROKER_FEED',
        status: 'HEALTHY',
        freshnessTimestamp: 9000,
        epoch: 11,
        bridgeStatus: 'CONNECTED'
      },
      callerProof
    );
    if (diagCallerProof.accepted || diagCallerProof.state !== disconnectedFeed || diagCallerProof.rejectionReason !== 'CALLER_RECONNECT_AUTHORITY_FORGERY') {
      throw new Error('Caller-supplied verify() callback or proof was accepted as trusted authority');
    }

    // 5. In the absence of integrated Control Service handshake authority, reconnection is BLOCKED fail-closed
    const diagBlocked = tryUpdateTelemetryState(disconnectedFeed, {
      source: 'BROKER_FEED',
      status: 'HEALTHY',
      freshnessTimestamp: 9000,
      epoch: 11,
      bridgeStatus: 'CONNECTED'
    });
    if (diagBlocked.accepted || diagBlocked.state !== disconnectedFeed || diagBlocked.rejectionReason !== 'RECONNECTION_BLOCKED_UNRESOLVED_CONTROL_SERVICE_AUTHORITY') {
      throw new Error('Reconnection from DISCONNECTED was permitted without integrated Control Service authority');
    }
  });

  await test('SC-01.9: Epoch regression rejection', () => {
    const nominalFeed: TelemetryProvenance = {
      source: 'CONTROL_SERVICE',
      status: 'HEALTHY',
      freshnessTimestamp: 10000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 15,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED'
    };

    // Stale message with regressed epoch (14 < 15)
    const regressed = updateTelemetryState(nominalFeed, {
      source: 'CONTROL_SERVICE',
      status: 'HEALTHY',
      freshnessTimestamp: 11000,
      epoch: 14
    });

    if (regressed.epoch !== 15 || regressed.freshnessTimestamp !== 10000) {
      throw new Error('Regressed epoch message was improperly accepted');
    }
  });

  await test('SC-01.10: Malformed epoch rejects update atomically with zero field mutation (D2-A Risk 1)', () => {
    const nominalFeed: TelemetryProvenance = {
      source: 'SIM_ENGINE',
      status: 'HEALTHY',
      freshnessTimestamp: 10000,
      isAuthoritative: false,
      staleThresholdMs: 5000,
      epoch: 5,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED'
    };

    const badEpochs = [-1, 0, 1.5, NaN, Infinity];
    for (const bad of badEpochs) {
      const result = updateTelemetryState(nominalFeed, {
        source: 'SIM_ENGINE',
        epoch: bad,
        freshnessTimestamp: 12000,
        bridgeStatus: 'COMPROMISED'
      });

      // D2-A: Snapshot must remain 100% bit-for-bit unchanged!
      if (result.epoch !== 5 || result.freshnessTimestamp !== 10000 || result.bridgeStatus !== 'OK' || result.status !== 'HEALTHY') {
        throw new Error(`Malformed epoch ${bad} caused partial mutation of snapshot fields!`);
      }
    }
  });

  await test('SC-01.11: Cross-source migration strictly rejected fail-closed (D2-A Risk 2)', () => {
    const brokerStream: TelemetryProvenance = {
      source: 'BROKER_FEED',
      status: 'HEALTHY',
      freshnessTimestamp: 10000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 10,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED'
    };

    // 1. Unauthorized migration without flags
    const attempt1 = updateTelemetryState(brokerStream, {
      source: 'CONTROL_SERVICE',
      freshnessTimestamp: 11000
    });
    if (attempt1.source !== 'BROKER_FEED' || attempt1.freshnessTimestamp !== 10000) {
      throw new Error('Cross-source migration was accepted');
    }

    // 2. Forged caller-controlled boolean (allowSourceMigration: true) MUST BE REJECTED
    const attempt2 = updateTelemetryState(brokerStream, {
      source: 'CONTROL_SERVICE',
      freshnessTimestamp: 11000,
      allowSourceMigration: true
    });
    if (attempt2.source !== 'BROKER_FEED' || attempt2.freshnessTimestamp !== 10000) {
      throw new Error('Caller-controlled allowSourceMigration flag was improperly honored');
    }

    // 3. Reverse direction migration (CONTROL_SERVICE -> BROKER_FEED) is also strictly rejected
    const controlStream: TelemetryProvenance = {
      ...brokerStream,
      source: 'CONTROL_SERVICE'
    };
    const attempt3 = updateTelemetryState(controlStream, {
      source: 'BROKER_FEED',
      freshnessTimestamp: 11000,
      allowSourceMigration: true
    });
    if (attempt3.source !== 'CONTROL_SERVICE' || attempt3.freshnessTimestamp !== 10000) {
      throw new Error('Reverse cross-source migration was improperly honored');
    }
  });

  await test('SC-01.12: Initial state creation does NOT synthesize Date.now() when timestamp absent (D2-A Risk 3)', () => {
    // Missing timestamp
    const initMissing = updateTelemetryState(undefined as any, {
      source: 'BROKER_FEED',
      status: 'HEALTHY'
    });
    if (initMissing.freshnessTimestamp !== 0 || initMissing.status !== 'UNKNOWN') {
      throw new Error(`Initial state with missing timestamp synthesized non-zero freshness: ${initMissing.freshnessTimestamp}`);
    }

    // Non-positive timestamp
    const initZero = updateTelemetryState(undefined as any, {
      source: 'BROKER_FEED',
      freshnessTimestamp: 0
    });
    if (initZero.freshnessTimestamp !== 0 || initZero.status !== 'UNKNOWN') {
      throw new Error('Initial state with zero timestamp did not initialize to 0 and UNKNOWN');
    }

    // Valid positive timestamp with valid source and explicit epoch succeeds
    const initValid = updateTelemetryState(undefined as any, {
      source: 'BROKER_FEED',
      epoch: 1,
      freshnessTimestamp: 55000,
      status: 'HEALTHY'
    });
    if (initValid.freshnessTimestamp !== 55000 || initValid.status !== 'HEALTHY' || initValid.epoch !== 1) {
      throw new Error('Initial state with valid timestamp was not accepted');
    }
  });

  await test('SC-01.13: Dual timestamp tracking preserves sourceEventTime and localReceiveTime', () => {
    const feed: TelemetryProvenance = {
      source: 'BROKER_FEED',
      status: 'HEALTHY',
      freshnessTimestamp: 10000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 10,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED'
    };

    const updated = updateTelemetryState(feed, {
      source: 'BROKER_FEED',
      freshnessTimestamp: 11000,
      sourceEventTimeMs: 10980
    });

    if (updated.sourceEventTimeMs !== 10980) {
      throw new Error(`sourceEventTimeMs failed to record, got: ${updated.sourceEventTimeMs}`);
    }
    if (typeof updated.localReceiveTimeMs !== 'number' || updated.localReceiveTimeMs <= 0) {
      throw new Error(`localReceiveTimeMs was not populated: ${updated.localReceiveTimeMs}`);
    }
  });

  await test('SC-01.14: Forged caller-controlled boolean reconnectAuthorized: true is strictly rejected fail-closed', () => {
    const disconnectedFeed: TelemetryProvenance = {
      source: 'CONTROL_SERVICE',
      status: 'DISCONNECTED',
      freshnessTimestamp: 4000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 20,
      bridgeStatus: 'DISCONNECTED',
      fenceStatus: 'ENFORCED'
    };

    // Caller attempts to forge authorization with reconnectAuthorized: true
    const forgedAttempt = updateTelemetryState(disconnectedFeed, {
      source: 'CONTROL_SERVICE',
      status: 'HEALTHY',
      freshnessTimestamp: 6000,
      epoch: 21,
      bridgeStatus: 'CONNECTED',
      reconnectAuthorized: true
    });

    if (forgedAttempt.status !== 'DISCONNECTED' || forgedAttempt.epoch !== 20 || forgedAttempt.freshnessTimestamp !== 4000) {
      throw new Error('Caller-controlled reconnectAuthorized: true forged a reconnection!');
    }
    if (forgedAttempt !== disconnectedFeed) {
      throw new Error('Rejected forged reconnection did not preserve snapshot identity');
    }
  });

  await test('SC-01.15: Reconnection attempt with UNKNOWN or unallowlisted bridge status is strictly rejected fail-closed', () => {
    const disconnectedFeed: TelemetryProvenance = {
      source: 'BROKER_FEED',
      status: 'DISCONNECTED',
      freshnessTimestamp: 5000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 10,
      bridgeStatus: 'DISCONNECTED',
      fenceStatus: 'ENFORCED'
    };

    const validProof: ReconnectAuthorizationProof = {
      authority: 'CONTROL_SERVICE_HANDSHAKE',
      token: 'valid_tok_1',
      issuedAt: 9000,
      nonce: 'n_1',
      verify: (src, ep) => src === 'BROKER_FEED' && ep === 11
    };

    const unallowlistedBridges = ['UNKNOWN', 'DISCONNECTED', 'DEGRADED', 'SOME_RANDOM_STATUS', ''];
    for (const badBridge of unallowlistedBridges) {
      const result = updateTelemetryState(
        disconnectedFeed,
        {
          source: 'BROKER_FEED',
          status: 'HEALTHY',
          freshnessTimestamp: 9000,
          epoch: 11,
          bridgeStatus: badBridge
        },
        validProof
      );

      if (result.status !== 'DISCONNECTED' || result.freshnessTimestamp !== 5000) {
        throw new Error(`Reconnection improperly accepted unallowlisted bridgeStatus: '${badBridge}'`);
      }
      if (result !== disconnectedFeed) {
        throw new Error('Rejected unallowlisted bridge reconnection did not preserve snapshot identity');
      }
    }
  });

  await test('SC-01.16: Malformed initial source and epoch produce DOCUMENTED_UNKNOWN_TELEMETRY without synthetic defaults', () => {
    // 1. Malformed source strings must NOT silently become 'SIM_ENGINE'
    const badSources = ['MALFORMED_SRC', 'ROGUE_FEED', 'UNKNOWN_SERVICE', ''];
    for (const badSrc of badSources) {
      const res = createInitialTelemetry({ source: badSrc as any, epoch: 5 });
      if (res.source !== 'FALLBACK_FIXTURE' || res.status !== 'UNKNOWN' || res.epoch !== 0) {
        throw new Error(`Malformed source '${badSrc}' was silently converted or given fabricated epoch! Got: ${res.source}, ep: ${res.epoch}`);
      }
    }

    // 2. Malformed epochs must NOT silently become epoch 1
    const badEpochs = [-1, 0, 1.5, NaN, Infinity, -Infinity];
    for (const badEp of badEpochs) {
      const res = createInitialTelemetry({ source: 'BROKER_FEED', epoch: badEp });
      if (res.status !== 'UNKNOWN' || res.epoch !== 0) {
        throw new Error(`Malformed epoch ${badEp} was silently converted to valid epoch! Got: ep ${res.epoch}`);
      }
    }
  });

  await test('SC-01.17: Negative, zero, NaN, and infinite thresholds reject update atomically on existing snapshot and produce DOCUMENTED_UNKNOWN_TELEMETRY initially', () => {
    const nominal: TelemetryProvenance = {
      source: 'SIM_ENGINE',
      status: 'HEALTHY',
      freshnessTimestamp: 10000,
      isAuthoritative: false,
      staleThresholdMs: 5000,
      epoch: 1,
      bridgeStatus: 'SIM_VIRTUAL_OK',
      fenceStatus: 'ENFORCED'
    };

    const badThresholds = [-500, 0, NaN, Infinity, -Infinity];
    for (const badTh of badThresholds) {
      // Existing snapshot update rejection:
      const updated = updateTelemetryState(nominal, {
        source: 'SIM_ENGINE',
        staleThresholdMs: badTh,
        freshnessTimestamp: 12000
      });
      if (updated !== nominal || updated.staleThresholdMs !== 5000 || updated.freshnessTimestamp !== 10000) {
        throw new Error(`Update with invalid threshold ${badTh} partially mutated snapshot!`);
      }

      // Initial creation rejection:
      const initial = createInitialTelemetry({
        source: 'SIM_ENGINE',
        staleThresholdMs: badTh,
        freshnessTimestamp: 12000
      });
      if (initial.status !== 'UNKNOWN' || initial.epoch !== 0) {
        throw new Error(`Initial creation with invalid threshold ${badTh} did not produce DOCUMENTED_UNKNOWN_TELEMETRY!`);
      }
    }

    // Explicit absence handling: genuine undefined threshold defaults to 5000
    const absInitial = createInitialTelemetry({
      source: 'SIM_ENGINE',
      epoch: 1,
      freshnessTimestamp: 12000,
      status: 'HEALTHY'
    });
    if (absInitial.staleThresholdMs !== 5000) {
      throw new Error(`Genuine absent threshold did not default to 5000: ${absInitial.staleThresholdMs}`);
    }
  });

  await test('SC-01.18: Invalid source-event timestamps reject update atomically and fail safely on initial state', () => {
    const nominal: TelemetryProvenance = {
      source: 'CONTROL_SERVICE',
      status: 'HEALTHY',
      freshnessTimestamp: 10000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 2,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED'
    };

    const badEventTimes = [-1, NaN, Infinity, -Infinity];
    for (const badTime of badEventTimes) {
      const updated = updateTelemetryState(nominal, {
        source: 'CONTROL_SERVICE',
        sourceEventTimeMs: badTime,
        freshnessTimestamp: 11000
      });
      if (updated !== nominal || updated.freshnessTimestamp !== 10000) {
        throw new Error(`Invalid sourceEventTimeMs ${badTime} was accepted on update!`);
      }

      const initial = createInitialTelemetry({
        source: 'CONTROL_SERVICE',
        sourceEventTimeMs: badTime,
        freshnessTimestamp: 11000
      });
      if (initial.status !== 'UNKNOWN' || initial.epoch !== 0) {
        throw new Error(`Invalid sourceEventTimeMs ${badTime} was accepted on initial creation!`);
      }
    }
  });

  await test('SC-01.19: Invalid status values reject update atomically and fail safely on initial state', () => {
    const nominal: TelemetryProvenance = {
      source: 'BROKER_FEED',
      status: 'HEALTHY',
      freshnessTimestamp: 10000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 3,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED'
    };

    const badStatuses = ['SUPER_HEALTHY', 'ONLINE', 'ACTIVE', ''];
    for (const badStat of badStatuses) {
      const updated = updateTelemetryState(nominal, {
        source: 'BROKER_FEED',
        status: badStat as any,
        freshnessTimestamp: 11000
      });
      if (updated !== nominal || updated.freshnessTimestamp !== 10000) {
        throw new Error(`Invalid status '${badStat}' was accepted on update!`);
      }

      const initial = createInitialTelemetry({
        source: 'BROKER_FEED',
        status: badStat as any,
        freshnessTimestamp: 11000
      });
      if (initial.status !== 'UNKNOWN' || initial.epoch !== 0) {
        throw new Error(`Invalid status '${badStat}' was accepted on initial creation!`);
      }
    }
  });

  await test('SC-01.20: Complete snapshot preservation on rejected updates across all invalid fields', () => {
    const original: TelemetryProvenance = {
      source: 'BROKER_FEED',
      status: 'HEALTHY',
      freshnessTimestamp: 10000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 4,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED',
      sourceEventTimeMs: 9990,
      localReceiveTimeMs: 10001
    };

    // A bundle of invalid fields targeting various invariants
    const rejections = [
      { source: 'SIM_ENGINE' as const }, // cross-source simulation tick
      { source: 'CONTROL_SERVICE' as const }, // cross-source migration
      { source: 'BOGUS_SOURCE' as any }, // unrecognized source
      { epoch: -1 }, // negative epoch
      { epoch: 3 }, // regressed epoch
      { freshnessTimestamp: 8000 }, // out-of-order stale timestamp
      { freshnessTimestamp: -50 }, // negative timestamp
      { freshnessTimestamp: NaN }, // NaN timestamp
      { staleThresholdMs: -100 }, // negative threshold
      { staleThresholdMs: NaN }, // NaN threshold
      { status: 'BOGUS_STATUS' as any }, // unrecognized status
      { sourceEventTimeMs: -500 } // negative event time
    ];

    for (const badUpdate of rejections) {
      const result = updateTelemetryState(original, badUpdate);
      if (result !== original) {
        throw new Error(`Update ${JSON.stringify(badUpdate)} did not return exact original reference!`);
      }
      // Bit-for-bit check
      if (
        result.source !== 'BROKER_FEED' ||
        result.status !== 'HEALTHY' ||
        result.freshnessTimestamp !== 10000 ||
        result.epoch !== 4 ||
        result.staleThresholdMs !== 5000 ||
        result.bridgeStatus !== 'OK' ||
        result.fenceStatus !== 'ENFORCED' ||
        result.sourceEventTimeMs !== 9990 ||
        result.localReceiveTimeMs !== 10001
      ) {
        throw new Error(`Update ${JSON.stringify(badUpdate)} corrupted protected snapshot fields!`);
      }
    }
  });

  await test('SC-01.21: Fail-closed reconnection enforcement: caller-manufactured proofs, tokens, and callbacks are strictly rejected as unauthenticated authority bypasses (Stage D.2.2)', () => {
    const disconnectedFeed: TelemetryProvenance = {
      source: 'CONTROL_SERVICE',
      status: 'DISCONNECTED',
      freshnessTimestamp: 7000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 50,
      bridgeStatus: 'DISCONNECTED',
      fenceStatus: 'ENFORCED'
    };

    // Caller constructs a fake proof object claiming CONTROL_SERVICE_HANDSHAKE authority with verify returning true
    const callerSuppliedProof: ReconnectAuthorizationProof = {
      authority: 'CONTROL_SERVICE_HANDSHAKE',
      token: 'fake_caller_token_xyz',
      issuedAt: 12000,
      nonce: 'fake_nonce_123',
      verify: () => true
    };

    // Caller attempts reconnection passing proof object: MUST FAIL CLOSED!
    const res = updateTelemetryState(
      disconnectedFeed,
      {
        source: 'CONTROL_SERVICE',
        status: 'HEALTHY',
        freshnessTimestamp: 12000,
        epoch: 51,
        bridgeStatus: 'CONNECTED'
      },
      callerSuppliedProof
    );

    if (res !== disconnectedFeed || res.status !== 'DISCONNECTED' || res.epoch !== 50 || res.freshnessTimestamp !== 7000) {
      throw new Error('Caller-supplied proof object with verify: () => true improperly authorized reconnection!');
    }

    // Verify diagnostic reason
    const diag = tryUpdateTelemetryState(
      disconnectedFeed,
      {
        source: 'CONTROL_SERVICE',
        status: 'HEALTHY',
        freshnessTimestamp: 12000,
        epoch: 51,
        bridgeStatus: 'CONNECTED'
      },
      callerSuppliedProof
    );
    if (diag.accepted || diag.rejectionReason !== 'CALLER_RECONNECT_AUTHORITY_FORGERY') {
      throw new Error(`Expected CALLER_RECONNECT_AUTHORITY_FORGERY rejection, got: ${diag.rejectionReason}`);
    }
  });

  await test('SC-01.22: Reconnection remains fail-closed and preserves snapshot even with advancing epoch and active bridge status (Stage D.2.2)', () => {
    const disconnectedFeed: TelemetryProvenance = {
      source: 'CONTROL_SERVICE',
      status: 'DISCONNECTED',
      freshnessTimestamp: 7000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 50,
      bridgeStatus: 'DISCONNECTED',
      fenceStatus: 'ENFORCED'
    };

    // Attempting reconnection with advancing epoch (51 > 50), valid timestamp, active bridge ('CONNECTED')
    // Without genuine backend authority, MUST BE REJECTED fail-closed
    const attempt = updateTelemetryState(disconnectedFeed, {
      source: 'CONTROL_SERVICE',
      status: 'HEALTHY',
      freshnessTimestamp: 12000,
      epoch: 51,
      bridgeStatus: 'CONNECTED'
    });

    if (attempt !== disconnectedFeed || attempt.status !== 'DISCONNECTED' || attempt.epoch !== 50 || attempt.freshnessTimestamp !== 7000) {
      throw new Error('Reconnection from DISCONNECTED was improperly accepted without trusted backend authority!');
    }

    const diag = tryUpdateTelemetryState(disconnectedFeed, {
      source: 'CONTROL_SERVICE',
      status: 'HEALTHY',
      freshnessTimestamp: 12000,
      epoch: 51,
      bridgeStatus: 'CONNECTED'
    });

    if (diag.accepted || diag.rejectionReason !== 'RECONNECTION_BLOCKED_UNRESOLVED_CONTROL_SERVICE_AUTHORITY') {
      throw new Error(`Expected RECONNECTION_BLOCKED_UNRESOLVED_CONTROL_SERVICE_AUTHORITY rejection, got: ${diag.rejectionReason}`);
    }

    // Confirm authority boundary declaration
    if (RECONNECT_AUTHORITY_BOUNDARY.isSupported !== false || RECONNECT_AUTHORITY_BOUNDARY.callerAuthorityAccepted !== false) {
      throw new Error('RECONNECT_AUTHORITY_BOUNDARY improperly marked supported or callerAuthorityAccepted');
    }
  });

  await test('SC-01.23: Initial-state strict validation: missing source, missing epoch, or missing observation timestamp fail safely to DOCUMENTED_UNKNOWN_TELEMETRY (Stage D.2.2)', () => {
    // 1. Missing source identity does NOT become 'SIM_ENGINE'
    const missingSource = createInitialTelemetry({
      epoch: 1,
      freshnessTimestamp: 10000,
      status: 'HEALTHY'
    });
    if (missingSource.source !== 'FALLBACK_FIXTURE' || missingSource.status !== 'UNKNOWN' || missingSource.epoch !== 0) {
      throw new Error(`Missing source improperly synthesized source '${missingSource.source}' with status '${missingSource.status}'`);
    }

    // 2. Missing epoch does NOT become epoch 1
    const missingEpoch = createInitialTelemetry({
      source: 'BROKER_FEED',
      freshnessTimestamp: 10000,
      status: 'HEALTHY'
    });
    if (missingEpoch.epoch !== 0 || missingEpoch.status !== 'UNKNOWN') {
      throw new Error(`Missing epoch improperly synthesized epoch ${missingEpoch.epoch} with status '${missingEpoch.status}'`);
    }

    // 3. Missing observation timestamp does NOT become fresh or HEALTHY
    const missingTime = createInitialTelemetry({
      source: 'BROKER_FEED',
      epoch: 1,
      status: 'HEALTHY'
    });
    if (missingTime.freshnessTimestamp !== 0 || missingTime.status !== 'UNKNOWN') {
      throw new Error(`Missing observation timestamp produced status '${missingTime.status}' with freshness ${missingTime.freshnessTimestamp}`);
    }

    // 4. Invalid thresholds on initial state produce DOCUMENTED_UNKNOWN_TELEMETRY
    const badThresholds = [0, -100, NaN, Infinity, -Infinity];
    for (const bt of badThresholds) {
      const res = createInitialTelemetry({
        source: 'BROKER_FEED',
        epoch: 1,
        freshnessTimestamp: 10000,
        staleThresholdMs: bt
      });
      if (res !== DOCUMENTED_UNKNOWN_TELEMETRY) {
        throw new Error(`Invalid initial threshold ${bt} did not produce DOCUMENTED_UNKNOWN_TELEMETRY!`);
      }
    }

    // 5. Valid initial state with explicit source, epoch, and timestamp succeeds
    const validInitial = createInitialTelemetry({
      source: 'BROKER_FEED',
      epoch: 1,
      freshnessTimestamp: 10000,
      status: 'HEALTHY'
    });
    if (validInitial.source !== 'BROKER_FEED' || validInitial.epoch !== 1 || validInitial.freshnessTimestamp !== 10000 || validInitial.status !== 'HEALTHY') {
      throw new Error('Valid initial state with explicit parameters was rejected');
    }
    if (validInitial.staleThresholdMs !== 5000) {
      throw new Error(`Absent threshold failed to default to 5000: ${validInitial.staleThresholdMs}`);
    }
  });

  // =========================================================================
  // SC-02: Secure Intent Identity & Idempotency
  // =========================================================================
  console.log('\n--- SC-02: Secure Intent Identity & Idempotency ---');
  clearIntentRegistry();

  await test('SC-02.1: Cryptographically secure intent identity generation without Math.random()', () => {
    const id1 = createLogicalIntentId('dan_op', 'CLOSE');
    const id2 = createLogicalIntentId('dan_op', 'CLOSE');

    if (!id1.startsWith('intent_close_dan_op_')) {
      throw new Error(`Invalid intentId prefix: ${id1}`);
    }
    if (id1 === id2) {
      throw new Error('Collision in generated logical intent IDs');
    }
    // Verify format contains UUID/hex from crypto
    const parts = id1.split('_');
    const token = parts[parts.length - 1];
    if (token.length < 16) {
      throw new Error(`Cryptographic random token too short: ${token}`);
    }
  });

  await test('SC-02.2: Two separate actions with identical payload receive distinct intent IDs and idempotency keys', () => {
    clearIntentRegistry();
    const actionA = createIntentFingerprint('operator_1', 'pos_01', 'EURUSD', 'CLOSE', { lots: 1.0 });
    const actionB = createIntentFingerprint('operator_1', 'pos_01', 'EURUSD', 'CLOSE', { lots: 1.0 });

    if (actionA.intentId === actionB.intentId) {
      throw new Error('Distinct actions produced identical intentId');
    }
    if (actionA.idempotencyKey === actionB.idempotencyKey) {
      throw new Error(`Distinct actions produced colliding idempotencyKey: ${actionA.idempotencyKey}`);
    }
    // But payload fingerprint remains deterministic and equal
    if (actionA.payloadFingerprint !== actionB.payloadFingerprint) {
      throw new Error('Identical payloads produced different fingerprints');
    }
  });

  await test('SC-02.3: Retrying same logical action preserves intent identity and idempotency key', () => {
    const action = createIntentFingerprint('op_recon', 'pos_01', 'EURUSD', 'TIGHTEN_STOP', { sl: 1.0850 });
    const retry = createIntentFingerprint('op_recon', 'pos_01', 'EURUSD', 'TIGHTEN_STOP', { sl: 1.0850 }, action.intentId, 2);

    if (retry.intentId !== action.intentId) {
      throw new Error('Retry did not preserve intentId');
    }
    if (retry.idempotencyKey !== action.idempotencyKey) {
      throw new Error('Retry did not preserve idempotencyKey');
    }
    if (retry.transportAttempt !== 2) {
      throw new Error('Retry attempt counter was not updated');
    }
  });

  await test('SC-02.4: Reusing existing intent ID with altered semantic payload is STRICTLY REJECTED', () => {
    const original = createIntentFingerprint('op_tamper', 'pos_02', 'GBPUSD', 'CLOSE', { lots: 1.0 });

    let threw = false;
    try {
      // Attacker or bug attempts to reuse original.intentId with lots: 2.0
      createIntentFingerprint('op_tamper', 'pos_02', 'GBPUSD', 'CLOSE', { lots: 2.0 }, original.intentId, 2);
    } catch (err) {
      if (err instanceof IntentReplayMismatchError) {
        threw = true;
      }
    }

    if (!threw) {
      throw new Error('Reusing existing intent ID with altered payload was not rejected!');
    }
  });

  await test('SC-02.5: Malformed existing intent IDs fail safely and are rejected', () => {
    const malformedIds = ['', '   ', 'invalid_prefix_123', 'pos_01', 'null'];
    for (const badId of malformedIds) {
      let threw = false;
      try {
        createIntentFingerprint('op', 'pos_01', 'EURUSD', 'CLOSE', {}, badId);
      } catch {
        threw = true;
      }
      if (!threw) {
        throw new Error(`Malformed existingIntentId '${badId}' was not rejected`);
      }
    }
  });

  await test('SC-02.6: Explicit non-authoritative boundary scoping (FF-D-03)', () => {
    if (IDEMPOTENCY_AUTHORITY_BOUNDARY.isAuthoritative !== false) {
      throw new Error('Idempotency boundary falsely declared authoritative status');
    }
    if (IDEMPOTENCY_AUTHORITY_BOUNDARY.layer !== 'CLIENT_GUI_SESSION') {
      throw new Error(`Unexpected idempotency layer: ${IDEMPOTENCY_AUTHORITY_BOUNDARY.layer}`);
    }
    if (IDEMPOTENCY_AUTHORITY_BOUNDARY.backendDependency !== 'UNRESOLVED_CONTROL_SERVICE_STORE') {
      throw new Error('Backend durable store dependency was not explicitly documented as unresolved');
    }
  });

  // =========================================================================
  // SC-03: Strict Canonicalization Invariants
  // =========================================================================
  console.log('\n--- SC-03: Strict Canonicalization Invariants ---');

  await test('SC-03.1: Deterministic key sorting across nested plain objects', () => {
    const a = { z: 1, a: { b: 2, a: 3 }, m: 'test' };
    const b = { a: { a: 3, b: 2 }, m: 'test', z: 1 };
    if (canonicalizeValue(a) !== canonicalizeValue(b)) {
      throw new Error('Key sorting was not deterministic across nesting levels');
    }
  });

  await test('SC-03.2: Negative zero (-0) normalizes deterministically to 0', () => {
    const posZero = canonicalizeValue({ val: 0 });
    const negZero = canonicalizeValue({ val: -0 });
    if (posZero !== negZero) {
      throw new Error(`Negative zero did not normalize to positive zero: ${negZero} !== ${posZero}`);
    }
    if (negZero !== '{"val":0}') {
      throw new Error(`Unexpected serialization for -0: ${negZero}`);
    }
  });

  await test('SC-03.3: Explicit null is preserved and distinguished from absent property', () => {
    const withNull = canonicalizeValue({ field: null });
    const withoutField = canonicalizeValue({});
    if (withNull === withoutField) {
      throw new Error('null was confounded with absent property');
    }
    if (withNull !== '{"field":null}') {
      throw new Error(`Expected '{"field":null}', got: ${withNull}`);
    }
  });

  await test('SC-03.4: Rejects sparse arrays and arrays with unexpected custom own properties', () => {
    // Sparse array
    const sparse = [1];
    sparse[3] = 4;
    let threw = false;
    try { canonicalizeValue(sparse); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed sparse array');

    // Custom property on array
    const arrWithProp = [1, 2, 3] as any;
    arrWithProp.extra = 'malicious';
    threw = false;
    try { canonicalizeValue(arrWithProp); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed array with custom own property');
  });

  await test('SC-03.5: Rejects undefined, NaN, Infinities, and BigInt', () => {
    let threw = false;
    try { canonicalizeValue({ x: undefined }); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed undefined');

    threw = false;
    try { canonicalizeValue({ x: NaN }); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed NaN');

    threw = false;
    try { canonicalizeValue({ x: Infinity }); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed Infinity');

    threw = false;
    try { canonicalizeValue({ x: -Infinity }); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed -Infinity');

    threw = false;
    try { canonicalizeValue({ x: BigInt(999) }); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed BigInt');
  });

  await test('SC-03.6: Rejects Date, RegExp, Map, Set, TypedArray, and custom classes', () => {
    const nonPlain = [
      new Date(),
      /test-regex/g,
      new Map(),
      new Set(),
      new Uint8Array(8),
      new Int32Array(4),
      new (class CustomOrder { symbol = 'EURUSD'; })()
    ];

    for (const item of nonPlain) {
      let threw = false;
      try {
        canonicalizeValue({ payload: item });
      } catch (e) {
        if (e instanceof CanonicalizationError) threw = true;
      }
      if (!threw) {
        throw new Error(`Allowed non-plain type: ${item?.constructor?.name}`);
      }
    }
  });

  await test('SC-03.7: Rejects cyclic structures and functions/symbols', () => {
    const cycle: Record<string, unknown> = { name: 'cycle' };
    cycle.self = cycle;

    let threw = false;
    try { canonicalizeValue(cycle); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed cyclic object');

    threw = false;
    try { canonicalizeValue({ fn: () => {} }); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed function');

    threw = false;
    try { canonicalizeValue({ sym: Symbol('token') }); } catch (e) { if (e instanceof CanonicalizationError) threw = true; }
    if (!threw) throw new Error('Allowed symbol');
  });

  // =========================================================================
  // SC-04: Simulation Reconciliation Truthfulness
  // =========================================================================
  console.log('\n--- SC-04: Simulation Reconciliation Truthfulness ---');

  await test('SC-04.1: Unknown intent ID strictly rejected with INTENT_NOT_RECORDED', async () => {
    const sim = new SimulationProvider();
    const res = await sim.reconcileCommand('intent_close_dan_op_unrecorded999');

    if (res.status !== 'REJECTED') {
      throw new Error(`Unknown intent must evaluate to REJECTED, got: ${res.status}`);
    }
    if (res.rejectionReason !== 'INTENT_NOT_RECORDED') {
      throw new Error(`Expected INTENT_NOT_RECORDED reason, got: ${res.rejectionReason}`);
    }
    if (res.authoritative !== false) {
      throw new Error('Reconciliation claimed authoritative status');
    }
  });

  await test('SC-04.2: Malformed intent IDs rejected safely with MALFORMED_INTENT_ID', async () => {
    const sim = new SimulationProvider();
    const badIds = ['', '   ', 'notanintent', '12345'];

    for (const id of badIds) {
      const res = await sim.reconcileCommand(id);
      if (res.status !== 'REJECTED' || res.rejectionReason !== 'MALFORMED_INTENT_ID') {
        throw new Error(`Malformed ID '${id}' was not rejected as MALFORMED_INTENT_ID`);
      }
      if (res.authoritative !== false) {
        throw new Error('Malformed reconciliation claimed authoritative status');
      }
    }
  });

  await test('SC-04.3: Recorded intents reconcile with consistent non-authoritative lifecycle', async () => {
    const sim = new SimulationProvider();
    const positions = await sim.getPositions();
    const target = positions[0];

    const intent = createIntentFingerprint('op_recon', target.id, target.symbol, 'MOVE_TO_BREAKEVEN');
    const submitRes = await sim.submitCommand(intent);

    const reconRes1 = await sim.reconcileCommand(intent.intentId);
    const reconRes2 = await sim.reconcileCommand(intent.intentId);

    if (reconRes1.status !== 'CONFIRMED' || reconRes1.intentId !== intent.intentId) {
      throw new Error('Failed to reconcile recorded intent');
    }
    if (reconRes1.authoritative !== false || reconRes2.authoritative !== false) {
      throw new Error('Reconciliation falsely claimed broker authority');
    }
    if (JSON.stringify(reconRes1) !== JSON.stringify(reconRes2)) {
      throw new Error('Repeated reconciliation yielded inconsistent outcomes');
    }
  });

  // =========================================================================
  // SC-05: Full-State Rejection Invariants
  // =========================================================================
  console.log('\n--- SC-05: Full-State Rejection Invariants ---');

  await test('SC-05.1: Rejected command leaves deep sandbox positions, orders, and events completely unmodified', async () => {
    const sim = new SimulationProvider();
    const initialPositions = await sim.getPositions();
    const initialOrders = await sim.getPendingOrders();
    const initialClosed = await sim.getClosedTrades();
    const target = initialPositions[0];

    const intent = createIntentFingerprint(
      'op_reject_test',
      target.id,
      target.symbol,
      'CLOSE',
      { simulateRejection: true }
    );

    const res = await sim.submitCommand(intent);
    if (res.status !== 'REJECTED') {
      throw new Error(`Expected REJECTED, got: ${res.status}`);
    }

    const afterPositions = await sim.getPositions();
    const afterOrders = await sim.getPendingOrders();
    const afterClosed = await sim.getClosedTrades();

    if (JSON.stringify(afterPositions) !== JSON.stringify(initialPositions)) {
      throw new Error('Sandbox positions mutated during rejected command');
    }
    if (JSON.stringify(afterOrders) !== JSON.stringify(initialOrders)) {
      throw new Error('Sandbox orders mutated during rejected command');
    }
    if (JSON.stringify(afterClosed) !== JSON.stringify(initialClosed)) {
      throw new Error('Sandbox closed trades mutated during rejected command');
    }
  });

  await test('SC-05.2: LiveCommandAdapter fails closed without mutating simulation state', async () => {
    const adapter = new LiveCommandAdapter();
    const sim = new SimulationProvider();
    const beforePositions = await sim.getPositions();

    const intent = createIntentFingerprint('op_live_test', 'pos_01', 'EURUSD', 'CLOSE');

    let threw = false;
    try {
      await adapter.submitCommand(intent);
    } catch (err) {
      if (err instanceof LiveExecutionBlockedError) {
        threw = true;
      }
    }

    if (!threw) {
      throw new Error('Live execution attempt did not fail closed with LiveExecutionBlockedError');
    }

    const afterPositions = await sim.getPositions();
    if (JSON.stringify(afterPositions) !== JSON.stringify(beforePositions)) {
      throw new Error('Blocked live action modified simulation state');
    }
  });

  await test('SC-05.3: Bit-for-bit protected state immutability proof (FF-D-04)', async () => {
    const sim = new SimulationProvider();
    const beforeSnapshot = sim.getProtectedTradingStateSnapshot();

    // 1. Rejection due to simulated constraint failure
    const pos = beforeSnapshot.positions[0];
    const rejectIntent1 = createIntentFingerprint('op_test', pos.id, pos.symbol, 'CLOSE', { simulateRejection: true });
    const res1 = await sim.submitCommand(rejectIntent1);
    if (res1.status !== 'REJECTED') {
      throw new Error(`Expected REJECTED, got ${res1.status}`);
    }

    const midSnapshot = sim.getProtectedTradingStateSnapshot();
    if (JSON.stringify(midSnapshot) !== JSON.stringify(beforeSnapshot)) {
      throw new Error('Protected trading state mutated after simulated rejection!');
    }

    // 2. Rejection due to missing position
    const rejectIntent2 = createIntentFingerprint('op_test', 'pos_nonexistent_999', 'EURUSD', 'CLOSE');
    const res2 = await sim.submitCommand(rejectIntent2);
    if (res2.status !== 'REJECTED') {
      throw new Error(`Expected REJECTED, got ${res2.status}`);
    }

    const finalSnapshot = sim.getProtectedTradingStateSnapshot();
    if (JSON.stringify(finalSnapshot) !== JSON.stringify(beforeSnapshot)) {
      throw new Error('Protected trading state mutated after missing position rejection!');
    }
  });

  // =========================================================================
  // SC-06: Audit-Event Persistence Truthfulness
  // =========================================================================
  console.log('\n--- SC-06: Audit-Event Persistence Truthfulness ---');

  await test('SC-06.1: Simulated and session events are labeled SIMULATED/SESSION without false PERSISTED claim', async () => {
    const sim = new SimulationProvider();
    const positions = await sim.getPositions();
    const target = positions[0];

    const intent = createIntentFingerprint('op_audit_truth', target.id, target.symbol, 'TIGHTEN_STOP');
    await sim.submitCommand(intent);

    const events = await sim.getSystemEvents();
    const latestEvent = events[0];

    if (latestEvent.status === 'PERSISTED') {
      throw new Error('In-memory simulated command event falsely claimed PERSISTED status!');
    }
    if (latestEvent.status !== 'SIMULATED' && latestEvent.status !== 'SESSION') {
      throw new Error(`Unexpected event status: ${latestEvent.status}`);
    }
    if (latestEvent.isAuthoritative !== false) {
      throw new Error('Event falsely claimed authoritative broker execution');
    }
  });

  // =========================================================================
  // Keyboard Safety & Operator Interaction Controls
  // =========================================================================
  console.log('\n--- Keyboard Safety & Operator Interaction Controls ---');

  await test('Keyboard guard rejects all interactive text inputs, textareas, and comboboxes', () => {
    const editableTargets = [
      { tagName: 'INPUT', isContentEditable: false, getAttribute: () => null },
      { tagName: 'TEXTAREA', isContentEditable: false, getAttribute: () => null },
      { tagName: 'SELECT', isContentEditable: false, getAttribute: () => null },
      { tagName: 'DIV', isContentEditable: true, getAttribute: () => null },
      { tagName: 'SPAN', isContentEditable: false, getAttribute: (attr: string) => attr === 'role' ? 'textbox' : null },
      { tagName: 'DIV', isContentEditable: false, getAttribute: (attr: string) => attr === 'role' ? 'searchbox' : null },
      { tagName: 'DIV', isContentEditable: false, getAttribute: (attr: string) => attr === 'role' ? 'combobox' : null },
    ];

    for (const t of editableTargets) {
      if (isSafeKeyboardShortcutTarget({ target: t } as unknown as KeyboardEvent) !== false) {
        throw new Error(`Failed to reject editable target: ${t.tagName}`);
      }
    }
  });

  await test('Keyboard guard rejects IME composition, repeated key chatter, and modal/in-flight states', () => {
    const safeTarget = { tagName: 'DIV', isContentEditable: false, getAttribute: () => null };

    // IME composition
    const imeEvent = { target: safeTarget, isComposing: true, keyCode: 229 } as unknown as KeyboardEvent;
    if (isValidShortcutEvent(imeEvent) !== false) {
      throw new Error('Allowed shortcut during IME composition');
    }

    // Key chatter
    const repeatEvent = { target: safeTarget, repeat: true } as unknown as KeyboardEvent;
    if (isValidShortcutEvent(repeatEvent, { allowRepeat: false }) !== false) {
      throw new Error('Allowed repeated key chatter');
    }

    // Modal open or command in flight
    const nominalEvent = { target: safeTarget, isComposing: false, repeat: false } as unknown as KeyboardEvent;
    if (isKeyboardShortcutAllowed(nominalEvent, { isModalOpen: true }) !== false) {
      throw new Error('Allowed shortcut while confirmation modal was open');
    }
    if (isKeyboardShortcutAllowed(nominalEvent, { isCommandInFlight: true }) !== false) {
      throw new Error('Allowed shortcut while operator command was in flight');
    }
  });

  console.log('\n========================================================');
  console.log(`Results: ${passed} PASSED, ${failed} FAILED`);
  console.log('========================================================\n');

  if (failed > 0) {
    process.exit(1);
  }
}

runStageDAdversarialTests().catch(err => {
  console.error('Fatal test runner error:', err);
  process.exit(1);
});
