import { 
  TelemetryProvenance, 
  IntentFingerprint, 
  CommandResult 
} from '../types/contracts';
import { 
  Position, 
  GateCandidate, 
  SystemEvent, 
  ClosedTrade 
} from '../types';

export interface IDataProvider {
  getHealth(): Promise<TelemetryProvenance>;
  getPositions(): Promise<Position[]>;
  getCandidates(): Promise<GateCandidate[]>;
  getSystemEvents(): Promise<SystemEvent[]>;
  getClosedTrades(): Promise<ClosedTrade[]>;
  subscribeTicks(callback: (symbol: string, tick: { bid: number; ask: number; timestamp: number }) => void): () => void;
}

export interface ICommandProvider {
  readonly isLiveAuthorized: boolean;
  submitCommand(intent: IntentFingerprint): Promise<CommandResult>;
  reconcileCommand(intentId: string): Promise<CommandResult>;
}
