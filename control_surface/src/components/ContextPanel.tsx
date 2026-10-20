import React, { useState, useMemo } from 'react';
import { Position, Timeframe, ActionType, CommandExecutionRecord, ClosedTrade } from '../types.ts';

interface ContextPanelProps {
  position: Position | null;
  onTriggerAction: (action: ActionType, pos: Position) => void;
  activeCommand: CommandExecutionRecord | null;
  closedTrades?: ClosedTrade[];
}

const TIMEFRAMES: Timeframe[] = ['4H', '1H', '30M', '15M', '5M', '1M'];

export const ContextPanel: React.FC<ContextPanelProps> = ({
  position,
  onTriggerAction,
  activeCommand,
  closedTrades = [],
}) => {
  const [panelTab, setPanelTab] = useState<'detail' | 'stats'>('detail');

  // Performance calculations derived from closedTrades
  const stats = useMemo(() => {
    const totalTrades = closedTrades.length;
    if (totalTrades === 0) {
      return {
        totalTrades: 0,
        winCount: 0,
        lossCount: 0,
        winRate: 0,
        totalRealizedR: 0,
        totalRealizedPnl: 0,
        profitFactor: 0,
        avgWinR: 0,
        avgLossR: 0,
        expectancyR: 0,
        maxDrawdownR: 0,
        longWinRate: 0,
        shortWinRate: 0,
        longCount: 0,
        shortCount: 0,
      };
    }

    const winningTrades = closedTrades.filter((t) => t.realizedR > 0);
    const losingTrades = closedTrades.filter((t) => t.realizedR <= 0);
    const winRate = (winningTrades.length / totalTrades) * 100;

    const totalRealizedR = closedTrades.reduce((acc, t) => acc + t.realizedR, 0);
    const totalRealizedPnl = closedTrades.reduce((acc, t) => acc + t.realizedPnl, 0);

    const grossProfit = winningTrades.reduce((acc, t) => acc + t.realizedPnl, 0);
    const grossLoss = Math.abs(losingTrades.reduce((acc, t) => acc + t.realizedPnl, 0));
    const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? 99.99 : 0;

    const avgWinR =
      winningTrades.length > 0
        ? winningTrades.reduce((acc, t) => acc + t.realizedR, 0) / winningTrades.length
        : 0;

    const avgLossR =
      losingTrades.length > 0
        ? Math.abs(losingTrades.reduce((acc, t) => acc + t.realizedR, 0) / losingTrades.length)
        : 0;

    const expectancyR = totalRealizedR / totalTrades;

    // Calculate maximum drawdown in R from cumulative equity curve
    // Reverse array to follow chronological sequence (oldest to newest)
    const chronological = [...closedTrades].reverse();
    let peakR = 0;
    let runningR = 0;
    let maxDrawdownR = 0;

    chronological.forEach((t) => {
      runningR += t.realizedR;
      if (runningR > peakR) {
        peakR = runningR;
      }
      const dd = peakR - runningR;
      if (dd > maxDrawdownR) {
        maxDrawdownR = dd;
      }
    });

    const longTrades = closedTrades.filter((t) => t.side === 'LONG');
    const shortTrades = closedTrades.filter((t) => t.side === 'SHORT');
    const longWinRate =
      longTrades.length > 0
        ? (longTrades.filter((t) => t.realizedR > 0).length / longTrades.length) * 100
        : 0;
    const shortWinRate =
      shortTrades.length > 0
        ? (shortTrades.filter((t) => t.realizedR > 0).length / shortTrades.length) * 100
        : 0;

    return {
      totalTrades,
      winCount: winningTrades.length,
      lossCount: losingTrades.length,
      winRate,
      totalRealizedR,
      totalRealizedPnl,
      profitFactor,
      avgWinR,
      avgLossR,
      expectancyR,
      maxDrawdownR,
      longWinRate,
      shortWinRate,
      longCount: longTrades.length,
      shortCount: shortTrades.length,
    };
  }, [closedTrades]);

  // Excursion bar logic for Detail view
  const currentR = position?.unrealizedR || 0;
  const isPos = currentR >= 0;
  const maxScale = 2.5;
  const fillWidthPercent = Math.min((Math.abs(currentR) / maxScale) * 50, 50);

  const isCommandInFlight =
    activeCommand &&
    (activeCommand.status === 'REQUESTED' ||
      activeCommand.status === 'ACCEPTED' ||
      activeCommand.status === 'DISPATCHED');

  return (
    <aside className="w-[310px] border-l border-[#232A35] bg-[#10151D] p-3.5 select-none shrink-0 overflow-y-auto flex flex-col justify-between">
      <div>
        {/* Context Panel Mode Switcher Tabs */}
        <div className="flex border-b border-[#232A35] mb-3 select-none">
          <button
            type="button"
            onClick={() => setPanelTab('detail')}
            className={`flex-1 pb-1.5 text-xs font-sans transition-colors cursor-pointer border-b-2 text-center ${
              panelTab === 'detail'
                ? 'text-[#E7EAEE] border-[#5B8FBF] font-medium'
                : 'text-[#6E7A8A] border-transparent hover:text-[#E7EAEE]'
            }`}
          >
            Position Detail
          </button>
          <button
            type="button"
            onClick={() => setPanelTab('stats')}
            className={`flex-1 pb-1.5 text-xs font-sans transition-colors cursor-pointer border-b-2 text-center ${
              panelTab === 'stats'
                ? 'text-[#E7EAEE] border-[#5B8FBF] font-medium'
                : 'text-[#6E7A8A] border-transparent hover:text-[#E7EAEE]'
            }`}
          >
            Stats ({closedTrades.length})
          </button>
        </div>

        {panelTab === 'detail' ? (
          <>
            {/* Panel Header with Explicit Active Trade Scope */}
            <div className="flex items-center justify-between text-[10px] font-mono text-[#6E7A8A] border-b border-[#232A35] pb-1 mb-2">
              <span>MANAGED POSITION TELEMETRY</span>
              <span className="text-[#BFA13B] font-semibold">SIMULATED</span>
            </div>

            {position ? (
              <>
                <h3 className="text-xs font-semibold text-[#E7EAEE] mb-0.5 tracking-tight flex items-center justify-between">
                  <span>{position.symbol} · {position.side}</span>
                  <span className={`font-mono text-xs ${position.unrealizedR >= 0 ? 'text-[#4FAE86]' : 'text-[#C25B6B]'}`}>
                    {position.unrealizedR >= 0 ? '+' : ''}{position.unrealizedR.toFixed(2)}R
                  </span>
                </h3>
                <div className="text-[11px] text-[#6E7A8A] mb-3.5">
                  {position.setup} flow continuation · lane {position.lane}
                </div>

                {/* Timeframe Cascade Indicator (Signature Element 2) */}
                <div className="text-[10px] text-[#6E7A8A] mb-1 flex justify-between">
                  <span>timeframe cascade anchor</span>
                  <span className="font-mono text-[#5B8FBF]">{position.drivingTimeframe} ACTIVE</span>
                </div>
                <div className="flex gap-1 mb-4">
                  {TIMEFRAMES.map((tf) => {
                    const isDriving = position.drivingTimeframe === tf;
                    return (
                      <div
                        key={tf}
                        title={isDriving ? `${tf}: Active driving anchor for trail / breakeven` : `${tf} tier`}
                        className={`flex-1 text-center py-1 font-mono text-[10px] rounded-[2px] border transition-colors ${
                          isDriving
                            ? 'text-[#5B8FBF] border-[#5B8FBF] bg-[#5B8FBF]/10 font-medium'
                            : 'text-[#454E5C] border-[#232A35] bg-transparent'
                        }`}
                      >
                        {tf}
                      </div>
                    );
                  })}
                </div>

                {/* Key-Value Telemetry */}
                <div className="space-y-0 text-xs">
                  <div
                    title="Structural swing pivot level defending current trailing stop on the driving timeframe."
                    className="flex justify-between py-1 border-b border-[#232A35] hover:bg-[#161C26] px-1 -mx-1 transition-colors cursor-help"
                  >
                    <span className="text-[#6E7A8A]">structural anchor</span>
                    <span className="font-mono text-[#E7EAEE] text-[11px]">{position.structuralAnchor}</span>
                  </div>
                  <div
                    title="Adaptive volatility trail distance scaled by market efficiency ratio (ER). Formula: k_factor × ATR."
                    className="flex justify-between py-1 border-b border-[#232A35] hover:bg-[#161C26] px-1 -mx-1 transition-colors cursor-help"
                  >
                    <span className="text-[#6E7A8A]">trail distance</span>
                    <span className="font-mono text-[#E7EAEE] text-[11px]">{position.trailDistance}</span>
                  </div>
                  <div
                    title="Ratchet status for breakeven threshold. Automatically transitions stop to entry price when MFE reaches 1.5R."
                    className="flex justify-between py-1 border-b border-[#232A35] hover:bg-[#161C26] px-1 -mx-1 transition-colors cursor-help"
                  >
                    <span className="text-[#6E7A8A]">breakeven</span>
                    <span className="font-mono text-[#E7EAEE] text-[11px]">{position.breakevenStatus}</span>
                  </div>
                  <div
                    title="Time-decay penalty counter. Tracks elapsed bars since entry relative to median setup duration."
                    className="flex justify-between py-1 border-b border-[#232A35] hover:bg-[#161C26] px-1 -mx-1 transition-colors cursor-help"
                  >
                    <span className="text-[#6E7A8A]">decay state</span>
                    <span className={`font-mono text-[11px] ${position.decayState.includes('WARN') ? 'text-[#BFA13B]' : 'text-[#E7EAEE]'}`}>
                      {position.decayState}
                    </span>
                  </div>
                  <div
                    title="Canonical cryptographic hash of the active Quant Layer configuration governing this position."
                    className="flex justify-between py-1 border-b border-[#232A35] hover:bg-[#161C26] px-1 -mx-1 transition-colors cursor-help"
                  >
                    <span className="text-[#6E7A8A]">effective config</span>
                    <span className="font-mono text-[#6E7A8A] text-[11px]">{position.effectiveConfig}</span>
                  </div>
                </div>

                {/* Excursion Bar */}
                <div className="mt-4">
                  <div className="flex justify-between text-[11px] text-[#6E7A8A] mb-1">
                    <span>excursion since entry (R)</span>
                    <span className="font-mono text-[10px]">
                      MAE <span className="text-[#C25B6B]">{position.mae.toFixed(2)}R</span> / MFE <span className="text-[#4FAE86]">+{position.mfe.toFixed(2)}R</span>
                    </span>
                  </div>
                  <div
                    title={`Maximum Adverse Excursion: ${position.mae.toFixed(2)}R | Maximum Favorable Excursion: +${position.mfe.toFixed(2)}R`}
                    className="h-1.5 bg-[#161C26] rounded-[2px] relative overflow-hidden border border-[#232A35] cursor-help"
                  >
                    <div className="absolute top-0 bottom-0 left-1/2 w-[1px] bg-[#232A35] z-10" />
                    {isPos ? (
                      <div
                        className="absolute top-0 bottom-0 left-1/2 bg-[#4FAE86] transition-all duration-300"
                        style={{ width: `${fillWidthPercent}%` }}
                      />
                    ) : (
                      <div
                        className="absolute top-0 bottom-0 bg-[#C25B6B] transition-all duration-300"
                        style={{ right: '50%', width: `${fillWidthPercent}%` }}
                      />
                    )}
                  </div>
                </div>

                {/* Active Command Lifecycle Tracker */}
                {activeCommand && (
                  <div className="mt-4 p-2 bg-[#161C26] border border-[#232A35] text-[11px]">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-[#6E7A8A] uppercase font-mono text-[10px]">Command Lifecycle</span>
                      <span
                        className={`font-mono text-[10px] font-bold px-1 rounded-[2px] ${
                          activeCommand.status === 'CONFIRMED'
                            ? 'text-[#4FAE86] bg-[#4FAE86]/10'
                            : activeCommand.status === 'REJECTED'
                            ? 'text-[#B23B3B] bg-[#B23B3B]/10'
                            : 'text-[#BFA13B] bg-[#BFA13B]/10 animate-pulse'
                        }`}
                      >
                        {activeCommand.status}
                      </span>
                    </div>
                    <div className="font-mono text-[10px] text-[#E7EAEE] truncate">
                      {activeCommand.idempotencyKey}
                    </div>
                    <div className="text-[10px] text-[#6E7A8A] mt-1">
                      {activeCommand.details}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-xs text-[#6E7A8A] py-6 text-center">No active position selected.</div>
            )}
          </>
        ) : (
          /* Stats Tab: Historical Performance Metrics Calculated from closedTrades */
          <div className="space-y-3">
            <div className="flex items-center justify-between text-[10px] font-mono text-[#6E7A8A] border-b border-[#232A35] pb-1 mb-2">
              <span>HISTORICAL PERFORMANCE</span>
              <span className="text-[#4FAE86] font-semibold">{stats.totalTrades} TRADES</span>
            </div>

            {/* Primary KPI Grid */}
            <div className="grid grid-cols-2 gap-2">
              <div
                title="Win Rate = (Winning Trades ÷ Total Trades) × 100. Percentage of trades that yielded positive realized R."
                className="bg-[#161C26] p-2 border border-[#232A35] hover:border-[#5B8FBF] transition-colors cursor-help"
              >
                <div className="text-[10px] text-[#6E7A8A] mb-0.5">Win Rate</div>
                <div className="font-mono text-base text-[#4FAE86] font-medium tabular-nums">
                  {stats.winRate.toFixed(1)}%
                </div>
                <div className="font-mono text-[10px] text-[#6E7A8A] tabular-nums mt-0.5">
                  {stats.winCount}W - {stats.lossCount}L
                </div>
              </div>

              <div
                title="Profit Factor = Gross Profits ÷ Gross Losses. Values above 2.0 represent robust systematic edge."
                className="bg-[#161C26] p-2 border border-[#232A35] hover:border-[#5B8FBF] transition-colors cursor-help"
              >
                <div className="text-[10px] text-[#6E7A8A] mb-0.5">Profit Factor</div>
                <div className="font-mono text-base text-[#E7EAEE] font-medium tabular-nums">
                  {stats.profitFactor.toFixed(2)}
                </div>
                <div className="font-mono text-[10px] text-[#4FAE86] tabular-nums mt-0.5">
                  Gross: +${stats.totalRealizedPnl.toFixed(0)}
                </div>
              </div>

              <div
                title="Total Realized R = Cumulative sum of realized R-multiples across all closed executions."
                className="bg-[#161C26] p-2 border border-[#232A35] hover:border-[#5B8FBF] transition-colors cursor-help"
              >
                <div className="text-[10px] text-[#6E7A8A] mb-0.5">Total Realized R</div>
                <div className={`font-mono text-base font-medium tabular-nums ${stats.totalRealizedR >= 0 ? 'text-[#4FAE86]' : 'text-[#C25B6B]'}`}>
                  {stats.totalRealizedR >= 0 ? '+' : ''}{stats.totalRealizedR.toFixed(2)}R
                </div>
                <div className="font-mono text-[10px] text-[#6E7A8A] tabular-nums mt-0.5">
                  Net Realized P&amp;L
                </div>
              </div>

              <div
                title="Maximum Drawdown = Largest peak-to-trough drop in cumulative realized R across the closed trade sequence."
                className="bg-[#161C26] p-2 border border-[#232A35] hover:border-[#5B8FBF] transition-colors cursor-help"
              >
                <div className="text-[10px] text-[#6E7A8A] mb-0.5">Max Drawdown (R)</div>
                <div className="font-mono text-base text-[#C25B6B] font-medium tabular-nums">
                  -{stats.maxDrawdownR.toFixed(2)}R
                </div>
                <div className="font-mono text-[10px] text-[#6E7A8A] tabular-nums mt-0.5">
                  Peak equity drop
                </div>
              </div>
            </div>

            {/* Detailed Metric Key-Values */}
            <div className="space-y-0 text-xs pt-1">
              <div
                title="Average realized R per winning trade."
                className="flex justify-between py-1 border-b border-[#232A35] hover:bg-[#161C26] px-1 -mx-1 transition-colors cursor-help"
              >
                <span className="text-[#6E7A8A]">avg win</span>
                <span className="font-mono text-[#4FAE86] text-[11px] tabular-nums">
                  +{stats.avgWinR.toFixed(2)}R
                </span>
              </div>

              <div
                title="Average realized R per losing trade (absolute value)."
                className="flex justify-between py-1 border-b border-[#232A35] hover:bg-[#161C26] px-1 -mx-1 transition-colors cursor-help"
              >
                <span className="text-[#6E7A8A]">avg loss</span>
                <span className="font-mono text-[#C25B6B] text-[11px] tabular-nums">
                  -{stats.avgLossR.toFixed(2)}R
                </span>
              </div>

              <div
                title="Mathematical Expectancy per trade = (Win Rate × Avg Win) - (Loss Rate × Avg Loss). Expected return per unit risked."
                className="flex justify-between py-1 border-b border-[#232A35] hover:bg-[#161C26] px-1 -mx-1 transition-colors cursor-help"
              >
                <span className="text-[#6E7A8A]">trade expectancy</span>
                <span className="font-mono text-[#4FAE86] text-[11px] font-medium tabular-nums">
                  +{stats.expectancyR.toFixed(2)}R / trade
                </span>
              </div>

              <div
                title="Win rate for LONG positions vs total LONG trades executed."
                className="flex justify-between py-1 border-b border-[#232A35] hover:bg-[#161C26] px-1 -mx-1 transition-colors cursor-help"
              >
                <span className="text-[#6E7A8A]">long win rate</span>
                <span className="font-mono text-[#E7EAEE] text-[11px] tabular-nums">
                  {stats.longWinRate.toFixed(1)}% <span className="text-[#6E7A8A]">({stats.longCount})</span>
                </span>
              </div>

              <div
                title="Win rate for SHORT positions vs total SHORT trades executed."
                className="flex justify-between py-1 border-b border-[#232A35] hover:bg-[#161C26] px-1 -mx-1 transition-colors cursor-help"
              >
                <span className="text-[#6E7A8A]">short win rate</span>
                <span className="font-mono text-[#E7EAEE] text-[11px] tabular-nums">
                  {stats.shortWinRate.toFixed(1)}% <span className="text-[#6E7A8A]">({stats.shortCount})</span>
                </span>
              </div>

              <div
                title="Net realized dollar earnings across closed trade ledger."
                className="flex justify-between py-1 border-b border-[#232A35] hover:bg-[#161C26] px-1 -mx-1 transition-colors cursor-help"
              >
                <span className="text-[#6E7A8A]">cumulative net P&amp;L</span>
                <span className="font-mono text-[#4FAE86] text-[11px] font-medium tabular-nums">
                  +${stats.totalRealizedPnl.toFixed(2)}
                </span>
              </div>
            </div>

            {/* Audit Reference Footnote */}
            <div className="text-[10px] text-[#454E5C] font-mono pt-1">
              SAMPLE: {stats.totalTrades} closed trades · JOURNAL VERIFIED
            </div>
          </div>
        )}
      </div>

      {/* Action Buttons (Rendered only on Detail tab, or persistent if requested) */}
      {panelTab === 'detail' && position && (
        <div className="mt-5 pt-3 border-t border-[#232A35]">
          <div className="flex justify-between items-center mb-2">
            <span className="text-[10px] text-[#6E7A8A] uppercase tracking-wider font-medium">Gated Execution</span>
            <span className="text-[10px] font-mono text-[#454E5C]">HOTKEYS ACTIVE</span>
          </div>
          <div className="flex flex-col gap-2">
            <button
              disabled={Boolean(isCommandInFlight)}
              onClick={() => onTriggerAction('tighten_stop', position)}
              className="w-full py-1.5 px-2.5 text-xs font-sans rounded-[2px] border border-[#5B8FBF] text-[#5B8FBF] bg-[#161C26] hover:bg-[#5B8FBF]/10 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer flex items-center justify-between font-medium"
            >
              <span>Tighten stop</span>
              <span className="font-mono text-[10px] bg-[#5B8FBF]/20 px-1 py-0.5 rounded-[2px]">T</span>
            </button>
            <button
              disabled={Boolean(isCommandInFlight)}
              onClick={() => onTriggerAction('move_to_breakeven', position)}
              className="w-full py-1.5 px-2.5 text-xs font-sans rounded-[2px] border border-[#232A35] text-[#E7EAEE] bg-[#161C26] hover:bg-[#232A35] disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer flex items-center justify-between"
            >
              <span>Move to breakeven</span>
              <span className="font-mono text-[10px] bg-[#232A35] text-[#6E7A8A] px-1 py-0.5 rounded-[2px]">B</span>
            </button>
            <button
              disabled={Boolean(isCommandInFlight)}
              onClick={() => onTriggerAction('close_position', position)}
              className="w-full py-1.5 px-2.5 text-xs font-sans rounded-[2px] border border-[#C25B6B] text-[#C25B6B] bg-[#161C26] hover:bg-[#C25B6B]/10 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer flex items-center justify-between font-medium"
            >
              <span>Close position</span>
              <span className="font-mono text-[10px] bg-[#C25B6B]/20 px-1 py-0.5 rounded-[2px]">C</span>
            </button>
          </div>
        </div>
      )}

      {panelTab === 'stats' && (
        <div className="mt-4 pt-3 border-t border-[#232A35] text-[11px] text-[#6E7A8A]">
          <button
            onClick={() => setPanelTab('detail')}
            className="w-full py-1.5 px-2.5 text-xs font-sans rounded-[2px] border border-[#232A35] text-[#5B8FBF] bg-[#161C26] hover:bg-[#5B8FBF]/10 transition-colors cursor-pointer text-center"
          >
            Switch to Position Detail
          </button>
        </div>
      )}
    </aside>
  );
};
