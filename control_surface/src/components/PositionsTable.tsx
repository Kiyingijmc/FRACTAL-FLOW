import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Position, PendingOrder, ClosedTrade, PositionsSubTab } from '../types.ts';

interface PositionsTableProps {
  positions: Position[];
  pendingOrders: PendingOrder[];
  closedTrades: ClosedTrade[];
  selectedPositionId: string;
  onSelectPosition: (id: string) => void;
  activeSubTab: PositionsSubTab;
  onSubTabChange: (tab: PositionsSubTab) => void;
}

type SortField = 'symbol' | 'entryPrice' | 'currentPrice' | 'size' | 'unrealizedR' | 'mfe' | 'age';
type SortDirection = 'asc' | 'desc';

interface MoreInstancesButtonProps {
  symbol: string;
  instances: Position[];
  currentPositionId: string;
  onSelectPosition: (id: string) => void;
}

const MoreInstancesButton: React.FC<MoreInstancesButtonProps> = ({
  symbol,
  instances,
  currentPositionId,
  onSelectPosition,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const otherInstancesCount = instances.length - 1;

  return (
    <div ref={dropdownRef} className="relative inline-flex items-center">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen((prev) => !prev);
        }}
        title={`View all ${instances.length} active positions for ${symbol}`}
        className="px-1 py-0.5 font-mono text-[9px] text-[#5B8FBF] bg-[#161C26] hover:bg-[#5B8FBF]/15 border border-[#232A35] hover:border-[#5B8FBF] rounded-[2px] transition-colors cursor-pointer select-none inline-flex items-center gap-1"
      >
        <span>More ({instances.length})</span>
        <span className="text-[8px] text-[#6E7A8A]">{isOpen ? '▲' : '▼'}</span>
      </button>

      {isOpen && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute left-0 top-full mt-1 z-40 min-w-[240px] bg-[#10151D] border border-[#232A35] py-1 text-xs select-none"
        >
          <div className="px-2.5 py-1 text-[10px] font-sans font-medium text-[#6E7A8A] border-b border-[#232A35] flex justify-between items-center">
            <span>{symbol} Active Instances ({instances.length})</span>
            <span className="font-mono text-[9px] text-[#4FAE86]">OPEN</span>
          </div>
          <div className="max-h-52 overflow-y-auto py-0.5">
            {instances.map((inst) => {
              const isCurrent = inst.id === currentPositionId;
              const isPos = inst.unrealizedR >= 0;
              return (
                <div
                  key={inst.id}
                  onClick={() => {
                    onSelectPosition(inst.id);
                    setIsOpen(false);
                  }}
                  className={`px-2.5 py-1.5 flex items-center justify-between hover:bg-[#161C26] cursor-pointer transition-colors border-b border-[#232A35]/40 last:border-b-0 ${
                    isCurrent ? 'bg-[#161C26] border-l-2 border-l-[#5B8FBF]' : ''
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`font-mono text-[9px] px-1 py-0.2 rounded-[2px] ${
                        inst.side === 'LONG'
                          ? 'bg-[#4FAE86]/[0.16] text-[#4FAE86]'
                          : 'bg-[#C25B6B]/[0.16] text-[#C25B6B]'
                      }`}
                    >
                      {inst.side}
                    </span>
                    <span className="font-mono text-[10px] text-[#E7EAEE] font-medium">{inst.setup}</span>
                    <span className="font-mono text-[9px] text-[#6E7A8A]">{inst.drivingTimeframe}</span>
                  </div>
                  <div className="text-right">
                    <div className={`font-mono text-[10px] font-medium tabular-nums ${isPos ? 'text-[#4FAE86]' : 'text-[#C25B6B]'}`}>
                      {isPos ? '+' : ''}{inst.unrealizedR.toFixed(2)}R
                    </div>
                    <div className="font-mono text-[9px] text-[#6E7A8A] tabular-nums">
                      {inst.size.toFixed(2)} lots
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export const PositionsTable: React.FC<PositionsTableProps> = ({
  positions,
  pendingOrders,
  closedTrades,
  selectedPositionId,
  onSelectPosition,
  activeSubTab,
  onSubTabChange,
}) => {
  const [sortField, setSortField] = useState<SortField>('unrealizedR');
  const [sortDir, setSortDir] = useState<SortDirection>('desc');

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const symbolInstances = useMemo(() => {
    const map = new Map<string, Position[]>();
    positions.forEach((p) => {
      const list = map.get(p.symbol) || [];
      list.push(p);
      map.set(p.symbol, list);
    });
    return map;
  }, [positions]);

  const sortedPositions = useMemo(() => {
    return [...positions].sort((a, b) => {
      let valA = a[sortField];
      let valB = b[sortField];
      if (typeof valA === 'string' && typeof valB === 'string') {
        return sortDir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortDir === 'asc' ? valA - valB : valB - valA;
      }
      return 0;
    });
  }, [positions, sortField, sortDir]);

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-[#0A0E14] overflow-hidden">
      {/* Sub-tabs */}
      <div className="flex items-center gap-0 border-b border-[#232A35] bg-[#10151D] shrink-0 select-none">
        <button
          onClick={() => onSubTabChange('open')}
          className={`px-3.5 py-2 text-xs font-sans transition-colors cursor-pointer border-b-2 ${
            activeSubTab === 'open'
              ? 'text-[#E7EAEE] border-[#5B8FBF] font-medium'
              : 'text-[#6E7A8A] border-transparent hover:text-[#E7EAEE]'
          }`}
        >
          Open positions ({positions.length})
        </button>
        <button
          onClick={() => onSubTabChange('pending')}
          className={`px-3.5 py-2 text-xs font-sans transition-colors cursor-pointer border-b-2 ${
            activeSubTab === 'pending'
              ? 'text-[#E7EAEE] border-[#5B8FBF] font-medium'
              : 'text-[#6E7A8A] border-transparent hover:text-[#E7EAEE]'
          }`}
        >
          Pending orders ({pendingOrders.length})
        </button>
        <button
          onClick={() => onSubTabChange('closed')}
          className={`px-3.5 py-2 text-xs font-sans transition-colors cursor-pointer border-b-2 ${
            activeSubTab === 'closed'
              ? 'text-[#E7EAEE] border-[#5B8FBF] font-medium'
              : 'text-[#6E7A8A] border-transparent hover:text-[#E7EAEE]'
          }`}
        >
          Recent closed ({closedTrades.length})
        </button>
      </div>

      {/* Table Content */}
      <div className="flex-1 overflow-auto">
        {activeSubTab === 'open' && (
          <table className="w-full border-collapse text-left whitespace-nowrap">
            <thead>
              <tr className="bg-[#10151D] sticky top-0 z-10 select-none border-b border-[#232A35]">
                <th
                  onClick={() => handleSort('symbol')}
                  className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] cursor-pointer hover:text-[#E7EAEE]"
                >
                  symbol {sortField === 'symbol' && (sortDir === 'asc' ? '↑' : '↓')}
                </th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A]">side</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A]">setup</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A]">mode</th>
                <th
                  onClick={() => handleSort('entryPrice')}
                  className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right cursor-pointer hover:text-[#E7EAEE]"
                >
                  entry {sortField === 'entryPrice' && (sortDir === 'asc' ? '↑' : '↓')}
                </th>
                <th
                  onClick={() => handleSort('currentPrice')}
                  className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right cursor-pointer hover:text-[#E7EAEE]"
                >
                  current {sortField === 'currentPrice' && (sortDir === 'asc' ? '↑' : '↓')}
                </th>
                <th
                  onClick={() => handleSort('size')}
                  className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right cursor-pointer hover:text-[#E7EAEE]"
                >
                  size {sortField === 'size' && (sortDir === 'asc' ? '↑' : '↓')}
                </th>
                <th
                  onClick={() => handleSort('unrealizedR')}
                  className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right cursor-pointer hover:text-[#E7EAEE]"
                >
                  unreal. R {sortField === 'unrealizedR' && (sortDir === 'asc' ? '↑' : '↓')}
                </th>
                <th
                  onClick={() => handleSort('mfe')}
                  className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right cursor-pointer hover:text-[#E7EAEE]"
                >
                  MFE {sortField === 'mfe' && (sortDir === 'asc' ? '↑' : '↓')}
                </th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A]">exit profile</th>
                <th
                  onClick={() => handleSort('age')}
                  className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right cursor-pointer hover:text-[#E7EAEE]"
                >
                  age {sortField === 'age' && (sortDir === 'asc' ? '↑' : '↓')}
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedPositions.map((pos) => {
                const isSelected = pos.id === selectedPositionId;
                const isPositive = pos.unrealizedR >= 0;

                // Check for live tick flash (within ~500ms)
                const isRecentTick = pos.lastTickTimestamp && Date.now() - pos.lastTickTimestamp < 500;
                let tickFlashClass = '';
                if (isRecentTick) {
                  tickFlashClass = pos.lastTickDir === 'up' ? 'bg-[#4FAE86]/20' : 'bg-[#C25B6B]/20';
                }

                const instances = symbolInstances.get(pos.symbol) || [];
                const hasMultiple = instances.length > 1;

                return (
                  <tr
                    key={pos.id}
                    onClick={() => onSelectPosition(pos.id)}
                    className={`h-7 border-b border-[#232A35] text-xs cursor-pointer select-none transition-colors duration-400 ${
                      isSelected
                        ? 'bg-[#161C26] shadow-[inset_2px_0_0_#5B8FBF]'
                        : 'hover:bg-[#161C26]'
                    } ${tickFlashClass}`}
                  >
                    <td className="py-1 px-3 text-[#E7EAEE] font-medium">
                      <div className="flex items-center gap-1.5">
                        <span>{pos.symbol}</span>
                        {hasMultiple && (
                          <MoreInstancesButton
                            symbol={pos.symbol}
                            instances={instances}
                            currentPositionId={pos.id}
                            onSelectPosition={onSelectPosition}
                          />
                        )}
                      </div>
                    </td>
                    <td className="py-1 px-3">
                      <span
                        className={`font-mono text-[10px] px-1.5 py-0.5 rounded-[2px] tracking-[0.3px] font-medium ${
                          pos.side === 'LONG'
                            ? 'bg-[#4FAE86]/[0.16] text-[#4FAE86]'
                            : 'bg-[#C25B6B]/[0.16] text-[#C25B6B]'
                        }`}
                      >
                        {pos.side}
                      </span>
                    </td>
                    <td className="py-1 px-3 text-[10px] text-[#6E7A8A] font-mono">{pos.setup}</td>
                    <td className="py-1 px-3 text-[10px] text-[#6E7A8A] font-mono">{pos.mode}</td>
                    <td className="py-1 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                      {pos.entryPrice.toFixed(pos.priceDecimals)}
                    </td>
                    <td className="py-1 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                      {pos.currentPrice.toFixed(pos.priceDecimals)}
                    </td>
                    <td className="py-1 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                      {pos.size.toFixed(2)}
                    </td>
                    <td
                      className={`py-1 px-3 text-right font-mono tabular-nums font-medium ${
                        isPositive ? 'text-[#4FAE86]' : 'text-[#C25B6B]'
                      }`}
                    >
                      {isPositive ? '+' : ''}
                      {pos.unrealizedR.toFixed(2)}R
                    </td>
                    <td className="py-1 px-3 text-right font-mono text-[#4FAE86] tabular-nums">
                      +{pos.mfe.toFixed(2)}R
                    </td>
                    <td className="py-1 px-3 text-[10px] text-[#6E7A8A] font-mono">
                      {pos.exitProfile}
                    </td>
                    <td className="py-1 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                      {pos.age}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {activeSubTab === 'pending' && (
          <table className="w-full border-collapse text-left whitespace-nowrap">
            <thead>
              <tr className="bg-[#10151D] sticky top-0 z-10 select-none border-b border-[#232A35]">
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A]">symbol</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A]">side</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A]">type</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A]">setup</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right">limit price</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right">size</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A]">trigger condition</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right">age</th>
              </tr>
            </thead>
            <tbody>
              {pendingOrders.map((ord) => (
                <tr key={ord.id} className="h-7 border-b border-[#232A35] text-xs hover:bg-[#161C26]">
                  <td className="py-1 px-3 text-[#E7EAEE] font-medium">{ord.symbol}</td>
                  <td className="py-1 px-3">
                    <span
                      className={`font-mono text-[10px] px-1.5 py-0.5 rounded-[2px] tracking-[0.3px] font-medium ${
                        ord.side === 'LONG'
                          ? 'bg-[#4FAE86]/[0.16] text-[#4FAE86]'
                          : 'bg-[#C25B6B]/[0.16] text-[#C25B6B]'
                      }`}
                    >
                      {ord.side}
                    </span>
                  </td>
                  <td className="py-1 px-3 text-[10px] text-[#6E7A8A] font-mono">{ord.type}</td>
                  <td className="py-1 px-3 text-[10px] text-[#6E7A8A] font-mono">{ord.setup}</td>
                  <td className="py-1 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                    {ord.price.toFixed(ord.priceDecimals)}
                  </td>
                  <td className="py-1 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                    {ord.size.toFixed(2)}
                  </td>
                  <td className="py-1 px-3 text-[11px] text-[#6E7A8A]">{ord.triggerCond}</td>
                  <td className="py-1 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                    {ord.age}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {activeSubTab === 'closed' && (
          <table className="w-full border-collapse text-left whitespace-nowrap">
            <thead>
              <tr className="bg-[#10151D] sticky top-0 z-10 select-none border-b border-[#232A35]">
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A]">symbol</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A]">side</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A]">setup</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right">entry</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right">exit</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right">size</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right">realized R</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right">P&amp;L ($)</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A]">exit reason</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right">duration</th>
                <th className="py-1.5 px-3 text-[11px] font-medium text-[#6E7A8A] text-right">closed at</th>
              </tr>
            </thead>
            <tbody>
              {closedTrades.map((tr) => {
                const isPositive = tr.realizedR >= 0;
                return (
                  <tr key={tr.id} className="h-7 border-b border-[#232A35] text-xs hover:bg-[#161C26]">
                    <td className="py-1 px-3 text-[#E7EAEE] font-medium">{tr.symbol}</td>
                    <td className="py-1 px-3">
                      <span
                        className={`font-mono text-[10px] px-1.5 py-0.5 rounded-[2px] tracking-[0.3px] font-medium ${
                          tr.side === 'LONG'
                            ? 'bg-[#4FAE86]/[0.16] text-[#4FAE86]'
                            : 'bg-[#C25B6B]/[0.16] text-[#C25B6B]'
                        }`}
                      >
                        {tr.side}
                      </span>
                    </td>
                    <td className="py-1 px-3 text-[10px] text-[#6E7A8A] font-mono">{tr.setup}</td>
                    <td className="py-1 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                      {tr.entryPrice.toFixed(tr.priceDecimals)}
                    </td>
                    <td className="py-1 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                      {tr.exitPrice.toFixed(tr.priceDecimals)}
                    </td>
                    <td className="py-1 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                      {tr.size.toFixed(2)}
                    </td>
                    <td
                      className={`py-1 px-3 text-right font-mono tabular-nums font-medium ${
                        isPositive ? 'text-[#4FAE86]' : 'text-[#C25B6B]'
                      }`}
                    >
                      {isPositive ? '+' : ''}
                      {tr.realizedR.toFixed(2)}R
                    </td>
                    <td
                      className={`py-1 px-3 text-right font-mono tabular-nums ${
                        tr.realizedPnl >= 0 ? 'text-[#4FAE86]' : 'text-[#C25B6B]'
                      }`}
                    >
                      {tr.realizedPnl >= 0 ? '+' : ''}${tr.realizedPnl.toFixed(2)}
                    </td>
                    <td className="py-1 px-3 text-[10px] text-[#6E7A8A] font-mono">{tr.exitReason}</td>
                    <td className="py-1 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                      {tr.duration}
                    </td>
                    <td className="py-1 px-3 text-right font-mono text-[#6E7A8A] tabular-nums">
                      {tr.closedAt}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
