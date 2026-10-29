import React from 'react';
import { ExtendedNavTab } from '../types';

interface NavRailProps {
  activeTab: ExtendedNavTab;
  onTabChange: (tab: ExtendedNavTab) => void;
}

const CORE_NAV_ITEMS: { id: ExtendedNavTab; label: string; full: string }[] = [
  { id: 'POS', label: 'POS', full: 'Positions' },
  { id: 'DEC', label: 'DEC', full: 'Decisions Log' },
  { id: 'RISK', label: 'RISK', full: 'Risk Monitor' },
  { id: 'MODE', label: 'MODE', full: 'Mode Profiles' },
  { id: 'NEWS', label: 'NEWS', full: 'Market News & Event Risk' },
  { id: 'CALIB', label: 'CALIB', full: 'Calibration & QUANT Layer' },
  { id: 'HEALTH', label: 'HEALTH', full: 'System Health' },
  { id: 'STATS', label: 'STATS', full: 'Closed Trade Analytics' },
];

const ANALYTICAL_NAV_ITEMS: { id: ExtendedNavTab; label: string; full: string }[] = [
  { id: 'LAB', label: 'LAB', full: 'Lab & Backtesting' },
  { id: 'OPS', label: 'OPS', full: 'Remediation Register' },
  { id: 'AUDIT', label: 'AUDIT', full: 'Audit Trail' },
];

export const NavRail: React.FC<NavRailProps> = ({ activeTab, onTabChange }) => {
  return (
    <nav className="hidden md:flex w-16 border-r border-[#232A35] bg-[#10151D] flex-col items-center pt-2.5 gap-1 select-none shrink-0 overflow-y-auto">
      {/* 8 Core Destination Buttons */}
      {CORE_NAV_ITEMS.map((item) => {
        const isActive = activeTab === item.id;
        return (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id)}
            title={item.full}
            className={`w-12 min-h-[38px] py-1.5 text-center text-[10px] font-sans font-medium rounded-[2px] transition-colors cursor-pointer flex flex-col items-center justify-center ${
              isActive
                ? 'bg-[#161C26] text-[#E7EAEE] border border-[#5B8FBF]/30 font-semibold'
                : 'text-[#6E7A8A] hover:text-[#E7EAEE] hover:bg-[#161C26]/50 border border-transparent'
            }`}
          >
            <span>{item.label}</span>
          </button>
        );
      })}

      {/* Subtle Divider for Extended Analytical Views */}
      <div className="w-8 h-[1px] bg-[#232A35] my-1" />

      {/* Analytical & Governance Surfaces */}
      {ANALYTICAL_NAV_ITEMS.map((item) => {
        const isActive = activeTab === item.id;
        return (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id)}
            title={item.full}
            className={`w-12 min-h-[32px] py-1 text-center text-[9px] font-mono font-medium rounded-[2px] transition-colors cursor-pointer flex flex-col items-center justify-center ${
              isActive
                ? 'bg-[#161C26] text-[#5B8FBF] border border-[#5B8FBF]/30 font-semibold'
                : 'text-[#454E5C] hover:text-[#6E7A8A] hover:bg-[#161C26]/30 border border-transparent'
            }`}
          >
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
};
