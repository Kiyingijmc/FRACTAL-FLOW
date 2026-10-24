import React, { useState } from 'react';
import { ShieldAlert, AlertTriangle, CheckCircle2, X, Sliders, ChevronRight } from 'lucide-react';
import { GateCandidate, OperationalRiskConfig, CandidateRiskValidation, Position } from '../types';
import { validateCandidateAgainstRiskConfig } from '../utils/riskValidator';

interface AutomatedRiskValidatorBadgeProps {
  validation: CandidateRiskValidation;
  candidate: GateCandidate;
  onOpenDetails: () => void;
}

export const AutomatedRiskValidatorBadge: React.FC<AutomatedRiskValidatorBadgeProps> = ({
  validation,
  candidate,
  onOpenDetails,
}) => {
  const isBreached = validation.status === 'BREACHED';
  const isWarning = validation.status === 'WARNING';
  const isInvalid = validation.status === 'INVALID';
  const isUnknown = validation.status === 'UNKNOWN';

  let badgeStyle = 'bg-[#4FAE86]/10 text-[#4FAE86] border-[#4FAE86]/30 hover:bg-[#4FAE86]/20';
  let labelText = `RISK CLEAR (${validation.projectedLaneRiskR}R / ${validation.laneRiskCapR}R)`;
  let icon = <CheckCircle2 className="w-3 h-3 text-[#4FAE86]" />;

  if (isInvalid) {
    badgeStyle = 'bg-[#B23B3B]/20 text-[#C25B6B] border-[#B23B3B]/60 hover:bg-[#B23B3B]/30';
    labelText = '⚠️ INVALID DATA / RISK FAIL-CLOSED';
    icon = <ShieldAlert className="w-3 h-3 text-[#C25B6B]" />;
  } else if (isUnknown) {
    badgeStyle = 'bg-[#BFA13B]/20 text-[#BFA13B] border-[#BFA13B]/50 hover:bg-[#BFA13B]/30';
    labelText = '⚠️ RISK UNKNOWN';
    icon = <AlertTriangle className="w-3 h-3 text-[#BFA13B]" />;
  } else if (isBreached) {
    badgeStyle = 'bg-[#B23B3B]/20 text-[#C25B6B] border-[#B23B3B]/50 hover:bg-[#B23B3B]/30 animate-pulse';
    const violation = validation.violations[0];
    const shortCode = violation?.code === 'MAX_LANE_RISK_EXCEEDED' 
      ? `LANE CAP BREACH (${validation.projectedLaneRiskR}R > ${validation.laneRiskCapR}R)` 
      : violation?.code === 'MAX_ACCOUNT_EXPOSURE_EXCEEDED'
      ? `EXPOSURE CAP BREACH (${validation.projectedAccountExposureR}R > ${validation.accountExposureCapR}R)`
      : violation?.code === 'DAILY_LOSS_LIMIT_EXCEEDED'
      ? 'DAILY LOSS CAP BREACH'
      : 'RISK VIOLATION';
    labelText = `⚠️ ${shortCode}`;
    icon = <ShieldAlert className="w-3 h-3 text-[#C25B6B]" />;
  } else if (isWarning) {
    badgeStyle = 'bg-[#BFA13B]/15 text-[#BFA13B] border-[#BFA13B]/40 hover:bg-[#BFA13B]/25';
    labelText = `⚠️ RISK WARNING`;
    icon = <AlertTriangle className="w-3 h-3 text-[#BFA13B]" />;
  }

  return (
    <button
      type="button"
      onClick={onOpenDetails}
      data-testid={`risk-badge-${candidate.id}`}
      data-risk-status={validation.status}
      aria-label={`Automated Risk Validator for ${candidate.symbol}: ${validation.status}`}
      title={`Click to inspect automated risk validation details for ${candidate.symbol}`}
      className={`min-h-[28px] px-2 py-0.5 rounded-[2px] border text-[10px] font-mono flex items-center gap-1.5 transition-colors cursor-pointer shrink-0 ${badgeStyle}`}
    >
      {icon}
      <span className="font-semibold">{labelText}</span>
      <ChevronRight className="w-2.5 h-2.5 opacity-60" />
    </button>
  );
};

interface AutomatedRiskValidatorModalProps {
  isOpen: boolean;
  onClose: () => void;
  candidate: GateCandidate;
  positions: Position[];
  riskConfig: OperationalRiskConfig;
  dailyPnl: number;
}

