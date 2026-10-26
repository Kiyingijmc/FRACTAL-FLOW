/**
 * Automated Risk Validator Utility
 * FRACTAL-FLOW Forensic Risk Engine
 * Priority: SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY
 *
 * Invariants:
 * 1. Explicit risk units: Open risk is denominated in R (initial structural risk allocated).
 * 2. Zero silent fallbacks: Missing or invalid position risk yields INVALID/UNKNOWN, never 0.6 or 1.0*size.
 * 3. Atomic portfolio aggregation: Never sum partial portfolios if any position is invalid/unknown.
 * 4. Exact boundary semantics: Limits are inclusive caps; strictly greater breaches.
 * 5. Floating-point precision: Deterministic cents / hundredths arithmetic.
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

export const RISK_ARITHMETIC_CONSTANTS = {
  SCALE: 1_000_000, // micro-R: 1 R = 1,000,000 micro-R
  MAX_INPUT_DECIMALS: 4, // 0.0001 R = 100 micro-R
  MIN_POSITION_RISK_R: 0.0001, // 100 micro-R
  MAX_POSITION_RISK_R: 100.0, // 100,000,000 micro-R
  MAX_PORTFOLIO_RISK_R: 200.0, // 200,000,000 micro-R
} as const;

export type PositionRiskRejectionReason =
  | 'EXPLICIT_ALLOCATED_RISK'
  | 'MISSING_ALLOCATED_RISK'
  | 'NON_FINITE_RISK'
  | 'NON_POSITIVE_RISK'
  | 'EXCEEDS_MAX_POSITION_RISK'
  | 'UNSUPPORTED_PRECISION'
  | 'INTEGER_OVERFLOW'
  | 'INVALID_OBJECT'
  | 'INVALID_LANE';

/**
 * Validates whether a numeric risk value conforms to the permitted input precision (at most 4 decimal places).
 * Rejects values with excess fractional precision beyond 4 decimal places (e.g. 0.00001, 0.12345).
 */
export function hasValidRiskPrecision(val: number): boolean {
  if (typeof val !== 'number' || !Number.isFinite(val)) return false;
  const scaled = val * 10_000;
  return Math.abs(scaled - Math.round(scaled)) < 1e-7;
}

/**
 * Safely converts a risk value in R to integer micro-R units (10^6 scale).
 * Strictly validates:
 * 1. Type: number only (no strings, booleans, objects, null, undefined).
 * 2. Finite: Number.isFinite (no NaN, Infinity, -Infinity).
 * 3. Positive: val > 0.
 * 4. Bound: val <= MAX_POSITION_RISK_R (100.0R).
 * 5. Precision: at most 4 decimal places (0.0001R). Rejects unsupported precision fail-closed.
 * 6. Safe integer: Math.round(val * 1_000_000) is a safe integer.
 */
export function toSafeMicroR(val: unknown): {
  isValid: boolean;
  microR: number;
  reason?: PositionRiskRejectionReason;
  error?: string;
} {
  if (typeof val !== 'number') {
    return {
      isValid: false,
      microR: NaN,
      reason: 'NON_FINITE_RISK',
      error: `Risk value (${val}) is not a number`
    };
  }
  if (!Number.isFinite(val)) {
    return {
      isValid: false,
      microR: NaN,
      reason: 'NON_FINITE_RISK',
      error: `Risk value (${val}) is non-finite (NaN or Infinity)`
    };
  }
  if (val <= 0) {
    return {
      isValid: false,
      microR: NaN,
      reason: 'NON_POSITIVE_RISK',
      error: `Risk value (${val}) is non-positive; must be strictly > 0`
    };
  }
  if (val > RISK_ARITHMETIC_CONSTANTS.MAX_POSITION_RISK_R) {
    return {
      isValid: false,
      microR: NaN,
      reason: 'EXCEEDS_MAX_POSITION_RISK',
      error: `Risk value (${val}R) exceeds maximum supported individual risk (${RISK_ARITHMETIC_CONSTANTS.MAX_POSITION_RISK_R}R)`
    };
  }
  if (!hasValidRiskPrecision(val)) {
    return {
      isValid: false,
      microR: NaN,
      reason: 'UNSUPPORTED_PRECISION',
      error: `Risk value (${val}) exceeds maximum permitted input precision of ${RISK_ARITHMETIC_CONSTANTS.MAX_INPUT_DECIMALS} decimal places (0.0001R)`
    };
  }
  const microR = Math.round(val * RISK_ARITHMETIC_CONSTANTS.SCALE);
  if (!Number.isSafeInteger(microR)) {
    return {
      isValid: false,
      microR: NaN,
      reason: 'INTEGER_OVERFLOW',
      error: `Risk value (${val}) causes integer overflow beyond safe integers`
    };
  }
  return { isValid: true, microR };
}

