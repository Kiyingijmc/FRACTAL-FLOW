import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Position, PendingOrder, ClosedTrade, PositionsSubTab } from '../types';

interface PositionsTableProps {
  positions: Position[];
  pendingOrders: PendingOrder[];
  closedTrades: ClosedTrade[];
  selectedPositionId: string;
  onSelectPosition: (id: string) => void;
  activeSubTab: PositionsSubTab;
  onSubTabChange: (tab: PositionsSubTab) => void;
  onOpenDetail?: () => void;
}

export type OpenSortField = 'symbol' | 'entryPrice' | 'currentPrice' | 'size' | 'unrealizedR' | 'mfe' | 'age';
export type PendingSortField = 'symbol' | 'price' | 'size' | 'age';
export type ClosedSortField = 'symbol' | 'entryPrice' | 'exitPrice' | 'size' | 'realizedR' | 'realizedPnl' | 'duration' | 'closedAt';

export type SortDirection = 'asc' | 'desc';

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

  return (
    <div ref={dropdownRef} className="relative inline-flex items-center">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen((prev) => !prev);
        }}
        title={`View all ${instances.length} active positions for ${symbol}`}
        className="px-1.5 py-1 min-h-[30px] font-mono text-[9px] text-[#5B8FBF] bg-[#161C26] hover:bg-[#5B8FBF]/15 border border-[#232A35] hover:border-[#5B8FBF] rounded-[2px] transition-colors cursor-pointer select-none inline-flex items-center gap-1"
      >
        <span>More ({instances.length})</span>
        <span className="text-[8px] text-[#6E7A8A]">{isOpen ? '▲' : '▼'}</span>
      </button>

      {isOpen && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute left-0 top-full mt-1 z-40 min-w-[240px] bg-[#10151D] border border-[#232A35] py-1 text-xs select-none shadow-xl"
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
                  className={`px-2.5 py-2 flex items-center justify-between hover:bg-[#161C26] cursor-pointer transition-colors border-b border-[#232A35]/40 last:border-b-0 ${
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
  onOpenDetail,
}) => {
  // Open Positions sort state (default: PnL / unrealizedR descending)
  const [openSortField, setOpenSortField] = useState<OpenSortField>('unrealizedR');
  const [openSortDir, setOpenSortDir] = useState<SortDirection>('desc');

  // Pending Orders sort state (default: symbol ascending)
  const [pendingSortField, setPendingSortField] = useState<PendingSortField>('symbol');
  const [pendingSortDir, setPendingSortDir] = useState<SortDirection>('asc');

  // Closed Trades sort state (default: realizedR / PnL descending)
  const [closedSortField, setClosedSortField] = useState<ClosedSortField>('realizedR');
  const [closedSortDir, setClosedSortDir] = useState<SortDirection>('desc');

  // Toggle or change sort column for Open Positions
  const handleOpenSort = (field: OpenSortField) => {
    if (openSortField === field) {
      setOpenSortDir(openSortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setOpenSortField(field);
      setOpenSortDir(field === 'symbol' ? 'asc' : 'desc');
    }
  };

  // Toggle or change sort column for Pending Orders
  const handlePendingSort = (field: PendingSortField) => {
    if (pendingSortField === field) {
      setPendingSortDir(pendingSortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setPendingSortField(field);
      setPendingSortDir(field === 'symbol' ? 'asc' : 'desc');
    }
  };

  // Toggle or change sort column for Closed Trades
  const handleClosedSort = (field: ClosedSortField) => {
    if (closedSortField === field) {
      setClosedSortDir(closedSortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setClosedSortField(field);
      setClosedSortDir(field === 'symbol' ? 'asc' : 'desc');
    }
  };

  // Symbol instances map for open positions
  const symbolInstances = useMemo(() => {
    const map = new Map<string, Position[]>();
    positions.forEach((p) => {
      const list = map.get(p.symbol) || [];
      list.push(p);
      map.set(p.symbol, list);
    });
    return map;
  }, [positions]);

  // Sorted Open Positions
  const sortedPositions = useMemo(() => {
    return [...positions].sort((a, b) => {
      const valA = a[openSortField];
      const valB = b[openSortField];
      if (typeof valA === 'string' && typeof valB === 'string') {
        return openSortDir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      if (typeof valA === 'number' && typeof valB === 'number') {
        return openSortDir === 'asc' ? valA - valB : valB - valA;
      }
      return 0;
    });
  }, [positions, openSortField, openSortDir]);

  // Sorted Pending Orders
  const sortedPendingOrders = useMemo(() => {
    return [...pendingOrders].sort((a, b) => {
      const valA = a[pendingSortField];
      const valB = b[pendingSortField];
      if (typeof valA === 'string' && typeof valB === 'string') {
        return pendingSortDir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      if (typeof valA === 'number' && typeof valB === 'number') {
        return pendingSortDir === 'asc' ? valA - valB : valB - valA;
      }
      return 0;
    });
  }, [pendingOrders, pendingSortField, pendingSortDir]);

  // Sorted Closed Trades
  const sortedClosedTrades = useMemo(() => {
    return [...closedTrades].sort((a, b) => {
      const valA = a[closedSortField];
      const valB = b[closedSortField];
      if (typeof valA === 'string' && typeof valB === 'string') {
        return closedSortDir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      if (typeof valA === 'number' && typeof valB === 'number') {
        return closedSortDir === 'asc' ? valA - valB : valB - valA;
      }
      return 0;
    });
  }, [closedTrades, closedSortField, closedSortDir]);

  // Reference to the currently selected position row to maintain view tracking during re-sorting
  const selectedRowRef = useRef<HTMLTableRowElement>(null);

  // Ensure that the currently selected position remains active and in view even after re-sorting
  useEffect(() => {
    if (activeSubTab === 'open' && selectedRowRef.current) {
      if (typeof selectedRowRef.current.scrollIntoView === 'function') {
        selectedRowRef.current.scrollIntoView({
          block: 'nearest',
          behavior: 'smooth',
        });
      }
    }
  }, [openSortField, openSortDir, selectedPositionId, activeSubTab]);

  // Helper for rendering sort indicator icon with distinct visual states
  const renderSortIndicator = (isActive: boolean, dir: SortDirection) => {
    if (!isActive) {
      return (
        <span
          className="inline-flex items-center text-[#556272] group-hover:text-[#9BA3AF] transition-colors ml-1"
          aria-hidden="true"
          title="Sortable column"
        >
          <svg
            className="w-2.5 h-2.5 opacity-70 group-hover:opacity-100 transition-opacity"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
          </svg>
        </span>
      );
    }
    return (
      <span
        className="inline-flex items-center text-[#5B8FBF] font-bold ml-1"
        aria-hidden="true"
        title={`Sorted ${dir === 'asc' ? 'ascending' : 'descending'}`}
      >
        {dir === 'asc' ? (
          <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
          </svg>
        ) : (
          <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </span>
    );
  };

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-[#0A0E14] overflow-hidden w-full">
      {/* Sub-tabs with 44px touch targets on mobile */}
      <div className="flex items-center justify-between border-b border-[#232A35] bg-[#10151D] shrink-0 select-none overflow-x-auto">
        <div className="flex items-center gap-0">
          <button
            onClick={() => onSubTabChange('open')}
            className={`min-h-[44px] px-3.5 py-2 text-xs font-sans transition-colors cursor-pointer border-b-2 flex items-center ${
              activeSubTab === 'open'
                ? 'text-[#E7EAEE] border-[#5B8FBF] font-medium bg-[#161C26]/40'
                : 'text-[#6E7A8A] border-transparent hover:text-[#E7EAEE]'
            }`}
          >
            Open ({positions.length})
          </button>
          <button
            onClick={() => onSubTabChange('pending')}
            className={`min-h-[44px] px-3.5 py-2 text-xs font-sans transition-colors cursor-pointer border-b-2 flex items-center ${
              activeSubTab === 'pending'
                ? 'text-[#E7EAEE] border-[#5B8FBF] font-medium bg-[#161C26]/40'
                : 'text-[#6E7A8A] border-transparent hover:text-[#E7EAEE]'
            }`}
          >
            Pending ({pendingOrders.length})
          </button>
          <button
            onClick={() => onSubTabChange('closed')}
            className={`min-h-[44px] px-3.5 py-2 text-xs font-sans transition-colors cursor-pointer border-b-2 flex items-center ${
              activeSubTab === 'closed'
                ? 'text-[#E7EAEE] border-[#5B8FBF] font-medium bg-[#161C26]/40'
                : 'text-[#6E7A8A] border-transparent hover:text-[#E7EAEE]'
            }`}
          >
            Closed ({closedTrades.length})
          </button>
        </div>

        {/* Current sort status and mobile detail prompt */}
        <div className="flex items-center gap-2 mr-2">
          {activeSubTab === 'open' && (
            <div className="hidden sm:flex items-center gap-1 font-mono text-[10px] text-[#6E7A8A] bg-[#161C26] px-2 py-1 rounded-[2px] border border-[#232A35]">
              <span>Sorted by:</span>
              <span className="text-[#5B8FBF] font-medium uppercase">{openSortField === 'unrealizedR' ? 'PnL (R)' : openSortField}</span>
              <span className="text-[#E7EAEE]">{openSortDir === 'asc' ? '▲' : '▼'}</span>
            </div>
          )}

          {activeSubTab === 'pending' && (
            <div className="hidden sm:flex items-center gap-1 font-mono text-[10px] text-[#6E7A8A] bg-[#161C26] px-2 py-1 rounded-[2px] border border-[#232A35]">
              <span>Sorted by:</span>
              <span className="text-[#5B8FBF] font-medium uppercase">{pendingSortField}</span>
              <span className="text-[#E7EAEE]">{pendingSortDir === 'asc' ? '▲' : '▼'}</span>
            </div>
          )}

          {activeSubTab === 'closed' && (
            <div className="hidden sm:flex items-center gap-1 font-mono text-[10px] text-[#6E7A8A] bg-[#161C26] px-2 py-1 rounded-[2px] border border-[#232A35]">
              <span>Sorted by:</span>
              <span className="text-[#5B8FBF] font-medium uppercase">{closedSortField === 'realizedR' ? 'PnL (R)' : closedSortField === 'realizedPnl' ? 'PnL ($)' : closedSortField}</span>
              <span className="text-[#E7EAEE]">{closedSortDir === 'asc' ? '▲' : '▼'}</span>
            </div>
          )}

          {/* Mobile View Detail Prompt / Button */}
          {onOpenDetail && (
            <button
              type="button"
              onClick={onOpenDetail}
              className="md:hidden min-h-[36px] px-2.5 py-1 text-[11px] font-sans font-medium text-[#5B8FBF] bg-[#161C26] border border-[#232A35] hover:border-[#5B8FBF] rounded-[2px] transition-colors cursor-pointer flex items-center gap-1"
            >
              <span>Diagnostics</span>
              <span>→</span>
            </button>
          )}
        </div>
      </div>

      {/* Table Content with horizontal scrolling container */}
      <div className="flex-1 overflow-auto w-full">
        {/* ========================================================================= */}
        {/* SUBTAB: OPEN POSITIONS                                                    */}
        {/* ========================================================================= */}
        {activeSubTab === 'open' && (
          <table className="w-full border-collapse text-left whitespace-nowrap min-w-[700px] md:min-w-full">
            <thead>
              <tr className="bg-[#10151D] sticky top-0 z-10 select-none border-b border-[#232A35]">
                {/* 1. SYMBOL */}
                <th
                  scope="col"
                  aria-sort={openSortField === 'symbol' ? (openSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleOpenSort('symbol')}
                  title={`Sort by Symbol (${openSortField === 'symbol' && openSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] cursor-pointer transition-colors group select-none border-b-2 ${
                    openSortField === 'symbol'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center gap-1">
                    <span>symbol</span>
                    {renderSortIndicator(openSortField === 'symbol', openSortDir)}
                  </div>
                </th>

                <th className="py-2 px-3 text-[11px] font-medium text-[#586270] select-none border-b-2 border-transparent">side</th>
                <th className="py-2 px-3 text-[11px] font-medium text-[#586270] select-none border-b-2 border-transparent">setup</th>
                <th className="py-2 px-3 text-[11px] font-medium text-[#586270] select-none border-b-2 border-transparent">mode</th>

                {/* 2. ENTRY PRICE */}
                <th
                  scope="col"
                  aria-sort={openSortField === 'entryPrice' ? (openSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleOpenSort('entryPrice')}
                  title={`Sort by Entry Price (${openSortField === 'entryPrice' && openSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    openSortField === 'entryPrice'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>entry</span>
                    {renderSortIndicator(openSortField === 'entryPrice', openSortDir)}
                  </div>
                </th>

                {/* 3. CURRENT PRICE */}
                <th
                  scope="col"
                  aria-sort={openSortField === 'currentPrice' ? (openSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleOpenSort('currentPrice')}
                  title={`Sort by Current Price (${openSortField === 'currentPrice' && openSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    openSortField === 'currentPrice'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>current</span>
                    {renderSortIndicator(openSortField === 'currentPrice', openSortDir)}
                  </div>
                </th>

                {/* 4. SIZE */}
                <th
                  scope="col"
                  aria-sort={openSortField === 'size' ? (openSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleOpenSort('size')}
                  title={`Sort by Size (${openSortField === 'size' && openSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    openSortField === 'size'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>size</span>
                    {renderSortIndicator(openSortField === 'size', openSortDir)}
                  </div>
                </th>

                {/* 5. PnL (UNREALIZED R) */}
                <th
                  scope="col"
                  aria-sort={openSortField === 'unrealizedR' ? (openSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleOpenSort('unrealizedR')}
                  title={`Sort by PnL (unrealized R) (${openSortField === 'unrealizedR' && openSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    openSortField === 'unrealizedR'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>PnL (unreal. R)</span>
                    {renderSortIndicator(openSortField === 'unrealizedR', openSortDir)}
                  </div>
                </th>

                {/* 6. MFE */}
                <th
                  scope="col"
                  aria-sort={openSortField === 'mfe' ? (openSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleOpenSort('mfe')}
                  title={`Sort by MFE (${openSortField === 'mfe' && openSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    openSortField === 'mfe'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>MFE</span>
                    {renderSortIndicator(openSortField === 'mfe', openSortDir)}
                  </div>
                </th>

                <th className="py-2 px-3 text-[11px] font-medium text-[#586270] select-none border-b-2 border-transparent">exit profile</th>

                {/* 7. AGE */}
                <th
                  scope="col"
                  aria-sort={openSortField === 'age' ? (openSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleOpenSort('age')}
                  title={`Sort by Age (${openSortField === 'age' && openSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    openSortField === 'age'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>age</span>
                    {renderSortIndicator(openSortField === 'age', openSortDir)}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedPositions.map((pos) => {
                const isSelected = pos.id === selectedPositionId;
                const isPositive = pos.unrealizedR >= 0;
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
                    ref={isSelected ? selectedRowRef : undefined}
                    data-position-id={pos.id}
                    data-selected={isSelected ? 'true' : 'false'}
                    onClick={() => onSelectPosition(pos.id)}
                    className={`min-h-[44px] h-10 border-b border-[#232A35] text-xs cursor-pointer select-none transition-colors duration-200 ${
                      isSelected
                        ? 'bg-[#161C26] shadow-[inset_3px_0_0_#5B8FBF] ring-1 ring-[#5B8FBF]/20'
                        : 'hover:bg-[#161C26]'
                    } ${tickFlashClass}`}
                  >
                    <td className="py-2 px-3 text-[#E7EAEE] font-medium">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold">{pos.symbol}</span>
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
                    <td className="py-2 px-3">
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
                    <td className="py-2 px-3 text-[10px] text-[#6E7A8A] font-mono">{pos.setup}</td>
                    <td className="py-2 px-3 text-[10px] text-[#6E7A8A] font-mono">{pos.mode}</td>
                    <td className="py-2 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                      {pos.entryPrice.toFixed(pos.priceDecimals)}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                      {pos.currentPrice.toFixed(pos.priceDecimals)}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-[#E7EAEE] tabular-nums font-semibold">
                      {pos.size.toFixed(2)}
                    </td>
                    <td
                      className={`py-2 px-3 text-right font-mono tabular-nums font-semibold ${
                        isPositive ? 'text-[#4FAE86]' : 'text-[#C25B6B]'
                      }`}
                    >
                      {isPositive ? '+' : ''}
                      {pos.unrealizedR.toFixed(2)}R
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-[#4FAE86] tabular-nums">
                      +{pos.mfe.toFixed(2)}R
                    </td>
                    <td className="py-2 px-3 text-[10px] text-[#6E7A8A] font-mono">
                      {pos.exitProfile}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                      {pos.age}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {/* ========================================================================= */}
        {/* SUBTAB: PENDING ORDERS                                                    */}
        {/* ========================================================================= */}
        {activeSubTab === 'pending' && (
          <table className="w-full border-collapse text-left whitespace-nowrap min-w-[650px] md:min-w-full">
            <thead>
              <tr className="bg-[#10151D] sticky top-0 z-10 select-none border-b border-[#232A35]">
                {/* 1. SYMBOL */}
                <th
                  scope="col"
                  aria-sort={pendingSortField === 'symbol' ? (pendingSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handlePendingSort('symbol')}
                  title={`Sort by Symbol (${pendingSortField === 'symbol' && pendingSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] cursor-pointer transition-colors group select-none border-b-2 ${
                    pendingSortField === 'symbol'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center gap-1">
                    <span>symbol</span>
                    {renderSortIndicator(pendingSortField === 'symbol', pendingSortDir)}
                  </div>
                </th>

                <th className="py-2 px-3 text-[11px] font-medium text-[#586270] select-none border-b-2 border-transparent">side</th>
                <th className="py-2 px-3 text-[11px] font-medium text-[#586270] select-none border-b-2 border-transparent">type</th>
                <th className="py-2 px-3 text-[11px] font-medium text-[#586270] select-none border-b-2 border-transparent">setup</th>

                {/* 2. LIMIT PRICE */}
                <th
                  scope="col"
                  aria-sort={pendingSortField === 'price' ? (pendingSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handlePendingSort('price')}
                  title={`Sort by Limit Price (${pendingSortField === 'price' && pendingSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    pendingSortField === 'price'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>limit price</span>
                    {renderSortIndicator(pendingSortField === 'price', pendingSortDir)}
                  </div>
                </th>

                {/* 3. SIZE */}
                <th
                  scope="col"
                  aria-sort={pendingSortField === 'size' ? (pendingSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handlePendingSort('size')}
                  title={`Sort by Size (${pendingSortField === 'size' && pendingSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    pendingSortField === 'size'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>size</span>
                    {renderSortIndicator(pendingSortField === 'size', pendingSortDir)}
                  </div>
                </th>

                <th className="py-2 px-3 text-[11px] font-medium text-[#586270] select-none border-b-2 border-transparent">trigger condition</th>

                {/* 4. AGE */}
                <th
                  scope="col"
                  aria-sort={pendingSortField === 'age' ? (pendingSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handlePendingSort('age')}
                  title={`Sort by Age (${pendingSortField === 'age' && pendingSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    pendingSortField === 'age'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>age</span>
                    {renderSortIndicator(pendingSortField === 'age', pendingSortDir)}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedPendingOrders.map((ord) => (
                <tr key={ord.id} className="min-h-[44px] h-10 border-b border-[#232A35] text-xs hover:bg-[#161C26]">
                  <td className="py-2 px-3 text-[#E7EAEE] font-medium">{ord.symbol}</td>
                  <td className="py-2 px-3">
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
                  <td className="py-2 px-3 text-[10px] text-[#6E7A8A] font-mono">{ord.type}</td>
                  <td className="py-2 px-3 text-[10px] text-[#6E7A8A] font-mono">{ord.setup}</td>
                  <td className="py-2 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                    {ord.price.toFixed(ord.priceDecimals)}
                  </td>
                  <td className="py-2 px-3 text-right font-mono text-[#E7EAEE] tabular-nums font-semibold">
                    {ord.size.toFixed(2)}
                  </td>
                  <td className="py-2 px-3 text-[11px] text-[#6E7A8A]">{ord.triggerCond}</td>
                  <td className="py-2 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                    {ord.age}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* ========================================================================= */}
        {/* SUBTAB: CLOSED TRADES                                                     */}
        {/* ========================================================================= */}
        {activeSubTab === 'closed' && (
          <table className="w-full border-collapse text-left whitespace-nowrap min-w-[750px] md:min-w-full">
            <thead>
              <tr className="bg-[#10151D] sticky top-0 z-10 select-none border-b border-[#232A35]">
                {/* 1. SYMBOL */}
                <th
                  scope="col"
                  aria-sort={closedSortField === 'symbol' ? (closedSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleClosedSort('symbol')}
                  title={`Sort by Symbol (${closedSortField === 'symbol' && closedSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] cursor-pointer transition-colors group select-none border-b-2 ${
                    closedSortField === 'symbol'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center gap-1">
                    <span>symbol</span>
                    {renderSortIndicator(closedSortField === 'symbol', closedSortDir)}
                  </div>
                </th>

                <th className="py-2 px-3 text-[11px] font-medium text-[#586270] select-none border-b-2 border-transparent">side</th>
                <th className="py-2 px-3 text-[11px] font-medium text-[#586270] select-none border-b-2 border-transparent">setup</th>

                {/* 2. ENTRY */}
                <th
                  scope="col"
                  aria-sort={closedSortField === 'entryPrice' ? (closedSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleClosedSort('entryPrice')}
                  title={`Sort by Entry Price (${closedSortField === 'entryPrice' && closedSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    closedSortField === 'entryPrice'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>entry</span>
                    {renderSortIndicator(closedSortField === 'entryPrice', closedSortDir)}
                  </div>
                </th>

                {/* 3. EXIT */}
                <th
                  scope="col"
                  aria-sort={closedSortField === 'exitPrice' ? (closedSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleClosedSort('exitPrice')}
                  title={`Sort by Exit Price (${closedSortField === 'exitPrice' && closedSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    closedSortField === 'exitPrice'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>exit</span>
                    {renderSortIndicator(closedSortField === 'exitPrice', closedSortDir)}
                  </div>
                </th>

                {/* 4. SIZE */}
                <th
                  scope="col"
                  aria-sort={closedSortField === 'size' ? (closedSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleClosedSort('size')}
                  title={`Sort by Size (${closedSortField === 'size' && closedSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    closedSortField === 'size'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>size</span>
                    {renderSortIndicator(closedSortField === 'size', closedSortDir)}
                  </div>
                </th>

                {/* 5. PnL (REALIZED R) */}
                <th
                  scope="col"
                  aria-sort={closedSortField === 'realizedR' ? (closedSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleClosedSort('realizedR')}
                  title={`Sort by PnL in R (${closedSortField === 'realizedR' && closedSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    closedSortField === 'realizedR'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>realized R</span>
                    {renderSortIndicator(closedSortField === 'realizedR', closedSortDir)}
                  </div>
                </th>

                {/* 6. PnL ($) */}
                <th
                  scope="col"
                  aria-sort={closedSortField === 'realizedPnl' ? (closedSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleClosedSort('realizedPnl')}
                  title={`Sort by PnL in Dollars (${closedSortField === 'realizedPnl' && closedSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    closedSortField === 'realizedPnl'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>P&amp;L ($)</span>
                    {renderSortIndicator(closedSortField === 'realizedPnl', closedSortDir)}
                  </div>
                </th>

                <th className="py-2 px-3 text-[11px] font-medium text-[#586270] select-none border-b-2 border-transparent">exit reason</th>

                {/* 7. DURATION */}
                <th
                  scope="col"
                  aria-sort={closedSortField === 'duration' ? (closedSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleClosedSort('duration')}
                  title={`Sort by Duration (${closedSortField === 'duration' && closedSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    closedSortField === 'duration'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>duration</span>
                    {renderSortIndicator(closedSortField === 'duration', closedSortDir)}
                  </div>
                </th>

                {/* 8. CLOSED AT */}
                <th
                  scope="col"
                  aria-sort={closedSortField === 'closedAt' ? (closedSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  onClick={() => handleClosedSort('closedAt')}
                  title={`Sort by Closed Time (${closedSortField === 'closedAt' && closedSortDir === 'asc' ? 'descending' : 'ascending'})`}
                  className={`py-2 px-3 text-[11px] text-right cursor-pointer transition-colors group select-none border-b-2 ${
                    closedSortField === 'closedAt'
                      ? 'text-[#5B8FBF] bg-[#161C26]/90 border-[#5B8FBF] font-semibold'
                      : 'text-[#8B98A5] hover:text-[#E7EAEE] hover:bg-[#161C26]/40 border-transparent hover:border-[#384454] font-medium'
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>closed at</span>
                    {renderSortIndicator(closedSortField === 'closedAt', closedSortDir)}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedClosedTrades.map((tr) => {
                const isPositive = tr.realizedR >= 0;
                return (
                  <tr key={tr.id} className="min-h-[44px] h-10 border-b border-[#232A35] text-xs hover:bg-[#161C26]">
                    <td className="py-2 px-3 text-[#E7EAEE] font-medium">{tr.symbol}</td>
                    <td className="py-2 px-3">
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
                    <td className="py-2 px-3 text-[10px] text-[#6E7A8A] font-mono">{tr.setup}</td>
                    <td className="py-2 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                      {tr.entryPrice.toFixed(tr.priceDecimals)}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                      {tr.exitPrice.toFixed(tr.priceDecimals)}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-[#E7EAEE] tabular-nums font-semibold">
                      {tr.size.toFixed(2)}
                    </td>
                    <td
                      className={`py-2 px-3 text-right font-mono tabular-nums font-semibold ${
                        isPositive ? 'text-[#4FAE86]' : 'text-[#C25B6B]'
                      }`}
                    >
                      {isPositive ? '+' : ''}
                      {tr.realizedR.toFixed(2)}R
                    </td>
                    <td
                      className={`py-2 px-3 text-right font-mono tabular-nums font-semibold ${
                        tr.realizedPnl >= 0 ? 'text-[#4FAE86]' : 'text-[#C25B6B]'
                      }`}
                    >
                      {tr.realizedPnl >= 0 ? '+' : ''}${tr.realizedPnl.toFixed(2)}
                    </td>
                    <td className="py-2 px-3 text-[10px] text-[#6E7A8A] font-mono">{tr.exitReason}</td>
                    <td className="py-2 px-3 text-right font-mono text-[#E7EAEE] tabular-nums">
                      {tr.duration}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-[#6E7A8A] tabular-nums">
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
