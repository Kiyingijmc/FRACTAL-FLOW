import {
  TelemetryProvenance,
  IntentFingerprint,
  CommandResult,
  CommandLifecycle
} from '../types/contracts';
import {
  Position,
  GateCandidate,
  SystemEvent,
  ClosedTrade
} from '../types';

export interface CommandProgressUpdate {
  status: CommandLifecycle;
  details: string;
  timestamp: number;
  authoritative: boolean;
}

export interface IDataProvider {
  getHealth(): Promise<TelemetryProvenance>;
  getPositions(): Promise<Position[]>;
  getCandidates(): Promise<GateCandidate[]>;
  getSystemEvents(): Promise<SystemEvent[]>;
  getClosedTrades(): Promise<ClosedTrade[]>;
  subscribeTicks(
    callback: (symbol: string, tick: { bid: number; ask: number; timestamp: number }, positions: Position[]) => void
  ): () => void;
}

export interface ICommandProvider {
  readonly isLiveAuthorized: boolean;
  submitCommand(
    intent: IntentFingerprint,
    onProgress?: (progress: CommandProgressUpdate) => void
  ): Promise<CommandResult>;
  reconcileCommand(intentId: string): Promise<CommandResult>;
}
