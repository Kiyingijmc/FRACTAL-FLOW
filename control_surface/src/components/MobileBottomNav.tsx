import React, { useEffect, useRef } from 'react';
import { ExtendedNavTab } from '../types';

interface MobileBottomNavProps {
  activeTab: ExtendedNavTab;
  onTabChange: (tab: ExtendedNavTab) => void;
  isMoreOpen: boolean;
  onToggleMore: (open: boolean) => void;
}

const PRIMARY_TABS: { id: ExtendedNavTab; label: string; full: string }[] = [
  { id: 'POS', label: 'POS', full: 'Positions' },
  { id: 'DEC', label: 'DEC', full: 'Decisions' },
  { id: 'RISK', label: 'RISK', full: 'Risk' },
  { id: 'MODE', label: 'MODE', full: 'Modes' },
];

const SECONDARY_TABS: { id: ExtendedNavTab; label: string; full: string; desc: string }[] = [
  { id: 'NEWS', label: 'NEWS', full: 'Market News & Embargo', desc: 'Gate N macro embargoes and scheduled releases' },
  { id: 'CALIB', label: 'CALIB', full: 'Calibration & QUANT', desc: 'Rollout stages: SHADOW → PAPER → CANARY → ACTIVE' },
  { id: 'HEALTH', label: 'HEALTH', full: 'System Health', desc: 'Gateway bridge, consensus epoch, and fence status' },
  { id: 'STATS', label: 'STATS', full: 'Performance Stats', desc: 'Expectancy, profit factor, and closed trade analytics' },
  { id: 'LAB', label: 'LAB', full: 'Lab & Backtesting', desc: 'Read-only multi-run artifacts and null-world validation' },
  { id: 'OPS', label: 'OPS', full: 'Remediation Register', desc: 'Open architectural blockers and governance ledger' },
  { id: 'AUDIT', label: 'AUDIT', full: 'System Audit Trail', desc: 'Cryptographically attributed event history' },
];

export const MobileBottomNav: React.FC<MobileBottomNavProps> = ({
  activeTab,
  onTabChange,
  isMoreOpen,
  onToggleMore,
}) => {
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Focus trap & focus restoration (UX-07)
  useEffect(() => {
    if (isMoreOpen) {
      setTimeout(() => {
        closeButtonRef.current?.focus();
      }, 50);

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          e.preventDefault();
          onToggleMore(false);
          triggerRef.current?.focus();
          return;
        }

        if (e.key === 'Tab' && drawerRef.current) {
          const focusable = drawerRef.current.querySelectorAll<HTMLElement>(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
          );
          if (focusable.length === 0) return;

          const firstEl = focusable[0];
          const lastEl = focusable[focusable.length - 1];

          if (e.shiftKey) {
            if (document.activeElement === firstEl) {
              e.preventDefault();
              lastEl.focus();
            }
          } else {
            if (document.activeElement === lastEl) {
              e.preventDefault();
              firstEl.focus();
            }
          }
        }
      };

      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [isMoreOpen, onToggleMore]);

  // Outside click closes drawer
  useEffect(() => {
    if (!isMoreOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        onToggleMore(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isMoreOpen, onToggleMore]);

  const isSecondaryActive = SECONDARY_TABS.some((t) => t.id === activeTab);

  return (
    <>
      {/* Slide-up drawer for secondary views */}
      {isMoreOpen && (
        <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-xs flex flex-col justify-end md:hidden animate-in fade-in duration-150">
          <div
            ref={drawerRef}
            role="dialog"
            aria-modal="true"
            aria-label="Secondary Navigation Destinations"
            className="bg-[#10151D] border-t border-[#232A35] rounded-t-lg p-4 space-y-3 max-h-[80vh] overflow-y-auto shadow-2xl"
          >
            <div className="flex items-center justify-between pb-2 border-b border-[#232A35]">
              <div className="text-xs font-semibold tracking-wide text-[#E7EAEE] uppercase">
                Additional Control Surfaces
              </div>
              <button
                ref={closeButtonRef}
                type="button"
                onClick={() => {
                  onToggleMore(false);
                  triggerRef.current?.focus();
                }}
                className="min-h-[44px] min-w-[44px] flex items-center justify-center text-sm text-[#6E7A8A] hover:text-[#E7EAEE] rounded-sm transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-[#5B8FBF] outline-none"
                aria-label="Close menu"
              >
                ✕ Close
              </button>
            </div>

            <div className="grid grid-cols-1 gap-2">
              {SECONDARY_TABS.map((item) => {
                const isCurrent = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      onTabChange(item.id);
                      onToggleMore(false);
                      triggerRef.current?.focus();
                    }}
                    className={`min-h-[48px] w-full text-left px-3.5 py-2.5 rounded-[3px] border transition-all flex flex-col justify-center cursor-pointer focus-visible:ring-2 focus-visible:ring-[#5B8FBF] outline-none ${
                      isCurrent
                        ? 'border-[#5B8FBF] bg-[#161C26] text-[#E7EAEE]'
                        : 'border-[#232A35] bg-[#10151D] hover:bg-[#161C26]/60 text-[#6E7A8A] hover:text-[#E7EAEE]'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-semibold tracking-wide text-[#E7EAEE]">
                        {item.label} — {item.full}
                      </span>
                      {isCurrent && (
                        <span className="font-mono text-[10px] text-[#5B8FBF] bg-[#5B8FBF]/15 px-1.5 py-0.5 rounded-[2px]">
                          ACTIVE
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] text-[#6E7A8A] mt-0.5 line-clamp-1">{item.desc}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Docked bottom navigation bar for mobile (< 768px) */}
      <nav
        className="fixed bottom-0 left-0 right-0 z-30 md:hidden bg-[#10151D] border-t border-[#232A35] flex items-stretch justify-around px-1 select-none"
        aria-label="Mobile Navigation"
      >
        {PRIMARY_TABS.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onTabChange(item.id)}
              className={`flex-1 min-h-[44px] py-1.5 text-center text-[11px] font-mono font-medium transition-colors flex flex-col items-center justify-center cursor-pointer border-t-2 ${
                isActive
                  ? 'border-[#5B8FBF] text-[#E7EAEE] bg-[#161C26]'
                  : 'border-transparent text-[#6E7A8A] hover:text-[#E7EAEE]'
              }`}
            >
              <span>{item.label}</span>
              <span className="text-[9px] text-[#454E5C] font-sans -mt-0.5">{item.full}</span>
            </button>
          );
        })}

        {/* More button */}
        <button
          ref={triggerRef}
          type="button"
          onClick={() => onToggleMore(!isMoreOpen)}
          aria-expanded={isMoreOpen}
          aria-haspopup="dialog"
          aria-label="More control surfaces and diagnostics"
          className={`flex-1 min-h-[44px] py-1.5 text-center text-[11px] font-mono font-medium transition-colors flex flex-col items-center justify-center cursor-pointer border-t-2 ${
            isSecondaryActive || isMoreOpen
              ? 'border-[#5B8FBF] text-[#E7EAEE] bg-[#161C26]'
              : 'border-transparent text-[#6E7A8A] hover:text-[#E7EAEE]'
          }`}
        >
          <span className="flex items-center gap-1">
            MORE ▾
            {isSecondaryActive && (
              <span className="w-1.5 h-1.5 rounded-full bg-[#5B8FBF] inline-block" />
            )}
          </span>
          <span className="text-[9px] text-[#454E5C] font-sans -mt-0.5">Surfaces</span>
        </button>
      </nav>
    </>
  );
};
