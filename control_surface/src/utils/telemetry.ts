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
 * Stage D.2.2 / D.2.3: Reconnection Authority Boundary Scoping.
 *
 * Primary defect remediation:
 * A caller-supplied object with authority: 'CONTROL_SERVICE_HANDSHAKE', a token,
 * or a caller-provided verify() callback returning true is NOT proof of Control Service
 * authentication. The caller can construct its own callback and claim that its credentials are valid.
 *
 * Genuine trust boundary analysis:
 * Inspection of the repository confirms zero trusted authentication mechanisms, zero cryptographic
 * verification keys or key-distribution mechanisms, zero trusted server adapters, and zero authenticated
 * Control Service handshake protocols.
 *
 * Fail-Closed Policy:
 * Reconnection from DISCONNECTED is strictly fail-closed rejected. All attempts to reconnect
 * preserve the accepted snapshot 100% bit-for-bit.
 */
export const RECONNECT_AUTHORITY_BOUNDARY = {
  isSupported: false,
  status: 'BLOCKED — TRUSTED CONTROL SERVICE AUTHORITY NOT INTEGRATED' as const,
  reason: 'CONTROL_SERVICE_HANDSHAKE_PROTOCOL_UNRESOLVED' as const,
  policy: 'RECONNECTION_FROM_DISCONNECTED_STRICTLY_FAIL_CLOSED_REJECTED' as const,
  callerAuthorityAccepted: false
} as const;

/**
 * Canonical Documented Unknown Telemetry State.
 * Used when initial input is missing, malformed, or invalid.
 * Invariant: Does NOT silently synthesize 'SIM_ENGINE', epoch 1, or a healthy-looking state.
 * D2.3-A: sourceEventTimeMs is explicitly undefined (never fabricated).
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
  sourceEventTimeMs: undefined,
  localReceiveTimeMs: 0
});

/**
 * Stage D.2.2 / D.2.3: Typed Telemetry Rejection Reasons.
 * Diagnostic codes emitted when an incoming update or initial creation is rejected.
 * Diagnostic evaluation NEVER mutates protected accepted state.
 */
export type TelemetryRejectionReason =
  | 'MISSING_INITIAL_TELEMETRY'
  | 'MISSING_SOURCE'
  | 'UNRECOGNIZED_SOURCE'
  | 'MISSING_EPOCH'
  | 'MALFORMED_EPOCH'
  | 'EPOCH_REGRESSION'
  | 'MISSING_TIMESTAMP'
  | 'INVALID_TIMESTAMP'
  | 'STALE_TIMESTAMP'
  | 'INVALID_STALE_THRESHOLD'
  | 'INVALID_STATUS'
  | 'INVALID_SOURCE_EVENT_TIME'
  | 'CROSS_SOURCE_OVERWRITE_FORBIDDEN'
  | 'CROSS_SOURCE_MIGRATION_BLOCKED'
  | 'CALLER_RECONNECT_AUTHORITY_FORGERY'
  | 'DISCONNECTED_INACTIVE_BRIDGE_STATUS'
  | 'RECONNECTION_BLOCKED_UNRESOLVED_CONTROL_SERVICE_AUTHORITY';

export interface TelemetryUpdateDiagnostic {
  readonly accepted: boolean;
  readonly state: TelemetryProvenance;
  readonly rejectionReason?: TelemetryRejectionReason;
}

/**
 * Deprecated proof interface retained for hostile regression verification.
 * Any attempt by callers to supply an authorization proof is rejected fail-closed.
 */
