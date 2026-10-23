export type Side = 'LONG' | 'SHORT';
export type Timeframe = '4H' | '1H' | '30M' | '15M' | '5M' | '1M';

export interface Position {
  id: string;
  symbol: string;
  side: Side;
  setup: string;
  mode: string;
  entryPrice: number;
  currentPrice: number;
  size: number;
  unrealizedR: number;
  mfe: number;
  mae: number;
  exitProfile: string;
  age: string;
  structuralAnchor: string;
  trailDistance: string;
  breakevenStatus: string;
  decayState: string;
  effectiveConfig: string;
  drivingTimeframe: Timeframe;
  lane: string;
  priceDecimals: number;
  lastTickDir?: 'up' | 'down';
  lastTickTimestamp?: number;
  isSimulated: boolean;
}

export interface PendingOrder {
  id: string;
  symbol: string;
  side: Side;
  setup: string;
  type: string;
  price: number;
  size: number;
  triggerCond: string;
  age: string;
  priceDecimals: number;
  isSimulated: boolean;
}

export interface ClosedTrade {
  id: string;
  symbol: string;
  side: Side;
  setup: string;
  mode: string;
  entryPrice: number;
  exitPrice: number;
  size: number;
  realizedR: number;
  realizedPnl: number;
  exitReason: string;
  duration: string;
  closedAt: string;
  priceDecimals: number;
  isSimulated: boolean;
}

export type GateLetter = 'Q' | 'E' | 'R' | 'P' | 'L' | 'O' | 'T' | 'N' | 'K' | 'A' | 'X';
export type GateStatus = 'pass' | 'fail' | 'na';

export interface GateEvaluation {
  letter: GateLetter;
  name: string;
  status: GateStatus;
  detail?: string;
  timestamp?: string;
}

export interface GateCandidate {
  id: string;
  symbol: string;
  setup: string;
  lane: string;
  evaluatedAt: string;
  gates: GateEvaluation[];
  summaryStatus: 'blocked' | 'passed';
  failureNotice?: {
    letter: GateLetter;
    title: string;
    detail: string;
  };
}

export interface SystemEvent {
  id: string;
  eventId: string;
  timestamp: string;
  message: string;
  source: 'JOURNAL' | 'GATEWAY' | 'SIM_ENGINE' | 'CLIENT_INTAKE';
  level: 'info' | 'warn' | 'crit';
  status?: 'PERSISTED' | 'DISPATCHED' | 'SIMULATED' | 'CONFIRMED' | 'REJECTED' | 'SESSION' | 'IN_MEMORY';
  isAuthoritative?: boolean;
}

export type NavTab = 'POS' | 'DEC' | 'RISK' | 'MODE' | 'NEWS' | 'CALIB' | 'HEALTH' | 'STATS';

export type NewsImpactLevel = 'High' | 'Med' | 'Low';
export type NewsCategory =
  | 'MACRO_ECONOMIC'
  | 'CENTRAL_BANK'
  | 'SYSTEM_ANNOUNCEMENT'
  | 'GATE_N_EMBARGO';

export interface MarketNewsItem {
  id: string;
  timestamp: string;
  title: string;
  category: NewsCategory;
  currency: string;
  impact: NewsImpactLevel;
  details: string;
  source: string;
  embargoActive?: boolean;
  affectedSymbols?: string[];
  actual?: string;
  forecast?: string;
  previous?: string;
}

export type PositionsSubTab = 'open' | 'pending' | 'closed';

export type ActionType = 'tighten_stop' | 'move_to_breakeven' | 'close_position';

export type CommandLifecycleState =
  | 'IDLE'
  | 'REQUESTED'
  | 'ACCEPTED'
  | 'DISPATCHED'
  | 'CONFIRMED'
  | 'REJECTED'
  | 'UNKNOWN';

export interface CommandExecutionRecord {
  id: string;
  action: ActionType;
  symbol: string;
  side: Side;
  status: CommandLifecycleState;
  idempotencyKey: string;
  requestedAt: string;
  confirmedAt?: string;
  source: 'SIMULATION_SANDBOX' | 'GATEWAY_PROV';
  details: string;
}