export interface PositionRiskEvaluation {
  isValid: boolean;
  riskR: number | null;
  reason?: string;
}

export interface PortfolioRiskResult {
  status: 'VALID' | 'INVALID' | 'UNKNOWN';
  totalRiskR: number | null;
  evaluatedCount: number;
  invalidPositionIds: string[];
  diagnostics: string[];
}

/**
 * Evaluates an individual position's allocated risk in R.
 * Invariant: Never assume lot size equals risk in R. Never use silent fallback values.
 */
export function getValidPositionRiskR(pos: Position): PositionRiskEvaluation {
  if (!pos || typeof pos !== 'object') {
    return { isValid: false, riskR: null, reason: 'Position is not an object' };
  }
  if (!pos.lane || typeof pos.lane !== 'string' || !pos.lane.trim()) {
    return { isValid: false, riskR: null, reason: `Position ${pos.id || 'UNKNOWN'} has missing or invalid lane` };
  }

  // Stage H.1.1 Mandatory Invariant: Existing positions must strictly have explicit allocatedRiskR.
  // Setup-mapped defaults are prohibited as silent fallbacks for open positions.
  if (pos.allocatedRiskR === undefined || pos.allocatedRiskR === null) {
    return {
      isValid: false,
      riskR: null,
      reason: `Position ${pos.id || 'UNKNOWN'} has missing allocatedRiskR (setup default estimates prohibited for open positions)`
    };
  }

  const safeMicro = toSafeMicroR(pos.allocatedRiskR);
  if (!safeMicro.isValid) {
    return {
      isValid: false,
      riskR: null,
      reason: `Position ${pos.id || 'UNKNOWN'} allocatedRiskR (${pos.allocatedRiskR}): ${safeMicro.error}`
    };
  }

  return { isValid: true, riskR: pos.allocatedRiskR };
}

/**
 * Resolves planned risk in R for a prospective trade candidate.
 * Dedicated strictly to candidate planning; never used for open position actual exposure.
 */
export function getCandidatePlannedRiskR(
  candidate: GateCandidate,
  overrideRiskR?: number
): { isValid: boolean; plannedRiskR: number | null; reason?: string } {
  if (!candidate || typeof candidate !== 'object') {
    return { isValid: false, plannedRiskR: null, reason: 'Candidate is null or invalid object' };
  }

  if (typeof overrideRiskR === 'number') {
    const safeMicro = toSafeMicroR(overrideRiskR);
    if (!safeMicro.isValid) {
      return {
        isValid: false,
        plannedRiskR: null,
        reason: `Candidate override risk (${overrideRiskR}): ${safeMicro.error}`
      };
    }
    return { isValid: true, plannedRiskR: overrideRiskR };
  }

  if (candidate.setup && typeof DEFAULT_SETUP_RISK_MAP[candidate.setup] === 'number') {
    const mapped = DEFAULT_SETUP_RISK_MAP[candidate.setup];
    const safeMicro = toSafeMicroR(mapped);
    if (safeMicro.isValid) {
      return { isValid: true, plannedRiskR: mapped };
    }
  }

  return {
    isValid: false,
    plannedRiskR: null,
    reason: `Candidate setup '${candidate.setup}' has no documented planned risk in DEFAULT_SETUP_RISK_MAP`
  };
}

/**
 * Evaluates aggregate risk in R across a list of positions, optionally filtered by lane.
 * Invariant: If ANY position is invalid, the entire portfolio risk evaluation fails closed.
 * Never partially aggregates a corrupted portfolio.
 */
