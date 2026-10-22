import { TelemetryProvenance, TelemetryStatus, TelemetrySource } from '../types/contracts';

export interface TelemetryEvaluation {
  status: TelemetryStatus;
  isStale: boolean;
  ageMs: number;
  reason?: string;
}

/**
 * Production Telemetry Freshness & Provenance Evaluator (SC-01 / SC-06).
 *
 * Invariants:
 * 1. An age >= staleThresholdMs evaluates strictly to STALE.
 * 2. Missing, non-positive, non-finite, or NaN timestamps evaluate to UNKNOWN or DEGRADED.
 * 3. Non-positive, non-finite, or invalid staleThresholdMs evaluates to DEGRADED (never false HEALTHY).
 * 4. Sources in DISCONNECTED state cannot be promoted to HEALTHY by age alone.
 * 5. Clock skew (future timestamps) evaluates to DEGRADED.
 * 6. UI timers MUST NOT synthesize fresh timestamps without a genuine provider event.
 */
export function evaluateTelemetryFreshness(
  telemetry: TelemetryProvenance,
  currentTimeMs: number = Date.now()
): TelemetryEvaluation {
  if (!telemetry) {
    return {
      status: 'UNKNOWN',
      isStale: true,
      ageMs: Infinity,
      reason: 'Telemetry object is null or undefined'
    };
  }

  const { freshnessTimestamp, staleThresholdMs, status } = telemetry;

  if (
    typeof freshnessTimestamp !== 'number' ||
    !Number.isFinite(freshnessTimestamp) ||
    isNaN(freshnessTimestamp) ||
    freshnessTimestamp <= 0
  ) {
    return {
      status: 'UNKNOWN',
      isStale: true,
      ageMs: Infinity,
      reason: 'Invalid, non-finite, or missing freshness timestamp'
    };
  }

  // SC-01 / SC-06: Treat non-positive, non-finite, or invalid staleThresholdMs strictly as DEGRADED (never false HEALTHY)
  if (
    typeof staleThresholdMs !== 'number' ||
    !Number.isFinite(staleThresholdMs) ||
    staleThresholdMs <= 0
  ) {
    return {
      status: 'DEGRADED',
      isStale: true,
      ageMs: Math.max(0, currentTimeMs - freshnessTimestamp),
      reason: 'Invalid, non-finite, or non-positive staleThresholdMs configuration'
    };
  }

  if (status === 'DISCONNECTED') {
    return {
      status: 'DISCONNECTED',
      isStale: true,
      ageMs: Math.max(0, currentTimeMs - freshnessTimestamp),
      reason: 'Source declared DISCONNECTED'
    };
  }

  const ageMs = currentTimeMs - freshnessTimestamp;

  if (ageMs < 0) {
    // Clock skew / future timestamp: flag as degraded
    return {
      status: 'DEGRADED',
      isStale: false,
      ageMs: 0,
      reason: 'Clock skew detected: timestamp in future'
    };
  }

  const isStale = ageMs >= staleThresholdMs;

  if (isStale) {
    return {
      status: 'STALE',
      isStale: true,
      ageMs,
      reason: `Telemetry age (${ageMs}ms) exceeds threshold (${staleThresholdMs}ms)`
    };
  }

  // Preserve degraded if already marked degraded
  if (status === 'DEGRADED') {
    return {
      status: 'DEGRADED',
      isStale: false,
      ageMs,
      reason: 'Source remains DEGRADED'
    };
  }

  return {
    status: 'HEALTHY',
    isStale: false,
    ageMs
  };
}

/**
 * SC-01 / SC-05: Safe telemetry state updater enforcing source provenance.
 *
 * Invariants:
 * 1. A simulation tick (SIM_ENGINE) CANNOT heal or refresh an external broker/feed source (BROKER_FEED/CONTROL_SERVICE).
 * 2. An event from a different source cannot refresh or overwrite the active source unless explicit source migration occurs.
 * 3. Stale events (older timestamps) cannot overwrite newer valid state.
 * 4. Invalid thresholds, timestamps, or malformed telemetry safely produce DEGRADED or UNKNOWN status.
 * 5. Sources in DISCONNECTED state cannot be promoted to HEALTHY without verified epoch advance for that source.
 */
const VALID_SOURCES: Set<TelemetrySource> = new Set([
  'SIM_ENGINE',
  'BROKER_FEED',
  'CONTROL_SERVICE',
  'FALLBACK_FIXTURE'
]);

export interface TelemetryUpdateOptions extends Partial<TelemetryProvenance> {
  allowSourceMigration?: boolean;
}

/**
 * SC-01 / SC-05 / FF-D-01 / FF-D-02: Safe telemetry state updater enforcing source provenance.
 *
 * Invariants:
 * 1. A simulation tick (SIM_ENGINE) CANNOT heal or refresh an external broker/feed source (BROKER_FEED/CONTROL_SERVICE).
 * 2. Cross-source migration requires explicit authorization (allowSourceMigration: true); unauthorized migration is strictly rejected.
 * 3. Stale events (older timestamps or regressed epochs) cannot overwrite newer valid state.
 * 4. Invalid thresholds, timestamps, or malformed epochs safely produce DEGRADED or UNKNOWN status.
 * 5. Sources in DISCONNECTED state CANNOT refresh freshnessTimestamp or clear DISCONNECTED without verified epoch advance (epoch > current.epoch) for that source.
 * 6. Explicitly tracks sourceEventTimeMs vs localReceiveTimeMs.
 */
