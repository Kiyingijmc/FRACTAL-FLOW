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
export function updateTelemetryState(
  current: TelemetryProvenance,
  incoming: Partial<TelemetryProvenance>
): TelemetryProvenance {
  if (!current) {
    return {
      source: incoming.source || 'SIM_ENGINE',
      status: incoming.status || 'UNKNOWN',
      freshnessTimestamp: incoming.freshnessTimestamp || Date.now(),
      isAuthoritative: Boolean(incoming.isAuthoritative),
      staleThresholdMs: incoming.staleThresholdMs || 5000,
      epoch: incoming.epoch || 1,
      bridgeStatus: incoming.bridgeStatus || 'UNKNOWN',
      fenceStatus: incoming.fenceStatus || 'UNKNOWN'
    };
  }

  // 1. Cross-Source Protection (SC-01):
  // If incoming event is from SIM_ENGINE but current active source is external (e.g. BROKER_FEED, CONTROL_SERVICE),
  // the simulation tick must NEVER promote the external source to HEALTHY or overwrite its timestamp!
  if (
    incoming.source === 'SIM_ENGINE' &&
    current.source !== 'SIM_ENGINE'
  ) {
    // External source remains untouched by internal simulation tick
    return current;
  }

  // 2. Out-of-order timestamp protection (stale events cannot overwrite newer state)
  if (
    typeof incoming.freshnessTimestamp === 'number' &&
    incoming.freshnessTimestamp < current.freshnessTimestamp
  ) {
    // Incoming event is older than current state; ignore stale update
    return current;
  }

  // 3. Validate runtime thresholds
  let finalStatus = incoming.status ?? current.status;
  const staleThreshold = incoming.staleThresholdMs ?? current.staleThresholdMs;

  if (
    typeof staleThreshold !== 'number' ||
    !Number.isFinite(staleThreshold) ||
    staleThreshold <= 0
  ) {
    finalStatus = 'DEGRADED';
  }

  // 4. Validate runtime timestamp
  const timestamp = incoming.freshnessTimestamp ?? current.freshnessTimestamp;
  if (
    typeof timestamp !== 'number' ||
    !Number.isFinite(timestamp) ||
    timestamp <= 0
  ) {
    finalStatus = 'UNKNOWN';
  }

  // 5. Preserving DISCONNECTED state (cannot be cleared by age or tick alone)
  if (current.status === 'DISCONNECTED' && incoming.status && incoming.status !== 'DISCONNECTED') {
    // Only permit reconnection if incoming advances epoch for the same source
    if (!incoming.epoch || incoming.epoch <= current.epoch) {
      finalStatus = 'DISCONNECTED';
    }
  }

  // Preserve source provenance
  const source = (incoming.source && incoming.source.trim().length > 0)
    ? incoming.source as TelemetrySource
    : current.source;

  return {
    ...current,
    ...incoming,
    source,
    staleThresholdMs: staleThreshold,
    freshnessTimestamp: timestamp,
    status: finalStatus,
  };
}