export function evaluatePortfolioRisk(positions: Position[], laneFilter?: string): PortfolioRiskResult {
  if (!Array.isArray(positions)) {
    return {
      status: 'INVALID',
      totalRiskR: null,
      evaluatedCount: 0,
      invalidPositionIds: [],
      diagnostics: ['Positions must be an array']
    };
  }

  const targetPositions = laneFilter
    ? positions.filter((p) => p && p.lane === laneFilter)
    : positions;

  const invalidPositionIds: string[] = [];
  const diagnostics: string[] = [];
  let totalMicroR = 0;

  for (const pos of targetPositions) {
    const evalResult = getValidPositionRiskR(pos);
    if (!evalResult.isValid || evalResult.riskR === null) {
      invalidPositionIds.push(pos?.id || 'UNKNOWN_ID');
      diagnostics.push(evalResult.reason || 'Invalid position risk');
    } else {
      const safeMicro = toSafeMicroR(evalResult.riskR);
      if (!safeMicro.isValid) {
        invalidPositionIds.push(pos?.id || 'UNKNOWN_ID');
        diagnostics.push(safeMicro.error || 'Invalid position micro-R conversion');
      } else {
        totalMicroR += safeMicro.microR;
        if (
          !Number.isSafeInteger(totalMicroR) ||
          totalMicroR > RISK_ARITHMETIC_CONSTANTS.MAX_PORTFOLIO_RISK_R * RISK_ARITHMETIC_CONSTANTS.SCALE
        ) {
          invalidPositionIds.push(pos?.id || 'UNKNOWN_ID');
          diagnostics.push(`Portfolio aggregate risk exceeds safe limit (${RISK_ARITHMETIC_CONSTANTS.MAX_PORTFOLIO_RISK_R}R)`);
        }
      }
    }
  }

  if (invalidPositionIds.length > 0) {
    return {
      status: 'INVALID',
      totalRiskR: null,
      evaluatedCount: targetPositions.length,
      invalidPositionIds,
      diagnostics
    };
  }

  // Preserve authoritative precision via exact micro-R integer scaling
  const totalRiskR = totalMicroR / RISK_ARITHMETIC_CONSTANTS.SCALE;
  return {
    status: 'VALID',
    totalRiskR,
    evaluatedCount: targetPositions.length,
    invalidPositionIds: [],
    diagnostics: []
  };
}

/**
 * Compute current total open risk in R for a given lane.
 * Returns NaN if any position in the lane is invalid or unknown.
 */
export function calculateLaneRiskR(positions: Position[], lane: string): number {
  const result = evaluatePortfolioRisk(positions, lane);
  return result.status === 'VALID' && result.totalRiskR !== null ? result.totalRiskR : NaN;
}

/**
 * Compute aggregate account exposure in R across all lanes.
 * Returns NaN if any position in the account is invalid or unknown.
 */
export function calculateAccountExposureR(positions: Position[]): number {
  const result = evaluatePortfolioRisk(positions);
  return result.status === 'VALID' && result.totalRiskR !== null ? result.totalRiskR : NaN;
}

/**
 * Pure validator for OperationalRiskConfig.
 * Invariant: Centralized, shared validation between UI drafts and simulation state mutation boundaries.
 */