export interface ReconnectAuthorizationProof {
  readonly authority: string;
  readonly token?: string;
  readonly issuedAt?: number;
  readonly nonce?: string;
  readonly verify?: (source: TelemetrySource, epoch: number) => boolean;
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
 * 2. Missing, non-positive, non-finite, or NaN timestamps evaluate to UNKNOWN.
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
      reason: 'No telemetry snapshot available'
    };
  }

  // Runtime threshold validation: threshold must be positive finite number
  if (
    typeof telemetry.staleThresholdMs !== 'number' ||
    !Number.isFinite(telemetry.staleThresholdMs) ||
    isNaN(telemetry.staleThresholdMs) ||
    telemetry.staleThresholdMs <= 0
  ) {
    return {
      status: 'DEGRADED',
      isStale: true,
      ageMs: Infinity,
      reason: 'Invalid or non-positive staleThresholdMs'
    };
  }

  // Runtime timestamp validation: missing, non-positive, or non-finite timestamp
  if (
    typeof telemetry.freshnessTimestamp !== 'number' ||
    !Number.isFinite(telemetry.freshnessTimestamp) ||
    isNaN(telemetry.freshnessTimestamp) ||
    telemetry.freshnessTimestamp <= 0
  ) {
    return {
      status: 'UNKNOWN',
      isStale: true,
      ageMs: Infinity,
      reason: 'Missing or non-finite freshness timestamp'
    };
  }

  // Disconnected state invariant: cannot be promoted to HEALTHY by age alone
  if (telemetry.status === 'DISCONNECTED') {
    const age = Math.max(0, currentTimeMs - telemetry.freshnessTimestamp);
    return {
      status: 'DISCONNECTED',
      isStale: true,
      ageMs: age,
      reason: 'Telemetry stream is in DISCONNECTED state'
    };
  }

  const ageMs = currentTimeMs - telemetry.freshnessTimestamp;

  // Clock skew: observation timestamp in future
  if (ageMs < -1000) {
    return {
      status: 'DEGRADED',
      isStale: false,
      ageMs,
      reason: 'Observation timestamp is in the future (clock skew)'
    };
  }

  const effectiveAge = Math.max(0, ageMs);

  if (effectiveAge >= telemetry.staleThresholdMs) {
    return {
      status: 'STALE',
      isStale: true,
      ageMs: effectiveAge,
      reason: `Heartbeat age ${effectiveAge}ms exceeds stale threshold ${telemetry.staleThresholdMs}ms`
    };
  }

  return {
    status: telemetry.status,
    isStale: false,
    ageMs: effectiveAge
  };
}

/**
 * Stage D.2.3: Single unified initial-state validator and constructor.
 * Ensures createInitialTelemetry() and tryUpdateTelemetryState(undefined, incoming)
 * share identical logic, preventing divergent diagnostic reporting.
 *
 * Strict Initial Contract:
 * - D2.3-A: Absent sourceEventTimeMs remains undefined. Never defaults to freshnessTimestamp.
 * - D2.3-B: Returns accurate typed rejection reasons (MISSING_SOURCE, UNRECOGNIZED_SOURCE,
 *   MISSING_EPOCH, MALFORMED_EPOCH, MISSING_TIMESTAMP, INVALID_TIMESTAMP, INVALID_STALE_THRESHOLD,
 *   INVALID_STATUS, INVALID_SOURCE_EVENT_TIME).
 * - D2.3-C: Absent initial status fails safely to 'UNKNOWN', never silently promoted to 'HEALTHY'.
 */
