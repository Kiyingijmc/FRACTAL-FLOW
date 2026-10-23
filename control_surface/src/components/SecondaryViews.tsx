import React, { useState, useMemo } from 'react';
import { NavTab, MarketNewsItem, NewsImpactLevel, NewsCategory } from '../types';
import { INITIAL_MARKET_NEWS, INITIAL_CLOSED_TRADES } from '../data/mockData';

interface SecondaryViewsProps {
  activeTab: NavTab;
  onReturnToPositions: () => void;
  newsItems?: MarketNewsItem[];
}

interface ModeProfileItem {
  name: string;
  status: 'ACTIVE' | 'CONSTRAINED' | 'MONITORING' | 'STANDBY';
  regimeConfidence: string;
  regimeConfidenceClass: string;
  anchorTimeframe: string;
  activeSymbols: string[];
  calibrationState: string;
}

const MODE_PROFILES: ModeProfileItem[] = [
  {
    name: 'TREND_RUNNER',
    status: 'ACTIVE',
    regimeConfidence: '0.84 (Strong)',
    regimeConfidenceClass: 'text-[#4FAE86]',
    anchorTimeframe: '15M',
    activeSymbols: ['EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'USDCHF'],
    calibrationState: 'ACTIVE (cfg_7f2a19c4)',
  },
  {
    name: 'RANGE_TARGET',
    status: 'ACTIVE',
    regimeConfidence: '0.78 (Moderate)',
    regimeConfidenceClass: 'text-[#4FAE86]',
    anchorTimeframe: '30M',
    activeSymbols: ['GBPUSD', 'EURJPY', 'AUDNZD', 'GBPJPY'],
    calibrationState: 'ACTIVE (cfg_7f2a19c4)',
  },
  {
    name: 'COUNTERFLOW_TIGHT',
    status: 'CONSTRAINED',
    regimeConfidence: '0.52 (Low)',
    regimeConfidenceClass: 'text-[#BFA13B]',
    anchorTimeframe: '5M',
    activeSymbols: ['USDJPY', 'EURGBP'],
    calibrationState: 'CANARY (cfg_5e1b82a0)',
  },
  {
    name: 'TRANSITION_WATCH',
    status: 'MONITORING',
    regimeConfidence: '0.61 (Neutral)',
    regimeConfidenceClass: 'text-[#6E7A8A]',
    anchorTimeframe: '1M',
    activeSymbols: ['EURUSD', 'USDCAD', 'GBPJPY'],
    calibrationState: 'ACTIVE (cfg_7f2a19c4)',
  },
  {
    name: 'VOLATILITY_EXPANSION',
    status: 'STANDBY',
    regimeConfidence: '0.45 (Below Threshold)',
    regimeConfidenceClass: 'text-[#C25B6B]',
    anchorTimeframe: '1H',
    activeSymbols: ['GBPAUD', 'EURCAD', 'USDCHF', 'XAUUSD'],
    calibrationState: 'SHADOW (cfg_3b9f12d8)',
  },
];

const ActiveSymbolsCell: React.FC<{ symbols: string[] }> = ({ symbols }) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const displayedSymbols = symbols.slice(0, 2);
  const extraSymbols = symbols.slice(2);
  const hasMore = extraSymbols.length > 0;

  return (
    <div ref={containerRef} className="relative inline-flex items-center gap-1.5 font-mono text-[11px] text-[#E7EAEE]">
      <span>{displayedSymbols.join(', ')}</span>
      {hasMore && (
        <>
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="px-1 py-0.5 min-h-[26px] text-[9px] text-[#5B8FBF] bg-[#161C26] hover:bg-[#5B8FBF]/20 border border-[#232A35] rounded-[2px] cursor-pointer"
          >
            +{extraSymbols.length}
          </button>
          {isOpen && (
            <div className="absolute left-0 top-full mt-1 z-30 bg-[#10151D] border border-[#232A35] p-2 text-xs rounded shadow-lg min-w-[140px]">
              <div className="text-[10px] text-[#6E7A8A] mb-1 font-sans">All Symbols</div>
              <div className="space-y-1 font-mono text-[11px] text-[#E7EAEE]">
                {symbols.map((sym) => (
                  <div key={sym}>{sym}</div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export const SecondaryViews: React.FC<SecondaryViewsProps> = ({
  activeTab,
  onReturnToPositions,
  newsItems = INITIAL_MARKET_NEWS,
}) => {
  const [newsFilterImpact, setNewsFilterImpact] = useState<NewsImpactLevel | 'ALL'>('ALL');
  const [newsFilterCategory, setNewsFilterCategory] = useState<NewsCategory | 'ALL'>('ALL');
  const [selectedCurrency, setSelectedCurrency] = useState<string>('ALL');
  const [isFilterCollapsed, setIsFilterCollapsed] = useState<boolean>(true);

  const filteredNews = useMemo(() => {
    return newsItems.filter((item) => {
      if (newsFilterImpact !== 'ALL' && item.impact !== newsFilterImpact) return false;
      if (newsFilterCategory !== 'ALL' && item.category !== newsFilterCategory) return false;
      if (selectedCurrency !== 'ALL' && item.currency !== selectedCurrency) return false;
      return true;
    });
  }, [newsItems, newsFilterImpact, newsFilterCategory, selectedCurrency]);

  const activeEmbargoCount = useMemo(() => {
    return newsItems.filter((item) => item.embargoActive).length;
  }, [newsItems]);

  const highImpactCount = useMemo(() => {
    return newsItems.filter((item) => item.impact === 'High').length;
  }, [newsItems]);

  // Derived closed trades statistics for STATS tab
  const stats = useMemo(() => {
    const closed = INITIAL_CLOSED_TRADES;
    const totalTrades = closed.length;
    const winning = closed.filter(t => t.realizedR > 0);
    const losing = closed.filter(t => t.realizedR <= 0);
    const winRate = totalTrades > 0 ? (winning.length / totalTrades) * 100 : 0;
    const totalR = closed.reduce((acc, t) => acc + t.realizedR, 0);
    const totalPnl = closed.reduce((acc, t) => acc + t.realizedPnl, 0);
    const grossProfit = winning.reduce((acc, t) => acc + t.realizedPnl, 0);
    const grossLoss = Math.abs(losing.reduce((acc, t) => acc + t.realizedPnl, 0));
    const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : 99.99;
    const avgWin = winning.length > 0 ? winning.reduce((acc, t) => acc + t.realizedR, 0) / winning.length : 0;
    const avgLoss = losing.length > 0 ? Math.abs(losing.reduce((acc, t) => acc + t.realizedR, 0) / losing.length) : 0;
    const expectancy = totalTrades > 0 ? totalR / totalTrades : 0;
    return {
      totalTrades,
      winCount: winning.length,
      lossCount: losing.length,
      winRate,
      totalR,
      totalPnl,
      profitFactor,
      avgWin,
      avgLoss,
      expectancy
    };
  }, []);

  return (
    <div className="flex-1 flex flex-col bg-[#0A0E14] overflow-y-auto p-3 sm:p-5 text-[#E7EAEE] w-full">
      {/* View Header with 44px touch target Back button */}
      <div className="flex items-center justify-between pb-3 mb-4 border-b border-[#232A35]">
        <div>
          <h2 className="text-sm font-semibold tracking-wide text-[#E7EAEE]">
            {activeTab === 'DEC' && 'Decision Snapshots & Candidate Gate Rejections'}
            {activeTab === 'RISK' && 'Per-Lane Risk State & Exposure Caps'}
            {activeTab === 'MODE' && 'Mode Profiles & Regime Confidence Gate'}
            {activeTab === 'NEWS' && 'Market Event Feed & Gate N Embargo Telemetry'}
            {activeTab === 'CALIB' && 'Calibration Service & Parameter Rollout Stages'}
            {activeTab === 'HEALTH' && 'System Health, Bridge Session & Fence Peer'}
            {activeTab === 'STATS' && 'Closed Trade Analytics & System Performance'}
          </h2>
          <div className="text-[11px] text-[#6E7A8A]">
            FRACTAL-FLOW Control Surface · Off-Broker Operator Monitor
          </div>
        </div>

        <button
          type="button"
          onClick={onReturnToPositions}
          className="min-h-[44px] px-3 py-1.5 text-xs font-sans rounded-[2px] border border-[#232A35] hover:border-[#5B8FBF] bg-[#161C26] hover:bg-[#5B8FBF]/10 text-[#5B8FBF] transition-colors cursor-pointer flex items-center gap-1.5"
        >
          <span>← Back to Positions</span>
          <span className="font-mono text-[10px] bg-[#5B8FBF]/20 px-1 py-0.5 rounded-[2px] hidden sm:inline">
            Esc
          </span>
        </button>
      </div>

      {/* DECISION VIEW */}
      {activeTab === 'DEC' && (
        <div className="space-y-4">
          <div className="text-xs text-[#6E7A8A]">
            Sequential 11-gate chain telemetry for recent candidate evaluations (<span className="font-mono">Q E R P L O T N K A X</span>).
          </div>

          <div className="w-full overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs min-w-[650px]">
              <thead>
                <tr className="bg-[#10151D] border-b border-[#232A35] text-[11px] text-[#6E7A8A]">
                  <th className="py-2 px-3">time</th>
                  <th className="py-2 px-3">symbol</th>
                  <th className="py-2 px-3">setup</th>
                  <th className="py-2 px-3">gate status (11 gates)</th>
                  <th className="py-2 px-3">terminal outcome</th>
                  <th className="py-2 px-3">rejection rationale</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-[#232A35] hover:bg-[#161C26]">
                  <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">14:04:12</td>
                  <td className="py-2.5 px-3 text-[#E7EAEE] font-medium">EURUSD</td>
                  <td className="py-2.5 px-3 font-mono text-[11px] text-[#6E7A8A]">FF-01</td>
                  <td className="py-2.5 px-3 font-mono text-[11px]">
                    <span className="text-[#4FAE86]">Q E R P</span>{' '}
                    <span className="text-[#B23B3B] font-semibold">L</span>{' '}
                    <span className="text-[#454E5C]">O T N K A X</span>
                  </td>
                  <td className="py-2.5 px-3 text-[#C25B6B] font-mono text-[11px]">REJECTED</td>
                  <td className="py-2.5 px-3 text-[#6E7A8A]">Location congested: price inside 15M swing congestion zone</td>
                </tr>
                <tr className="border-b border-[#232A35] hover:bg-[#161C26]">
                  <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">13:48:05</td>
                  <td className="py-2.5 px-3 text-[#E7EAEE] font-medium">GBPUSD</td>
                  <td className="py-2.5 px-3 font-mono text-[11px] text-[#6E7A8A]">FF-03</td>
                  <td className="py-2.5 px-3 font-mono text-[11px]">
                    <span className="text-[#4FAE86]">Q E R P L O T</span>{' '}
                    <span className="text-[#B23B3B] font-semibold">N</span>{' '}
                    <span className="text-[#454E5C]">K A X</span>
                  </td>
                  <td className="py-2.5 px-3 text-[#C25B6B] font-mono text-[11px]">REJECTED</td>
                  <td className="py-2.5 px-3 text-[#6E7A8A]">News embargo window active: UK CPI release in 8m</td>
                </tr>
                <tr className="border-b border-[#232A35] hover:bg-[#161C26]">
                  <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">13:12:44</td>
                  <td className="py-2.5 px-3 text-[#E7EAEE] font-medium">USDJPY</td>
                  <td className="py-2.5 px-3 font-mono text-[11px] text-[#6E7A8A]">FF-02</td>
                  <td className="py-2.5 px-3 font-mono text-[11px] text-[#4FAE86]">
                    Q E R P L O T N K A X
                  </td>
                  <td className="py-2.5 px-3 text-[#4FAE86] font-mono text-[11px]">ACCEPTED</td>
                  <td className="py-2.5 px-3 text-[#6E7A8A]">All 11 gates cleared; routed to ExecutionGateway (ord_usdjpy_01)</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* RISK VIEW */}
      {activeTab === 'RISK' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Open Lane Risk</div>
              <div className="font-mono text-base text-[#E7EAEE]">
                1.8R <span className="text-xs text-[#6E7A8A]">/ 3.0R cap</span>
              </div>
              <div className="text-[10px] text-[#4FAE86] mt-1">60% utilization (Nominal)</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Active Margin Used</div>
              <div className="font-mono text-base text-[#E7EAEE]">$8,420.00</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">17.4% of total equity</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Daily Drawdown</div>
              <div className="font-mono text-base text-[#4FAE86]">+0.65%</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">Halt limit: -3.00%</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Kill Switch Ladder</div>
              <div className="font-mono text-base text-[#4FAE86]">LEVEL 0</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">All execution systems active</div>
            </div>
          </div>
        </div>
      )}

      {/* MODE VIEW */}
      {activeTab === 'MODE' && (
        <div className="space-y-3">
          <div className="w-full overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs min-w-[650px]">
              <thead>
                <tr className="bg-[#10151D] border-b border-[#232A35] text-[11px] text-[#6E7A8A]">
                  <th className="py-2 px-3">mode profile</th>
                  <th className="py-2 px-3">status</th>
                  <th className="py-2 px-3">regime confidence</th>
                  <th className="py-2 px-3">anchor timeframe</th>
                  <th className="py-2 px-3">active symbols</th>
                  <th className="py-2 px-3">calibration state</th>
                </tr>
              </thead>
              <tbody>
                {MODE_PROFILES.map((profile) => (
                  <tr key={profile.name} className="border-b border-[#232A35] hover:bg-[#161C26]">
                    <td className="py-2.5 px-3 font-mono text-[#E7EAEE]">{profile.name}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`font-mono text-[10px] ${
                          profile.status === 'ACTIVE'
                            ? 'text-[#4FAE86]'
                            : profile.status === 'CONSTRAINED'
                            ? 'text-[#BFA13B]'
                            : 'text-[#6E7A8A]'
                        }`}
                      >
                        {profile.status}
                      </span>
                    </td>
                    <td className={`py-2.5 px-3 font-mono ${profile.regimeConfidenceClass}`}>
                      {profile.regimeConfidence}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[#5B8FBF]">{profile.anchorTimeframe}</td>
                    <td className="py-2.5 px-3">
                      <ActiveSymbolsCell symbols={profile.activeSymbols} />
                    </td>
                    <td className="py-2.5 px-3 text-[#6E7A8A]">{profile.calibrationState}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* NEWS VIEW */}
      {activeTab === 'NEWS' && (
        <div className="space-y-4">
          {/* Quick Status Strip */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Active Gate N Embargo</div>
              <div className="font-mono text-base text-[#C25B6B] font-medium">
                {activeEmbargoCount} ENGAGED
              </div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">GBPUSD, EURGBP, GBPJPY (T-15m)</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
              <div className="text-[11px] text-[#6E7A8A] mb-1">High-Impact Events</div>
              <div className="font-mono text-base text-[#C25B6B] font-medium">
                {highImpactCount} Scheduled
              </div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">UK CPI, US NFP, ECB Deposit Rate</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Embargo Buffer Window</div>
              <div className="font-mono text-base text-[#E7EAEE]">±15 min</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">Strict Gate N block prior to release</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Feed Freshness</div>
              <div className="font-mono text-base text-[#4FAE86]">SYNCED (0.4s)</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">Macro Calendar Gateway nominal</div>
            </div>
          </div>

          {/* Collapsible Mobile Filter Controls */}
          <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
            <div className="flex items-center justify-between sm:hidden mb-2">
              <span className="text-xs text-[#6E7A8A]">Filter Event Risk</span>
              <button
                type="button"
                onClick={() => setIsFilterCollapsed(!isFilterCollapsed)}
                className="text-xs text-[#5B8FBF] min-h-[36px] px-2"
              >
                {isFilterCollapsed ? 'Show Filters ▾' : 'Hide Filters ▴'}
              </button>
            </div>

            <div className={`flex flex-wrap items-center gap-2 sm:flex ${isFilterCollapsed ? 'hidden sm:flex' : 'flex'}`}>
              <div className="text-xs text-[#6E7A8A] mr-1">Impact:</div>
              {(['ALL', 'High', 'Med', 'Low'] as const).map((imp) => (
                <button
                  key={imp}
                  type="button"
                  onClick={() => setNewsFilterImpact(imp)}
                  className={`min-h-[36px] px-2.5 py-1 text-xs font-mono rounded-[2px] transition-colors cursor-pointer ${
                    newsFilterImpact === imp
                      ? 'bg-[#5B8FBF] text-[#10151D] font-semibold'
                      : 'bg-[#161C26] text-[#6E7A8A] hover:text-[#E7EAEE] border border-[#232A35]'
                  }`}
                >
                  {imp}
                </button>
              ))}
            </div>
          </div>

          {/* Event Items */}
          <div className="w-full overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs min-w-[700px]">
              <thead>
                <tr className="bg-[#10151D] border-b border-[#232A35] text-[11px] text-[#6E7A8A]">
                  <th className="py-2 px-3">time</th>
                  <th className="py-2 px-3">ccy</th>
                  <th className="py-2 px-3">impact</th>
                  <th className="py-2 px-3">event &amp; details</th>
                  <th className="py-2 px-3">embargo state</th>
                  <th className="py-2 px-3 text-right">source</th>
                </tr>
              </thead>
              <tbody>
                {filteredNews.map((item) => (
                  <tr key={item.id} className="border-b border-[#232A35] hover:bg-[#161C26]">
                    <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">{item.timestamp}</td>
                    <td className="py-2.5 px-3 font-mono font-semibold text-[#E7EAEE]">{item.currency}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`font-mono text-[10px] px-1.5 py-0.5 rounded-[2px] ${
                          item.impact === 'High'
                            ? 'bg-[#C25B6B]/20 text-[#C25B6B]'
                            : item.impact === 'Med'
                            ? 'bg-[#BFA13B]/20 text-[#BFA13B]'
                            : 'bg-[#6E7A8A]/20 text-[#6E7A8A]'
                        }`}
                      >
                        {item.impact}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="text-[#E7EAEE] font-medium">{item.title}</div>
                      <div className="text-[11px] text-[#6E7A8A] mt-0.5">{item.details}</div>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px]">
                      {item.embargoActive ? (
                        <span className="text-[#C25B6B] font-semibold bg-[#C25B6B]/10 px-1.5 py-0.5 rounded-[2px] border border-[#C25B6B]/30">
                          EMBARGO ACTIVE
                        </span>
                      ) : (
                        <span className="text-[#6E7A8A]">None</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[10px] text-[#6E7A8A] text-right">
                      {item.source}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* CALIBRATION VIEW */}
      {activeTab === 'CALIB' && (
        <div className="space-y-3">
          <div className="text-xs text-[#6E7A8A]">
            Parameter rollout stage tracking per Quant Layer discipline (SHADOW → PAPER → CANARY → ACTIVE).
          </div>
          <div className="w-full overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs min-w-[650px]">
              <thead>
                <tr className="bg-[#10151D] border-b border-[#232A35] text-[11px] text-[#6E7A8A]">
                  <th className="py-2 px-3">parameter</th>
                  <th className="py-2 px-3">effective config</th>
                  <th className="py-2 px-3">rollout stage</th>
                  <th className="py-2 px-3">current value</th>
                  <th className="py-2 px-3">validation sample</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-[#232A35] hover:bg-[#161C26]">
                  <td className="py-2.5 px-3 font-mono text-[#E7EAEE]">adaptive_trail_k_factor</td>
                  <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">cfg_7f2a19c4</td>
                  <td className="py-2.5 px-3 text-[#4FAE86] font-mono text-[10px]">ACTIVE</td>
                  <td className="py-2.5 px-3 font-mono text-[#E7EAEE]">3.60</td>
                  <td className="py-2.5 px-3 text-[#6E7A8A]">1,420 trades (p &lt; 0.001)</td>
                </tr>
                <tr className="border-b border-[#232A35] hover:bg-[#161C26]">
                  <td className="py-2.5 px-3 font-mono text-[#E7EAEE]">counterflow_exhaustion_threshold</td>
                  <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">cfg_5e1b82a0</td>
                  <td className="py-2.5 px-3 text-[#BFA13B] font-mono text-[10px]">CANARY</td>
                  <td className="py-2.5 px-3 font-mono text-[#E7EAEE]">2.00σ</td>
                  <td className="py-2.5 px-3 text-[#6E7A8A]">240 trades (live sandbox)</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* HEALTH VIEW */}
      {activeTab === 'HEALTH' && (
        <div className="space-y-4">
          <div className="bg-[#10151D] border border-[#232A35] p-3 text-xs space-y-2 rounded-[2px]">
            <div className="flex justify-between border-b border-[#232A35] pb-1.5">
              <span className="text-[#6E7A8A]">Execution Gateway Bridge</span>
              <span className="text-[#4FAE86] font-mono">CONNECTED (0.7ms latency)</span>
            </div>
            <div className="flex justify-between border-b border-[#232A35] pb-1.5">
              <span className="text-[#6E7A8A]">Fence Consensus Epoch</span>
              <span className="text-[#E7EAEE] font-mono">epoch 418 (peer confirmed)</span>
            </div>
            <div className="flex justify-between border-b border-[#232A35] pb-1.5">
              <span className="text-[#6E7A8A]">Market Feed Heartbeat</span>
              <span className="text-[#4FAE86] font-mono">NOMINAL · 0 gaps detected</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#6E7A8A]">Authentication &amp; Role</span>
              <span className="text-[#E7EAEE] font-mono">daniel · OPERATOR (write_gated)</span>
            </div>
          </div>
        </div>
      )}

      {/* STATS VIEW */}
      {activeTab === 'STATS' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Win Rate</div>
              <div className="font-mono text-xl text-[#4FAE86] font-semibold">{stats.winRate.toFixed(1)}%</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">{stats.winCount} wins / {stats.lossCount} losses</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Profit Factor</div>
              <div className="font-mono text-xl text-[#4FAE86] font-semibold">{stats.profitFactor.toFixed(2)}</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">Gross Win / Gross Loss</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Trade Expectancy</div>
              <div className="font-mono text-xl text-[#4FAE86] font-semibold">+{stats.expectancy.toFixed(2)}R</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">Average return per risk unit</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Cumulative Realized PnL</div>
              <div className="font-mono text-xl text-[#4FAE86] font-semibold">+${stats.totalPnl.toFixed(2)}</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">From {stats.totalTrades} journal-verified trades</div>
            </div>
          </div>

          <div className="bg-[#10151D] border border-[#232A35] p-4 rounded-[2px] space-y-2 text-xs">
            <div className="font-semibold text-xs text-[#E7EAEE] mb-2 uppercase tracking-wide">
              Trade Performance Invariant Breakdown
            </div>
            <div className="flex justify-between border-b border-[#232A35] py-1.5">
              <span className="text-[#6E7A8A]">Average Win Magnitude</span>
              <span className="font-mono text-[#4FAE86]">+{stats.avgWin.toFixed(2)}R</span>
            </div>
            <div className="flex justify-between border-b border-[#232A35] py-1.5">
              <span className="text-[#6E7A8A]">Average Loss Magnitude</span>
              <span className="font-mono text-[#C25B6B]">-{stats.avgLoss.toFixed(2)}R</span>
            </div>
            <div className="flex justify-between border-b border-[#232A35] py-1.5">
              <span className="text-[#6E7A8A]">Total Realized R</span>
              <span className="font-mono text-[#4FAE86]">+{stats.totalR.toFixed(2)}R</span>
            </div>
            <div className="flex justify-between pt-1.5">
              <span className="text-[#6E7A8A]">Ledger Verification Status</span>
              <span className="font-mono text-[#5B8FBF]">CONFIRMED HISTORICAL (NO OPEN RISK INCLUDED)</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