export function validateOperationalRiskConfig(config: unknown): { isValid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!config || typeof config !== 'object') {
    return { isValid: false, errors: ['Configuration must be a non-null object'] };
  }

  const cfg = config as Partial<OperationalRiskConfig>;

  if (typeof cfg.effectiveConfigId !== 'string' || !cfg.effectiveConfigId.trim()) {
    errors.push('effectiveConfigId must be a non-empty string');
  }

  if (typeof cfg.version !== 'string' || !cfg.version.trim()) {
    errors.push('version must be a non-empty string');
  }

  if (typeof cfg.maxLaneRiskR !== 'number' || !Number.isFinite(cfg.maxLaneRiskR) || cfg.maxLaneRiskR <= 0 || cfg.maxLaneRiskR > 100) {
    errors.push('maxLaneRiskR must be a finite positive number <= 100R');
  }

  if (typeof cfg.maxAccountExposureR !== 'number' || !Number.isFinite(cfg.maxAccountExposureR) || cfg.maxAccountExposureR <= 0 || cfg.maxAccountExposureR > 200) {
    errors.push('maxAccountExposureR must be a finite positive number <= 200R');
  }

  if (typeof cfg.dailyLossLimitUsd !== 'number' || !Number.isFinite(cfg.dailyLossLimitUsd) || cfg.dailyLossLimitUsd <= 0 || cfg.dailyLossLimitUsd > 10000000) {
    errors.push('dailyLossLimitUsd must be a finite positive number <= $10,000,000');
  }

  if (typeof cfg.killSwitchThresholdL !== 'number' || !Number.isInteger(cfg.killSwitchThresholdL) || cfg.killSwitchThresholdL < 1 || cfg.killSwitchThresholdL > 10) {
    errors.push('killSwitchThresholdL must be a positive integer between 1 and 10');
  }

  // Cross-field invariant: maxLaneRiskR cannot exceed maxAccountExposureR
  if (
    typeof cfg.maxLaneRiskR === 'number' &&
    typeof cfg.maxAccountExposureR === 'number' &&
    Number.isFinite(cfg.maxLaneRiskR) &&
    Number.isFinite(cfg.maxAccountExposureR) &&
    cfg.maxLaneRiskR > cfg.maxAccountExposureR
  ) {
    errors.push(`Cross-field invariant violation: maxLaneRiskR (${cfg.maxLaneRiskR}R) cannot exceed maxAccountExposureR (${cfg.maxAccountExposureR}R)`);
  }

  return {
    isValid: errors.length === 0,
    errors
  };
}

/**
 * Analyzes a GateCandidate against the active OperationalRiskConfig.
 * Detects whether admitting this candidate into execution would breach lane or account caps.
 *
 * Boundary semantics:
 * - Limits are inclusive ceilings: projected <= cap is permitted; strictly greater (projected > cap) breaches.
 * - Daily loss limit: currentDailyPnlUsd <= -dailyLossLimitUsd breaches.
 * - Proximity warning: 80% of daily loss limit triggers a warning.
 * - Invalid or unknown inputs strictly yield INVALID or UNKNOWN status, NEVER green CLEAR.
 */
