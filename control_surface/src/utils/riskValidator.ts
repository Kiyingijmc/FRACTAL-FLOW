/**
 * Automated Risk Validator Utility
 * FRACTAL-FLOW Forensic Risk Engine
 * Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM
 */

import { 
  Position, 
  GateCandidate, 
  OperationalRiskConfig, 
  CandidateRiskValidation, 
  RiskViolation,
  ActionType 
} from '../types';

/**
 * Standard risk allocation in R per setup class in FRACTAL-FLOW
 */
export const DEFAULT_SETUP_RISK_MAP: Record<string, number> = {
  'FF-01': 0.8, // Trend Runner
  'FF-02': 0.6, // Counterflow Reversion
  'FF-03': 0.5, // Range Ladder
  'FF-04': 0.5, // Transition Watch
};

/**
 * Compute current total open risk in R for a given lane.
 */
export function calculateLaneRiskR(positions: Position[], lane: string): number {
  return positions
    .filter((p) => p.lane === lane)
    .reduce((acc, p) => acc + (p.size ? p.size * 1.0 : 0.6), 0);
}

/**
 * Compute aggregate account exposure in R across all lanes.
 */
export function calculateAccountExposureR(positions: Position[]): number {
  return positions.reduce((acc, p) => acc + (p.size ? p.size * 1.0 : 0.6), 0);
}

/**
 * Analyzes a GateCandidate against the active OperationalRiskConfig.
 * Detects whether admitting this candidate into execution would breach lane or account caps.
 */
export function validateCandidateAgainstRiskConfig(
  candidate: GateCandidate,
  currentPositions: Position[],
  riskConfig: OperationalRiskConfig,
  currentDailyPnlUsd: number,
  candidateRiskOverride?: number
): CandidateRiskValidation {
  const candidateRisk = candidateRiskOverride ?? (DEFAULT_SETUP_RISK_MAP[candidate.setup] || 0.6);
  const currentLaneRisk = calculateLaneRiskR(currentPositions, candidate.lane);
  const currentAccountExposure = calculateAccountExposureR(currentPositions);

  const projectedLaneRiskR = Number((currentLaneRisk + candidateRisk).toFixed(2));
  const projectedAccountExposureR = Number((currentAccountExposure + candidateRisk).toFixed(2));
  const violations: RiskViolation[] = [];

  // Invariant 1: Max Lane Risk Cap
  if (projectedLaneRiskR > riskConfig.maxLaneRiskR) {
    violations.push({
      code: 'MAX_LANE_RISK_EXCEEDED',
      severity: 'BLOCKING',
      message: `Projected lane risk (${projectedLaneRiskR}R) exceeds maximum lane risk limit (${riskConfig.maxLaneRiskR.toFixed(1)}R) by ${(projectedLaneRiskR - riskConfig.maxLaneRiskR).toFixed(2)}R`,
      metric: 'LANE_RISK',
      currentValue: projectedLaneRiskR,
      limitValue: riskConfig.maxLaneRiskR,
    });
  }

  // Invariant 2: Max Account Aggregate Exposure Cap
  if (projectedAccountExposureR > riskConfig.maxAccountExposureR) {
    violations.push({
      code: 'MAX_ACCOUNT_EXPOSURE_EXCEEDED',
      severity: 'BLOCKING',
      message: `Projected total account exposure (${projectedAccountExposureR}R) exceeds account exposure limit (${riskConfig.maxAccountExposureR.toFixed(1)}R) by ${(projectedAccountExposureR - riskConfig.maxAccountExposureR).toFixed(2)}R`,
      metric: 'ACCOUNT_EXPOSURE',
      currentValue: projectedAccountExposureR,
      limitValue: riskConfig.maxAccountExposureR,
    });
  }

  // Invariant 3: Daily Dollar Loss Limit Enforcement
  if (currentDailyPnlUsd < -Math.abs(riskConfig.dailyLossLimitUsd)) {
    violations.push({
      code: 'DAILY_LOSS_LIMIT_EXCEEDED',
      severity: 'BLOCKING',
      message: `Current daily loss ($${Math.abs(currentDailyPnlUsd).toFixed(2)}) has breached the daily loss limit ($${riskConfig.dailyLossLimitUsd.toFixed(2)})`,
      metric: 'DAILY_LOSS',
      currentValue: currentDailyPnlUsd,
      limitValue: -riskConfig.dailyLossLimitUsd,
    });
  } else if (currentDailyPnlUsd < -Math.abs(riskConfig.dailyLossLimitUsd) * 0.8) {
    // Proximity warning at 80% of daily loss threshold
    violations.push({
      code: 'DAILY_LOSS_LIMIT_EXCEEDED',
      severity: 'WARNING',
      message: `Daily loss is at 80%+ threshold ($${Math.abs(currentDailyPnlUsd).toFixed(2)} / $${riskConfig.dailyLossLimitUsd.toFixed(2)})`,
      metric: 'DAILY_LOSS_PROXIMITY',
      currentValue: currentDailyPnlUsd,
      limitValue: -riskConfig.dailyLossLimitUsd,
    });
  }

  const hasBlocking = violations.some((v) => v.severity === 'BLOCKING');
  const status: 'CLEAR' | 'WARNING' | 'BREACHED' = hasBlocking
    ? 'BREACHED'
    : violations.length > 0
    ? 'WARNING'
    : 'CLEAR';

  return {
    candidateId: candidate.id,
    hasViolations: violations.length > 0,
    violations,
    projectedLaneRiskR,
    projectedAccountExposureR,
    laneRiskCapR: riskConfig.maxLaneRiskR,
    accountExposureCapR: riskConfig.maxAccountExposureR,
    dailyLossLimitUsd: riskConfig.dailyLossLimitUsd,
    currentDailyPnlUsd,
    status,
  };
}

/**
 * Analyzes a proposed position modification action against OperationalRiskConfig.
 * Note: Risk reductions (tighten stop, BE, close) are de-risking actions and strictly safe.
 */
export function validatePositionModification(
  action: ActionType,
  _position: Position,
  riskConfig: OperationalRiskConfig,
  currentDailyPnlUsd: number
): { isAllowed: boolean; violations: RiskViolation[] } {
  // Protective exit or tightening actions always de-risk the book
  if (action === 'tighten_stop' || action === 'move_to_breakeven' || action === 'close_position') {
    return { isAllowed: true, violations: [] };
  }

  // If daily loss limit is already breached, new risk is forbidden
  if (currentDailyPnlUsd < -Math.abs(riskConfig.dailyLossLimitUsd)) {
    return {
      isAllowed: false,
      violations: [
        {
          code: 'DAILY_LOSS_LIMIT_EXCEEDED',
          severity: 'BLOCKING',
          message: 'Daily loss limit breached. All non-protective mutations are rejected fail-closed.',
          metric: 'DAILY_LOSS',
          currentValue: currentDailyPnlUsd,
          limitValue: -riskConfig.dailyLossLimitUsd,
        },
      ],
    };
  }

  return { isAllowed: true, violations: [] };
}
