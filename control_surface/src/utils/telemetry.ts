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

/**
 * D2-A: Explicit Architecture & Migration Boundary Scoping.
 * Cross-source migration requires a trusted distributed authorization lease signed by
 * the Control Service authority. In this frontend client session, no distributed authority
 * is provisioned, so cross-source migration is strictly fail-closed rejected.
 */
export const MIGRATION_AUTHORITY_BOUNDARY = {
  isSupported: false,
  reason: 'UNRESOLVED_CONTROL_SERVICE_MIGRATION_AUTHORITY',
  policy: 'CROSS_SOURCE_MIGRATION_STRICTLY_REJECTED'
} as const;

export interface TelemetryUpdateOptions extends Partial<TelemetryProvenance> {
  reconnectAuthorized?: boolean;
  // Retained as forbidden caller property for hostile verification testing
  allowSourceMigration?: boolean;
}

/**
 * SC-01 / D2-A: Safe telemetry state updater enforcing source provenance and atomicity.
 *
 * Invariants:
 * 1. All-or-Nothing Atomicity: If an incoming update fails any validation (malformed epoch, invalid timestamp,
 *    invalid threshold, unauthorized source migration, or unauthorized reconnection), the update is REJECTED
 *    and the current accepted snapshot is preserved 100% bit-for-bit without partial field pollution.
 * 2. Cross-Source Migration Protection: Cross-source migration is strictly rejected fail-closed; caller-controlled
 *    boolean flags cannot authorize source transitions.
 * 3. Zero Synthetic Timestamps: Initial state creation does NOT invent Date.now() when a genuine observation
 *    timestamp is absent or invalid (evaluates safely to 0 and UNKNOWN status).
 * 4. Gated Reconnection: Reconnection from DISCONNECTED cannot be authorized by epoch advance alone; it requires
 *    same-source identity, reconnectAuthorized flag, strictly advancing epoch, valid observation timestamp,
 *    and non-disconnected bridge status.
 * 5. Distinct Event Time: sourceEventTimeMs records external observation time; localReceiveTimeMs records local arrival.
 */