export function validateCandidateAgainstRiskConfig(
  candidate: GateCandidate,
  currentPositions: Position[],
  riskConfig: OperationalRiskConfig,
  currentDailyPnlUsd: number,
  candidateRiskOverride?: number
): CandidateRiskValidation {
  const violations: RiskViolation[] = [];

  // Step 1: Validate OperationalRiskConfig
  const configValidation = validateOperationalRiskConfig(riskConfig);
  if (!configValidation.isValid) {
    violations.push({
      code: 'INVALID_CONFIG',
      severity: 'BLOCKING',
      message: `Invalid OperationalRiskConfig: ${configValidation.errors.join('; ')}`,
      metric: 'CONFIG_VALIDATION',
      currentValue: NaN,
      limitValue: NaN
    });

    return {
      candidateId: candidate?.id || 'UNKNOWN',
      hasViolations: true,
      violations,
      projectedLaneRiskR: NaN,
      projectedAccountExposureR: NaN,
      laneRiskCapR: NaN,
      accountExposureCapR: NaN,
      dailyLossLimitUsd: NaN,
      currentDailyPnlUsd,
      status: 'INVALID',
      isValid: false,
      diagnostic: 'OperationalRiskConfig validation failed'
    };
  }

  // Step 2: Validate candidate fields
  if (!candidate || typeof candidate !== 'object' || !candidate.id || !candidate.lane || !candidate.setup) {
    violations.push({
      code: 'INVALID_POSITION_PARAM',
      severity: 'BLOCKING',
      message: 'Candidate has missing or malformed identifier, lane, or setup',
      metric: 'CANDIDATE_INPUT',
      currentValue: NaN,
      limitValue: NaN
    });

    return {
      candidateId: candidate?.id || 'UNKNOWN',
      hasViolations: true,
      violations,
      projectedLaneRiskR: NaN,
      projectedAccountExposureR: NaN,
      laneRiskCapR: riskConfig.maxLaneRiskR,
      accountExposureCapR: riskConfig.maxAccountExposureR,
      dailyLossLimitUsd: riskConfig.dailyLossLimitUsd,
      currentDailyPnlUsd,
      status: 'INVALID',
      isValid: false,
      diagnostic: 'Candidate fields invalid'
    };
  }

  // Step 3: Resolve candidate planned risk via dedicated candidate planner
  const plannedRiskEval = getCandidatePlannedRiskR(candidate, candidateRiskOverride);
  if (!plannedRiskEval.isValid || plannedRiskEval.plannedRiskR === null) {
    violations.push({
      code: 'INVALID_POSITION_PARAM',
      severity: 'BLOCKING',
      message: plannedRiskEval.reason || `Candidate setup '${candidate.setup}' has no documented planned risk`,
      metric: 'CANDIDATE_RISK_MAPPING',
      currentValue: NaN,
      limitValue: 0
    });

    return {
      candidateId: candidate.id,
      hasViolations: true,
      violations,
      projectedLaneRiskR: NaN,
      projectedAccountExposureR: NaN,
      laneRiskCapR: riskConfig.maxLaneRiskR,
      accountExposureCapR: riskConfig.maxAccountExposureR,
      dailyLossLimitUsd: riskConfig.dailyLossLimitUsd,
      currentDailyPnlUsd,
      status: typeof candidateRiskOverride === 'number' ? 'INVALID' : 'UNKNOWN',
      isValid: false,
      diagnostic: plannedRiskEval.reason || 'Candidate planned risk could not be determined'
    };
  }
  const candidateRisk = plannedRiskEval.plannedRiskR;

  // Step 4: Validate current positions and calculate portfolio exposure
  const laneRiskEval = evaluatePortfolioRisk(currentPositions, candidate.lane);
  const accountExposureEval = evaluatePortfolioRisk(currentPositions);

  if (laneRiskEval.status !== 'VALID' || accountExposureEval.status !== 'VALID') {
    violations.push({
      code: 'INVALID_POSITION_PARAM',
      severity: 'BLOCKING',
      message: `Open position portfolio contains invalid risk data: ${[...laneRiskEval.diagnostics, ...accountExposureEval.diagnostics].join('; ')}`,
      metric: 'PORTFOLIO_INPUT',
      currentValue: NaN,
      limitValue: NaN
    });

    return {
      candidateId: candidate.id,
      hasViolations: true,
      violations,
      projectedLaneRiskR: NaN,
      projectedAccountExposureR: NaN,
      laneRiskCapR: riskConfig.maxLaneRiskR,
      accountExposureCapR: riskConfig.maxAccountExposureR,
      dailyLossLimitUsd: riskConfig.dailyLossLimitUsd,
      currentDailyPnlUsd,
      status: 'INVALID',
      isValid: false,
      diagnostic: 'Portfolio position validation failed'
    };
  }

  // Step 5: Validate currentDailyPnlUsd
  if (!Number.isFinite(currentDailyPnlUsd)) {
    violations.push({
      code: 'INVALID_POSITION_PARAM',
      severity: 'BLOCKING',
      message: `Daily P&L input (${currentDailyPnlUsd}) is non-finite`,
      metric: 'DAILY_PNL_INPUT',
      currentValue: currentDailyPnlUsd,
      limitValue: 0
    });

    return {
      candidateId: candidate.id,
      hasViolations: true,
      violations,
      projectedLaneRiskR: NaN,
      projectedAccountExposureR: NaN,
      laneRiskCapR: riskConfig.maxLaneRiskR,
      accountExposureCapR: riskConfig.maxAccountExposureR,
      dailyLossLimitUsd: riskConfig.dailyLossLimitUsd,
      currentDailyPnlUsd,
      status: 'INVALID',
      isValid: false,
      diagnostic: 'Daily P&L input non-finite'
    };
  }

  // Step 6: Deterministic arithmetic (micro-R basis and integer cents USD)
  const currentLaneMicroR = Math.round(laneRiskEval.totalRiskR! * 1_000_000);
  const currentAccountMicroR = Math.round(accountExposureEval.totalRiskR! * 1_000_000);
  const candidateMicroR = Math.round(candidateRisk * 1_000_000);

  const projectedLaneMicroR = currentLaneMicroR + candidateMicroR;
  const projectedAccountMicroR = currentAccountMicroR + candidateMicroR;

  // Authoritative un-rounded values
  const projectedLaneRiskR = projectedLaneMicroR / 1_000_000;
  const projectedAccountExposureR = projectedAccountMicroR / 1_000_000;

  const maxLaneMicroR = Math.round(riskConfig.maxLaneRiskR * 1_000_000);
  const maxAccountMicroR = Math.round(riskConfig.maxAccountExposureR * 1_000_000);

  // Invariant 1: Max Lane Risk Cap (inclusive ceiling: > breaches)
  if (projectedLaneMicroR > maxLaneMicroR) {
    const excessR = (projectedLaneMicroR - maxLaneMicroR) / 1_000_000;
    violations.push({
      code: 'MAX_LANE_RISK_EXCEEDED',
      severity: 'BLOCKING',
      message: `Projected lane risk (${projectedLaneRiskR.toFixed(4)}R) exceeds maximum lane risk limit (${riskConfig.maxLaneRiskR.toFixed(1)}R) by ${excessR.toFixed(4)}R`,
      metric: 'LANE_RISK',
      currentValue: projectedLaneRiskR,
      limitValue: riskConfig.maxLaneRiskR,
    });
  }

  // Invariant 2: Max Account Aggregate Exposure Cap (inclusive ceiling: > breaches)
  if (projectedAccountMicroR > maxAccountMicroR) {
    const excessR = (projectedAccountMicroR - maxAccountMicroR) / 1_000_000;
    violations.push({
      code: 'MAX_ACCOUNT_EXPOSURE_EXCEEDED',
      severity: 'BLOCKING',
      message: `Projected total account exposure (${projectedAccountExposureR.toFixed(4)}R) exceeds account exposure limit (${riskConfig.maxAccountExposureR.toFixed(1)}R) by ${excessR.toFixed(4)}R`,
      metric: 'ACCOUNT_EXPOSURE',
      currentValue: projectedAccountExposureR,
      limitValue: riskConfig.maxAccountExposureR,
    });
  }

  // Invariant 3: Daily Dollar Loss Limit Enforcement
  // Financial rounding to exact cents to prevent IEEE 754 precision artifacts
  const pnlCents = Math.round(currentDailyPnlUsd * 100);
  const lossLimitCents = Math.round(Math.abs(riskConfig.dailyLossLimitUsd) * 100);

  if (pnlCents <= -lossLimitCents) {
    violations.push({
      code: 'DAILY_LOSS_LIMIT_EXCEEDED',
      severity: 'BLOCKING',
      message: `Current daily loss ($${Math.abs(currentDailyPnlUsd).toFixed(2)}) has breached the daily loss limit ($${riskConfig.dailyLossLimitUsd.toFixed(2)})`,
      metric: 'DAILY_LOSS',
      currentValue: currentDailyPnlUsd,
      limitValue: -riskConfig.dailyLossLimitUsd,
    });
  } else if (pnlCents <= -Math.round(lossLimitCents * 0.8)) {
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
    isValid: true,
  };
}

