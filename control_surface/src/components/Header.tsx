import React from 'react';
import { TelemetryProvenance, ApplicationMode } from '../types/contracts';

interface HeaderProps {
  equity: number;
  dailyPnl: number;
  openRiskR: number;
  lane: string;
  onLaneChange: (lane: string) => void;
  isSimPaused: boolean;
  onToggleSimPause: () => void;
  telemetry: TelemetryProvenance;
  applicationMode: ApplicationMode;
}

export const Header: React.FC<HeaderProps> = ({
  equity,
  dailyPnl,
  openRiskR,
  lane,
  onLaneChange,
  isSimPaused,
  onToggleSimPause,
  telemetry,
  applicationMode,
}) => {
  const getStatusColor = () => {
    switch (telemetry.status) {
      case 'HEALTHY':
        return 'bg-[#4FAE86] text-[#4FAE86]';
      case 'STALE':
        return 'bg-[#BFA13B] text-[#BFA13B] animate-pulse';
      case 'DISCONNECTED':
      case 'DEGRADED':
        return 'bg-[#C25B6B] text-[#C25B6B]';
      default:
        return 'bg-[#6E7A8A] text-[#6E7A8A]';
    }
  };

  const statusColorClass = getStatusColor();

  return (
    <header className="flex items-center gap-4 px-4 h-12 border-b border-[#232A35] bg-[#10151D] shrink-0 select-none overflow-x-auto">
      {/* Brand */}
      <div className="text-[13px] tracking-[0.2px] text-[#E7EAEE] font-semibold flex items-center gap-1.5 whitespace-nowrap shrink-0">
        FRACTAL&#8209;FLOW
        <span className="text-[#6E7A8A] font-normal">control surface</span>
      </div>

      {/* Operational Mode Boundary Badge (P0 Separation of Authority) */}
      <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-[2px] border border-[#BFA13B]/40 bg-[#BFA13B]/10 text-[#BFA13B] font-mono text-[10px] tracking-wide whitespace-nowrap shrink-0">
        <span className="w-1.5 h-1.5 rounded-full bg-[#BFA13B]" />
        <span>MODE: {applicationMode.replace('_', ' ')} (OFF-BROKER)</span>
      </div>

      {/* Lane Selector */}
      <select
        value={lane}
        onChange={(e) => onLaneChange(e.target.value)}
        className="font-mono text-xs bg-[#161C26] border border-[#232A35] text-[#E7EAEE] px-2.5 py-1 rounded-[2px] cursor-pointer outline-none focus:border-[#5B8FBF] shrink-0"
      >
        <option value="ACT_PRIMARY">ACT_PRIMARY — EURUSD,GBPUSD,USDJPY</option>
        <option value="ACT_SECONDARY">ACT_SECONDARY — AUDUSD,USDCAD</option>
      </select>

      {/* Health & Provenance */}
      <div className="flex items-center gap-2 font-mono text-[11px] text-[#6E7A8A] whitespace-nowrap shrink-0">
        <span className={`w-1.5 h-1.5 rounded-full ${statusColorClass.split(' ')[0]} inline-block`} />
        <span>
          {telemetry.status === 'HEALTHY' 
            ? `${telemetry.bridgeStatus} · ${telemetry.fenceStatus} · ep ${telemetry.epoch}`
            : `TELEMETRY ${telemetry.status}`
          }
        </span>
        <span className="px-1 py-0.2 rounded border border-[#232A35] bg-[#161C26] text-[9px] text-[#5B8FBF]">
          SRC: {telemetry.source}
        </span>
        <span className="px-1 py-0.2 rounded border border-[#232A35] bg-[#161C26] text-[9px] text-[#6E7A8A]">
          AUTH: {telemetry.isAuthoritative ? 'LIVE' : 'NO (SIM)'}
        </span>
      </div>

      {/* Sim Tick Control */}
      <button
        onClick={onToggleSimPause}
        title={isSimPaused ? 'Resume simulated tick stream' : 'Pause simulated tick stream'}
        className="px-2 py-0.5 text-[10px] font-mono rounded-[2px] border border-[#232A35] bg-[#161C26] text-[#6E7A8A] hover:text-[#E7EAEE] transition-colors cursor-pointer shrink-0"
      >
        {isSimPaused ? '▶ RESUME TICKS' : '⏸ PAUSE TICKS'}
      </button>

      <div className="flex-1" />

      {/* Summary KPI Cards with [SIM] indicator */}
      <div className="flex gap-5 items-center shrink-0">
        <div className="text-right">
          <div className="text-[10px] text-[#6E7A8A]">equity (sim)</div>
          <div className="font-mono text-[15px] text-[#E7EAEE] tabular-nums">
            ${equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>

        <div className="text-right">
          <div className="text-[10px] text-[#6E7A8A]">daily P&amp;L (sim)</div>
          <div className={`font-mono text-[15px] tabular-nums ${dailyPnl >= 0 ? 'text-[#4FAE86]' : 'text-[#C25B6B]'}`}>
            {dailyPnl >= 0 ? '+' : ''}${dailyPnl.toFixed(2)}
          </div>
        </div>

        <div className="text-right">
          <div className="text-[10px] text-[#6E7A8A]">open risk (sim)</div>
          <div className="font-mono text-[15px] text-[#E7EAEE] tabular-nums">
            {openRiskR.toFixed(1)}R
          </div>
        </div>
      </div>

      <div className="text-xs text-[#6E7A8A] border-l border-[#232A35] pl-3.5 whitespace-nowrap shrink-0">
        daniel · OPERATOR
      </div>
    </header>
  );
};