export const AutomatedRiskValidatorModal: React.FC<AutomatedRiskValidatorModalProps> = ({
  isOpen,
  onClose,
  candidate,
  positions,
  riskConfig,
  dailyPnl,
}) => {
  const [simulatedRiskR, setSimulatedRiskR] = useState<number>(0.6);

  if (!isOpen) return null;

  const validation = validateCandidateAgainstRiskConfig(
    candidate,
    positions,
    riskConfig,
    dailyPnl,
    simulatedRiskR
  );

  const laneRiskPct = Math.min(100, Math.round((validation.projectedLaneRiskR / validation.laneRiskCapR) * 100));
  const expRiskPct = Math.min(100, Math.round((validation.projectedAccountExposureR / validation.accountExposureCapR) * 100));

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Automated Risk Validator Inspector"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4"
    >
      <div 
        className="w-full max-w-xl bg-[#10151D] border border-[#232A35] rounded-[3px] shadow-2xl flex flex-col max-h-[90vh] overflow-hidden animate-in fade-in zoom-in-95 duration-150"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#232A35] bg-[#161C26]">
          <div className="flex items-center gap-2">
            <ShieldAlert className={`w-4 h-4 ${validation.status === 'BREACHED' ? 'text-[#C25B6B]' : 'text-[#4FAE86]'}`} />
            <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#E7EAEE]">
              Automated Risk Validator — Intake Pre-Flight Check
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close risk validator inspector"
            className="p-1 text-[#6E7A8A] hover:text-[#E7EAEE] rounded-[2px]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4 overflow-y-auto font-mono text-xs text-[#E7EAEE]">
          {/* Candidate Context */}
          <div className="p-3 bg-[#161C26] border border-[#232A35] rounded-[2px] flex items-center justify-between">
            <div>
              <span className="text-[10px] text-[#6E7A8A] block">CANDIDATE UNDER EVALUATION</span>
              <span className="font-bold text-[#E7EAEE] text-sm">{candidate.symbol}</span>
              <span className="text-[#6E7A8A] ml-2">Setup: {candidate.setup} · Lane: {candidate.lane}</span>
            </div>
            <div className="text-right">
              <span className="text-[10px] text-[#6E7A8A] block">INSPECTION STATUS</span>
              <span
                data-testid="risk-validation-status"
                className={`font-semibold px-2 py-0.5 rounded-[2px] text-[10px] ${
                  validation.status === 'BREACHED'
                    ? 'bg-[#B23B3B]/20 text-[#C25B6B] border border-[#B23B3B]/40'
                    : validation.status === 'WARNING'
                    ? 'bg-[#BFA13B]/20 text-[#BFA13B] border border-[#BFA13B]/40'
                    : 'bg-[#4FAE86]/20 text-[#4FAE86] border border-[#4FAE86]/40'
                }`}
              >
                {validation.status}
              </span>
            </div>
          </div>

          {/* Interactive Proposed Risk Size Simulation */}
          <div className="p-3 bg-[#161C26]/60 border border-[#232A35] rounded-[2px] space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-[#6E7A8A] flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-[#5B8FBF]" />
                Simulate Proposed Intake Risk (R):
              </span>
              <span className="text-[#5B8FBF] font-bold text-sm">+{simulatedRiskR.toFixed(2)}R</span>
            </div>
            <input
              type="range"
              min="0.1"
              max="2.0"
              step="0.1"
              value={simulatedRiskR}
              onChange={(e) => setSimulatedRiskR(parseFloat(e.target.value))}
              aria-label="Simulated candidate risk in R"
              className="w-full accent-[#5B8FBF] cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-[#6E7A8A]">
              <span>0.1R (Conservative)</span>
              <span>0.6R (Standard FF-02)</span>
              <span>0.8R (Runner FF-01)</span>
              <span>2.0R (Max)</span>
            </div>
          </div>

          {/* Violations Alert Box */}
          {validation.violations.length > 0 ? (
            <div 
              data-testid="risk-violations-alert"
              className="p-3 bg-[#B23B3B]/10 border border-[#B23B3B]/40 rounded-[2px] space-y-2"
            >
              <div className="flex items-center gap-1.5 text-[#C25B6B] font-semibold text-[11px]">
                <ShieldAlert className="w-3.5 h-3.5" />
                <span>OperationalRiskConfig Violations Detected ({validation.violations.length})</span>
              </div>
              <ul className="space-y-1.5 text-[11px]">
                {validation.violations.map((v, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-[#E7EAEE]">
                    <span className="px-1 py-0.2 rounded-[2px] text-[9px] bg-[#B23B3B]/30 text-[#C25B6B] border border-[#B23B3B]/50 shrink-0 font-bold">
                      {v.code}
                    </span>
                    <span className="text-[#E7EAEE]">{v.message}</span>
                  </li>
                ))}
              </ul>
              <div className="text-[10px] text-[#6E7A8A] pt-1 border-t border-[#B23B3B]/20">
                Pre-flight analysis only — authoritative admission enforcement not implemented in simulation. Execution dispatch is not supported on candidate pipeline.
              </div>
            </div>
          ) : (
            <div 
              data-testid="risk-clear-notice"
              className="p-3 bg-[#4FAE86]/10 border border-[#4FAE86]/30 rounded-[2px] text-[#4FAE86] flex items-center gap-2"
            >
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>Proposed candidate change is strictly within all active OperationalRiskConfig invariant limits.</span>
            </div>
          )}

          {/* Caps & Metrics Breakdown */}
          <div className="space-y-3 pt-1">
            {/* Lane Risk Gauge */}
            <div className="space-y-1">
              <div className="flex justify-between text-[11px]">
                <span className="text-[#6E7A8A]">Lane Risk ({candidate.lane}):</span>
                <span className={`font-semibold ${validation.projectedLaneRiskR > validation.laneRiskCapR ? 'text-[#C25B6B]' : 'text-[#E7EAEE]'}`}>
                  {validation.projectedLaneRiskR}R / {validation.laneRiskCapR.toFixed(1)}R ({laneRiskPct}%)
                </span>
              </div>
              <div className="w-full bg-[#161C26] h-2 rounded-[1px] overflow-hidden border border-[#232A35]">
                <div 
                  className={`h-full transition-all duration-300 ${validation.projectedLaneRiskR > validation.laneRiskCapR ? 'bg-[#C25B6B]' : laneRiskPct > 80 ? 'bg-[#BFA13B]' : 'bg-[#4FAE86]'}`}
                  style={{ width: `${Math.min(100, laneRiskPct)}%` }}
                />
              </div>
            </div>

            {/* Account Exposure Gauge */}
            <div className="space-y-1">
              <div className="flex justify-between text-[11px]">
                <span className="text-[#6E7A8A]">Account Aggregate Exposure:</span>
                <span className={`font-semibold ${validation.projectedAccountExposureR > validation.accountExposureCapR ? 'text-[#C25B6B]' : 'text-[#E7EAEE]'}`}>
                  {validation.projectedAccountExposureR}R / {validation.accountExposureCapR.toFixed(1)}R ({expRiskPct}%)
                </span>
              </div>
              <div className="w-full bg-[#161C26] h-2 rounded-[1px] overflow-hidden border border-[#232A35]">
                <div 
                  className={`h-full transition-all duration-300 ${validation.projectedAccountExposureR > validation.accountExposureCapR ? 'bg-[#C25B6B]' : expRiskPct > 80 ? 'bg-[#BFA13B]' : 'bg-[#4FAE86]'}`}
                  style={{ width: `${Math.min(100, expRiskPct)}%` }}
                />
              </div>
            </div>

            {/* Daily Loss Status */}
            <div className="flex justify-between text-[11px] p-2 bg-[#161C26] rounded-[2px] border border-[#232A35]">
              <span className="text-[#6E7A8A]">Daily P&amp;L vs Loss Cap:</span>
              <span className={`font-semibold ${dailyPnl < -riskConfig.dailyLossLimitUsd ? 'text-[#C25B6B]' : 'text-[#4FAE86]'}`}>
                {dailyPnl >= 0 ? '+' : ''}${dailyPnl.toFixed(2)} (Cap: -${riskConfig.dailyLossLimitUsd.toFixed(2)})
              </span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-2.5 border-t border-[#232A35] bg-[#161C26]">
          <span className="text-[10px] font-mono text-[#6E7A8A]">
            Authority: OperationalRiskConfig ({riskConfig.effectiveConfigId})
          </span>
          <button
            type="button"
            onClick={onClose}
            className="min-h-[32px] px-3 py-1 bg-[#232A35] hover:bg-[#2C3542] text-[#E7EAEE] font-mono text-xs rounded-[2px] cursor-pointer"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
};
