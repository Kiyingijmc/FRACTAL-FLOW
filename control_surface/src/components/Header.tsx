import React from 'react';
import { Settings, Bell } from 'lucide-react';
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
  onOpenSettings?: () => void;
  onOpenNotifications?: () => void;
  unreadNotificationsCount?: number;
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
  onOpenSettings,
  onOpenNotifications,
  unreadNotificationsCount = 1,
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
    <>
      {/* Mobile Two-Deck Header (< 768px) */}
      <header className="flex flex-col md:hidden bg-[#10151D] border-b border-[#232A35] shrink-0 select-none px-3 py-2 space-y-2">
        {/* Top Deck: Brand, Mode Badge, Telemetry, and Sim Tick Toggle */}
        <div className="flex items-center justify-between gap-2">
          <div className="text-xs tracking-[0.2px] text-[#E7EAEE] font-semibold flex items-center gap-1 shrink-0">
            FRACTAL&#8209;FLOW
            <span className="text-[#6E7A8A] font-normal text-[10px]">gui</span>
          </div>

          {/* Operational Mode Boundary Badge (Safety Critical: P0 Live Separation) */}
          <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-[2px] border border-[#BFA13B]/50 bg-[#BFA13B]/10 text-[#BFA13B] font-mono text-[9px] tracking-tight shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-[#BFA13B]" />
            <span>SIM: OFF-BROKER</span>
          </div>

          {/* Telemetry Status Dot & Source */}
          <div className="flex items-center gap-1.5 font-mono text-[10px] text-[#6E7A8A] shrink-0">
            <span className={`w-2 h-2 rounded-full ${statusColorClass.split(' ')[0]}`} />
            <span className="text-[9px] text-[#5B8FBF] uppercase">{telemetry.status}</span>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {/* Notifications Trigger */}
            <button
              type="button"
              onClick={onOpenNotifications}
              data-testid="notifications-trigger"
              className="relative min-h-[44px] min-w-[36px] flex items-center justify-center p-1.5 text-[#6E7A8A] hover:text-[#E7EAEE] border border-[#232A35] bg-[#161C26] rounded-[2px]"
              aria-label="Open notifications center"
            >
              <Bell className="w-3.5 h-3.5" />
              {unreadNotificationsCount > 0 && (
                <span className="absolute top-1 right-1 w-2 h-2 bg-[#B23B3B] rounded-full" />
              )}
            </button>

            {/* Settings Trigger */}
            <button
              type="button"
              onClick={onOpenSettings}
              data-testid="settings-trigger"
              className="min-h-[44px] min-w-[36px] flex items-center justify-center p-1.5 text-[#6E7A8A] hover:text-[#E7EAEE] border border-[#232A35] bg-[#161C26] rounded-[2px]"
              aria-label="Open system settings"
            >
              <Settings className="w-3.5 h-3.5" />
            </button>

            {/* Sim Tick Control with min 44px touch target */}
            <button
              type="button"
              onClick={onToggleSimPause}
              title={isSimPaused ? 'Resume simulated tick stream' : 'Pause simulated tick stream'}
              className="min-h-[44px] min-w-[44px] px-2 py-1 text-[10px] font-mono rounded-[2px] border border-[#232A35] bg-[#161C26] text-[#6E7A8A] hover:text-[#E7EAEE] active:bg-[#232A35] transition-colors cursor-pointer shrink-0 flex items-center justify-center"
            >
              {isSimPaused ? '▶' : '⏸'}
            </button>
          </div>
        </div>

        {/* Bottom Deck: Lane Selector & Compact KPIs */}
        <div className="flex items-center justify-between gap-2 pt-1 border-t border-[#232A35]/60 overflow-x-auto">
          {/* Lane Selector */}
          <select
            value={lane}
            onChange={(e) => onLaneChange(e.target.value)}
            className="min-h-[36px] font-mono text-[11px] bg-[#161C26] border border-[#232A35] text-[#E7EAEE] px-2 py-1 rounded-[2px] cursor-pointer outline-none focus:border-[#5B8FBF] shrink-0"
          >
            <option value="ACT_PRIMARY">ACT_PRIMARY</option>
            <option value="ACT_SECONDARY">ACT_SECONDARY</option>
          </select>

          {/* Compact KPIs */}
          <div className="flex items-center gap-3 font-mono text-[11px] shrink-0">
            <div className="text-right">
              <span className="text-[9px] text-[#6E7A8A] block">eq (sim)</span>
              <span className="text-[#E7EAEE] tabular-nums font-semibold">
                ${(equity / 1000).toFixed(1)}k
              </span>
            </div>
            <div className="text-right">
              <span className="text-[9px] text-[#6E7A8A] block">p&amp;l (sim)</span>
              <span className={`tabular-nums font-semibold ${dailyPnl >= 0 ? 'text-[#4FAE86]' : 'text-[#C25B6B]'}`}>
                {dailyPnl >= 0 ? '+' : ''}${dailyPnl.toFixed(0)}
              </span>
            </div>
            <div className="text-right">
              <span className="text-[9px] text-[#6E7A8A] block">risk (sim)</span>
              <span className="text-[#E7EAEE] tabular-nums font-semibold">
                {openRiskR.toFixed(1)}R
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Desktop Single-Deck Header (>= 768px) */}
      <header className="hidden md:flex items-center gap-4 px-4 h-12 border-b border-[#232A35] bg-[#10151D] shrink-0 select-none overflow-x-auto">
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
        <div className="flex gap-4 items-center shrink-0">
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

        {/* Notification Bell & Settings Triggers */}
        <div className="flex items-center gap-1.5 border-l border-[#232A35] pl-3 shrink-0">
          <button
            type="button"
            onClick={onOpenNotifications}
            data-testid="settings-trigger-desktop-notif"
            className="relative p-1.5 text-[#6E7A8A] hover:text-[#E7EAEE] border border-transparent hover:border-[#232A35] hover:bg-[#161C26] rounded-[2px] transition-colors"
            title="Notification Center & Alert Log"
            aria-label="Open notifications center"
          >
            <Bell className="w-4 h-4" />
            {unreadNotificationsCount > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 bg-[#B23B3B] rounded-full" />
            )}
          </button>

          <button
            type="button"
            onClick={onOpenSettings}
            data-testid="settings-trigger"
            className="p-1.5 text-[#6E7A8A] hover:text-[#E7EAEE] border border-transparent hover:border-[#232A35] hover:bg-[#161C26] rounded-[2px] transition-colors"
            title="System Settings & Operational Risk Configuration"
            aria-label="Open system settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>

        <div className="text-xs text-[#6E7A8A] border-l border-[#232A35] pl-3 whitespace-nowrap shrink-0">
          daniel · OPERATOR
        </div>
      </header>
    </>
  );
};
