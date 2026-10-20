/**
 * FRACTAL-FLOW Control Surface — Canonical Contracts & Safety Invariants
 * Governed by Universal Forensic Engineering Protocol (Survival > Correctness > Authority Integrity)
 */

export type ApplicationMode = 
  | 'SIMULATION_SANDBOX'      // Local off-broker deterministic sandbox (safe for demonstration)
  | 'DISCONNECTED'            // Offline state, all network and mutation controls disabled
  | 'READ_ONLY_CONNECTED'     // Telemetry observation only, no mutation authority
  | 'LIVE_OPERATIONAL';       // Broker-connected (STRICTLY BLOCKED until backend Control Service exists)

export type AuthorityRole = 'VIEWER' | 'OPERATOR' | 'ADMIN';

export type TelemetrySource = 
  | 'SIM_ENGINE' 
  | 'BROKER_FEED' 
  | 'CONTROL_SERVICE' 
  | 'FALLBACK_FIXTURE';

export type TelemetryStatus = 
  | 'HEALTHY' 
  | 'STALE' 
  | 'DEGRADED' 
  | 'DISCONNECTED' 
  | 'UNKNOWN';

export interface TelemetryProvenance {
  source: TelemetrySource;
  status: TelemetryStatus;
  freshnessTimestamp: number; // Unix epoch ms
  isAuthoritative: boolean;
  staleThresholdMs: number;    // Default: 5000ms
  epoch: number;
  bridgeStatus: string;
  fenceStatus: string;
}

export type CommandLifecycle = 
  | 'INTENT_PREPARED'
  | 'PENDING_AUTHORIZATION'
  | 'ACCEPTED_BY_GATEWAY'
  | 'DISPATCHED_TO_BROKER'
  | 'CONFIRMED'
  | 'REJECTED'
  | 'UNKNOWN_PENDING_RECONCILIATION';

export interface IntentFingerprint {
  intentId: string;
  operatorId: string;
  targetPositionId: string;
  symbol: string;
  actionType: 'CLOSE' | 'TIGHTEN_STOP' | 'MOVE_TO_BREAKEVEN' | 'KILL_SWITCH';
  parameters: Record<string, unknown>;
  idempotencyKey: string;
  createdAt: number;
}

export interface CommandResult {
  intentId: string;
  idempotencyKey: string;
  status: CommandLifecycle;
  authoritative: boolean;
  message: string;
  timestamp: number;
  rejectionReason?: string;
}

export class LiveExecutionBlockedError extends Error {
  constructor(message = 'LIVE_EXECUTION_BLOCKED: Backend Control Service and authoritative ExecutionGateway are not provisioned. Live orders are strictly prohibited.') {
    super(message);
    this.name = 'LiveExecutionBlockedError';
  }
}