/**
 * Analyzes a proposed position modification action against OperationalRiskConfig.
 * Note: Risk reductions (tighten stop, BE, close) are de-risking actions and strictly safe.
 * Risk-increasing actions (add_size, scale_in) require valid portfolio risk, deterministic projected-risk calculation,
 * and strict enforcement of both aggregate account exposure cap and lane-level risk cap.
 */
export function validatePositionModification(
  action: ActionType,
  position: Position,
  riskConfig: OperationalRiskConfig,
  currentDailyPnlUsd: number,
  portfolioPositions?: Position[],
  incrementalRiskR?: number
): { isAllowed: boolean; violations: RiskViolation[] } {
  // Protective exit or tightening actions always de-risk the book
  if (action === 'tighten_stop' || action === 'move_to_breakeven' || action === 'close_position') {
    return { isAllowed: true, violations: [] };
  }

  // Validate operational risk configuration
  const configVal = validateOperationalRiskConfig(riskConfig);
  if (!configVal.isValid || !Number.isFinite(currentDailyPnlUsd)) {
    return {
      isAllowed: false,
      violations: [
        {
          code: 'INVALID_POSITION_PARAM',
          severity: 'BLOCKING',
          message: 'Invalid risk configuration or non-finite daily P&L',
          metric: 'VALIDATION',
          currentValue: NaN,
          limitValue: 0
        }
      ]
    };
  }

  // If daily loss limit is already breached, new non-protective mutations are forbidden
  const pnlCents = Math.round(currentDailyPnlUsd * 100);
  const lossLimitCents = Math.round(Math.abs(riskConfig.dailyLossLimitUsd) * 100);

  if (pnlCents <= -lossLimitCents) {
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

  // Risk-increasing actions (add_size, scale_in) require valid portfolio risk and strict projected cap checks
  if (action === 'add_size' || action === 'scale_in') {
    // 1. Mandatory portfolioPositions: must be a valid array containing target position
    if (!Array.isArray(portfolioPositions) || portfolioPositions.length === 0) {
      return {
        isAllowed: false,
        violations: [
          {
            code: 'INVALID_POSITION_PARAM',
            severity: 'BLOCKING',
            message: `Cannot execute risk-increasing action '${action}': portfolio positions snapshot is missing or empty`,
            metric: 'PORTFOLIO_INPUT',
            currentValue: NaN,
            limitValue: riskConfig.maxAccountExposureR,
          },
        ],
      };
    }

    // 2. Validate target position object and lane
    if (!position || typeof position !== 'object' || !position.id || !position.lane) {
      return {
        isAllowed: false,
        violations: [
          {
            code: 'INVALID_POSITION_PARAM',
            severity: 'BLOCKING',
            message: `Cannot execute risk-increasing action '${action}': target position is null or missing id/lane`,
            metric: 'POSITION_INPUT',
            currentValue: NaN,
            limitValue: NaN,
          },
        ],
      };
    }

    // Target position must exist in portfolio snapshot
    const targetInPortfolio = portfolioPositions.find(p => p && p.id === position.id);
    if (!targetInPortfolio) {
      return {
        isAllowed: false,
        violations: [
          {
            code: 'INVALID_POSITION_PARAM',
            severity: 'BLOCKING',
            message: `Target position '${position.id}' does not exist in authoritative portfolio snapshot`,
            metric: 'POSITION_IDENTITY',
            currentValue: NaN,
            limitValue: NaN,
          },
        ],
      };
    }

    // 3. Validate target position allocated risk
    const targetRiskEval = getValidPositionRiskR(targetInPortfolio);
    if (!targetRiskEval.isValid || targetRiskEval.riskR === null) {
      return {
        isAllowed: false,
        violations: [
          {
            code: 'INVALID_POSITION_PARAM',
            severity: 'BLOCKING',
            message: `Target position '${position.id}' has invalid allocated risk: ${targetRiskEval.reason}`,
            metric: 'POSITION_RISK',
            currentValue: NaN,
            limitValue: NaN,
          },
        ],
      };
    }

    const targetMicro = toSafeMicroR(targetRiskEval.riskR);
    if (!targetMicro.isValid) {
      return {
        isAllowed: false,
        violations: [
          {
            code: 'INVALID_POSITION_PARAM',
            severity: 'BLOCKING',
            message: `Target position '${position.id}' micro-R conversion failed: ${targetMicro.error}`,
            metric: 'POSITION_MICRO_R',
            currentValue: NaN,
            limitValue: NaN,
          },
        ],
      };
    }

    // 4. Determine incremental risk delta in micro-R
    let deltaMicroR: number;
    if (typeof incrementalRiskR === 'number') {
      const explicitDeltaMicro = toSafeMicroR(incrementalRiskR);
      if (!explicitDeltaMicro.isValid) {
        return {
          isAllowed: false,
          violations: [
            {
              code: 'INVALID_POSITION_PARAM',
              severity: 'BLOCKING',
              message: `Supplied incremental risk (${incrementalRiskR}R) is invalid: ${explicitDeltaMicro.error}`,
              metric: 'INCREMENTAL_RISK',
              currentValue: incrementalRiskR,
              limitValue: NaN,
            },
          ],
        };
      }
      deltaMicroR = explicitDeltaMicro.microR;
    } else {
      // Canonical standard: +50% size addition scales structural risk by 50%
      deltaMicroR = Math.round(targetMicro.microR * 0.5);
    }

    if (!Number.isSafeInteger(deltaMicroR) || deltaMicroR <= 0) {
      return {
        isAllowed: false,
        violations: [
          {
            code: 'INVALID_POSITION_PARAM',
            severity: 'BLOCKING',
            message: 'Incremental risk delta is non-positive or overflows safe integer arithmetic',
            metric: 'INCREMENTAL_RISK_ARITHMETIC',
            currentValue: NaN,
            limitValue: 0,
          },
        ],
      };
    }

    // 5. Evaluate current portfolio risk across all lanes and for the target position's lane
    const portEval = evaluatePortfolioRisk(portfolioPositions);
    if (portEval.status !== 'VALID' || portEval.totalRiskR === null) {
      return {
        isAllowed: false,
        violations: [
          {
            code: 'MAX_ACCOUNT_EXPOSURE_EXCEEDED',
            severity: 'BLOCKING',
            message: `Cannot execute risk-increasing action '${action}' while portfolio risk is invalid or unknown (${portEval.status}): ${portEval.diagnostics.join('; ')}`,
            metric: 'PORTFOLIO_RISK_STATUS',
            currentValue: NaN,
            limitValue: riskConfig.maxAccountExposureR,
          },
        ],
      };
    }

    const laneEval = evaluatePortfolioRisk(portfolioPositions, targetInPortfolio.lane);
    if (laneEval.status !== 'VALID' || laneEval.totalRiskR === null) {
      return {
        isAllowed: false,
        violations: [
          {
            code: 'MAX_LANE_RISK_EXCEEDED',
            severity: 'BLOCKING',
            message: `Cannot execute risk-increasing action '${action}' while lane '${targetInPortfolio.lane}' risk is invalid or unknown (${laneEval.status}): ${laneEval.diagnostics.join('; ')}`,
            metric: 'LANE_RISK_STATUS',
            currentValue: NaN,
            limitValue: riskConfig.maxLaneRiskR,
          },
        ],
      };
    }

    // 6. Compute projected exposure in micro-R
    const currentAccountMicroR = Math.round(portEval.totalRiskR * RISK_ARITHMETIC_CONSTANTS.SCALE);
    const currentLaneMicroR = Math.round(laneEval.totalRiskR * RISK_ARITHMETIC_CONSTANTS.SCALE);
    const maxAccountMicroR = Math.round(riskConfig.maxAccountExposureR * RISK_ARITHMETIC_CONSTANTS.SCALE);
    const maxLaneMicroR = Math.round(riskConfig.maxLaneRiskR * RISK_ARITHMETIC_CONSTANTS.SCALE);

    const projectedAccountMicroR = currentAccountMicroR + deltaMicroR;
    const projectedLaneMicroR = currentLaneMicroR + deltaMicroR;

    const projectedAccountExposureR = projectedAccountMicroR / RISK_ARITHMETIC_CONSTANTS.SCALE;
    const projectedLaneRiskR = projectedLaneMicroR / RISK_ARITHMETIC_CONSTANTS.SCALE;

    const violations: RiskViolation[] = [];

    // Check Lane Cap (inclusive ceiling: > breaches)
    if (projectedLaneMicroR > maxLaneMicroR) {
      const excessR = (projectedLaneMicroR - maxLaneMicroR) / RISK_ARITHMETIC_CONSTANTS.SCALE;
      violations.push({
        code: 'MAX_LANE_RISK_EXCEEDED',
        severity: 'BLOCKING',
        message: `Projected lane risk (${projectedLaneRiskR.toFixed(4)}R) exceeds maximum lane risk limit (${riskConfig.maxLaneRiskR.toFixed(1)}R) by ${excessR.toFixed(4)}R`,
        metric: 'LANE_RISK',
        currentValue: projectedLaneRiskR,
        limitValue: riskConfig.maxLaneRiskR,
      });
    }

    // Check Account Cap (inclusive ceiling: > breaches)
    if (projectedAccountMicroR > maxAccountMicroR) {
      const excessR = (projectedAccountMicroR - maxAccountMicroR) / RISK_ARITHMETIC_CONSTANTS.SCALE;
      violations.push({
        code: 'MAX_ACCOUNT_EXPOSURE_EXCEEDED',
        severity: 'BLOCKING',
        message: `Projected total account exposure (${projectedAccountExposureR.toFixed(4)}R) exceeds account exposure limit (${riskConfig.maxAccountExposureR.toFixed(1)}R) by ${excessR.toFixed(4)}R`,
        metric: 'ACCOUNT_EXPOSURE',
        currentValue: projectedAccountExposureR,
        limitValue: riskConfig.maxAccountExposureR,
      });
    }

    if (violations.length > 0) {
      return { isAllowed: false, violations };
    }
  }

  return { isAllowed: true, violations: [] };
}