export function evaluateInitialTelemetry(
  incoming?: TelemetryUpdateOptions
): TelemetryUpdateDiagnostic {
  if (!incoming) {
    return {
      accepted: false,
      state: DOCUMENTED_UNKNOWN_TELEMETRY,
      rejectionReason: 'MISSING_INITIAL_TELEMETRY'
    };
  }

  // 1. Source validation (D2.3-F01 / Stage D.2.3.1):
  // Required: undefined, null, empty string, or whitespace-only evaluates strictly to MISSING_SOURCE.
  const rawSource = incoming.source;
  if (
    rawSource === undefined ||
    rawSource === null ||
    (typeof rawSource === 'string' && rawSource.trim() === '')
  ) {
    return {
      accepted: false,
      state: DOCUMENTED_UNKNOWN_TELEMETRY,
      rejectionReason: 'MISSING_SOURCE'
    };
  }

  // Non-empty unrecognized source, or malformed non-string runtime value:
  // Evaluates to UNRECOGNIZED_SOURCE fail-closed without throwing, coercing, or trimming.
  if (typeof rawSource !== 'string' || !VALID_SOURCES.has(rawSource as TelemetrySource)) {
    return {
      accepted: false,
      state: DOCUMENTED_UNKNOWN_TELEMETRY,
      rejectionReason: 'UNRECOGNIZED_SOURCE'
    };
  }

  // 2. Epoch validation: required; must be positive safe integer
  if (incoming.epoch === undefined) {
    return {
      accepted: false,
      state: DOCUMENTED_UNKNOWN_TELEMETRY,
      rejectionReason: 'MISSING_EPOCH'
    };
  }
  if (!Number.isSafeInteger(incoming.epoch) || incoming.epoch <= 0) {
    return {
      accepted: false,
      state: DOCUMENTED_UNKNOWN_TELEMETRY,
      rejectionReason: 'MALFORMED_EPOCH'
    };
  }

  // 3. Timestamp validation: required; must be positive finite number
  if (incoming.freshnessTimestamp === undefined) {
    return {
      accepted: false,
      state: DOCUMENTED_UNKNOWN_TELEMETRY,
      rejectionReason: 'MISSING_TIMESTAMP'
    };
  }
  if (
    typeof incoming.freshnessTimestamp !== 'number' ||
    !Number.isFinite(incoming.freshnessTimestamp) ||
    isNaN(incoming.freshnessTimestamp) ||
    incoming.freshnessTimestamp <= 0
  ) {
    return {
      accepted: false,
      state: DOCUMENTED_UNKNOWN_TELEMETRY,
      rejectionReason: 'INVALID_TIMESTAMP'
    };
  }

  // 4. Stale threshold validation: defaults to 5000 only when genuinely undefined
  if (incoming.staleThresholdMs !== undefined) {
    if (
      typeof incoming.staleThresholdMs !== 'number' ||
      !Number.isFinite(incoming.staleThresholdMs) ||
      isNaN(incoming.staleThresholdMs) ||
      incoming.staleThresholdMs <= 0
    ) {
      return {
        accepted: false,
        state: DOCUMENTED_UNKNOWN_TELEMETRY,
        rejectionReason: 'INVALID_STALE_THRESHOLD'
      };
    }
  }

  // 5. Status validation: must be in VALID_STATUSES if provided
  if (incoming.status !== undefined && !VALID_STATUSES.has(incoming.status)) {
    return {
      accepted: false,
      state: DOCUMENTED_UNKNOWN_TELEMETRY,
      rejectionReason: 'INVALID_STATUS'
    };
  }

  // 6. Source event time validation: must be finite and non-negative if provided
  if (incoming.sourceEventTimeMs !== undefined) {
    if (
      typeof incoming.sourceEventTimeMs !== 'number' ||
      !Number.isFinite(incoming.sourceEventTimeMs) ||
      isNaN(incoming.sourceEventTimeMs) ||
      incoming.sourceEventTimeMs < 0
    ) {
      return {
        accepted: false,
        state: DOCUMENTED_UNKNOWN_TELEMETRY,
        rejectionReason: 'INVALID_SOURCE_EVENT_TIME'
      };
    }
  }

  // All initial validations passed: construct truthful initial snapshot
  const source: TelemetrySource = rawSource as TelemetrySource;
  const epoch: number = incoming.epoch;
  const freshnessTimestamp: number = incoming.freshnessTimestamp;
  const staleThresholdMs: number =
    incoming.staleThresholdMs === undefined ? 5000 : incoming.staleThresholdMs;

  // D2.3-C: Absent initial status fails safely to 'UNKNOWN', never silently promoted to 'HEALTHY'
  const status: TelemetryStatus = incoming.status ?? 'UNKNOWN';
  const receiveTime = Date.now();

  // D2.3-A: Absent sourceEventTimeMs remains undefined; never fabricated from freshnessTimestamp
  const sourceEventTime = incoming.sourceEventTimeMs;

  return {
    accepted: true,
    state: {
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
    }
  };
}

/**
 * Stage D.2.3: Safe initial telemetry constructor.
 * Delegates directly to evaluateInitialTelemetry to guarantee identical contracts.
 */
export function createInitialTelemetry(
  incoming?: TelemetryUpdateOptions
): TelemetryProvenance {
  return evaluateInitialTelemetry(incoming).state;
}

