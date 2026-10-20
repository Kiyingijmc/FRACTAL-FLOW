import React from 'react';
import { NavTab } from '../types.ts';

interface NavRailProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
}

const NAV_ITEMS: { id: NavTab; label: string; full: string }[] = [
  { id: 'POS', label: 'POS', full: 'Positions' },
  { id: 'DEC', label: 'DEC', full: 'Decisions Log' },
  { id: 'RISK', label: 'RISK', full: 'Risk Monitor' },
  { id: 'MODE', label: 'MODE', full: 'Mode Profiles' },
  { id: 'NEWS', label: 'NEWS', full: 'Market News & Event Risk' },
  { id: 'CALIB', label: 'CALIB', full: 'Calibration' },
  { id: 'HEALTH', label: 'HEALTH', full: 'System Health' },
];

export const NavRail: React.FC<NavRailProps> = ({ activeTab, onTabChange }) => {
  return (
    <nav className="w-16 border-r border-[#232A35] bg-[#10151D] flex flex-col items-center pt-2.5 gap-0.5 select-none shrink-0">
      {NAV_ITEMS.map((item) => {
        const isActive = activeTab === item.id;
        return (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id)}
            title={item.full}
            className={`w-12 py-2 text-center text-[10px] font-sans font-medium rounded-[2px] transition-colors cursor-pointer ${
              isActive
                ? 'bg-[#161C26] text-[#E7EAEE]'
                : 'text-[#6E7A8A] hover:text-[#E7EAEE] hover:bg-[#161C26]/50'
            }`}
          >
            {item.label}
          </button>
        );
      })}
    </nav>
  );
};
