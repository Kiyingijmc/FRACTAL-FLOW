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
  evaluateInitialTelemetry,
  createInitialTelemetry,
  VALID_SOURCES,
  VALID_STATUSES,
  VALID_ACTIVE_BRIDGE_STATUSES,
  MIGRATION_AUTHORITY_BOUNDARY,
  RECONNECT_AUTHORITY_BOUNDARY,
  DOCUMENTED_UNKNOWN_TELEMETRY,
  ReconnectAuthorizationProof
} from '../utils/telemetry';
import { LiveExecutionBlockedError, TelemetryProvenance, TelemetrySource } from '../types/contracts';

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
  });

  await test('SC-01.24: Source-event timestamp provenance and absence preservation (Stage D.2.3 / D2.3-A)', () => {
    // 1. Absent sourceEventTimeMs on initial creation remains strictly undefined (never defaults to freshnessTimestamp)
    const initNoEventTime = createInitialTelemetry({
      source: 'BROKER_FEED',
      epoch: 1,
      freshnessTimestamp: 10000,
      status: 'HEALTHY'
    });
    if (initNoEventTime.sourceEventTimeMs !== undefined) {
      throw new Error(`Absent sourceEventTimeMs was improperly defaulted to: ${initNoEventTime.sourceEventTimeMs}`);
    }

    // 2. Updating without sourceEventTimeMs preserves previous state (remains undefined, not defaulted to freshnessTimestamp)
    const updatedNoEventTime = updateTelemetryState(initNoEventTime, {
      source: 'BROKER_FEED',
      freshnessTimestamp: 11000,
      epoch: 2
    });
    if (updatedNoEventTime.sourceEventTimeMs !== undefined) {
      throw new Error(`Update improperly fabricated sourceEventTimeMs from freshnessTimestamp: ${updatedNoEventTime.sourceEventTimeMs}`);
    }

    // 3. Valid positive and zero sourceEventTimeMs are accepted
    const initZeroEventTime = createInitialTelemetry({
      source: 'BROKER_FEED',
      epoch: 1,
      freshnessTimestamp: 10000,
      status: 'HEALTHY',
      sourceEventTimeMs: 0
    });
    if (initZeroEventTime.sourceEventTimeMs !== 0) {
      throw new Error(`Zero sourceEventTimeMs was rejected or altered: ${initZeroEventTime.sourceEventTimeMs}`);
    }

    const initPosEventTime = createInitialTelemetry({
      source: 'BROKER_FEED',
      epoch: 1,
      freshnessTimestamp: 10000,
      status: 'HEALTHY',
      sourceEventTimeMs: 9985
    });
    if (initPosEventTime.sourceEventTimeMs !== 9985) {
      throw new Error(`Valid sourceEventTimeMs was not recorded: ${initPosEventTime.sourceEventTimeMs}`);
    }

    // 4. Updating with explicit sourceEventTimeMs updates the field cleanly
    const updatedWithEventTime = updateTelemetryState(initPosEventTime, {
      source: 'BROKER_FEED',
      freshnessTimestamp: 12000,
      epoch: 2,
      sourceEventTimeMs: 11980
    });
    if (updatedWithEventTime.sourceEventTimeMs !== 11980) {
      throw new Error(`Explicit sourceEventTimeMs was not updated: ${updatedWithEventTime.sourceEventTimeMs}`);
    }

    // 5. Distinctness: localReceiveTimeMs is non-zero and distinct from sourceEventTimeMs
    if (typeof updatedWithEventTime.localReceiveTimeMs !== 'number' || updatedWithEventTime.localReceiveTimeMs <= 0) {
      throw new Error('localReceiveTimeMs was not populated with receipt timestamp');
    }

    // 6. Invalid sourceEventTimeMs values (negative, NaN, Infinity) are rejected with INVALID_SOURCE_EVENT_TIME
    const badTimes = [-1, -1000, NaN, Infinity, -Infinity];
    for (const bt of badTimes) {
      // Rejection on existing snapshot
      const diagUpdate = tryUpdateTelemetryState(initPosEventTime, {
        source: 'BROKER_FEED',
        freshnessTimestamp: 13000,
        epoch: 3,
        sourceEventTimeMs: bt
      });
      if (diagUpdate.accepted || diagUpdate.state !== initPosEventTime || diagUpdate.rejectionReason !== 'INVALID_SOURCE_EVENT_TIME') {
        throw new Error(`Invalid sourceEventTimeMs ${bt} on update was not rejected with INVALID_SOURCE_EVENT_TIME!`);
      }

      // Safe failure on initial creation
      const diagInitial = tryUpdateTelemetryState(undefined, {
        source: 'BROKER_FEED',
        epoch: 1,
        freshnessTimestamp: 10000,
        status: 'HEALTHY',
        sourceEventTimeMs: bt
      });
      if (diagInitial.accepted || diagInitial.rejectionReason !== 'INVALID_SOURCE_EVENT_TIME') {
        throw new Error(`Invalid sourceEventTimeMs ${bt} on initial state was not rejected with INVALID_SOURCE_EVENT_TIME!`);
      }
    }
  });

  await test('SC-01.25: Precise typed initial-state diagnostics and fail-safe unstated status (Stage D.2.3 / D2.3-B & D2.3-C)', () => {
    // 1. Missing incoming options -> MISSING_INITIAL_TELEMETRY
    const diagNull = tryUpdateTelemetryState(undefined, undefined as any);
    if (diagNull.accepted || diagNull.rejectionReason !== 'MISSING_INITIAL_TELEMETRY') {
      throw new Error(`Expected MISSING_INITIAL_TELEMETRY, got: ${diagNull.rejectionReason}`);
    }

    // 2. Missing source -> MISSING_SOURCE
    const diagMissingSource = tryUpdateTelemetryState(undefined, {
      epoch: 1,
      freshnessTimestamp: 10000,
      status: 'HEALTHY'
    });
    if (diagMissingSource.accepted || diagMissingSource.rejectionReason !== 'MISSING_SOURCE') {
      throw new Error(`Expected MISSING_SOURCE, got: ${diagMissingSource.rejectionReason}`);
    }

    // 3. Unrecognized source -> UNRECOGNIZED_SOURCE
    const diagBadSource = tryUpdateTelemetryState(undefined, {
      source: 'INVALID_ROUTER' as any,
      epoch: 1,
      freshnessTimestamp: 10000,
      status: 'HEALTHY'
    });
    if (diagBadSource.accepted || diagBadSource.rejectionReason !== 'UNRECOGNIZED_SOURCE') {
      throw new Error(`Expected UNRECOGNIZED_SOURCE, got: ${diagBadSource.rejectionReason}`);
    }

    // 4. Missing epoch -> MISSING_EPOCH
    const diagMissingEpoch = tryUpdateTelemetryState(undefined, {
      source: 'BROKER_FEED',
      freshnessTimestamp: 10000,
      status: 'HEALTHY'
    });
    if (diagMissingEpoch.accepted || diagMissingEpoch.rejectionReason !== 'MISSING_EPOCH') {
      throw new Error(`Expected MISSING_EPOCH, got: ${diagMissingEpoch.rejectionReason}`);
    }

    // 5. Malformed epoch -> MALFORMED_EPOCH
    const badEpochs = [0, -1, 1.5, NaN, Infinity];
    for (const be of badEpochs) {
      const diagBadEpoch = tryUpdateTelemetryState(undefined, {
        source: 'BROKER_FEED',
        epoch: be,
        freshnessTimestamp: 10000,
        status: 'HEALTHY'
      });
      if (diagBadEpoch.accepted || diagBadEpoch.rejectionReason !== 'MALFORMED_EPOCH') {
        throw new Error(`Expected MALFORMED_EPOCH for epoch ${be}, got: ${diagBadEpoch.rejectionReason}`);
      }
    }

    // 6. Missing timestamp -> MISSING_TIMESTAMP
    const diagMissingTimestamp = tryUpdateTelemetryState(undefined, {
      source: 'BROKER_FEED',
      epoch: 1,
      status: 'HEALTHY'
    });
    if (diagMissingTimestamp.accepted || diagMissingTimestamp.rejectionReason !== 'MISSING_TIMESTAMP') {
      throw new Error(`Expected MISSING_TIMESTAMP, got: ${diagMissingTimestamp.rejectionReason}`);
    }

    // 7. Invalid timestamp -> INVALID_TIMESTAMP
    const badTimestamps = [0, -50, NaN, Infinity];
    for (const bt of badTimestamps) {
      const diagBadTimestamp = tryUpdateTelemetryState(undefined, {
        source: 'BROKER_FEED',
        epoch: 1,
        freshnessTimestamp: bt,
        status: 'HEALTHY'
      });
      if (diagBadTimestamp.accepted || diagBadTimestamp.rejectionReason !== 'INVALID_TIMESTAMP') {
        throw new Error(`Expected INVALID_TIMESTAMP for timestamp ${bt}, got: ${diagBadTimestamp.rejectionReason}`);
      }
    }

    // 8. Invalid threshold -> INVALID_STALE_THRESHOLD
    const badThresholds = [0, -500, NaN, Infinity];
    for (const th of badThresholds) {
      const diagBadThreshold = tryUpdateTelemetryState(undefined, {
        source: 'BROKER_FEED',
        epoch: 1,
        freshnessTimestamp: 10000,
        staleThresholdMs: th,
        status: 'HEALTHY'
      });
      if (diagBadThreshold.accepted || diagBadThreshold.rejectionReason !== 'INVALID_STALE_THRESHOLD') {
        throw new Error(`Expected INVALID_STALE_THRESHOLD for threshold ${th}, got: ${diagBadThreshold.rejectionReason}`);
      }
    }

    // 9. Invalid status -> INVALID_STATUS
    const diagBadStatus = tryUpdateTelemetryState(undefined, {
      source: 'BROKER_FEED',
      epoch: 1,
      freshnessTimestamp: 10000,
      status: 'NOT_A_REAL_STATUS' as any
    });
    if (diagBadStatus.accepted || diagBadStatus.rejectionReason !== 'INVALID_STATUS') {
      throw new Error(`Expected INVALID_STATUS, got: ${diagBadStatus.rejectionReason}`);
    }

    // 10. D2.3-C: Unstated initial status safely defaults to 'UNKNOWN', never promoted to 'HEALTHY'
    const unstatedStatus = createInitialTelemetry({
      source: 'BROKER_FEED',
      epoch: 1,
      freshnessTimestamp: 10000
    });
    if (unstatedStatus.status !== 'UNKNOWN') {
      throw new Error(`Unstated initial status was silently promoted to '${unstatedStatus.status}' instead of UNKNOWN!`);
    }

    // 11. Explicit status is respected
    const explicitHealthy = createInitialTelemetry({
      source: 'BROKER_FEED',
      epoch: 1,
      freshnessTimestamp: 10000,
      status: 'HEALTHY'
    });
    if (explicitHealthy.status !== 'HEALTHY') {
      throw new Error(`Explicit status was not preserved: ${explicitHealthy.status}`);
    }
  });

  await test('SC-01.26: Source classification matrix, empty/whitespace classification, and strict diagnostic precedence (Stage D.2.3.1 / D2.3-F01)', () => {
    // -------------------------------------------------------------------------
    // 1. Source Classification Matrix (Section 4.1)
    // -------------------------------------------------------------------------
    const missingSourceInputs: Array<{ label: string; value: any }> = [
      { label: 'undefined', value: undefined },
      { label: 'runtime null', value: null },
      { label: 'empty string', value: '' },
      { label: 'single space', value: ' ' },
      { label: 'multiple spaces and tabs', value: '   \t\t   ' },
      { label: 'newline and carriage return whitespace', value: '\n\r\t \v\f' }
    ];

    for (const item of missingSourceInputs) {
      const diag = tryUpdateTelemetryState(undefined, {
        source: item.value,
        epoch: 1,
        freshnessTimestamp: 10000,
        status: 'HEALTHY'
      });
      if (diag.accepted) {
        throw new Error(`Expected rejected for missing source (${item.label}), but was accepted`);
      }
      if (diag.rejectionReason !== 'MISSING_SOURCE') {
        throw new Error(`Expected MISSING_SOURCE for (${item.label}), got: ${diag.rejectionReason}`);
      }
      if (diag.state !== DOCUMENTED_UNKNOWN_TELEMETRY) {
        throw new Error(`Expected DOCUMENTED_UNKNOWN_TELEMETRY for (${item.label}), got altered state`);
      }
      if (diag.state.status === 'HEALTHY') {
        throw new Error(`State was improperly promoted to HEALTHY for (${item.label})`);
      }
      if (diag.state.source !== 'FALLBACK_FIXTURE') {
        throw new Error(`Invalid source value leaked into state for (${item.label}): ${diag.state.source}`);
      }
    }

    // Unrecognized non-empty string sources
    const unrecognizedSources: Array<{ label: string; value: any }> = [
      { label: 'arbitrary unknown feed', value: 'UNKNOWN_FEED' },
      { label: 'leading whitespace around valid identifier', value: ' BROKER_FEED' },
      { label: 'trailing whitespace around valid identifier', value: 'BROKER_FEED ' },
      { label: 'surrounding whitespace around valid identifier', value: '  BROKER_FEED  ' },
      { label: 'whitespace around SIM_ENGINE', value: '\tSIM_ENGINE\t' }
    ];

    for (const item of unrecognizedSources) {
      const diag = tryUpdateTelemetryState(undefined, {
        source: item.value,
        epoch: 1,
        freshnessTimestamp: 10000,
        status: 'HEALTHY'
      });
      if (diag.accepted) {
        throw new Error(`Expected rejected for unrecognized source (${item.label}), but was accepted`);
      }
      if (diag.rejectionReason !== 'UNRECOGNIZED_SOURCE') {
        throw new Error(`Expected UNRECOGNIZED_SOURCE for (${item.label}), got: ${diag.rejectionReason}`);
      }
      if (diag.state !== DOCUMENTED_UNKNOWN_TELEMETRY) {
        throw new Error(`Expected DOCUMENTED_UNKNOWN_TELEMETRY for (${item.label})`);
      }
    }

    // Malformed non-string runtime types: fail closed without throwing or coercing
    const malformedRuntimeValues: Array<{ label: string; value: any }> = [
      { label: 'number 12345', value: 12345 },
      { label: 'boolean true', value: true },
      { label: 'boolean false', value: false },
      { label: 'plain object', value: { name: 'BROKER_FEED' } },
      { label: 'array', value: ['BROKER_FEED'] }
    ];

    for (const item of malformedRuntimeValues) {
      const diag = tryUpdateTelemetryState(undefined, {
        source: item.value,
        epoch: 1,
        freshnessTimestamp: 10000,
        status: 'HEALTHY'
      });
      if (diag.accepted) {
        throw new Error(`Malformed source (${item.label}) was unexpectedly accepted`);
      }
      if (diag.rejectionReason !== 'UNRECOGNIZED_SOURCE') {
        throw new Error(`Expected UNRECOGNIZED_SOURCE for (${item.label}), got: ${diag.rejectionReason}`);
      }
      if (diag.state !== DOCUMENTED_UNKNOWN_TELEMETRY) {
        throw new Error(`Expected DOCUMENTED_UNKNOWN_TELEMETRY for malformed source (${item.label})`);
      }
    }

    // Every allowlisted valid source must continue to be accepted
    const allowlistedSources: TelemetrySource[] = Array.from(VALID_SOURCES);
    for (const validSrc of allowlistedSources) {
      const diag = tryUpdateTelemetryState(undefined, {
        source: validSrc,
        epoch: 1,
        freshnessTimestamp: 10000,
        status: 'HEALTHY'
      });
      if (!diag.accepted) {
        throw new Error(`Valid allowlisted source ${validSrc} was rejected: ${diag.rejectionReason}`);
      }
      if (diag.state.source !== validSrc) {
        throw new Error(`Valid source ${validSrc} was not recorded: ${diag.state.source}`);
      }
      if (diag.state.epoch !== 1 || diag.state.freshnessTimestamp !== 10000 || diag.state.status !== 'HEALTHY') {
        throw new Error(`Valid initial state fields corrupted for ${validSrc}`);
      }
    }

    // -------------------------------------------------------------------------
    // 2. Diagnostic Precedence Invariants (Section 4.2)
    // -------------------------------------------------------------------------
    // Precedence: MISSING_SOURCE > UNRECOGNIZED_SOURCE > MISSING_EPOCH > MALFORMED_EPOCH >
    //             MISSING_TIMESTAMP > INVALID_TIMESTAMP > INVALID_STALE_THRESHOLD >
    //             INVALID_STATUS > INVALID_SOURCE_EVENT_TIME

    // Case 2.1: Missing source + invalid epoch -> MISSING_SOURCE
    const prec1 = tryUpdateTelemetryState(undefined, {
      source: undefined,
      epoch: -5,
      freshnessTimestamp: 10000
    });
    if (prec1.rejectionReason !== 'MISSING_SOURCE') {
      throw new Error(`Precedence 1 failed: expected MISSING_SOURCE, got ${prec1.rejectionReason}`);
    }

    // Case 2.2: Empty source + invalid timestamp -> MISSING_SOURCE
    const prec2 = tryUpdateTelemetryState(undefined, {
      source: '' as any,
      epoch: 1,
      freshnessTimestamp: -100
    });
    if (prec2.rejectionReason !== 'MISSING_SOURCE') {
      throw new Error(`Precedence 2 failed: expected MISSING_SOURCE, got ${prec2.rejectionReason}`);
    }

    // Case 2.3: Whitespace source + malformed epoch + invalid timestamp -> MISSING_SOURCE
    const prec3 = tryUpdateTelemetryState(undefined, {
      source: '   \t' as any,
      epoch: 0,
      freshnessTimestamp: NaN
    });
    if (prec3.rejectionReason !== 'MISSING_SOURCE') {
      throw new Error(`Precedence 3 failed: expected MISSING_SOURCE, got ${prec3.rejectionReason}`);
    }

    // Case 2.4: Unrecognized source + missing epoch -> UNRECOGNIZED_SOURCE
    const prec4 = tryUpdateTelemetryState(undefined, {
      source: 'UNKNOWN_ROUTER' as any,
      freshnessTimestamp: 10000
    });
    if (prec4.rejectionReason !== 'UNRECOGNIZED_SOURCE') {
      throw new Error(`Precedence 4 failed: expected UNRECOGNIZED_SOURCE, got ${prec4.rejectionReason}`);
    }

    // Case 2.5: Valid source + malformed epoch + invalid timestamp -> MALFORMED_EPOCH
    const prec5 = tryUpdateTelemetryState(undefined, {
      source: 'BROKER_FEED',
      epoch: 0,
      freshnessTimestamp: -50
    });
    if (prec5.rejectionReason !== 'MALFORMED_EPOCH') {
      throw new Error(`Precedence 5 failed: expected MALFORMED_EPOCH, got ${prec5.rejectionReason}`);
    }

    // Case 2.6: Valid source + valid epoch + missing timestamp + invalid threshold -> MISSING_TIMESTAMP
    const prec6 = tryUpdateTelemetryState(undefined, {
      source: 'BROKER_FEED',
      epoch: 1,
      staleThresholdMs: -500
    });
    if (prec6.rejectionReason !== 'MISSING_TIMESTAMP') {
      throw new Error(`Precedence 6 failed: expected MISSING_TIMESTAMP, got ${prec6.rejectionReason}`);
    }

    // Case 2.7: Valid source/epoch/timestamp + invalid threshold + invalid status -> INVALID_STALE_THRESHOLD
    const prec7 = tryUpdateTelemetryState(undefined, {
      source: 'BROKER_FEED',
      epoch: 1,
      freshnessTimestamp: 10000,
      staleThresholdMs: 0,
      status: 'NOT_A_STATUS' as any
    });
    if (prec7.rejectionReason !== 'INVALID_STALE_THRESHOLD') {
      throw new Error(`Precedence 7 failed: expected INVALID_STALE_THRESHOLD, got ${prec7.rejectionReason}`);
    }

    // Case 2.8: Valid source/epoch/timestamp/threshold + invalid status + negative event time -> INVALID_STATUS
    const prec8 = tryUpdateTelemetryState(undefined, {
      source: 'BROKER_FEED',
      epoch: 1,
      freshnessTimestamp: 10000,
      staleThresholdMs: 5000,
      status: 'INVALID_STATUS_STRING' as any,
      sourceEventTimeMs: -1
    });
    if (prec8.rejectionReason !== 'INVALID_STATUS') {
      throw new Error(`Precedence 8 failed: expected INVALID_STATUS, got ${prec8.rejectionReason}`);
    }

    // -------------------------------------------------------------------------
    // 3. Atomicity & Snapshot Immutability on Rejected Updates (Section 4.3)
    // -------------------------------------------------------------------------
    const preUpdateSnapshot: TelemetryProvenance = {
      source: 'BROKER_FEED',
      status: 'HEALTHY',
      freshnessTimestamp: 50000,
      isAuthoritative: true,
      staleThresholdMs: 5000,
      epoch: 10,
      bridgeStatus: 'OK',
      fenceStatus: 'ENFORCED',
      sourceEventTimeMs: 49990,
      localReceiveTimeMs: 50001
    };

    const invalidUpdateSources: any[] = ['', '   ', '\t\n', null, 'ANOTHER_SOURCE', ' BROKER_FEED '];
    for (const badSrc of invalidUpdateSources) {
      const updateResult = tryUpdateTelemetryState(preUpdateSnapshot, {
        source: badSrc,
        freshnessTimestamp: 51000,
        epoch: 11
      });
      if (updateResult.accepted) {
        throw new Error(`Update with invalid source ${JSON.stringify(badSrc)} was accepted!`);
      }
      if (updateResult.state !== preUpdateSnapshot) {
        throw new Error(`Rejected update did not preserve exact original snapshot reference!`);
      }
      // Deep content equality
      if (
        updateResult.state.source !== 'BROKER_FEED' ||
        updateResult.state.epoch !== 10 ||
        updateResult.state.freshnessTimestamp !== 50000 ||
        updateResult.state.sourceEventTimeMs !== 49990 ||
        updateResult.state.status !== 'HEALTHY'
      ) {
        throw new Error(`Rejected update corrupted pre-update snapshot content!`);
      }
    }

    // -------------------------------------------------------------------------
    // 4. Validator / Constructor Consistency (Section 4.4)
    // -------------------------------------------------------------------------
    const consistencyFixtures: Array<Partial<TelemetryProvenance> | undefined> = [
      undefined,
      {},
      { source: '' as any, epoch: 1, freshnessTimestamp: 10000 },
      { source: '   ' as any, epoch: 1, freshnessTimestamp: 10000 },
      { source: null as any, epoch: 1, freshnessTimestamp: 10000 },
      { source: 'UNKNOWN_FEED' as any, epoch: 1, freshnessTimestamp: 10000 },
      { source: 999 as any, epoch: 1, freshnessTimestamp: 10000 },
      { source: 'BROKER_FEED', epoch: 1, freshnessTimestamp: 10000 },
      { source: 'SIM_ENGINE', epoch: 2, freshnessTimestamp: 20000, status: 'HEALTHY' },
      { source: 'CONTROL_SERVICE', epoch: 3, freshnessTimestamp: 30000, sourceEventTimeMs: 29990 },
      { source: 'FALLBACK_FIXTURE', epoch: 4, freshnessTimestamp: 40000, staleThresholdMs: 3000 }
    ];

    for (const fixture of consistencyFixtures) {
      const constructed = createInitialTelemetry(fixture as any);
      const evaluated = evaluateInitialTelemetry(fixture as any);
      // Exclude non-deterministic localReceiveTimeMs if set, but compare all canonical fields
      if (
        constructed.source !== evaluated.state.source ||
        constructed.status !== evaluated.state.status ||
        constructed.epoch !== evaluated.state.epoch ||
        constructed.freshnessTimestamp !== evaluated.state.freshnessTimestamp ||
        constructed.staleThresholdMs !== evaluated.state.staleThresholdMs ||
        constructed.isAuthoritative !== evaluated.state.isAuthoritative ||
        constructed.bridgeStatus !== evaluated.state.bridgeStatus ||
        constructed.fenceStatus !== evaluated.state.fenceStatus ||
        constructed.sourceEventTimeMs !== evaluated.state.sourceEventTimeMs
      ) {
        throw new Error(`Divergence detected between createInitialTelemetry and evaluateInitialTelemetry for fixture ${JSON.stringify(fixture)}`);
      }
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