export function updateTelemetryState(
  current: TelemetryProvenance,
  incoming: TelemetryUpdateOptions
): TelemetryProvenance {
  if (!current) {
    const initialSource: TelemetrySource =
      incoming.source && VALID_SOURCES.has(incoming.source) ? incoming.source : 'SIM_ENGINE';
    const initialEpoch =
      incoming.epoch && Number.isSafeInteger(incoming.epoch) && incoming.epoch > 0
        ? incoming.epoch
        : 1;

    return {
      source: initialSource,
      status: incoming.status || 'UNKNOWN',
      freshnessTimestamp: incoming.freshnessTimestamp || Date.now(),
      isAuthoritative: Boolean(incoming.isAuthoritative),
      staleThresholdMs: incoming.staleThresholdMs || 5000,
      epoch: initialEpoch,
      bridgeStatus: incoming.bridgeStatus || 'UNKNOWN',
      fenceStatus: incoming.fenceStatus || 'UNKNOWN',
      sourceEventTimeMs: incoming.sourceEventTimeMs ?? incoming.freshnessTimestamp ?? Date.now(),
      localReceiveTimeMs: incoming.localReceiveTimeMs ?? Date.now()
    };
  }

  // 1. Cross-Source Protection (SC-01):
  // If incoming event is from SIM_ENGINE but current active source is external (e.g. BROKER_FEED, CONTROL_SERVICE),
  // the simulation tick must NEVER promote the external source to HEALTHY or overwrite its timestamp!
  if (
    incoming.source === 'SIM_ENGINE' &&
    current.source !== 'SIM_ENGINE'
  ) {
    return current;
  }

  // 2. Source Identifier Validation & Migration Gate (FF-D-02):
  let targetSource: TelemetrySource = current.source;
  if (incoming.source !== undefined) {
    if (!VALID_SOURCES.has(incoming.source)) {
      // Invalid/unrecognized source identifier -> fail safely to DEGRADED without migrating source
      return {
        ...current,
        status: 'DEGRADED',
        localReceiveTimeMs: Date.now()
      };
    }
    if (incoming.source !== current.source) {
      if (!incoming.allowSourceMigration) {
        // Unauthorized source migration attempt is strictly rejected!
        return current;
      }
      targetSource = incoming.source;
    }
  }

  // 3. Epoch Validation & Regression Protection:
  let finalEpoch = current.epoch;
  let epochIsMalformed = false;
  if (incoming.epoch !== undefined) {
    if (!Number.isSafeInteger(incoming.epoch) || incoming.epoch <= 0) {
      epochIsMalformed = true;
    } else if (incoming.epoch < current.epoch && targetSource === current.source) {
      // Stale out-of-order epoch regression for the same source
      return current;
    } else {
      finalEpoch = incoming.epoch;
    }
  }

  // 4. Disconnected State Invariant (FF-D-01):
  // In DISCONNECTED state, no timestamp refresh is permitted unless an explicit reconnect handshake
  // advances the epoch (epoch > current.epoch). Otherwise, timestamp remains FROZEN.
  const isCurrentlyDisconnected = current.status === 'DISCONNECTED';
  if (isCurrentlyDisconnected) {
    const isReconnectionAttempt = Boolean(incoming.status && incoming.status !== 'DISCONNECTED');
    const hasValidAdvancingEpoch = Boolean(
      incoming.epoch !== undefined &&
      Number.isSafeInteger(incoming.epoch) &&
      incoming.epoch > current.epoch
    );

    if (!isReconnectionAttempt || !hasValidAdvancingEpoch) {
      // Reconnection rejected or not attempted: stay DISCONNECTED with FROZEN timestamp
      return {
        ...current,
        status: 'DISCONNECTED'
      };
    }
  }

  // 5. Out-of-order timestamp protection for connected streams
  if (
    typeof incoming.freshnessTimestamp === 'number' &&
    incoming.freshnessTimestamp < current.freshnessTimestamp
  ) {
    // Incoming event is older than current state; ignore stale update
    return current;
  }

  // 6. Validate runtime stale threshold
  const staleThreshold = incoming.staleThresholdMs ?? current.staleThresholdMs;
  let thresholdIsInvalid = false;
  if (
    typeof staleThreshold !== 'number' ||
    !Number.isFinite(staleThreshold) ||
    staleThreshold <= 0
  ) {
    thresholdIsInvalid = true;
  }

  // 7. Validate runtime timestamp
  const timestamp = incoming.freshnessTimestamp ?? current.freshnessTimestamp;
  let timestampIsInvalid = false;
  if (
    typeof timestamp !== 'number' ||
    !Number.isFinite(timestamp) ||
    timestamp <= 0
  ) {
    timestampIsInvalid = true;
  }

  let finalStatus: TelemetryStatus = incoming.status ?? current.status;
  if (epochIsMalformed || thresholdIsInvalid) {
    finalStatus = 'DEGRADED';
  } else if (timestampIsInvalid) {
    finalStatus = 'UNKNOWN';
  }

  const receiveTime = Date.now();
  const eventTime = incoming.sourceEventTimeMs ?? incoming.freshnessTimestamp ?? current.sourceEventTimeMs ?? timestamp;

  return {
    ...current,
    ...incoming,
    source: targetSource,
    epoch: epochIsMalformed ? current.epoch : finalEpoch,
    staleThresholdMs: staleThreshold,
    freshnessTimestamp: timestamp,
    status: finalStatus,
    sourceEventTimeMs: eventTime,
    localReceiveTimeMs: receiveTime
  };
}