/**
 * Stage D.2.3: Strict Telemetry Transition Table Implementation & Diagnostic Evaluator.
 *
 * Transition Policy:
 * 1. Initial valid: Valid source, epoch, timestamp -> accepted initial state.
 * 2. Initial missing observation: Missing timestamp -> DOCUMENTED_UNKNOWN_TELEMETRY (MISSING_TIMESTAMP).
 * 3. Initial malformed: Bad source, epoch, threshold, or status -> accurate typed rejection reasons.
 * 4. Same-source valid update: Monotonic epoch, valid timestamp, same source -> accepted updated state.
 * 5. Stale / regressing epoch: incoming.epoch < current.epoch -> rejected fail-closed, snapshot preserved.
 * 6. Malformed update with mixed fields: Any invalid field -> rejected atomically, snapshot preserved.
 * 7. DISCONNECTED state update: No status change -> rejected fail-closed, frozen timestamp preserved.
 * 8. Reconnection with forged boolean or caller proof: -> rejected fail-closed, snapshot preserved.
 * 9. Reconnection with UNKNOWN or unallowlisted bridge: -> rejected fail-closed, snapshot preserved.
 * 10. Cross-source migration: Different source in either direction -> rejected fail-closed.
 * 11. Session reset: -> DOCUMENTED_UNKNOWN_TELEMETRY until authentic stream established.
 * 12. Authenticated reconnection: -> BLOCKED fail-closed (Control Service authority unresolved).
 */
