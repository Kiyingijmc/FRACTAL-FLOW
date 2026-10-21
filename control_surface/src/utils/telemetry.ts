import { TelemetryProvenance, TelemetryStatus } from '../types/contracts';

export interface TelemetryEvaluation {
  status: TelemetryStatus;
  isStale: boolean;
  ageMs: number;
  reason?: string;
}

/**
 * Production Telemetry Freshness & Provenance Evaluator
 * 
 * Invariants:
 * 1. An age >= staleThresholdMs evaluates strictly to STALE.
 * 2. Missing, non-positive, or NaN timestamps evaluate to UNKNOWN or DEGRADED.
 * 3. Non-positive, non-finite, or invalid staleThresholdMs evaluates to DEGRADED (never false HEALTHY) (SC-06).
 * 4. Sources in DISCONNECTED state cannot be promoted to HEALTHY by age alone.
 * 5. UI timers MUST NOT synthesize fresh timestamps without a genuine provider event.
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

  if (typeof freshnessTimestamp !== 'number' || isNaN(freshnessTimestamp) || freshnessTimestamp <= 0) {
    return {
      status: 'UNKNOWN',
      isStale: true,
      ageMs: Infinity,
      reason: 'Invalid or missing freshness timestamp'
    };
  }

  // SC-06: Treat non-positive, non-finite, or invalid staleThresholdMs strictly as DEGRADED (never false HEALTHY)
  if (typeof staleThresholdMs !== 'number' || !Number.isFinite(staleThresholdMs) || staleThresholdMs <= 0) {
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
 * SC-05: Safe telemetry state updater.
 * Prevents clobbering source identity or clearing DISCONNECTED state without a verifiable epoch advance.
 */
export function updateTelemetryState(
  current: TelemetryProvenance,
  incoming: Partial<TelemetryProvenance>
): TelemetryProvenance {
  // If current is DISCONNECTED and incoming does not advance epoch, preserve DISCONNECTED
  let finalStatus = incoming.status ?? current.status;
  if (current.status === 'DISCONNECTED' && incoming.status && incoming.status !== 'DISCONNECTED') {
    if (!incoming.epoch || incoming.epoch <= current.epoch) {
      finalStatus = 'DISCONNECTED';
    }
  }

  // Preserve source provenance unless explicitly updated with a valid non-empty string
  const source = incoming.source && incoming.source.trim().length > 0 ? incoming.source : current.source;

  return {
    ...current,
    ...incoming,
    source,
    status: finalStatus,
  };
}
