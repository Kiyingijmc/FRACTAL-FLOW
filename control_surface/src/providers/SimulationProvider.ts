import { 
  IDataProvider, 
  ICommandProvider, 
  CommandProgressUpdate 
} from './interfaces';
import { 
  TelemetryProvenance, 
  IntentFingerprint, 
  CommandResult 
} from '../types/contracts';
import { 
  Position, 
  GateCandidate, 
  SystemEvent, 
  ClosedTrade,
  PendingOrder 
} from '../types';
import { 
  INITIAL_POSITIONS, 
  GATE_CANDIDATES, 
  INITIAL_SYSTEM_EVENTS, 
  INITIAL_CLOSED_TRADES,
  INITIAL_PENDING_ORDERS 
} from '../data/mockData';

/**
 * SimulationProvider
 * 
 * Boundary-isolated, deterministic simulation provider for off-broker operator interaction.
 * 
 * Safety Invariants:
 * 1. NEVER initiates network connections to live brokers, sockets, or external servers.
 * 2. ALL returned data and progress updates are explicitly tagged with `authoritative: false` and `source: 'SIM_ENGINE'`.
 * 3. Market tick simulation and command progression are owned entirely within this provider boundary.
 * 4. State mutations are isolated strictly to local sandbox memory.
 * 5. SC-07: Validates reconciliation against recorded simulated intents; strictly rejects unknown intent IDs.
 */
export class SimulationProvider implements IDataProvider, ICommandProvider {
  readonly isLiveAuthorized = false;

  private positions: Position[];
  private pendingOrders: PendingOrder[];
  private candidates: GateCandidate[];
  private systemEvents: SystemEvent[];
  private closedTrades: ClosedTrade[];
  private epoch = 418;
  private lastHeartbeatTime = Date.now();
  private isPaused = false;
  // SC-07: Track recorded simulated intents in local memory
  private simulatedIntents = new Map<string, CommandResult>();

  constructor() {
    this.positions = JSON.parse(JSON.stringify(INITIAL_POSITIONS));
    this.pendingOrders = JSON.parse(JSON.stringify(INITIAL_PENDING_ORDERS));
    this.candidates = JSON.parse(JSON.stringify(GATE_CANDIDATES));
    this.systemEvents = JSON.parse(JSON.stringify(INITIAL_SYSTEM_EVENTS));
    this.closedTrades = JSON.parse(JSON.stringify(INITIAL_CLOSED_TRADES));
  }

  setPaused(paused: boolean): void {
    this.isPaused = paused;
  }

  getPaused(): boolean {
    return this.isPaused;
  }

  async getHealth(): Promise<TelemetryProvenance> {
    this.lastHeartbeatTime = Date.now();
    return {
      source: 'SIM_ENGINE',
      status: 'HEALTHY',
      freshnessTimestamp: this.lastHeartbeatTime,
      isAuthoritative: false,
      staleThresholdMs: 5000,
      epoch: this.epoch,
      bridgeStatus: 'SIM_SANDBOX_VIRTUAL',
      fenceStatus: 'SIM_FENCE_ENFORCED'
    };
  }

  async getPositions(): Promise<Position[]> {
    return JSON.parse(JSON.stringify(this.positions));
  }

  async getPendingOrders(): Promise<PendingOrder[]> {
    return JSON.parse(JSON.stringify(this.pendingOrders));
  }

  async getCandidates(): Promise<GateCandidate[]> {
    return JSON.parse(JSON.stringify(this.candidates));
  }

  async getSystemEvents(): Promise<SystemEvent[]> {
    return JSON.parse(JSON.stringify(this.systemEvents));
  }

  async getClosedTrades(): Promise<ClosedTrade[]> {
    return JSON.parse(JSON.stringify(this.closedTrades));
  }

  /**
   * Owns market tick generation and internal sandbox position price updates.
   */
  subscribeTicks(
    callback: (symbol: string, tick: { bid: number; ask: number; timestamp: number }, updatedPositions: Position[]) => void
  ): () => void {
    const timer = setInterval(() => {
      if (this.isPaused || this.positions.length === 0) return;

      const targetIndex = Math.floor(Math.random() * this.positions.length);
      const target = this.positions[targetIndex];
      const isTickUp = Math.random() > 0.48;
      const tickStep = target.priceDecimals === 3 ? 0.008 : 0.00004;
      const delta = isTickUp ? tickStep : -tickStep;

      const newPrice = Number((target.currentPrice + delta).toFixed(target.priceDecimals));
      const rDelta = (isTickUp ? 1 : -1) * (target.side === 'LONG' ? 0.02 : -0.02);
      const newUnrealizedR = Number((target.unrealizedR + rDelta).toFixed(2));

      target.currentPrice = newPrice;
      target.unrealizedR = newUnrealizedR;
      this.lastHeartbeatTime = Date.now();

      callback(
        target.symbol,
        {
          bid: newPrice,
          ask: Number((newPrice + (target.priceDecimals === 3 ? 0.015 : 0.00015)).toFixed(target.priceDecimals)),
          timestamp: this.lastHeartbeatTime
        },
        JSON.parse(JSON.stringify(this.positions))
      );
    }, 2000);

    return () => clearInterval(timer);
  }