export function tryUpdateTelemetryState(
  current: TelemetryProvenance | undefined,
  incoming: TelemetryUpdateOptions,
  deprecatedProof?: unknown
): TelemetryUpdateDiagnostic {
  // Case 1: Initial state construction
  if (!current) {
    return evaluateInitialTelemetry(incoming);
  }

  // Rejection check: Any attempt to supply a caller authorization proof is rejected as untrusted
  if (deprecatedProof !== undefined) {
    return {
      accepted: false,
      state: current,
      rejectionReason: 'CALLER_RECONNECT_AUTHORITY_FORGERY'
    };
  }

  // 1. Cross-Source Overwrite Protection (SC-01.1):
  // Simulation tick (SIM_ENGINE) CANNOT touch or overwrite external broker state!
  if (incoming.source === 'SIM_ENGINE' && current.source !== 'SIM_ENGINE') {
    return {
      accepted: false,
      state: current,
      rejectionReason: 'CROSS_SOURCE_OVERWRITE_FORBIDDEN'
    };
  }

  // 2. Cross-Source Migration Protection (Fail-Closed) (D2-A Risk 2 / SC-01.11):
  // Caller-controlled flags (e.g. allowSourceMigration: true) are REJECTED.
  if (incoming.source !== undefined && incoming.source !== current.source) {
    return {
      accepted: false,
      state: current,
      rejectionReason: 'CROSS_SOURCE_MIGRATION_BLOCKED'
    };
  }

  // 3. Source Identifier Validity:
  if (incoming.source !== undefined && !VALID_SOURCES.has(incoming.source)) {
    return {
      accepted: false,
      state: current,
      rejectionReason: 'UNRECOGNIZED_SOURCE'
    };
  }

  // 4. Epoch Validation (All-or-Nothing Atomicity):
  if (incoming.epoch !== undefined) {
    if (!Number.isSafeInteger(incoming.epoch) || incoming.epoch <= 0) {
      return {
        accepted: false,
        state: current,
        rejectionReason: 'MALFORMED_EPOCH'
      };
    }
    if (incoming.epoch < current.epoch) {
      return {
        accepted: false,
        state: current,
        rejectionReason: 'EPOCH_REGRESSION'
      };
    }
  }

  // 5. Stale / Out-of-Order Timestamp Protection:
  if (
    typeof incoming.freshnessTimestamp === 'number' &&
    incoming.freshnessTimestamp < current.freshnessTimestamp
  ) {
    return {
      accepted: false,
      state: current,
      rejectionReason: 'STALE_TIMESTAMP'
    };
  }

  // 6. Runtime Timestamp Validity (All-or-Nothing Atomicity):
  if (incoming.freshnessTimestamp !== undefined) {
    if (
      typeof incoming.freshnessTimestamp !== 'number' ||
      !Number.isFinite(incoming.freshnessTimestamp) ||
      isNaN(incoming.freshnessTimestamp) ||
      incoming.freshnessTimestamp <= 0
    ) {
      return {
        accepted: false,
        state: current,
        rejectionReason: 'INVALID_TIMESTAMP'
      };
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
      return {
        accepted: false,
        state: current,
        rejectionReason: 'INVALID_STALE_THRESHOLD'
      };
    }
  }

  // 8. Runtime Status Validity:
  if (incoming.status !== undefined && !VALID_STATUSES.has(incoming.status)) {
    return {
      accepted: false,
      state: current,
      rejectionReason: 'INVALID_STATUS'
    };
  }

  // 9. Source Event Timestamp Validity (D2.3-A):
  if (incoming.sourceEventTimeMs !== undefined) {
    if (
      typeof incoming.sourceEventTimeMs !== 'number' ||
      !Number.isFinite(incoming.sourceEventTimeMs) ||
      isNaN(incoming.sourceEventTimeMs) ||
      incoming.sourceEventTimeMs < 0
    ) {
      return {
        accepted: false,
        state: current,
        rejectionReason: 'INVALID_SOURCE_EVENT_TIME'
      };
    }
  }

  // 10. Forged reconnectAuthorized Flag Rejection:
  // A caller-controlled boolean `reconnectAuthorized: true` on incoming is NOT a trusted authorization proof.
  if (incoming.reconnectAuthorized !== undefined) {
    return {
      accepted: false,
      state: current,
      rejectionReason: 'CALLER_RECONNECT_AUTHORITY_FORGERY'
    };
  }

  // 11. Disconnected State Invariants & Fail-Closed Reconnection Gating:
  // In DISCONNECTED state, no field update or timestamp refresh is permitted.
  // Because no authenticated Control Service handshake exists, all reconnection attempts fail closed.
  const isCurrentlyDisconnected = current.status === 'DISCONNECTED';
  if (isCurrentlyDisconnected) {
    const isReconnectionAttempt = Boolean(incoming.status && incoming.status !== 'DISCONNECTED');
    if (!isReconnectionAttempt) {
      // Still disconnected or no status change: snapshot remains frozen, zero timestamp refresh
      return {
        accepted: false,
        state: current,
        rejectionReason: 'RECONNECTION_BLOCKED_UNRESOLVED_CONTROL_SERVICE_AUTHORITY'
      };
    }

    // Bridge status check: UNKNOWN and DISCONNECTED are strictly rejected
    const hasActiveBridge = Boolean(
      incoming.bridgeStatus !== undefined &&
      VALID_ACTIVE_BRIDGE_STATUSES.has(incoming.bridgeStatus)
    );

    if (!hasActiveBridge) {
      return {
        accepted: false,
        state: current,
        rejectionReason: 'DISCONNECTED_INACTIVE_BRIDGE_STATUS'
      };
    }

    // In the absence of trusted Control Service authority integration, reconnection is BLOCKED
    return {
      accepted: false,
      state: current,
      rejectionReason: 'RECONNECTION_BLOCKED_UNRESOLVED_CONTROL_SERVICE_AUTHORITY'
    };
  }

  // --- All validations passed: Apply atomic update ---
  const finalEpoch = incoming.epoch ?? current.epoch;
  const staleThreshold = incoming.staleThresholdMs ?? current.staleThresholdMs;
  const timestamp = incoming.freshnessTimestamp ?? current.freshnessTimestamp;
  const finalStatus: TelemetryStatus = incoming.status ?? current.status;
  const receiveTime = Date.now();

  // D2.3-A: If incoming.sourceEventTimeMs is provided, update it; otherwise preserve current.sourceEventTimeMs
  // Never synthesize or default sourceEventTimeMs to freshnessTimestamp or receiveTime
  const eventTime =
    incoming.sourceEventTimeMs !== undefined
      ? incoming.sourceEventTimeMs
      : current.sourceEventTimeMs;

  return {
    accepted: true,
    state: {
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
    }
  };
}

/**
 * SC-01 / D2-A / D2.1 / D.2.2 / D.2.3: Safe telemetry state updater enforcing source provenance,
 * all-or-nothing atomicity, and fail-closed reconnection authorization.
 *
 * On any rejected update, returns the accepted snapshot `current` 100% bit-for-bit untouched.
 */
export function updateTelemetryState(
  current: TelemetryProvenance | undefined,
  incoming: TelemetryUpdateOptions,
  deprecatedProof?: unknown
): TelemetryProvenance {
  return tryUpdateTelemetryState(current, incoming, deprecatedProof).state;
}
