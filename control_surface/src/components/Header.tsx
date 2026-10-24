import React, { useState } from 'react';
import { Settings, Bell, Activity, AlertTriangle, Clock, Sliders, X } from 'lucide-react';
import { TelemetryProvenance, ApplicationMode } from '../types/contracts';
import { LatencyMetrics } from '../types';

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
  latency?: LatencyMetrics;
  onUpdateLatencyDelay?: (delayMs: number) => void;
}

const DEFAULT_LATENCY: LatencyMetrics = {
  lastRttMs: null,
  avgRttMs: null,
  minRttMs: null,
  maxRttMs: null,
  sampleCount: 0,
  warningThresholdMs: 250,
  criticalThresholdMs: 500,
  status: 'NO_DATA',
  lastMeasuredAt: null,
  injectedDelayMs: 0,
  measuredExecutionTimeMs: null,
  metricName: 'SIMULATED COMMAND-PROCESSING TIME',
};

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
  latency = DEFAULT_LATENCY,
  onUpdateLatencyDelay,
}) => {
  const [isLatencyOpen, setIsLatencyOpen] = useState(false);

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

  const getLatencyStyle = (status: LatencyMetrics['status']) => {
    switch (status) {
      case 'EXCEEDED':
        return {
          dot: 'bg-[#C25B6B] animate-pulse',
          badge: 'border-[#B23B3B]/60 bg-[#B23B3B]/20 text-[#C25B6B]',
          text: 'text-[#C25B6B]',
          label: 'EXCEEDED',
        };
      case 'ELEVATED':
        return {
          dot: 'bg-[#BFA13B]',
          badge: 'border-[#BFA13B]/50 bg-[#BFA13B]/15 text-[#BFA13B]',
          text: 'text-[#BFA13B]',
          label: 'ELEVATED',
        };
      case 'STALE':
        return {
          dot: 'bg-[#BFA13B] animate-pulse',
          badge: 'border-[#BFA13B]/50 bg-[#BFA13B]/15 text-[#BFA13B]',
          text: 'text-[#BFA13B]',
          label: 'STALE',
        };
      case 'INVALID':
        return {
          dot: 'bg-[#C25B6B]',
          badge: 'border-[#B23B3B]/60 bg-[#B23B3B]/20 text-[#C25B6B]',
          text: 'text-[#C25B6B]',
          label: 'INVALID',
        };
      case 'NO_DATA':
        return {
          dot: 'bg-[#6E7A8A]',
          badge: 'border-[#6E7A8A]/30 bg-[#161C26] text-[#6E7A8A]',
          text: 'text-[#6E7A8A]',
          label: 'NO DATA',
        };
      case 'NOMINAL':
      default:
        return {
          dot: 'bg-[#4FAE86]',
          badge: 'border-[#4FAE86]/40 bg-[#4FAE86]/10 text-[#4FAE86]',
          text: 'text-[#4FAE86]',
          label: 'NOMINAL',
        };
    }
  };

  const statusColorClass = getStatusColor();
  const latencyStyle = getLatencyStyle(latency.status);
  const isLatencyDelayed = latency.status === 'ELEVATED' || latency.status === 'EXCEEDED';
  const displayRttText = latency.lastRttMs !== null ? `${latency.lastRttMs}ms` : '--ms';

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

          {/* Mobile Real-Time Latency Monitor */}
          <button
            type="button"
            onClick={() => setIsLatencyOpen((prev) => !prev)}
            data-testid="latency-monitor-mobile"
            aria-label={`Simulated command processing time: ${displayRttText} status ${latency.status}`}
            className="min-h-[44px] px-2 flex items-center gap-1 text-[10px] font-mono text-[#6E7A8A] border border-[#232A35] bg-[#161C26] rounded-[2px]"
          >
            <span className={`w-1.5 h-1.5 rounded-full ${latencyStyle.dot}`} />
            <span className={`font-semibold ${latencyStyle.text}`}>{displayRttText}</span>
            {isLatencyDelayed && (
              <span data-testid="latency-warning-badge-mobile" className="text-[#C25B6B]">
                ⚠️
              </span>
            )}
          </button>

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
      <header className="hidden md:flex items-center gap-3 px-4 h-12 border-b border-[#232A35] bg-[#10151D] shrink-0 select-none overflow-x-auto">
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

        {/* Real-Time Command Execution Latency Monitor (Desktop) */}
        <div className="relative shrink-0">
          <button
            type="button"
            onClick={() => setIsLatencyOpen((prev) => !prev)}
            data-testid="latency-monitor"
            data-latency-status={latency.status}
            title="Inspect simulated command-processing latency & delay thresholds"
            className="flex items-center gap-2 px-2 py-1 rounded-[2px] border border-[#232A35] hover:border-[#5B8FBF] bg-[#161C26] text-[11px] font-mono cursor-pointer transition-colors"
          >
            <Activity className={`w-3.5 h-3.5 ${latencyStyle.text}`} />
            <div className="flex items-center gap-1.5">
              <span className="text-[#6E7A8A] text-[10px]">SIM RTT:</span>
              <span className={`font-semibold tabular-nums ${latencyStyle.text}`}>
                {displayRttText}
              </span>
              <span className={`px-1 py-0.2 text-[9px] rounded-[2px] border ${latencyStyle.badge}`}>
                {latencyStyle.label}
              </span>
            </div>
          </button>

          {/* Visual Warning Badge when delay exceeds threshold */}
          {isLatencyDelayed && (
            <div
              data-testid="latency-warning-badge"
              className="absolute -top-2 -right-2 flex items-center gap-1 px-1.5 py-0.5 rounded-[2px] bg-[#B23B3B] text-[#FFFFFF] text-[9px] font-mono font-bold shadow-md animate-bounce"
            >
              <AlertTriangle className="w-2.5 h-2.5" />
              <span>DELAY &gt; {latency.status === 'EXCEEDED' ? latency.criticalThresholdMs : latency.warningThresholdMs}ms</span>
            </div>
          )}
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
          LOCAL SESSION (NON-AUTH)
        </div>
      </header>

      {/* Latency Monitor Flyout Dialog */}
      {isLatencyOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Command Execution Latency Monitor"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4"
        >
          <div className="w-full max-w-md bg-[#10151D] border border-[#232A35] rounded-[3px] shadow-2xl p-4 font-mono text-xs space-y-4">
            <div className="flex items-center justify-between border-b border-[#232A35] pb-2">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-[#5B8FBF]" />
                <h3 className="font-semibold text-[#E7EAEE] uppercase tracking-wider text-[11px]">
                  Simulated Command-Processing Telemetry
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setIsLatencyOpen(false)}
                className="p-1 text-[#6E7A8A] hover:text-[#E7EAEE]"
                aria-label="Close latency monitor dialog"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Threshold Warning Banner */}
            {isLatencyDelayed && (
              <div 
                data-testid="latency-dialog-warning"
                className={`p-2.5 rounded-[2px] border flex items-center gap-2 ${
                  latency.status === 'EXCEEDED' 
                    ? 'bg-[#B23B3B]/15 text-[#C25B6B] border-[#B23B3B]/40' 
                    : 'bg-[#BFA13B]/15 text-[#BFA13B] border-[#BFA13B]/40'
                }`}
              >
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>
                  Visual Warning Active: Processing delay ({displayRttText}) exceeds{' '}
                  {latency.status === 'EXCEEDED' ? `critical threshold (${latency.criticalThresholdMs}ms)` : `warning threshold (${latency.warningThresholdMs}ms)`}.
                </span>
              </div>
            )}

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 gap-2 bg-[#161C26] p-3 rounded-[2px] border border-[#232A35]">
              <div>
                <span className="text-[10px] text-[#6E7A8A] block">LAST COMMAND DURATION</span>
                <span className={`text-base font-bold ${latencyStyle.text}`}>{displayRttText}</span>
              </div>
              <div>
                <span className="text-[10px] text-[#6E7A8A] block">ROLLING AVG DURATION</span>
                <span className="text-base font-bold text-[#E7EAEE]">
                  {latency.avgRttMs !== null ? `${latency.avgRttMs}ms` : '--'}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-[#6E7A8A] block">MIN / MAX RECORDED</span>
                <span className="text-[#6E7A8A]">
                  {latency.minRttMs !== null ? `${latency.minRttMs}ms / ${latency.maxRttMs}ms` : '--'}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-[#6E7A8A] block">TOTAL SAMPLES</span>
                <span className="text-[#6E7A8A]">{latency.sampleCount} commands</span>
              </div>
            </div>

            {/* Threshold Settings Info */}
            <div className="p-2.5 bg-[#161C26]/60 border border-[#232A35] rounded-[2px] space-y-1.5 text-[11px]">
              <div className="flex justify-between">
                <span className="text-[#6E7A8A]">Nominal Target:</span>
                <span className="text-[#4FAE86]">&lt; {latency.warningThresholdMs}ms</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#6E7A8A]">Warning Threshold:</span>
                <span className="text-[#BFA13B]">&gt;= {latency.warningThresholdMs}ms</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#6E7A8A]">Critical Threshold:</span>
                <span className="text-[#C25B6B]">&gt;= {latency.criticalThresholdMs}ms</span>
              </div>
            </div>

            {/* Interactive Delay Injector for Testing */}
            {onUpdateLatencyDelay && (
              <div className="p-3 bg-[#161C26] border border-[#232A35] rounded-[2px] space-y-2">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-[#6E7A8A] flex items-center gap-1">
                    <Sliders className="w-3.5 h-3.5 text-[#5B8FBF]" />
                    Inject Simulated Latency Jitter:
                  </span>
                  <span className="font-bold text-[#5B8FBF]">+{latency.injectedDelayMs || 0}ms</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="700"
                  step="50"
                  value={latency.injectedDelayMs || 0}
                  onChange={(e) => onUpdateLatencyDelay(parseInt(e.target.value, 10))}
                  aria-label="Simulated latency delay in milliseconds"
                  className="w-full accent-[#5B8FBF] cursor-pointer"
                />
                <div className="flex justify-between text-[9px] text-[#6E7A8A]">
                  <span>0ms (Nominal)</span>
                  <span>250ms (Elevated)</span>
                  <span>550ms+ (Exceeded Warning)</span>
                </div>
              </div>
            )}

            <div className="flex justify-end pt-1">
              <button
                type="button"
                onClick={() => setIsLatencyOpen(false)}
                className="min-h-[32px] px-3 py-1 bg-[#232A35] hover:bg-[#2C3542] text-[#E7EAEE] rounded-[2px] cursor-pointer"
              >
                Close Monitor
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