export function updateTelemetryState(
  current: TelemetryProvenance,
  incoming: TelemetryUpdateOptions
): TelemetryProvenance {
  // --- Case 1: Initial state initialization ---
  if (!current) {
    const initialSource: TelemetrySource =
      incoming.source && VALID_SOURCES.has(incoming.source) ? incoming.source : 'SIM_ENGINE';
    
    const initialEpoch =
      incoming.epoch && Number.isSafeInteger(incoming.epoch) && incoming.epoch > 0
        ? incoming.epoch
        : 1;

    // D2-A Risk 3: Do NOT substitute Date.now() if valid observation timestamp is absent!
    const hasValidTimestamp =
      typeof incoming.freshnessTimestamp === 'number' &&
      Number.isFinite(incoming.freshnessTimestamp) &&
      incoming.freshnessTimestamp > 0;

    const freshnessTimestamp = hasValidTimestamp ? incoming.freshnessTimestamp! : 0;
    const initialStatus: TelemetryStatus = hasValidTimestamp
      ? (incoming.status || 'UNKNOWN')
      : 'UNKNOWN';

    const receiveTime = Date.now();
    const sourceEventTime = incoming.sourceEventTimeMs ?? (hasValidTimestamp ? freshnessTimestamp : 0);

    return {
      source: initialSource,
      status: initialStatus,
      freshnessTimestamp,
      isAuthoritative: Boolean(incoming.isAuthoritative),
      staleThresholdMs: incoming.staleThresholdMs || 5000,
      epoch: initialEpoch,
      bridgeStatus: incoming.bridgeStatus || 'UNKNOWN',
      fenceStatus: incoming.fenceStatus || 'UNKNOWN',
      sourceEventTimeMs: sourceEventTime,
      localReceiveTimeMs: receiveTime
    };
  }

  // --- Case 2: Atomic update validation for existing state snapshot ---

  // 1. Cross-Source Protection (SC-01):
  // Simulation tick (SIM_ENGINE) CANNOT touch or overwrite external broker state!
  if (incoming.source === 'SIM_ENGINE' && current.source !== 'SIM_ENGINE') {
    return current;
  }

  // 2. D2-A Risk 2: Cross-Source Migration Protection (Fail-Closed)
  // Caller-controlled flags (e.g. allowSourceMigration: true) are REJECTED.
  if (incoming.source !== undefined && incoming.source !== current.source) {
    // Migration is strictly prohibited in the absence of a backend signed lease
    return current;
  }

  // 3. Source Identifier Validity:
  if (incoming.source !== undefined && !VALID_SOURCES.has(incoming.source)) {
    return current;
  }

  // 4. D2-A Risk 1: Epoch Validation (All-or-Nothing Atomicity)
  // If incoming epoch is malformed, REJECT the update completely (preserve snapshot untouched)
  if (incoming.epoch !== undefined) {
    if (!Number.isSafeInteger(incoming.epoch) || incoming.epoch <= 0) {
      // Malformed epoch: entire update rejected!
      return current;
    }
    if (incoming.epoch < current.epoch) {
      // Epoch regression: entire update rejected!
      return current;
    }
  }

  // 5. Stale / Out-of-Order Timestamp Protection:
  if (
    typeof incoming.freshnessTimestamp === 'number' &&
    incoming.freshnessTimestamp < current.freshnessTimestamp
  ) {
    return current;
  }

  // 6. Runtime Timestamp Validity (All-or-Nothing Atomicity):
  if (incoming.freshnessTimestamp !== undefined) {
    if (
      typeof incoming.freshnessTimestamp !== 'number' ||
      !Number.isFinite(incoming.freshnessTimestamp) ||
      incoming.freshnessTimestamp <= 0
    ) {
      // Invalid timestamp: entire update rejected!
      return current;
    }
  }

  // 7. Runtime Threshold Validity (All-or-Nothing Atomicity):
  if (incoming.staleThresholdMs !== undefined) {
    if (
      typeof incoming.staleThresholdMs !== 'number' ||
      !Number.isFinite(incoming.staleThresholdMs) ||
      incoming.staleThresholdMs <= 0
    ) {
      // Invalid threshold: entire update rejected!
      return current;
    }
  }

  // 8. D2-A Risk 4: Disconnected State Invariants & Gated Reconnection
  // In DISCONNECTED state, no field update or timestamp refresh is permitted unless an explicit
  // authorized reconnect handshake occurs with advancing epoch and active bridge status.
  const isCurrentlyDisconnected = current.status === 'DISCONNECTED';
  if (isCurrentlyDisconnected) {
    const isReconnectionAttempt = Boolean(incoming.status && incoming.status !== 'DISCONNECTED');
    const isReconnectAuthorized = Boolean(incoming.reconnectAuthorized);
    const hasAdvancingEpoch = Boolean(
      incoming.epoch !== undefined &&
      Number.isSafeInteger(incoming.epoch) &&
      incoming.epoch > current.epoch
    );
    const hasValidObservationTimestamp = Boolean(
      incoming.freshnessTimestamp !== undefined &&
      typeof incoming.freshnessTimestamp === 'number' &&
      Number.isFinite(incoming.freshnessTimestamp) &&
      incoming.freshnessTimestamp > 0
    );
    const hasActiveBridge = Boolean(
      incoming.bridgeStatus && incoming.bridgeStatus !== 'DISCONNECTED'
    );

    const isAuthorizedReconnect =
      isReconnectionAttempt &&
      isReconnectAuthorized &&
      hasAdvancingEpoch &&
      hasValidObservationTimestamp &&
      hasActiveBridge;

    if (!isAuthorizedReconnect) {
      // Reconnection rejected or not authorized: preserve accepted snapshot untouched!
      return current;
    }
  }

  // --- All validations passed: Apply atomic update ---
  const finalEpoch = incoming.epoch ?? current.epoch;
  const staleThreshold = incoming.staleThresholdMs ?? current.staleThresholdMs;
  const timestamp = incoming.freshnessTimestamp ?? current.freshnessTimestamp;
  const finalStatus: TelemetryStatus = incoming.status ?? current.status;
  const receiveTime = Date.now();
  const eventTime = incoming.sourceEventTimeMs ?? incoming.freshnessTimestamp ?? current.sourceEventTimeMs ?? timestamp;

  return {
    ...current,
    source: current.source,
    epoch: finalEpoch,
    staleThresholdMs: staleThreshold,
    freshnessTimestamp: timestamp,
    status: finalStatus,
    isAuthoritative: incoming.isAuthoritative ?? current.isAuthoritative,
    bridgeStatus: incoming.bridgeStatus ?? current.bridgeStatus,
    fenceStatus: incoming.fenceStatus ?? current.fenceStatus,
    sourceEventTimeMs: eventTime,
    localReceiveTimeMs: receiveTime
  };
}
