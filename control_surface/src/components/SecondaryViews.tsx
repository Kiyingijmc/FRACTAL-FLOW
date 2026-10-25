import React, { useState, useMemo } from 'react';
import { 
  ExtendedNavTab, 
  MarketNewsItem, 
  NewsImpactLevel, 
  NewsCategory,
  QuantModelRecord,
  ModelAdviceRecord,
  RolloutPromotionEvent,
  LabRunArtifact,
  RemediationBlockerRecord,
  AuditTrailRecord,
  Position,
  OperationalRiskConfig
} from '../types';
import { evaluatePortfolioRisk } from '../utils/riskValidator';
import { 
  INITIAL_POSITIONS,
  INITIAL_MARKET_NEWS, 
  INITIAL_CLOSED_TRADES,
  INITIAL_QUANT_MODELS,
  INITIAL_MODEL_ADVICE_STREAM,
  INITIAL_ROLLOUT_PROMOTIONS,
  INITIAL_LAB_RUNS,
  INITIAL_REMEDIATION_BLOCKERS,
  INITIAL_AUDIT_TRAIL
} from '../data/mockData';
import { 
  ShieldCheck, 
  Layers, 
  Database, 
  FlaskConical, 
  AlertTriangle, 
  History,
  Lock,
  Cpu,
  CheckCircle2,
  XCircle,
  FileText
} from 'lucide-react';

