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

// -----------------------------------------------------------------------------
// EXPANDED DOMAIN TYPES (QUANT, NOTIFICATIONS, SETTINGS, LAB, OPS, AUDIT)
// -----------------------------------------------------------------------------

export type ExtendedNavTab = NavTab | 'LAB' | 'OPS' | 'AUDIT';

export type NotificationClass =
  | 'safety_critical'
  | 'trade_lifecycle'
  | 'risk_limit'
  | 'calibration_rollout'
  | 'informational_daily';

export interface NotificationDeliveryAttempt {
  channel: 'gui' | 'telegram';
  status: 'DELIVERED' | 'PENDING' | 'SIMULATED' | 'FAILED';
  timestamp?: number;
}

export interface NotificationEvent {
  id: string;
  class: NotificationClass;
  severity: 'CRITICAL' | 'WARN' | 'INFO';
  timestamp: number;
  title: string;
  detail: string;
  lane?: string;
  symbol?: string;
  acknowledged: boolean;
  acknowledgedAt?: number;
  resolved: boolean;
  resolvedAt?: number;
  deliveryAttempts: NotificationDeliveryAttempt[];
  isAuthoritative: boolean;
}

export interface PresentationPreferences {
  layoutDensity: 'compact' | 'default' | 'spacious';
  audioCues: boolean;
  colorTheme: 'obsidian_black';
}

export interface OperationalRiskConfig {
  effectiveConfigId: string;
  version: string;
  maxLaneRiskR: number;
  maxAccountExposureR: number;
  dailyLossLimitUsd: number;
  killSwitchThresholdL: number;
  lastUpdated: number;
  source: 'SIM_ENGINE' | 'CONTROL_SERVICE';
}

export type ModelPermittedIntent = 'VETO' | 'REDUCE' | 'NONE';

export interface QuantModelRecord {
  id: string;
  name: string;
  version: string;
  artifactSha256: string;
  rolloutStage: 'SHADOW' | 'PAPER' | 'CANARY' | 'ACTIVE';
  permittedIntents: ModelPermittedIntent[];
  laneEligibility: string[];
  health: 'HEALTHY' | 'DEGRADED' | 'STALE';
  lastInferenceTime: number;
  sourceState: 'SIMULATED' | 'SHADOW' | 'LIVE';
}

export interface ModelAdviceRecord {
  id: string;
  timestamp: number;
  modelId: string;
  symbol: string;
  lane: string;
  prediction: string;
  confidence: number;
  permittedIntent: ModelPermittedIntent;
  recommendedAction: string;
  gateDisposition: 'ACCEPTED_AS_ADVICE' | 'VETO_OVERRIDDEN_BY_RISK_GATE' | 'DEGRADED_BY_STALENESS';
  rationale: string;
  isAuthoritative: boolean;
}

export interface RolloutPromotionEvent {
  id: string;
  timestamp: number;
  target: string;
  fromStage: 'SHADOW' | 'PAPER' | 'CANARY';
  toStage: 'PAPER' | 'CANARY' | 'ACTIVE';
  evidenceSha256: string;
  approver: string;
  gateStatus: 'PASS' | 'FAIL';
}

export interface LabRunArtifact {
  id: string;
  name: string;
  commitSha: string;
  engineVersion: string;
  fidelity: 'F0' | 'F1' | 'F2' | 'F3';
  labTier: 'Lab-0' | 'Lab-1' | 'Lab-2' | 'Lab-3';
  dateRange: string;
  costModel: {
    spreadPips: number;
    commissionUsdPerLot: number;
    slippageModel: string;
  };
  netRealizedR: number;
  winRate: number;
  profitFactor: number;
  maxDrawdownR: number;
  maxDrawdownPct: number;
  sharpe: number;
  totalTrades: number;
  nullWorldCheck: 'PASS' | 'FAIL';
  plantedEdgeRecovery: 'PASS' | 'FAIL';
  oosDegradationPct: number;
  sensitivity: 'STABLE' | 'SENSITIVE';
  isAuthoritative: boolean;
}

export interface RemediationBlockerRecord {
  id: string;
  category: 'AUTHORITY' | 'SECURITY' | 'BRIDGE' | 'TELEMETRY' | 'PERSISTENCE';
  severity: 'P0' | 'P1' | 'P2';
  status: 'RESOLVED_IN_STAGE_D' | 'BLOCKED_ON_BACKEND' | 'MONITORING';
  summary: string;
  owner: string;
  evidenceArtifact: string;
  lastUpdated: string;
}

export interface AuditTrailRecord {
  id: string;
  timestamp: number;
  actor: string;
  action: string;
  target: string;
  outcome: 'SUCCESS_SIMULATED' | 'REJECTED_FAIL_CLOSED' | 'MUTATION_BLOCKED';
  correlationId: string;
  intentDigestSha256: string;
  details: string;
}

