import React, { useState, useMemo } from 'react';
import { NavTab, MarketNewsItem, NewsImpactLevel, NewsCategory } from '../types.ts';
import { INITIAL_MARKET_NEWS } from '../data/mockData.ts';

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
        <div className="relative inline-block">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setIsOpen((prev) => !prev);
            }}
            className="px-1.5 py-0.5 font-mono text-[10px] text-[#5B8FBF] bg-[#161C26] hover:bg-[#5B8FBF]/15 border border-[#232A35] hover:border-[#5B8FBF] rounded-[2px] transition-colors cursor-pointer select-none inline-flex items-center gap-1"
          >
            <span>+{extraSymbols.length} more</span>
            <span className="text-[8px] text-[#6E7A8A]">{isOpen ? '▲' : '▼'}</span>
          </button>

          {isOpen && (
            <div className="absolute left-0 top-full mt-1 z-30 min-w-[150px] bg-[#10151D] border border-[#232A35] py-1 text-xs select-none">
              <div className="px-2.5 py-1 text-[10px] font-sans font-medium text-[#6E7A8A] border-b border-[#232A35] flex justify-between items-center">
                <span>Active Symbols</span>
                <span className="font-mono text-[#4FAE86] text-[9px]">+{extraSymbols.length}</span>
              </div>
              <div className="max-h-44 overflow-y-auto py-0.5">
                {extraSymbols.map((sym) => (
                  <div
                    key={sym}
                    className="px-2.5 py-1.5 font-mono text-[11px] text-[#E7EAEE] hover:bg-[#161C26] flex items-center justify-between border-b border-[#232A35]/50 last:border-b-0"
                  >
                    <span>{sym}</span>
                    <span className="font-mono text-[9px] text-[#4FAE86] px-1 py-0.2 rounded-[2px] bg-[#4FAE86]/10">ACTIVE</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export const SecondaryViews: React.FC<SecondaryViewsProps> = ({
  activeTab,
  onReturnToPositions,
  newsItems,
}) => {
  const [selectedImpact, setSelectedImpact] = useState<string>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedCurrency, setSelectedCurrency] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedNewsId, setExpandedNewsId] = useState<string | null>('news_01');

  const allNews = newsItems || INITIAL_MARKET_NEWS;

  const filteredNews = useMemo(() => {
    return allNews.filter((item) => {
      if (selectedImpact !== 'ALL' && item.impact !== selectedImpact) return false;
      if (selectedCategory !== 'ALL' && item.category !== selectedCategory) return false;
      if (selectedCurrency !== 'ALL' && item.currency !== selectedCurrency) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          item.title.toLowerCase().includes(q) ||
          item.details.toLowerCase().includes(q) ||
          item.source.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [allNews, selectedImpact, selectedCategory, selectedCurrency, searchQuery]);

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-[#0A0E14] overflow-auto p-4 select-none">
      <div className="flex items-center justify-between pb-3 mb-4 border-b border-[#232A35]">
        <div className="flex items-center gap-3">
          <h2 className="text-xs font-semibold text-[#E7EAEE] tracking-tight">
            {activeTab === 'DEC' && 'Decision Snapshots & Candidate Gate Rejections'}
            {activeTab === 'RISK' && 'Per-Lane Risk State & Exposure Caps'}
            {activeTab === 'MODE' && 'Mode Profiles & Regime Confidence Gate'}
            {activeTab === 'NEWS' && 'Market Event Feed & Gate N Embargo Telemetry'}
            {activeTab === 'CALIB' && 'Calibration Service & Parameter Rollout Stages'}
            {activeTab === 'HEALTH' && 'System Health, Bridge Session & Fence Peer'}
          </h2>
          <span className="font-mono text-[10px] text-[#6E7A8A]">lane ACT_PRIMARY</span>
        </div>
        <button
          onClick={onReturnToPositions}
          title="Return to Positions table (Hotkey: Esc or Backspace)"
          className="px-2.5 py-1 text-xs font-sans text-[#5B8FBF] hover:bg-[#5B8FBF]/10 border border-[#5B8FBF] rounded-[2px] transition-colors cursor-pointer flex items-center gap-1.5"
        >
          <span>Back to Positions (POS)</span>
          <span className="font-mono text-[10px] bg-[#5B8FBF]/20 px-1 py-0.5 rounded-[2px]">Esc</span>
        </button>
      </div>

      {activeTab === 'DEC' && (
        <div className="space-y-4">
          <div className="text-xs text-[#6E7A8A]">
            Sequential 11-gate chain telemetry for recent candidate evaluations (<span className="font-mono">Q E R P L O T N K A X</span>).
          </div>
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="bg-[#10151D] border-b border-[#232A35] text-[11px] text-[#6E7A8A]">
                <th className="py-2 px-3">time</th>
                <th className="py-2 px-3">symbol</th>
                <th className="py-2 px-3">setup</th>
                <th className="py-2 px-3">gate status</th>
                <th className="py-2 px-3">terminal outcome</th>
                <th className="py-2 px-3">rejection rationale</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-[#232A35] hover:bg-[#161C26]">
                <td className="py-2 px-3 font-mono text-[#6E7A8A]">14:04:12</td>
                <td className="py-2 px-3 text-[#E7EAEE] font-medium">EURUSD</td>
                <td className="py-2 px-3 font-mono text-[11px] text-[#6E7A8A]">FF-01</td>
                <td className="py-2 px-3 font-mono text-[11px]">
                  <span className="text-[#4FAE86]">Q E R P</span> <span className="text-[#B23B3B] font-semibold">L</span> <span className="text-[#454E5C]">O T N K A X</span>
                </td>
                <td className="py-2 px-3 text-[#C25B6B] font-mono text-[11px]">REJECTED</td>
                <td className="py-2 px-3 text-[#6E7A8A]">Location congested: price inside 15M swing congestion zone</td>
              </tr>
              <tr className="border-b border-[#232A35] hover:bg-[#161C26]">
                <td className="py-2 px-3 font-mono text-[#6E7A8A]">13:48:05</td>
                <td className="py-2 px-3 text-[#E7EAEE] font-medium">GBPUSD</td>
                <td className="py-2 px-3 font-mono text-[11px] text-[#6E7A8A]">FF-03</td>
                <td className="py-2 px-3 font-mono text-[11px]">
                  <span className="text-[#4FAE86]">Q E R P L O T</span> <span className="text-[#B23B3B] font-semibold">N</span> <span className="text-[#454E5C]">K A X</span>
                </td>
                <td className="py-2 px-3 text-[#C25B6B] font-mono text-[11px]">REJECTED</td>
                <td className="py-2 px-3 text-[#6E7A8A]">News embargo window active: UK CPI release in 8m</td>
              </tr>
              <tr className="border-b border-[#232A35] hover:bg-[#161C26]">
                <td className="py-2 px-3 font-mono text-[#6E7A8A]">13:12:44</td>
                <td className="py-2 px-3 text-[#E7EAEE] font-medium">USDJPY</td>
                <td className="py-2 px-3 font-mono text-[11px] text-[#6E7A8A]">FF-02</td>
                <td className="py-2 px-3 font-mono text-[11px] text-[#4FAE86]">
                  Q E R P L O T N K A X
                </td>
                <td className="py-2 px-3 text-[#4FAE86] font-mono text-[11px]">ACCEPTED</td>
                <td className="py-2 px-3 text-[#6E7A8A]">All 11 gates cleared; routed to ExecutionGateway (ord_usdjpy_01)</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'RISK' && (
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-3">
            <div className="bg-[#10151D] border border-[#232A35] p-3">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Open Lane Risk</div>
              <div className="font-mono text-base text-[#E7EAEE]">1.8R <span className="text-xs text-[#6E7A8A]">/ 3.0R cap</span></div>
              <div className="text-[10px] text-[#4FAE86] mt-1">60% utilization (Nominal)</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Active Margin Used</div>
              <div className="font-mono text-base text-[#E7EAEE]">$8,420.00</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">17.4% of total equity</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Daily Drawdown</div>
              <div className="font-mono text-base text-[#4FAE86]">+0.65%</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">Halt limit: -3.00%</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Kill Switch Ladder</div>
              <div className="font-mono text-base text-[#4FAE86]">LEVEL 0</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">All execution systems active</div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'MODE' && (
        <div className="space-y-3">
          <table className="w-full border-collapse text-left text-xs">
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
                  <td className="py-2 px-3 font-mono text-[#E7EAEE]">{profile.name}</td>
                  <td className="py-2 px-3">
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
                  <td className={`py-2 px-3 font-mono ${profile.regimeConfidenceClass}`}>
                    {profile.regimeConfidence}
                  </td>
                  <td className="py-2 px-3 font-mono text-[#5B8FBF]">{profile.anchorTimeframe}</td>
                  <td className="py-2 px-3">
                    <ActiveSymbolsCell symbols={profile.activeSymbols} />
                  </td>
                  <td className="py-2 px-3 text-[#6E7A8A]">{profile.calibrationState}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'NEWS' && (
        <div className="space-y-4">
          {/* Top Quick Status Strip */}
          <div className="grid grid-cols-4 gap-3">
            <div className="bg-[#10151D] border border-[#232A35] p-3">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Active Gate N Embargo</div>
              <div className="font-mono text-base text-[#C25B6B] font-medium">1 ENGAGED</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">GBPUSD, EURGBP, GBPJPY (T-15m)</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3">
              <div className="text-[11px] text-[#6E7A8A] mb-1">High-Impact Events</div>
              <div className="font-mono text-base text-[#C25B6B] font-medium">3 Scheduled</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">UK CPI, US NFP, ECB Deposit Rate</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3">
              <div className="text-[11px] text-[#6E7A8A] mb-1">System Announcements</div>
              <div className="font-mono text-base text-[#BFA13B] font-medium">3 Directives</div>
              <div className="text-[10px] text-[#6E7A8A] mt-1">Fence Epoch 418, Cooldown, Calib</div>
            </div>
            <div className="bg-[#10151D] border border-[#232A35] p-3">
              <div className="text-[11px] text-[#6E7A8A] mb-1">Pipeline Feed Status</div>
              <div className="font-mono text-base text-[#4FAE86] font-medium">NOMINAL</div>
              <div className="text-[10px] text-[#4FAE86] mt-1">Low-latency wire connected (0 gaps)</div>
            </div>
          </div>

          {/* Filters Bar */}
          <div className="bg-[#10151D] border border-[#232A35] p-2.5 flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-[#6E7A8A] font-medium">Impact Level:</span>
              <div className="flex gap-1">
                {['ALL', 'High', 'Med', 'Low'].map((lvl) => (
                  <button
                    key={lvl}
                    onClick={() => setSelectedImpact(lvl)}
                    className={`px-2 py-0.5 text-[10px] font-mono rounded-[2px] border transition-colors cursor-pointer ${
                      selectedImpact === lvl
                        ? 'border-[#5B8FBF] bg-[#5B8FBF]/15 text-[#5B8FBF] font-semibold'
                        : 'border-[#232A35] bg-[#161C26] text-[#6E7A8A] hover:text-[#E7EAEE]'
                    }`}
                  >
                    {lvl === 'ALL' ? 'ALL IMPACT' : lvl.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] text-[#6E7A8A] font-medium">Category:</span>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="bg-[#161C26] text-[#E7EAEE] font-mono text-[11px] border border-[#232A35] rounded-[2px] px-2 py-0.5 outline-none cursor-pointer focus:border-[#5B8FBF]"
              >
                <option value="ALL">All Categories</option>
                <option value="GATE_N_EMBARGO">Gate N Embargo</option>
                <option value="MACRO_ECONOMIC">Macro Economic</option>
                <option value="CENTRAL_BANK">Central Bank</option>
                <option value="SYSTEM_ANNOUNCEMENT">System Announcement</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] text-[#6E7A8A] font-medium">Currency:</span>
              <select
                value={selectedCurrency}
                onChange={(e) => setSelectedCurrency(e.target.value)}
                className="bg-[#161C26] text-[#E7EAEE] font-mono text-[11px] border border-[#232A35] rounded-[2px] px-2 py-0.5 outline-none cursor-pointer focus:border-[#5B8FBF]"
              >
                <option value="ALL">All Currencies</option>
                <option value="USD">USD</option>
                <option value="GBP">GBP</option>
                <option value="EUR">EUR</option>
                <option value="CHF">CHF</option>
              </select>
            </div>

            <div className="flex-1 min-w-[180px] max-w-[260px]">
              <input
                type="text"
                placeholder="Search headlines / wire..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[#161C26] text-[#E7EAEE] placeholder-[#454E5C] font-sans text-xs border border-[#232A35] rounded-[2px] px-2.5 py-1 outline-none focus:border-[#5B8FBF]"
              />
            </div>
          </div>

          {/* Curated Feed Table */}
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="bg-[#10151D] border-b border-[#232A35] text-[11px] text-[#6E7A8A]">
                <th className="py-2 px-3 w-20">time</th>
                <th className="py-2 px-3 w-20">impact</th>
                <th className="py-2 px-3 w-16">cur</th>
                <th className="py-2 px-3 w-40">category</th>
                <th className="py-2 px-3">headline &amp; market telemetry</th>
                <th className="py-2 px-3 text-right w-44">source</th>
              </tr>
            </thead>
            <tbody>
              {filteredNews.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-[#6E7A8A] text-xs">
                    No market news or announcements matching the active filter criteria.
                  </td>
                </tr>
              ) : (
                filteredNews.map((item) => {
                  const isExpanded = expandedNewsId === item.id;
                  let impactStyle = 'bg-[#4FAE86]/[0.16] text-[#4FAE86] border-[#4FAE86]/40';
                  if (item.impact === 'High') {
                    impactStyle = 'bg-[#C25B6B]/[0.18] text-[#C25B6B] border-[#C25B6B]/45 font-semibold';
                  } else if (item.impact === 'Med') {
                    impactStyle = 'bg-[#BFA13B]/[0.18] text-[#BFA13B] border-[#BFA13B]/45 font-medium';
                  }

                  return (
                    <tr
                      key={item.id}
                      onClick={() => setExpandedNewsId(isExpanded ? null : item.id)}
                      className="border-b border-[#232A35] hover:bg-[#161C26] cursor-pointer transition-colors"
                    >
                      <td className="py-2.5 px-3 font-mono text-[#6E7A8A] tabular-nums align-top text-[11px]">
                        {item.timestamp}
                      </td>
                      <td className="py-2.5 px-3 align-top">
                        <span className={`font-mono text-[9px] px-1.5 py-0.5 rounded-[2px] border ${impactStyle}`}>
                          {item.impact.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[#E7EAEE] font-medium align-top">
                        {item.currency}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[10px] text-[#6E7A8A] align-top">
                        {item.category.replace(/_/g, ' ')}
                      </td>
                      <td className="py-2.5 px-3 align-top">
                        <div className="font-medium text-[#E7EAEE] mb-1 flex items-center gap-2 flex-wrap">
                          <span>{item.title}</span>
                          {item.embargoActive && (
                            <span className="font-mono text-[9px] px-1 py-0.2 rounded-[2px] bg-[#B23B3B]/20 text-[#B23B3B] border border-[#B23B3B]/40 font-semibold">
                              GATE N HALT
                            </span>
                          )}
                        </div>

                        {/* Macro metrics strip if present */}
                        {(item.actual || item.forecast || item.previous) && (
                          <div className="flex items-center gap-3 font-mono text-[10px] text-[#6E7A8A] my-1 bg-[#10151D] px-2 py-0.5 rounded-[2px] w-fit border border-[#232A35]">
                            {item.actual && (
                              <span>
                                ACTUAL: <strong className="text-[#4FAE86]">{item.actual}</strong>
                              </span>
                            )}
                            {item.forecast && <span>FCST: {item.forecast}</span>}
                            {item.previous && <span>PREV: {item.previous}</span>}
                          </div>
                        )}

                        {/* Detailed narrative */}
                        <div className={`text-[11px] text-[#6E7A8A] leading-relaxed ${isExpanded ? '' : 'line-clamp-1'}`}>
                          {item.details}
                        </div>

                        {item.affectedSymbols && item.affectedSymbols.length > 0 && (
                          <div className="flex items-center gap-1.5 mt-1.5 text-[10px] font-mono text-[#5B8FBF]">
                            <span className="text-[#6E7A8A]">AFFECTED:</span>
                            {item.affectedSymbols.map((sym) => (
                              <span key={sym} className="bg-[#161C26] px-1 rounded-[2px] border border-[#232A35]">
                                {sym}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[10px] text-[#6E7A8A] text-right align-top whitespace-nowrap">
                        {item.source}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'CALIB' && (
        <div className="space-y-3">
          <div className="text-xs text-[#6E7A8A]">
            Parameter rollout stage tracking per Quant Layer discipline (SHADOW → PAPER → CANARY → ACTIVE).
          </div>
          <table className="w-full border-collapse text-left text-xs">
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
                <td className="py-2 px-3 font-mono text-[#E7EAEE]">adaptive_trail_k_factor</td>
                <td className="py-2 px-3 font-mono text-[#6E7A8A]">cfg_7f2a19c4</td>
                <td className="py-2 px-3 text-[#4FAE86] font-mono text-[10px]">ACTIVE</td>
                <td className="py-2 px-3 font-mono text-[#E7EAEE]">3.60</td>
                <td className="py-2 px-3 text-[#6E7A8A]">1,420 trades (p &lt; 0.001)</td>
              </tr>
              <tr className="border-b border-[#232A35] hover:bg-[#161C26]">
                <td className="py-2 px-3 font-mono text-[#E7EAEE]">counterflow_exhaustion_threshold</td>
                <td className="py-2 px-3 font-mono text-[#6E7A8A]">cfg_5e1b82a0</td>
                <td className="py-2 px-3 text-[#BFA13B] font-mono text-[10px]">CANARY</td>
                <td className="py-2 px-3 font-mono text-[#E7EAEE]">2.00σ</td>
                <td className="py-2 px-3 text-[#6E7A8A]">240 trades (live sandbox)</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'HEALTH' && (
        <div className="space-y-4">
          <div className="bg-[#10151D] border border-[#232A35] p-3 text-xs space-y-2">
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
    </div>
  );
};