interface SecondaryViewsProps {
  activeTab: ExtendedNavTab;
  onReturnToPositions: () => void;
  newsItems?: MarketNewsItem[];
  quantModels?: QuantModelRecord[];
  modelAdvice?: ModelAdviceRecord[];
  rolloutPromotions?: RolloutPromotionEvent[];
  labRuns?: LabRunArtifact[];
  blockers?: RemediationBlockerRecord[];
  auditTrail?: AuditTrailRecord[];
  positions?: Position[];
  riskConfig?: OperationalRiskConfig;
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
            <div className="absolute left-0 bottom-full mb-1 z-50 bg-[#10151D] border border-[#232A35] p-2 rounded-[2px] shadow-lg flex flex-wrap gap-1 min-w-[120px]">
              {symbols.map((s) => (
                <span key={s} className="px-1.5 py-0.5 bg-[#161C26] text-[#E7EAEE] text-[10px] font-mono border border-[#232A35]">
                  {s}
                </span>
              ))}
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
  quantModels = INITIAL_QUANT_MODELS,
  modelAdvice = INITIAL_MODEL_ADVICE_STREAM,
  rolloutPromotions = INITIAL_ROLLOUT_PROMOTIONS,
  labRuns = INITIAL_LAB_RUNS,
  blockers = INITIAL_REMEDIATION_BLOCKERS,
  auditTrail = INITIAL_AUDIT_TRAIL,
  positions,
  riskConfig
}) => {
  // News filtering state
  const [newsFilterImpact, setNewsFilterImpact] = useState<NewsImpactLevel | 'ALL'>('ALL');
  const [newsFilterCategory, setNewsFilterCategory] = useState<NewsCategory | 'ALL'>('ALL');
  const [isFilterCollapsed, setIsFilterCollapsed] = useState(true);

  // QUANT view sub-tabs
  const [quantSubTab, setQuantSubTab] = useState<'params' | 'registry' | 'advice' | 'promotions'>('params');

  // Lab view selected run
  const [selectedLabRunId, setSelectedLabRunId] = useState<string>(labRuns[0]?.id || '');
  const activeLabRun = useMemo(() => {
    return labRuns.find(r => r.id === selectedLabRunId) || labRuns[0];
  }, [labRuns, selectedLabRunId]);

  // Closed trades stats computation
  const stats = useMemo(() => {
    const totalTrades = INITIAL_CLOSED_TRADES.length;
    const wins = INITIAL_CLOSED_TRADES.filter((t) => t.realizedR > 0);
    const losses = INITIAL_CLOSED_TRADES.filter((t) => t.realizedR < 0);
    const winCount = wins.length;
    const lossCount = losses.length;
    const winRate = totalTrades > 0 ? (winCount / totalTrades) * 100 : 0;

    const grossWinR = wins.reduce((acc, t) => acc + t.realizedR, 0);
    const grossLossR = Math.abs(losses.reduce((acc, t) => acc + t.realizedR, 0));
    const profitFactor = grossLossR > 0 ? grossWinR / grossLossR : grossWinR > 0 ? 99.9 : 0;

    const totalR = INITIAL_CLOSED_TRADES.reduce((acc, t) => acc + t.realizedR, 0);
    const totalPnl = INITIAL_CLOSED_TRADES.reduce((acc, t) => acc + t.realizedPnl, 0);
    const expectancy = totalTrades > 0 ? totalR / totalTrades : 0;
    const avgWin = winCount > 0 ? grossWinR / winCount : 0;
    const avgLoss = lossCount > 0 ? grossLossR / lossCount : 0;

    return { totalTrades, winCount, lossCount, winRate, profitFactor, totalR, totalPnl, expectancy, avgWin, avgLoss };
  }, []);

  const filteredNews = useMemo(() => {
    return newsItems.filter((item) => {
      const matchImpact = newsFilterImpact === 'ALL' || item.impact === newsFilterImpact;
      const matchCategory = newsFilterCategory === 'ALL' || item.category === newsFilterCategory;
      return matchImpact && matchCategory;
    });
  }, [newsItems, newsFilterImpact, newsFilterCategory]);

  return (
    <div className="flex-1 flex flex-col p-4 overflow-y-auto space-y-4">
      {/* Back button header for mobile context */}
      <div className="flex items-center justify-between border-b border-[#232A35] pb-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-[#5B8FBF] uppercase font-bold tracking-wider">
            {activeTab === 'CALIB' ? 'CALIB / QUANT LAYER' : activeTab}
          </span>
          <span className="text-[#6E7A8A] text-xs">·</span>
          <span className="text-xs text-[#6E7A8A]">
            {activeTab === 'DEC' && 'System Decision Snapshot & Rejection Journal'}
            {activeTab === 'RISK' && 'Account & Lane Risk Capacity Allocation'}
            {activeTab === 'MODE' && 'Structural Mode Profile Engine & Timeframe Alignment'}
            {activeTab === 'NEWS' && 'Gate N Macro News Shield & Volatility Embargoes'}
            {activeTab === 'CALIB' && 'Parameters, Models, Real-Time Advice & Promotion Rollout'}
            {activeTab === 'HEALTH' && 'Bridge Connectivity, Fence Consensus & Security Telemetry'}
            {activeTab === 'STATS' && 'Journal-Verified Historical Performance Analytics'}
            {activeTab === 'LAB' && 'Read-Only Backtesting & Robustness Analysis (Synthetic Fixtures)'}
            {activeTab === 'OPS' && 'Operational Blocker Register & Governance Matrix'}
            {activeTab === 'AUDIT' && 'Session Audit Log (Non-Authoritative / Simulation Only)'}
          </span>
        </div>
        <button
          type="button"
          onClick={onReturnToPositions}
          className="md:hidden text-xs text-[#5B8FBF] hover:underline font-mono min-h-[44px] flex items-center px-2"
        >
          ← POSITIONS
        </button>
      </div>

      {/* DECISIONS VIEW */}
      {activeTab === 'DEC' && (
        <div className="space-y-3">
          <div className="text-xs text-[#6E7A8A]">
            Recent candidate signal evaluations across all monitored currency lanes.
          </div>
          <div className="w-full overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs min-w-[650px]">
              <thead>
                <tr className="bg-[#10151D] border-b border-[#232A35] text-[11px] text-[#6E7A8A]">
                  <th className="py-2 px-3">time</th>
                  <th className="py-2 px-3">symbol</th>
                  <th className="py-2 px-3">setup</th>
                  <th className="py-2 px-3">gate status</th>
                  <th className="py-2 px-3">decision rationale</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-[#232A35] hover:bg-[#161C26]">
                  <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">14:02:11</td>
                  <td className="py-2.5 px-3 font-mono font-semibold text-[#E7EAEE]">EURUSD</td>
                  <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">FF-01</td>
                  <td className="py-2.5 px-3 text-[#4FAE86] font-mono text-[10px]">ALL GATES PASSED</td>
                  <td className="py-2.5 px-3 text-[#E7EAEE]">Order dispatched to Execution Gateway (1.08420 entry)</td>
                </tr>
                <tr className="border-b border-[#232A35] hover:bg-[#161C26]">
                  <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">13:58:30</td>
                  <td className="py-2.5 px-3 font-mono font-semibold text-[#E7EAEE]">GBPUSD</td>
                  <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">FF-03</td>
                  <td className="py-2.5 px-3 text-[#C25B6B] font-mono text-[10px]">BLOCKED AT L</td>
                  <td className="py-2.5 px-3 text-[#E7EAEE]">Location congested: price inside 15M swing congestion zone</td>
                </tr>
                <tr className="border-b border-[#232A35] hover:bg-[#161C26]">
                  <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">13:45:00</td>
                  <td className="py-2.5 px-3 font-mono font-semibold text-[#E7EAEE]">USDJPY</td>
                  <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">FF-02</td>
                  <td className="py-2.5 px-3 text-[#C25B6B] font-mono text-[10px]">BLOCKED AT N</td>
                  <td className="py-2.5 px-3 text-[#E7EAEE]">News embargo: Gate N pre-embargo window active for JPY</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* RISK VIEW */}
      {activeTab === 'RISK' && (() => {
        const targetPositions = positions || INITIAL_POSITIONS;
        const portfolioEval = evaluatePortfolioRisk(targetPositions);
        const laneEval = evaluatePortfolioRisk(targetPositions, 'ACT_PRIMARY');
        const accountCap = riskConfig?.maxAccountExposureR ?? 5.0;
        const laneCap = riskConfig?.maxLaneRiskR ?? 2.5;

        const totalRiskDisplay = portfolioEval.status === 'VALID' && portfolioEval.totalRiskR !== null
          ? `${portfolioEval.totalRiskR.toFixed(2)}R`
          : 'INVALID';
        const laneRiskDisplay = laneEval.status === 'VALID' && laneEval.totalRiskR !== null
          ? `${laneEval.totalRiskR.toFixed(2)}R`
          : 'INVALID';

        const accountPercent = portfolioEval.status === 'VALID' && portfolioEval.totalRiskR !== null
          ? Math.round((portfolioEval.totalRiskR / accountCap) * 100)
          : null;
        const lanePercent = laneEval.status === 'VALID' && laneEval.totalRiskR !== null
          ? Math.round((laneEval.totalRiskR / laneCap) * 100)
          : null;

        return (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
                <div className="text-[11px] text-[#6E7A8A] mb-1">Total Open Risk</div>
                <div data-testid="secondary-total-open-risk" className={`font-mono text-xl font-semibold ${portfolioEval.status === 'VALID' ? 'text-[#E7EAEE]' : 'text-[#C25B6B]'}`}>
                  {totalRiskDisplay}
                </div>
                <div className="text-[10px] text-[#4FAE86] mt-1">
                  {accountPercent !== null ? `${accountPercent}% of ${accountCap.toFixed(2)}R cap` : 'Risk evaluation invalid'}
                </div>
              </div>
              <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
                <div className="text-[11px] text-[#6E7A8A] mb-1">Max Lane Risk (ACT_PRIM)</div>
                <div data-testid="secondary-lane-risk" className={`font-mono text-xl font-semibold ${laneEval.status === 'VALID' ? 'text-[#E7EAEE]' : 'text-[#C25B6B]'}`}>
                  {laneRiskDisplay}
                </div>
                <div className="text-[10px] text-[#4FAE86] mt-1">
                  {lanePercent !== null ? `${lanePercent}% of ${laneCap.toFixed(2)}R lane cap` : 'Lane evaluation invalid'}
                </div>
              </div>
              <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
                <div className="text-[11px] text-[#6E7A8A] mb-1">Daily Loss Limit</div>
                <div className="font-mono text-xl text-[#4FAE86] font-semibold">+$312.50</div>
                <div className="text-[10px] text-[#6E7A8A] mt-1">
                  Circuit breaker: -${riskConfig ? riskConfig.dailyLossLimitUsd.toLocaleString() : '1,500.00'}
                </div>
              </div>
              <div className="bg-[#10151D] border border-[#232A35] p-3 rounded-[2px]">
                <div className="text-[11px] text-[#6E7A8A] mb-1">Kill-Switch State</div>
                <div className="font-mono text-xl text-[#4FAE86] font-semibold">NOMINAL</div>
                <div className="text-[10px] text-[#4FAE86] mt-1">L0 Normal Operation</div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* MODE VIEW */}
      {activeTab === 'MODE' && (
        <div className="space-y-3">
          <div className="text-xs text-[#6E7A8A]">
            Active mode profile eligibility, timeframe anchors, and regime-confidence ratings per 01_MODE_PROFILES_ARCHITECTURE.
          </div>
          <div className="w-full overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs min-w-[700px]">
              <thead>
                <tr className="bg-[#10151D] border-b border-[#232A35] text-[11px] text-[#6E7A8A]">
                  <th className="py-2 px-3">profile name</th>
                  <th className="py-2 px-3">status</th>
                  <th className="py-2 px-3">regime confidence</th>
                  <th className="py-2 px-3">anchor tf</th>
                  <th className="py-2 px-3">active symbols</th>
                  <th className="py-2 px-3">calibration state</th>
                </tr>
              </thead>
              <tbody>
                {MODE_PROFILES.map((profile) => (
                  <tr key={profile.name} className="border-b border-[#232A35] hover:bg-[#161C26]">
                    <td className="py-2.5 px-3 font-mono font-semibold text-[#E7EAEE]">{profile.name}</td>
                    <td className="py-2.5 px-3">
                      <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded-[2px] ${
                        profile.status === 'ACTIVE'
                          ? 'bg-[#4FAE86]/20 text-[#4FAE86]'
                          : profile.status === 'CONSTRAINED'
                          ? 'bg-[#BFA13B]/20 text-[#BFA13B]'
                          : 'bg-[#6E7A8A]/20 text-[#6E7A8A]'
                      }`}>
                        {profile.status}
                      </span>
                    </td>
                    <td className={`py-2.5 px-3 font-mono text-[11px] ${profile.regimeConfidenceClass}`}>
                      {profile.regimeConfidence}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[#5B8FBF]">{profile.anchorTimeframe}</td>
                    <td className="py-2.5 px-3">
                      <ActiveSymbolsCell symbols={profile.activeSymbols} />
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-[#6E7A8A]">{profile.calibrationState}</td>
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
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#232A35] pb-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-[#E7EAEE] uppercase font-bold">
                Economic Calendar &amp; Gate N Embargo Feeds
              </span>
              <button
                type="button"
                onClick={() => setIsFilterCollapsed(!isFilterCollapsed)}
                className="sm:hidden px-2 py-1 text-xs text-[#5B8FBF] bg-[#161C26] border border-[#232A35] rounded-[2px]"
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
                      <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded-[2px] ${
                        item.impact === 'High'
                          ? 'bg-[#C25B6B]/20 text-[#C25B6B]'
                          : item.impact === 'Med'
                          ? 'bg-[#BFA13B]/20 text-[#BFA13B]'
                          : 'bg-[#6E7A8A]/20 text-[#6E7A8A]'
                      }`}>
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

      {/* CALIB / QUANT EXPANDED VIEW */}
      {activeTab === 'CALIB' && (
        <div className="space-y-4">
          {/* Sub-view selector */}
          <div className="flex border-b border-[#232A35] bg-[#10151D] p-1 gap-1 text-xs">
            <button
              onClick={() => setQuantSubTab('params')}
              className={`px-3 py-1.5 border font-mono transition-colors min-h-[36px] flex items-center gap-1.5 ${
                quantSubTab === 'params'
                  ? 'border-[#4FAE86] bg-[#161C26] text-[#E7EAEE] font-semibold'
                  : 'border-transparent text-[#6E7A8A] hover:text-[#E7EAEE]'
              }`}
            >
              <Layers className="w-3.5 h-3.5 text-[#4FAE86]" />
              Parameters &amp; Rollout
            </button>
            <button
              onClick={() => setQuantSubTab('registry')}
              className={`px-3 py-1.5 border font-mono transition-colors min-h-[36px] flex items-center gap-1.5 ${
                quantSubTab === 'registry'
                  ? 'border-[#5B8FBF] bg-[#161C26] text-[#E7EAEE] font-semibold'
                  : 'border-transparent text-[#6E7A8A] hover:text-[#E7EAEE]'
              }`}
            >
              <Cpu className="w-3.5 h-3.5 text-[#5B8FBF]" />
              Model Registry ({quantModels.length})
            </button>
            <button
              onClick={() => setQuantSubTab('advice')}
              className={`px-3 py-1.5 border font-mono transition-colors min-h-[36px] flex items-center gap-1.5 ${
                quantSubTab === 'advice'
                  ? 'border-[#BFA13B] bg-[#161C26] text-[#E7EAEE] font-semibold'
                  : 'border-transparent text-[#6E7A8A] hover:text-[#E7EAEE]'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5 text-[#BFA13B]" />
              Model Advice &amp; Telemetry
            </button>
            <button
              onClick={() => setQuantSubTab('promotions')}
              className={`px-3 py-1.5 border font-mono transition-colors min-h-[36px] flex items-center gap-1.5 ${
                quantSubTab === 'promotions'
                  ? 'border-[#5B8FBF] bg-[#161C26] text-[#E7EAEE] font-semibold'
                  : 'border-transparent text-[#6E7A8A] hover:text-[#E7EAEE]'
              }`}
            >
              <History className="w-3.5 h-3.5 text-[#5B8FBF]" />
              Promotion History
            </button>
          </div>

          {/* Subview 1: Parameters & Rollout */}
          {quantSubTab === 'params' && (
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

          {/* Subview 2: Model Registry */}
          {quantSubTab === 'registry' && (
            <div className="space-y-3">
              <div className="text-xs text-[#6E7A8A]">
                Statistical &amp; ML Model Registry. Permitted intents are strictly constrained to VETO, REDUCE, or NONE (no order creation authority).
              </div>
              <div className="w-full overflow-x-auto">
                <table className="w-full border-collapse text-left text-xs min-w-[750px]">
                  <thead>
                    <tr className="bg-[#10151D] border-b border-[#232A35] text-[11px] text-[#6E7A8A]">
                      <th className="py-2 px-3">Model ID / Name</th>
                      <th className="py-2 px-3">Version</th>
                      <th className="py-2 px-3">Stage</th>
                      <th className="py-2 px-3">Permitted Intents</th>
                      <th className="py-2 px-3">Lane Scope</th>
                      <th className="py-2 px-3">Health</th>
                      <th className="py-2 px-3">Artifact Digest</th>
                    </tr>
                  </thead>
                  <tbody>
                    {quantModels.map((m) => (
                      <tr key={m.id} className="border-b border-[#232A35] hover:bg-[#161C26]">
                        <td className="py-2.5 px-3">
                          <div className="font-mono font-semibold text-[#E7EAEE]">{m.id}</div>
                          <div className="text-[11px] text-[#6E7A8A]">{m.name}</div>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">{m.version}</td>
                        <td className="py-2.5 px-3">
                          <span className={`font-mono text-[10px] px-1.5 py-0.5 border ${
                            m.rolloutStage === 'ACTIVE'
                              ? 'bg-[#4FAE86]/10 text-[#4FAE86] border-[#4FAE86]/30'
                              : m.rolloutStage === 'CANARY'
                              ? 'bg-[#BFA13B]/10 text-[#BFA13B] border-[#BFA13B]/30'
                              : 'bg-[#161C26] text-[#6E7A8A] border-[#232A35]'
                          }`}>
                            {m.rolloutStage}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[10px] text-[#E7EAEE]">
                          {m.permittedIntents.join(', ')}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[11px] text-[#6E7A8A]">
                          {m.laneEligibility.join(', ')}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className={`font-mono text-[10px] ${
                            m.health === 'HEALTHY' ? 'text-[#4FAE86]' : 'text-[#BFA13B]'
                          }`}>
                            {m.health}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[10px] text-[#6E7A8A] truncate max-w-[120px]">
                          {m.artifactSha256.substring(0, 14)}...
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Subview 3: Model Advice & Telemetry */}
          {quantSubTab === 'advice' && (
            <div className="space-y-3">
              <div className="p-2.5 bg-[#161C26] border border-[#BFA13B]/40 text-xs text-[#E7EAEE] flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-[#BFA13B] shrink-0" />
                <span>
                  <strong className="text-[#BFA13B]">Model Advice Guardrail:</strong> Inferences are strictly advisory. Permitted actions are limited to <code className="text-[#4FAE86]">VETO</code> and <code className="text-[#4FAE86]">REDUCE</code>. Models possess NO order initiation authority and cannot bypass upstream risk gates.
                </span>
              </div>

              <div className="w-full overflow-x-auto">
                <table className="w-full border-collapse text-left text-xs min-w-[800px]">
                  <thead>
                    <tr className="bg-[#10151D] border-b border-[#232A35] text-[11px] text-[#6E7A8A]">
                      <th className="py-2 px-3">Time</th>
                      <th className="py-2 px-3">Model</th>
                      <th className="py-2 px-3">Symbol / Lane</th>
                      <th className="py-2 px-3">Inference / Confidence</th>
                      <th className="py-2 px-3">Permitted Intent</th>
                      <th className="py-2 px-3">Gate Disposition</th>
                      <th className="py-2 px-3">Rationale</th>
                    </tr>
                  </thead>
                  <tbody>
                    {modelAdvice.map((a) => (
                      <tr key={a.id} className="border-b border-[#232A35] hover:bg-[#161C26]">
                        <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">
                          {new Date(a.timestamp).toLocaleTimeString()}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[#5B8FBF]">{a.modelId}</td>
                        <td className="py-2.5 px-3 font-mono font-semibold text-[#E7EAEE]">
                          {a.symbol} <span className="text-[10px] text-[#6E7A8A]">({a.lane})</span>
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="font-mono text-[11px] text-[#E7EAEE]">{a.prediction}</div>
                          <div className="font-mono text-[10px] text-[#4FAE86]">{(a.confidence * 100).toFixed(0)}% confidence</div>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[10px] text-[#BFA13B]">
                          {a.permittedIntent}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className={`font-mono text-[10px] px-1.5 py-0.5 border ${
                            a.gateDisposition === 'ACCEPTED_AS_ADVICE'
                              ? 'bg-[#4FAE86]/10 text-[#4FAE86] border-[#4FAE86]/30'
                              : 'bg-[#B23B3B]/10 text-[#C25B6B] border-[#B23B3B]/30'
                          }`}>
                            {a.gateDisposition}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-[11px] text-[#6E7A8A] max-w-xs">
                          {a.rationale}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Subview 4: Promotion History */}
          {quantSubTab === 'promotions' && (
            <div className="space-y-3">
              <div className="text-xs text-[#6E7A8A]">
                Evidence-backed parameter and model promotion audit ledger. Every transition is backed by cryptographic validation digests.
              </div>
              <div className="w-full overflow-x-auto">
                <table className="w-full border-collapse text-left text-xs min-w-[700px]">
                  <thead>
                    <tr className="bg-[#10151D] border-b border-[#232A35] text-[11px] text-[#6E7A8A]">
                      <th className="py-2 px-3">Date / Time</th>
                      <th className="py-2 px-3">Target</th>
                      <th className="py-2 px-3">Stage Transition</th>
                      <th className="py-2 px-3">Approver</th>
                      <th className="py-2 px-3">Validation Gate</th>
                      <th className="py-2 px-3">Evidence SHA-256</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rolloutPromotions.map((p) => (
                      <tr key={p.id} className="border-b border-[#232A35] hover:bg-[#161C26]">
                        <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">
                          {new Date(p.timestamp).toLocaleDateString()}
                        </td>
                        <td className="py-2.5 px-3 font-mono font-semibold text-[#E7EAEE]">{p.target}</td>
                        <td className="py-2.5 px-3 font-mono text-[11px]">
                          <span className="text-[#6E7A8A]">{p.fromStage}</span> → <span className="text-[#4FAE86] font-bold">{p.toStage}</span>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[11px] text-[#6E7A8A]">{p.approver}</td>
                        <td className="py-2.5 px-3">
                          <span className="font-mono text-[10px] text-[#4FAE86] bg-[#4FAE86]/10 px-1.5 py-0.5 border border-[#4FAE86]/30">
                            {p.gateStatus}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[10px] text-[#6E7A8A] truncate max-w-[120px]">
                          {p.evidenceSha256.substring(0, 16)}...
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
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

      {/* LAB & BACKTESTING VIEW (READ-ONLY) */}
      {activeTab === 'LAB' && (
        <div className="space-y-4">
          <div className="p-3 bg-[#161C26] border border-[#BFA13B]/40 text-xs text-[#E7EAEE] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FlaskConical className="w-4 h-4 text-[#BFA13B] shrink-0" />
              <div>
                <span className="font-semibold text-[#BFA13B]">SYNTHETIC LAB FIXTURES (UNVERIFIED):</span>{' '}
                <span className="text-[#6E7A8A]">
                  Displayed backtest runs are offline analytical fixtures. No statistical trading edge or live execution capability is asserted or proven.
                </span>
              </div>
            </div>
            <span className="font-mono text-[10px] px-2 py-0.5 bg-[#0A0E14] text-[#C25B6B] border border-[#232A35] shrink-0">
              EXECUTION DISABLED (READ-ONLY)
            </span>
          </div>

          {/* Run comparison cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {labRuns.map((run) => (
              <div 
                key={run.id}
                onClick={() => setSelectedLabRunId(run.id)}
                className={`p-4 border transition-all cursor-pointer ${
                  selectedLabRunId === run.id
                    ? 'border-[#5B8FBF] bg-[#161C26]'
                    : 'border-[#232A35] bg-[#10151D] hover:border-[#6E7A8A]'
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <div className="font-mono text-[10px] text-[#5B8FBF] font-semibold">{run.id}</div>
                    <div className="font-semibold text-sm text-[#E7EAEE] mt-0.5">{run.name}</div>
                  </div>
                  <span className="font-mono text-[10px] bg-[#0A0E14] px-1.5 py-0.5 border border-[#232A35] text-[#4FAE86]">
                    {run.fidelity} ({run.labTier})
                  </span>
                </div>

                <div className="font-mono text-xs text-[#6E7A8A] space-y-1 mb-3">
                  <div>Commit: <span className="text-[#E7EAEE]">{run.commitSha.substring(0, 10)}</span> · Engine: <span className="text-[#E7EAEE]">{run.engineVersion}</span></div>
                  <div>Period: <span className="text-[#E7EAEE]">{run.dateRange}</span></div>
                </div>

                <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[#232A35] font-mono text-xs">
                  <div>
                    <span className="text-[10px] text-[#6E7A8A] block">Net Realized R</span>
                    <span className="text-[#4FAE86] font-bold text-sm">+{run.netRealizedR}R</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-[#6E7A8A] block">Win Rate</span>
                    <span className="text-[#E7EAEE] font-bold text-sm">{(run.winRate * 100).toFixed(1)}%</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-[#6E7A8A] block">Max DD</span>
                    <span className="text-[#C25B6B] font-bold text-sm">-{run.maxDrawdownR}R ({run.maxDrawdownPct}%)</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Selected Run Deep Robustness Inspection */}
          {activeLabRun && (
            <div className="p-4 bg-[#10151D] border border-[#232A35] space-y-3 text-xs">
              <div className="font-semibold text-[#E7EAEE] uppercase tracking-wide flex items-center justify-between">
                <span>Robustness &amp; Null-World Validation Matrix: {activeLabRun.id}</span>
                <span className="font-mono text-[10px] text-[#6E7A8A]">Sharpe: {activeLabRun.sharpe} · Trades: {activeLabRun.totalTrades}</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 font-mono text-xs">
                <div className="p-3 bg-[#0A0E14] border border-[#232A35]">
                  <span className="text-[10px] text-[#6E7A8A] block mb-1">Null-World Shuffle Check</span>
                  <div className="flex items-center gap-1.5 text-[#4FAE86] font-bold">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>{activeLabRun.nullWorldCheck} (No edge in noise)</span>
                  </div>
                </div>

                <div className="p-3 bg-[#0A0E14] border border-[#232A35]">
                  <span className="text-[10px] text-[#6E7A8A] block mb-1">Planted-Edge Recovery</span>
                  <div className="flex items-center gap-1.5 text-[#4FAE86] font-bold">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>{activeLabRun.plantedEdgeRecovery} (Signal recovered)</span>
                  </div>
                </div>

                <div className="p-3 bg-[#0A0E14] border border-[#232A35]">
                  <span className="text-[10px] text-[#6E7A8A] block mb-1">OOS Degradation Bound</span>
                  <div className="text-[#E7EAEE] font-bold">
                    {activeLabRun.oosDegradationPct}% <span className="text-[10px] text-[#4FAE86]">(&lt; 20% limit)</span>
                  </div>
                </div>

                <div className="p-3 bg-[#0A0E14] border border-[#232A35]">
                  <span className="text-[10px] text-[#6E7A8A] block mb-1">Parameter Perturbation</span>
                  <div className="text-[#4FAE86] font-bold">
                    {activeLabRun.sensitivity} (Eigen &lt; 1.0)
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* OPS / BLOCKERS VIEW */}
      {activeTab === 'OPS' && (
        <div className="space-y-3">
          <div className="p-3 bg-[#161C26] border border-[#232A35] text-xs text-[#6E7A8A] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-[#C25B6B]" />
              <span className="text-[#E7EAEE] font-medium">Remediation Register &amp; Governance Ledger:</span>
              <span>Open architectural blockers and safety invariants per HPL audit.</span>
            </div>
            <span className="font-mono text-[10px] px-2 py-0.5 bg-[#0A0E14] text-[#BFA13B] border border-[#232A35]">
              READ-ONLY AUDIT
            </span>
          </div>

          <div className="w-full overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs min-w-[750px]">
              <thead>
                <tr className="bg-[#10151D] border-b border-[#232A35] text-[11px] text-[#6E7A8A]">
                  <th className="py-2 px-3">Blocker ID</th>
                  <th className="py-2 px-3">Category</th>
                  <th className="py-2 px-3">Severity</th>
                  <th className="py-2 px-3">Resolution Status</th>
                  <th className="py-2 px-3">Summary</th>
                  <th className="py-2 px-3">Owner</th>
                  <th className="py-2 px-3">Evidence Artifact</th>
                </tr>
              </thead>
              <tbody>
                {blockers.map((b) => (
                  <tr key={b.id} className="border-b border-[#232A35] hover:bg-[#161C26]">
                    <td className="py-2.5 px-3 font-mono font-semibold text-[#E7EAEE]">{b.id}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-[#6E7A8A]">{b.category}</td>
                    <td className="py-2.5 px-3">
                      <span className={`font-mono text-[10px] px-1.5 py-0.5 border ${
                        b.severity === 'P0' 
                          ? 'bg-[#B23B3B]/10 text-[#C25B6B] border-[#B23B3B]/30 font-bold'
                          : 'bg-[#BFA13B]/10 text-[#BFA13B] border-[#BFA13B]/30'
                      }`}>
                        {b.severity}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`font-mono text-[10px] px-1.5 py-0.5 border ${
                        b.status === 'RESOLVED_IN_STAGE_D'
                          ? 'bg-[#4FAE86]/10 text-[#4FAE86] border-[#4FAE86]/30'
                          : 'bg-[#B23B3B]/10 text-[#C25B6B] border-[#B23B3B]/30'
                      }`}>
                        {b.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-[#E7EAEE] max-w-sm">{b.summary}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-[#6E7A8A]">{b.owner}</td>
                    <td className="py-2.5 px-3 font-mono text-[10px] text-[#5B8FBF]">{b.evidenceArtifact}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* AUDIT TRAIL VIEW */}
      {activeTab === 'AUDIT' && (
        <div className="space-y-3">
          <div className="p-3 bg-[#161C26] border border-[#232A35] text-xs text-[#6E7A8A] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-[#5B8FBF]" />
              <span className="text-[#E7EAEE] font-medium">Session Audit Log (Non-Authoritative):</span>
              <span>In-memory simulation events and local mutation records. Non-persistent · Local Session Only.</span>
            </div>
            <span className="font-mono text-[10px] text-[#6E7A8A]">
              Simulation Sandbox · Session Only
            </span>
          </div>

          <div className="w-full overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs min-w-[800px]">
              <thead>
                <tr className="bg-[#10151D] border-b border-[#232A35] text-[11px] text-[#6E7A8A]">
                  <th className="py-2 px-3">Timestamp (UTC)</th>
                  <th className="py-2 px-3">Actor</th>
                  <th className="py-2 px-3">Action</th>
                  <th className="py-2 px-3">Target</th>
                  <th className="py-2 px-3">Outcome</th>
                  <th className="py-2 px-3">Intent SHA-256</th>
                  <th className="py-2 px-3">Details</th>
                </tr>
              </thead>
              <tbody>
                {auditTrail.map((ev) => (
                  <tr key={ev.id} className="border-b border-[#232A35] hover:bg-[#161C26]">
                    <td className="py-2.5 px-3 font-mono text-[#6E7A8A]">
                      {new Date(ev.timestamp).toISOString().replace('T', ' ').substring(0, 19)}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[#5B8FBF]">{ev.actor}</td>
                    <td className="py-2.5 px-3 font-mono font-semibold text-[#E7EAEE]">{ev.action}</td>
                    <td className="py-2.5 px-3 font-mono text-[#E7EAEE]">{ev.target}</td>
                    <td className="py-2.5 px-3">
                      <span className={`font-mono text-[10px] px-1.5 py-0.5 border ${
                        ev.outcome === 'SUCCESS_SIMULATED'
                          ? 'bg-[#4FAE86]/10 text-[#4FAE86] border-[#4FAE86]/30'
                          : 'bg-[#B23B3B]/10 text-[#C25B6B] border-[#B23B3B]/30'
                      }`}>
                        {ev.outcome}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[10px] text-[#6E7A8A] truncate max-w-[120px]">
                      {ev.intentDigestSha256.substring(0, 14)}...
                    </td>
                    <td className="py-2.5 px-3 text-[11px] text-[#6E7A8A] max-w-xs">{ev.details}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
