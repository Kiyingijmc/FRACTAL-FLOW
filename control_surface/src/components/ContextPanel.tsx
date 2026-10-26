import React, { useState, useMemo } from 'react';
import { Position, Timeframe, ActionType, CommandExecutionRecord, ClosedTrade } from '../types';

interface ContextPanelProps {
  position: Position | null;
  onTriggerAction: (action: ActionType, pos: Position) => void;
  activeCommand: CommandExecutionRecord | null;
  closedTrades?: ClosedTrade[];
  onBackToTable?: () => void;
}

const TIMEFRAMES: Timeframe[] = ['4H', '1H', '30M', '15M', '5M', '1M'];

export const ContextPanel: React.FC<ContextPanelProps> = ({
  position,
  onTriggerAction,
  activeCommand,
  closedTrades = [],
  onBackToTable,
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
    const longWins = longTrades.filter((t) => t.realizedR > 0).length;
    const shortWins = shortTrades.filter((t) => t.realizedR > 0).length;

    const longWinRate = longTrades.length > 0 ? (longWins / longTrades.length) * 100 : 0;
    const shortWinRate = shortTrades.length > 0 ? (shortWins / shortTrades.length) * 100 : 0;

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

  const isCommandInFlight =
    activeCommand &&
    (activeCommand.status === 'REQUESTED' ||
      activeCommand.status === 'ACCEPTED' ||
      activeCommand.status === 'DISPATCHED');

  return (
    <aside className="w-full md:w-80 border-t md:border-t-0 md:border-l border-[#232A35] bg-[#10151D] p-3.5 flex flex-col justify-between shrink-0 overflow-y-auto">
      <div>
        {/* Mobile Navigation Header: Back to Positions */}
        {onBackToTable && (
          <div className="flex md:hidden items-center justify-between pb-2 mb-2 border-b border-[#232A35]">
            <button
              type="button"
              onClick={onBackToTable}
              className="min-h-[44px] px-3 py-1.5 text-xs font-sans font-medium text-[#5B8FBF] bg-[#161C26] hover:bg-[#5B8FBF]/15 border border-[#232A35] hover:border-[#5B8FBF] rounded-[2px] transition-colors cursor-pointer flex items-center gap-1.5"
            >
              <span>← Back to Positions</span>
            </button>
            <span className="font-mono text-[10px] text-[#6E7A8A]">
              {position?.symbol || 'NO SELECTION'}
            </span>
          </div>
        )}

        {/* Tab Switcher: Detail vs Stats */}
        <div className="flex border-b border-[#232A35] mb-3">
          <button
            type="button"
            onClick={() => setPanelTab('detail')}
            className={`min-h-[38px] flex-1 py-1 text-xs font-sans text-center transition-colors cursor-pointer border-b-2 ${
              panelTab === 'detail'
                ? 'text-[#E7EAEE] border-[#5B8FBF] font-medium bg-[#161C26]/30'
                : 'text-[#6E7A8A] border-transparent hover:text-[#E7EAEE]'
            }`}
          >
            Position detail
          </button>
          <button
            type="button"
            onClick={() => setPanelTab('stats')}
            className={`min-h-[38px] flex-1 py-1 text-xs font-sans text-center transition-colors cursor-pointer border-b-2 ${
              panelTab === 'stats'
                ? 'text-[#E7EAEE] border-[#5B8FBF] font-medium bg-[#161C26]/30'
                : 'text-[#6E7A8A] border-transparent hover:text-[#E7EAEE]'
            }`}
          >
            Performance stats
          </button>
        </div>

        {panelTab === 'detail' && (
          <>
            {position ? (
              <>
                {/* Header Info */}
                <div className="flex justify-between items-baseline mb-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-semibold text-[#E7EAEE]">
                      {position.symbol}
                    </span>
                    <span
                      className={`font-mono text-[10px] px-1.5 py-0.5 rounded-[2px] tracking-[0.3px] font-medium ${
                        position.side === 'LONG'
                          ? 'bg-[#4FAE86]/[0.16] text-[#4FAE86]'
                          : 'bg-[#C25B6B]/[0.16] text-[#C25B6B]'
                      }`}
                    >
                      {position.side}
                    </span>
                    <span className="text-[11px] text-[#6E7A8A]">{position.lane}</span>
                  </div>
                  <div className="font-mono text-xs text-[#6E7A8A]">
                    {position.mode} · {position.setup}
                  </div>
                </div>

                {/* In-Flight Command Lifecycle Banner */}
                {activeCommand && (
                  <div
                    className={`mb-3 p-2 rounded-[2px] border text-xs font-mono space-y-1 ${
                      activeCommand.status === 'CONFIRMED'
                        ? 'border-[#4FAE86]/40 bg-[#4FAE86]/10 text-[#4FAE86]'
                        : activeCommand.status === 'REJECTED'
                        ? 'border-[#C25B6B]/40 bg-[#C25B6B]/10 text-[#C25B6B]'
                        : 'border-[#5B8FBF]/40 bg-[#5B8FBF]/10 text-[#5B8FBF] animate-pulse'
                    }`}
                  >
                    <div className="flex justify-between items-center text-[10px]">
                      <span className="font-semibold uppercase tracking-wider">
                        {activeCommand.status}
                      </span>
                      <span>{activeCommand.requestedAt}</span>
                    </div>
                    <div className="text-[11px] truncate text-[#E7EAEE]">{activeCommand.details}</div>
                    <div className="text-[9px] text-[#6E7A8A] truncate">
                      IDEMP: {activeCommand.idempotencyKey.slice(0, 22)}...
                    </div>
                  </div>
                )}

                {/* Signature Element: Timeframe Cascade Strip */}
                <div className="mb-4">
                  <div className="text-[10px] text-[#6E7A8A] uppercase tracking-wider mb-1.5 font-medium">
                    Timeframe cascade
                  </div>
                  <div className="grid grid-cols-6 gap-1 text-center font-mono text-[10px]">
                    {TIMEFRAMES.map((tf) => {
                      const isDriving = tf === position.drivingTimeframe;
                      return (
                        <div
                          key={tf}
                          className={`py-1 rounded-[2px] border transition-colors ${
                            isDriving
                              ? 'border-[#5B8FBF] bg-[#5B8FBF]/15 text-[#5B8FBF] font-semibold'
                              : 'border-[#232A35] bg-[#161C26] text-[#6E7A8A]'
                          }`}
                        >
                          <div>{tf}</div>
                          <div className="text-[8px] mt-0.5">{isDriving ? 'DRIVE' : 'CONF'}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Key Metrics Grid */}
                <div className="space-y-1.5 text-xs">
                  <div className="flex justify-between py-1 border-b border-[#232A35]">
                    <span className="text-[#6E7A8A]">structural anchor</span>
                    <span className="font-mono text-[#E7EAEE] text-[11px]">{position.structuralAnchor}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#232A35]">
                    <span className="text-[#6E7A8A]">trail distance</span>
                    <span className="font-mono text-[#E7EAEE] text-[11px]">{position.trailDistance}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#232A35]">
                    <span className="text-[#6E7A8A]">breakeven status</span>
                    <span className="font-mono text-[#E7EAEE] text-[11px]">{position.breakevenStatus}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#232A35]">
                    <span className="text-[#6E7A8A]">decay state</span>
                    <span className="font-mono text-[#E7EAEE] text-[11px]">{position.decayState}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#232A35]">
                    <span className="text-[#6E7A8A]">effective config</span>
                    <span className="font-mono text-[#6E7A8A] text-[10px]">{position.effectiveConfig}</span>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-10 text-xs text-[#6E7A8A]">
                No position selected.
              </div>
            )}
          </>
        )}

        {/* Performance Statistics Tab */}
        {panelTab === 'stats' && (
          <div className="space-y-3">
            <div className="text-[10px] text-[#6E7A8A] uppercase tracking-wider font-medium">
              Closed Trade Ledger Stats
            </div>

            {/* Quick KPI Strip */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-[#161C26] p-2 border border-[#232A35]">
                <div className="text-[10px] text-[#6E7A8A]">Win Rate</div>
                <div className="font-mono text-base font-semibold text-[#4FAE86] tabular-nums">
                  {stats.winRate.toFixed(1)}%
                </div>
                <div className="text-[9px] text-[#6E7A8A]">{stats.winCount}W / {stats.lossCount}L</div>
              </div>
              <div className="bg-[#161C26] p-2 border border-[#232A35]">
                <div className="text-[10px] text-[#6E7A8A]">Profit Factor</div>
                <div className="font-mono text-base font-semibold text-[#4FAE86] tabular-nums">
                  {stats.profitFactor.toFixed(2)}
                </div>
                <div className="text-[9px] text-[#6E7A8A]">Total {stats.totalTrades} trades</div>
              </div>
            </div>

            {/* Detailed Metric Key-Values */}
            <div className="space-y-1 text-xs pt-1">
              <div className="flex justify-between py-1 border-b border-[#232A35]">
                <span className="text-[#6E7A8A]">avg win</span>
                <span className="font-mono text-[#4FAE86] text-[11px] tabular-nums">
                  +{stats.avgWinR.toFixed(2)}R
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#232A35]">
                <span className="text-[#6E7A8A]">avg loss</span>
                <span className="font-mono text-[#C25B6B] text-[11px] tabular-nums">
                  -{stats.avgLossR.toFixed(2)}R
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#232A35]">
                <span className="text-[#6E7A8A]">trade expectancy</span>
                <span className="font-mono text-[#4FAE86] text-[11px] font-medium tabular-nums">
                  +{stats.expectancyR.toFixed(2)}R / trade
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#232A35]">
                <span className="text-[#6E7A8A]">max drawdown</span>
                <span className="font-mono text-[#C25B6B] text-[11px] tabular-nums">
                  -{stats.maxDrawdownR.toFixed(2)}R
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#232A35]">
                <span className="text-[#6E7A8A]">long win rate</span>
                <span className="font-mono text-[#E7EAEE] text-[11px] tabular-nums">
                  {stats.longWinRate.toFixed(1)}% ({stats.longCount})
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#232A35]">
                <span className="text-[#6E7A8A]">short win rate</span>
                <span className="font-mono text-[#E7EAEE] text-[11px] tabular-nums">
                  {stats.shortWinRate.toFixed(1)}% ({stats.shortCount})
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#232A35]">
                <span className="text-[#6E7A8A]">cumulative net P&amp;L</span>
                <span className="font-mono text-[#4FAE86] text-[11px] font-medium tabular-nums">
                  +${stats.totalRealizedPnl.toFixed(2)}
                </span>
              </div>
            </div>

            <div className="text-[10px] text-[#454E5C] font-mono pt-1">
              SAMPLE: {stats.totalTrades} closed trades · JOURNAL VERIFIED
            </div>
          </div>
        )}
      </div>

      {/* Action Buttons with 44px minimum touch targets */}
      {panelTab === 'detail' && position && (
        <div className="mt-4 pt-3 border-t border-[#232A35]">
          <div className="flex justify-between items-center mb-2">
            <span className="text-[10px] text-[#6E7A8A] uppercase tracking-wider font-medium">
              Gated Execution
            </span>
            <span className="text-[10px] font-mono text-[#454E5C]">HOTKEYS ACTIVE</span>
          </div>
          <div className="flex flex-col gap-2">
            <button
              disabled={Boolean(isCommandInFlight)}
              onClick={() => onTriggerAction('tighten_stop', position)}
              className="w-full min-h-[44px] py-2 px-3 text-xs font-sans rounded-[2px] border border-[#5B8FBF] text-[#5B8FBF] bg-[#161C26] hover:bg-[#5B8FBF]/10 active:bg-[#5B8FBF]/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer flex items-center justify-between font-medium"
            >
              <span>Tighten stop</span>
              <span className="font-mono text-[10px] bg-[#5B8FBF]/20 px-1.5 py-0.5 rounded-[2px]">T</span>
            </button>
            <button
              disabled={Boolean(isCommandInFlight)}
              onClick={() => onTriggerAction('move_to_breakeven', position)}
              className="w-full min-h-[44px] py-2 px-3 text-xs font-sans rounded-[2px] border border-[#232A35] text-[#E7EAEE] bg-[#161C26] hover:bg-[#232A35] active:bg-[#232A35]/80 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer flex items-center justify-between"
            >
              <span>Move to breakeven</span>
              <span className="font-mono text-[10px] bg-[#232A35] text-[#6E7A8A] px-1.5 py-0.5 rounded-[2px]">B</span>
            </button>
            <button
              disabled={Boolean(isCommandInFlight)}
              onClick={() => onTriggerAction('add_size', position)}
              data-testid="context-btn-add-size"
              className="w-full min-h-[44px] py-2 px-3 text-xs font-sans rounded-[2px] border border-[#384454] text-[#8B98A5] bg-[#161C26] hover:bg-[#384454]/30 active:bg-[#384454]/50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer flex items-center justify-between font-medium"
            >
              <span>Add size (+50%)</span>
              <span className="font-mono text-[10px] bg-[#232A35] text-[#8B98A5] px-1.5 py-0.5 rounded-[2px]">+</span>
            </button>
            <button
              disabled={Boolean(isCommandInFlight)}
              onClick={() => onTriggerAction('close_position', position)}
              data-testid="context-btn-close-position"
              className="w-full min-h-[44px] py-2 px-3 text-xs font-sans rounded-[2px] border border-[#C25B6B] text-[#C25B6B] bg-[#161C26] hover:bg-[#C25B6B]/10 active:bg-[#C25B6B]/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer flex items-center justify-between font-medium"
            >
              <span>Close position</span>
              <span className="font-mono text-[10px] bg-[#C25B6B]/20 px-1.5 py-0.5 rounded-[2px]">C</span>
            </button>
          </div>
        </div>
      )}

      {panelTab === 'stats' && (
        <div className="mt-4 pt-3 border-t border-[#232A35] text-[11px] text-[#6E7A8A]">
          <button
            onClick={() => setPanelTab('detail')}
            className="w-full min-h-[44px] py-2 px-3 text-xs font-sans rounded-[2px] border border-[#232A35] text-[#5B8FBF] bg-[#161C26] hover:bg-[#5B8FBF]/10 transition-colors cursor-pointer text-center"
          >
            Switch to Position Detail
          </button>
        </div>
      )}
    </aside>
  );
};