  /**
   * Owns simulated command execution and asynchronous step progression.
   */
  async submitCommand(
    intent: IntentFingerprint,
    onProgress?: (progress: CommandProgressUpdate) => void
  ): Promise<CommandResult> {
    const targetIdx = this.positions.findIndex(p => p.id === intent.targetPositionId);

    // Initial simulation progression step: ACCEPTED_BY_GATEWAY
    if (onProgress) {
      onProgress({
        status: 'ACCEPTED_BY_GATEWAY',
        details: '[SANDBOX] In-memory validation passed (authoritative: false)',
        timestamp: Date.now(),
        authoritative: false
      });
      // Small simulated tick delay
      await new Promise(res => setTimeout(res, 80));
    }

    // Check rejection simulation
    const simulateRejection = Boolean(intent.parameters?.simulateRejection);
    if (simulateRejection) {
      if (onProgress) {
        onProgress({
          status: 'REJECTED',
          details: 'Sandbox REJECTED: Simulated constraint invariant failure',
          timestamp: Date.now(),
          authoritative: false
        });
      }
      const rejectionResult: CommandResult = {
        intentId: intent.intentId,
        idempotencyKey: intent.idempotencyKey,
        status: 'REJECTED',
        authoritative: false,
        message: 'Sandbox REJECTED: Invariant constraint check failed (simulated)',
        timestamp: Date.now(),
        rejectionReason: 'SIMULATED_CONSTRAINT_FAILURE'
      };
      this.simulatedIntents.set(intent.intentId, rejectionResult);
      return rejectionResult;
    }

    if (targetIdx === -1 && intent.actionType !== 'KILL_SWITCH') {
      if (onProgress) {
        onProgress({
          status: 'REJECTED',
          details: `Target position ${intent.targetPositionId} not found in sandbox`,
          timestamp: Date.now(),
          authoritative: false
        });
      }
      const notFoundResult: CommandResult = {
        intentId: intent.intentId,
        idempotencyKey: intent.idempotencyKey,
        status: 'REJECTED',
        authoritative: false,
        message: `Target position ${intent.targetPositionId} not found in sandbox`,
        timestamp: Date.now(),
        rejectionReason: 'POSITION_NOT_FOUND'
      };
      this.simulatedIntents.set(intent.intentId, notFoundResult);
      return notFoundResult;
    }

    // Second simulation progression step: DISPATCHED_TO_BROKER (simulated virtual broker)
    if (onProgress) {
      onProgress({
        status: 'DISPATCHED_TO_BROKER',
        details: '[SANDBOX] Dispatched to virtual matching engine (authoritative: false)',
        timestamp: Date.now(),
        authoritative: false
      });
      await new Promise(res => setTimeout(res, 120));
    }

    // Perform state mutation in local sandbox memory
    if (intent.actionType === 'CLOSE') {
      if (targetIdx >= 0) {
        this.positions.splice(targetIdx, 1);
      }
    } else if (intent.actionType === 'MOVE_TO_BREAKEVEN') {
      if (targetIdx >= 0) {
        this.positions[targetIdx].breakevenStatus = 'confirmed @ BE (sim)';
      }
    } else if (intent.actionType === 'TIGHTEN_STOP') {
      if (targetIdx >= 0) {
        this.positions[targetIdx].trailDistance = 'tightened 2.0σ (sim)';
      }
    } else if (intent.actionType === 'KILL_SWITCH') {
      this.positions = [];
    }

    // Record audit event in sandbox system events (SC-09: labeled SIMULATED / SESSION, never false PERSISTED)
    const auditEvent: SystemEvent = {
      id: `evt_sim_${Date.now()}`,
      eventId: `EVT-${Date.now().toString().slice(-4)}`,
      timestamp: new Date().toLocaleTimeString(),
      source: 'SIM_ENGINE',
      level: 'info',
      status: 'SIMULATED',
      message: `[SANDBOX] ${intent.actionType} applied for ${intent.symbol} (${intent.targetPositionId}) [key: ${intent.idempotencyKey.slice(0, 16)}...]`,
      isAuthoritative: false
    };
    this.systemEvents.unshift(auditEvent);

    const result: CommandResult = {
      intentId: intent.intentId,
      idempotencyKey: intent.idempotencyKey,
      status: 'CONFIRMED',
      authoritative: false,
      message: `Simulated sandbox execution completed for ${intent.actionType}`,
      timestamp: Date.now()
    };

    // SC-07: Record simulated intent
    this.simulatedIntents.set(intent.intentId, result);

    if (onProgress) {
      onProgress({
        status: 'CONFIRMED',
        details: `${result.message} (NON-BROKER)`,
        timestamp: Date.now(),
        authoritative: false
      });
    }

    return result;
  }

  /**
   * SC-04 / SC-07: Validates reconciliation against recorded intents.
   * Unknown or malformed intent IDs are strictly rejected; outcomes remain non-authoritative.
   */
  async reconcileCommand(intentId: string): Promise<CommandResult> {
    // Malformed ID guard
    if (typeof intentId !== 'string' || !intentId.trim() || !intentId.startsWith('intent_')) {
      return {
        intentId: String(intentId),
        idempotencyKey: `malformed_${intentId}`,
        status: 'REJECTED',
        authoritative: false,
        message: `Malformed intentId '${intentId}' cannot be reconciled`,
        timestamp: Date.now(),
        rejectionReason: 'MALFORMED_INTENT_ID'
      };
    }

    const recorded = this.simulatedIntents.get(intentId);
    if (!recorded) {
      return {
        intentId,
        idempotencyKey: `unknown_${intentId}`,
        status: 'REJECTED',
        authoritative: false,
        message: `Intent '${intentId}' not found in simulation memory`,
        timestamp: Date.now(),
        rejectionReason: 'INTENT_NOT_RECORDED'
      };
    }

    return {
      ...recorded,
      authoritative: false,
      message: `Reconciled simulated intent '${intentId}' against local sandbox memory`
    };
  }
}
