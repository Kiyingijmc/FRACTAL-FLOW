import { IDataProvider, ICommandProvider } from './interfaces';
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
 * Self-contained, deterministic simulation provider for off-broker operator testing.
 * 
 * INVARIANTS:
 * 1. NEVER initiates network connections to live brokers or external servers.
 * 2. ALL returned data is explicitly tagged with `isAuthoritative: false` and `source: 'SIM_ENGINE'`.
 * 3. Commands only modify the isolated local sandbox state and emit non-authoritative audit lines.
 */
export class SimulationProvider implements IDataProvider, ICommandProvider {
  readonly isLiveAuthorized = false;

  private positions: Position[];
  private pendingOrders: PendingOrder[];
  private candidates: GateCandidate[];
  private systemEvents: SystemEvent[];
  private closedTrades: ClosedTrade[];
  private epoch = 418;
  private lastTelemetryTime = Date.now();

  constructor() {
    // Deep clone initial fixtures into isolated sandbox memory
    this.positions = JSON.parse(JSON.stringify(INITIAL_POSITIONS));
    this.pendingOrders = JSON.parse(JSON.stringify(INITIAL_PENDING_ORDERS));
    this.candidates = JSON.parse(JSON.stringify(GATE_CANDIDATES));
    this.systemEvents = JSON.parse(JSON.stringify(INITIAL_SYSTEM_EVENTS));
    this.closedTrades = JSON.parse(JSON.stringify(INITIAL_CLOSED_TRADES));
  }

  async getHealth(): Promise<TelemetryProvenance> {
    this.lastTelemetryTime = Date.now();
    return {
      source: 'SIM_ENGINE',
      status: 'HEALTHY',
      freshnessTimestamp: this.lastTelemetryTime,
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

  subscribeTicks(callback: (symbol: string, tick: { bid: number; ask: number; timestamp: number }) => void): () => void {
    const symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD'];
    const timer = setInterval(() => {
      const sym = symbols[Math.floor(Math.random() * symbols.length)];
      const jitter = (Math.random() - 0.5) * 0.0004;
      const basePrice = sym === 'USDJPY' ? 154.20 : 1.0850;
      const current = +(basePrice + jitter).toFixed(sym === 'USDJPY' ? 3 : 5);
      callback(sym, {
        bid: current,
        ask: +(current + 0.00015).toFixed(sym === 'USDJPY' ? 3 : 5),
        timestamp: Date.now()
      });
    }, 2500);

    return () => clearInterval(timer);
  }

  async submitCommand(intent: IntentFingerprint): Promise<CommandResult> {
    const targetIdx = this.positions.findIndex(p => p.id === intent.targetPositionId);
    
    if (targetIdx === -1 && intent.actionType !== 'KILL_SWITCH') {
      return {
        intentId: intent.intentId,
        idempotencyKey: intent.idempotencyKey,
        status: 'REJECTED',
        authoritative: false,
        message: `Target position ${intent.targetPositionId} not found in sandbox`,
        timestamp: Date.now(),
        rejectionReason: 'POSITION_NOT_FOUND'
      };
    }

    if (intent.actionType === 'CLOSE') {
      if (targetIdx >= 0) {
        this.positions.splice(targetIdx, 1);
      }
    } else if (intent.actionType === 'MOVE_TO_BREAKEVEN') {
      if (targetIdx >= 0) {
        const pos = this.positions[targetIdx];
        pos.breakevenStatus = 'confirmed @ BE (sim)';
      }
    } else if (intent.actionType === 'TIGHTEN_STOP') {
      if (targetIdx >= 0) {
        const pos = this.positions[targetIdx];
        pos.trailDistance = 'tightened 2.0σ (sim)';
      }
    }

    // Record audit line in simulated events
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

    return {
      intentId: intent.intentId,
      idempotencyKey: intent.idempotencyKey,
      status: 'CONFIRMED',
      authoritative: false,
      message: `Simulated sandbox execution completed for ${intent.actionType}`,
      timestamp: Date.now()
    };
  }

  async reconcileCommand(intentId: string): Promise<CommandResult> {
    return {
      intentId,
      idempotencyKey: `sim_${intentId}`,
      status: 'CONFIRMED',
      authoritative: false,
      message: 'Simulated intent is reconciled against local sandbox memory',
      timestamp: Date.now()
    };
  }
}
