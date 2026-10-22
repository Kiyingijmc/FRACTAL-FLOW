import { TelemetryProvenance, TelemetryStatus, TelemetrySource } from '../types/contracts';

export interface TelemetryEvaluation {
  status: TelemetryStatus;
  isStale: boolean;
  ageMs: number;
  reason?: string;
}

/**
 * Valid set of telemetry source identifiers recognized by the domain.
 */
export const VALID_SOURCES: ReadonlySet<TelemetrySource> = new Set([
  'SIM_ENGINE',
  'BROKER_FEED',
  'CONTROL_SERVICE',
  'FALLBACK_FIXTURE'
]);

/**
 * Valid set of telemetry status identifiers recognized by the domain contract.
 */
export const VALID_STATUSES: ReadonlySet<TelemetryStatus> = new Set([
  'HEALTHY',
  'STALE',
  'DEGRADED',
  'DISCONNECTED',
  'UNKNOWN'
]);

/**
 * Explicit allowlist of active bridge statuses permitted for reconnection.
 * Invariant: 'UNKNOWN', 'DISCONNECTED', empty strings, or unallowlisted values
 * must NEVER count as active.
 */
export const VALID_ACTIVE_BRIDGE_STATUSES: ReadonlySet<string> = new Set([
  'SIM_VIRTUAL_OK',
  'CONNECTED',
  'OK',
  'SIM_SANDBOX_VIRTUAL'
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

/**
 * D2.1: Explicit Reconnection Authority Boundary Scoping.
 * Reconnection from DISCONNECTED state cannot be authorized by caller-controlled boolean flags.
 * A boolean such as `reconnectAuthorized: true` is treated as a caller forgery.
 * In the absence of an authenticated Control Service handshake proof, reconnection from
 * DISCONNECTED is strictly fail-closed rejected and preserves the current snapshot unchanged.
 */
export const RECONNECT_AUTHORITY_BOUNDARY = {
  isSupported: false,
  reason: 'UNRESOLVED_CONTROL_SERVICE_RECONNECT_AUTHORITY',
  policy: 'RECONNECTION_WITHOUT_INDEPENDENT_CONTROL_SERVICE_PROOF_STRICTLY_REJECTED'
} as const;

/**
 * Canonical Documented Unknown Telemetry State.
 * Used when initial input is missing, malformed, or invalid.
 * Invariant: Does NOT silently synthesize 'SIM_ENGINE', epoch 1, or a healthy-looking state.
 */
export const DOCUMENTED_UNKNOWN_TELEMETRY: Readonly<TelemetryProvenance> = Object.freeze({
  source: 'FALLBACK_FIXTURE',
  status: 'UNKNOWN',
  freshnessTimestamp: 0,
  isAuthoritative: false,
  staleThresholdMs: 5000,
  epoch: 0,
  bridgeStatus: 'UNKNOWN',
  fenceStatus: 'UNKNOWN',
  sourceEventTimeMs: 0,
  localReceiveTimeMs: 0
});

/**
 * Independent authorization proof for establishing trusted reconnection.
 * A caller-controlled boolean is not accepted.
 */
export interface ReconnectAuthorizationProof {
  readonly authority: 'CONTROL_SERVICE_HANDSHAKE';
  readonly token: string;
  readonly issuedAt: number;
  readonly nonce: string;
  readonly verify: (source: TelemetrySource, epoch: number) => boolean;
}

export interface TelemetryUpdateOptions extends Partial<TelemetryProvenance> {
  // Retained as forbidden caller property for hostile verification testing
  reconnectAuthorized?: boolean;
  allowSourceMigration?: boolean;
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
    isNaN(staleThresholdMs) ||
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
 * Validates initial telemetry input before constructing accepted state.
 *
 * Invariants (Stage D.2.1):
 * 1. Reject or preserve an explicit unknown state for malformed sources, invalid epochs,
 *    non-finite or non-positive timestamps, invalid thresholds, invalid status values,
 *    and malformed source-event timestamps.
 * 2. Do not silently turn malformed input into 'SIM_ENGINE', epoch 1, or a healthy-looking state.
 * 3. Replace truthiness-based threshold defaulting with explicit absence handling and validation.
 *    A default (5000ms) may be used ONLY when the field is genuinely absent (undefined).
 *    Reject negative, zero, NaN, and infinite threshold values.
 * 4. Do not synthesize Date.now() when valid observation timestamps are absent.
 */
export function createInitialTelemetry(
  incoming?: TelemetryUpdateOptions
): TelemetryProvenance {
  if (!incoming) {
    return DOCUMENTED_UNKNOWN_TELEMETRY;
  }

  // 1. Source Validation: If provided, must be in VALID_SOURCES.
  // Do NOT silently turn malformed input into 'SIM_ENGINE'.
  if (incoming.source !== undefined && !VALID_SOURCES.has(incoming.source)) {
    return DOCUMENTED_UNKNOWN_TELEMETRY;
  }

  // 2. Epoch Validation: If provided, must be a positive safe integer.
  // Do NOT silently turn malformed epoch into 1.
  if (
    incoming.epoch !== undefined &&
    (!Number.isSafeInteger(incoming.epoch) || incoming.epoch <= 0)
  ) {
    return DOCUMENTED_UNKNOWN_TELEMETRY;
  }

  // 3. Threshold Validation (Explicit Absence Handling):
  // Default is permitted ONLY when staleThresholdMs is genuinely undefined.
  // Reject negative, zero, NaN, and infinite values fail-closed to DOCUMENTED_UNKNOWN_TELEMETRY.
  if (incoming.staleThresholdMs !== undefined) {
    if (
      typeof incoming.staleThresholdMs !== 'number' ||
      !Number.isFinite(incoming.staleThresholdMs) ||
      isNaN(incoming.staleThresholdMs) ||
      incoming.staleThresholdMs <= 0
    ) {
      return DOCUMENTED_UNKNOWN_TELEMETRY;
    }
  }

  // 4. Status Validation: If provided, must be in VALID_STATUSES.
  if (incoming.status !== undefined && !VALID_STATUSES.has(incoming.status)) {
    return DOCUMENTED_UNKNOWN_TELEMETRY;
  }

  // 5. Source Event Timestamp Validation: If provided, must be non-negative finite number.
  if (incoming.sourceEventTimeMs !== undefined) {
    if (
      typeof incoming.sourceEventTimeMs !== 'number' ||
      !Number.isFinite(incoming.sourceEventTimeMs) ||
      isNaN(incoming.sourceEventTimeMs) ||
      incoming.sourceEventTimeMs < 0
    ) {
      return DOCUMENTED_UNKNOWN_TELEMETRY;
    }
  }

  // 6. Freshness Timestamp Validation:
  const hasValidTimestamp =
    typeof incoming.freshnessTimestamp === 'number' &&
    Number.isFinite(incoming.freshnessTimestamp) &&
    !isNaN(incoming.freshnessTimestamp) &&
    incoming.freshnessTimestamp > 0;

  // If freshnessTimestamp was explicitly provided but is invalid (<=0, NaN, Infinity):
  if (incoming.freshnessTimestamp !== undefined && !hasValidTimestamp) {
    return DOCUMENTED_UNKNOWN_TELEMETRY;
  }

  // If all provided fields are valid, construct accepted initial state:
  const source: TelemetrySource = incoming.source ?? 'FALLBACK_FIXTURE';
  const epoch = incoming.epoch ?? (hasValidTimestamp ? 1 : 0);
  const staleThresholdMs =
    incoming.staleThresholdMs === undefined ? 5000 : incoming.staleThresholdMs;
  const freshnessTimestamp = hasValidTimestamp ? incoming.freshnessTimestamp! : 0;
  const status: TelemetryStatus = hasValidTimestamp
    ? (incoming.status ?? 'HEALTHY')
    : 'UNKNOWN';

  const receiveTime = hasValidTimestamp ? Date.now() : 0;
  const sourceEventTime =
    incoming.sourceEventTimeMs ?? (hasValidTimestamp ? freshnessTimestamp : 0);

  return {
    source,
    status,
    freshnessTimestamp,
    isAuthoritative: Boolean(incoming.isAuthoritative),
    staleThresholdMs,
    epoch,
    bridgeStatus: incoming.bridgeStatus ?? 'UNKNOWN',
    fenceStatus: incoming.fenceStatus ?? 'UNKNOWN',
    sourceEventTimeMs: sourceEventTime,
    localReceiveTimeMs: receiveTime
  };
}

/**
 * SC-01 / D2-A / D2.1: Safe telemetry state updater enforcing source provenance,
 * all-or-nothing atomicity, and independent reconnection authorization.
 *
 * Invariants:
 * 1. All-or-Nothing Atomicity: If an incoming update fails ANY validation (malformed epoch,
 *    invalid timestamp, invalid threshold, invalid status, unauthorized source migration,
 *    or unverified reconnection), the update is REJECTED and current is returned 100% untouched.
 * 2. Cross-Source Migration Protection: Cross-source migration is strictly rejected fail-closed;
 *    caller-controlled boolean flags cannot authorize source transitions.
 * 3. Zero Synthetic Timestamps: Initial state creation does NOT invent Date.now() when a genuine
 *    observation timestamp is absent or invalid (evaluates safely to 0 and UNKNOWN status).
 * 4. Independent Reconnection Authorization: A caller-controlled boolean `reconnectAuthorized: true`
 *    is strictly rejected as a forgery. Reconnection from DISCONNECTED requires an independent
 *    authorization proof (CONTROL_SERVICE_HANDSHAKE), strictly advancing epoch, valid observation
 *    timestamp, and an active bridge status in VALID_ACTIVE_BRIDGE_STATUSES ('UNKNOWN' is rejected).
 * 5. Distinct Event Time: sourceEventTimeMs records external observation time; localReceiveTimeMs records local arrival.
 */
export function updateTelemetryState(
  current: TelemetryProvenance | undefined,
  incoming: TelemetryUpdateOptions,
  authProof?: ReconnectAuthorizationProof
): TelemetryProvenance {
  // --- Case 1: Initial state initialization ---
  if (!current) {
    return createInitialTelemetry(incoming);
  }

  // --- Case 2: Atomic update validation for existing state snapshot ---

  // 1. Cross-Source Protection (SC-01.1):
  // Simulation tick (SIM_ENGINE) CANNOT touch or overwrite external broker state!
  if (incoming.source === 'SIM_ENGINE' && current.source !== 'SIM_ENGINE') {
    return current;
  }

  // 2. Cross-Source Migration Protection (Fail-Closed) (D2-A Risk 2):
  // Caller-controlled flags (e.g. allowSourceMigration: true) are REJECTED.
  if (incoming.source !== undefined && incoming.source !== current.source) {
    return current;
  }

  // 3. Source Identifier Validity:
  if (incoming.source !== undefined && !VALID_SOURCES.has(incoming.source)) {
    return current;
  }

  // 4. Epoch Validation (All-or-Nothing Atomicity):
  if (incoming.epoch !== undefined) {
    if (!Number.isSafeInteger(incoming.epoch) || incoming.epoch <= 0) {
      return current;
    }
    if (incoming.epoch < current.epoch) {
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
      isNaN(incoming.freshnessTimestamp) ||
      incoming.freshnessTimestamp <= 0
    ) {
      return current;
    }
  }

  // 7. Runtime Threshold Validity (All-or-Nothing Atomicity & Explicit Absence Handling):
  if (incoming.staleThresholdMs !== undefined) {
    if (
      typeof incoming.staleThresholdMs !== 'number' ||
      !Number.isFinite(incoming.staleThresholdMs) ||
      isNaN(incoming.staleThresholdMs) ||
      incoming.staleThresholdMs <= 0
    ) {
      return current;
    }
  }

  // 8. Runtime Status Validity:
  if (incoming.status !== undefined && !VALID_STATUSES.has(incoming.status)) {
    return current;
  }

  // 9. Source Event Timestamp Validity:
  if (incoming.sourceEventTimeMs !== undefined) {
    if (
      typeof incoming.sourceEventTimeMs !== 'number' ||
      !Number.isFinite(incoming.sourceEventTimeMs) ||
      isNaN(incoming.sourceEventTimeMs) ||
      incoming.sourceEventTimeMs < 0
    ) {
      return current;
    }
  }

  // 10. Forged reconnectAuthorized Flag Rejection (D2.1):
  // A caller-controlled boolean `reconnectAuthorized: true` on incoming is NOT a trusted authorization proof.
  // It is treated as an unauthorized forgery attempt and rejected if attempting to reconnect.
  if (incoming.reconnectAuthorized !== undefined && !authProof) {
    if (current.status === 'DISCONNECTED') {
      return current;
    }
  }

  // 11. Disconnected State Invariants & Independent Reconnection Authorization (D2.1):
  // In DISCONNECTED state, no field update or timestamp refresh is permitted unless an independent
  // Control Service authorization proof is provided, the epoch strictly advances, timestamp is valid,
  // and bridgeStatus is in the explicit active allowlist (UNKNOWN is rejected).
  const isCurrentlyDisconnected = current.status === 'DISCONNECTED';
  if (isCurrentlyDisconnected) {
    const isReconnectionAttempt = Boolean(incoming.status && incoming.status !== 'DISCONNECTED');
    if (!isReconnectionAttempt) {
      // Still disconnected or no status change: snapshot remains frozen, zero timestamp refresh
      return current;
    }

    const targetSource = incoming.source ?? current.source;
    const targetEpoch = incoming.epoch ?? current.epoch;

    // Independent authorization proof check:
    const isProofValid = Boolean(
      authProof &&
      authProof.authority === 'CONTROL_SERVICE_HANDSHAKE' &&
      typeof authProof.verify === 'function' &&
      authProof.verify(targetSource, targetEpoch)
    );

    const hasAdvancingEpoch = Boolean(
      incoming.epoch !== undefined &&
      Number.isSafeInteger(incoming.epoch) &&
      incoming.epoch > current.epoch
    );

    const hasValidObservationTimestamp = Boolean(
      incoming.freshnessTimestamp !== undefined &&
      typeof incoming.freshnessTimestamp === 'number' &&
      Number.isFinite(incoming.freshnessTimestamp) &&
      !isNaN(incoming.freshnessTimestamp) &&
      incoming.freshnessTimestamp > 0
    );

    // Explicit bridge-status allowlist: UNKNOWN, DISCONNECTED, or unallowlisted values must NOT count as active!
    const hasActiveBridge = Boolean(
      incoming.bridgeStatus !== undefined &&
      VALID_ACTIVE_BRIDGE_STATUSES.has(incoming.bridgeStatus)
    );

    const isAuthorizedReconnect =
      isProofValid &&
      hasAdvancingEpoch &&
      hasValidObservationTimestamp &&
      hasActiveBridge;

    if (!isAuthorizedReconnect) {
      // Reconnection rejected fail-closed: preserve accepted snapshot untouched!
      return current;
    }
  }

  // --- All validations passed: Apply atomic update ---
  const finalEpoch = incoming.epoch ?? current.epoch;
  const staleThreshold = incoming.staleThresholdMs ?? current.staleThresholdMs;
  const timestamp = incoming.freshnessTimestamp ?? current.freshnessTimestamp;
  const finalStatus: TelemetryStatus = incoming.status ?? current.status;
  const receiveTime = Date.now();
  const eventTime =
    incoming.sourceEventTimeMs ??
    incoming.freshnessTimestamp ??
    current.sourceEventTimeMs ??
    timestamp;

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
