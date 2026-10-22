import React, { useState, useEffect, useRef } from 'react';
import { SystemEvent } from '../types';

interface FooterLogProps {
  events: SystemEvent[];
}

export const FooterLog: React.FC<FooterLogProps> = ({ events }) => {
  const [isMobileJournalOpen, setIsMobileJournalOpen] = useState(false);
  const latestEvent = events[0];
  const displayedEvents = events.slice(0, 3);

  const modalRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLDivElement>(null);

  // Focus trap & restoration on mobile journal sheet (UX-07)
  useEffect(() => {
    if (isMobileJournalOpen) {
      setTimeout(() => {
        closeBtnRef.current?.focus();
      }, 50);

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          e.preventDefault();
          setIsMobileJournalOpen(false);
          return;
        }

        if (e.key === 'Tab' && modalRef.current) {
          const focusable = modalRef.current.querySelectorAll<HTMLElement>(
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
  }, [isMobileJournalOpen]);

  return (
    <>
      {/* Mobile Compact Journal Strip (< 768px) */}
      <div
        ref={triggerRef}
        role="button"
        tabIndex={0}
        aria-label="Open Event Journal Stream"
        onClick={() => setIsMobileJournalOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setIsMobileJournalOpen(true);
          }
        }}
        className="md:hidden h-8 border-t border-[#232A35] bg-[#0A0E14] px-3 text-[10px] text-[#6E7A8A] flex items-center justify-between shrink-0 select-none cursor-pointer hover:bg-[#161C26]/50 focus-visible:ring-1 focus-visible:ring-[#5B8FBF] outline-none"
      >
        <div className="flex items-center gap-1.5 truncate mr-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[#4FAE86] shrink-0" />
          <span className="font-mono text-[#454E5C] uppercase tracking-wider shrink-0">JOURNAL:</span>
          {latestEvent && (
            <span className="truncate text-[#E7EAEE]">
              [{latestEvent.eventId}] {latestEvent.message}
            </span>
          )}
        </div>
        <div className="text-[10px] text-[#5B8FBF] font-mono shrink-0">
          View All ({events.length}) ▴
        </div>
      </div>

      {/* Mobile Expandable Journal Modal / Sheet */}
      {isMobileJournalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex flex-col justify-end md:hidden animate-in fade-in duration-150">
          <div
            ref={modalRef}
            role="dialog"
            aria-modal="true"
            aria-label="Event Journal Stream"
            className="bg-[#10151D] border-t border-[#232A35] rounded-t-lg p-4 space-y-3 max-h-[75vh] flex flex-col shadow-2xl"
          >
            <div className="flex items-center justify-between pb-2 border-b border-[#232A35]">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold tracking-wide text-[#E7EAEE] uppercase">
                  Event Journal Stream
                </span>
                <span className="w-1.5 h-1.5 rounded-full bg-[#4FAE86]" />
              </div>
              <button
                ref={closeBtnRef}
                type="button"
                onClick={() => setIsMobileJournalOpen(false)}
                className="min-h-[44px] min-w-[44px] flex items-center justify-center text-sm text-[#6E7A8A] hover:text-[#E7EAEE] rounded-sm transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-[#5B8FBF] outline-none"
              >
                ✕ Close
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {events.map((evt) => {
                let textClass = 'text-[#E7EAEE]';
                if (evt.level === 'crit') textClass = 'text-[#C25B6B] font-medium';
                else if (evt.level === 'warn') textClass = 'text-[#BFA13B]';

                return (
                  <div
                    key={evt.id}
                    className="p-2 rounded-[2px] bg-[#161C26] border border-[#232A35] text-xs space-y-1 font-mono"
                  >
                    <div className="flex items-center justify-between text-[10px] text-[#6E7A8A]">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[#454E5C]">[{evt.eventId}]</span>
                        <span className="px-1 rounded-[2px] bg-[#10151D] border border-[#232A35] text-[#5B8FBF]">
                          {evt.source}
                        </span>
                      </div>
                      <span>{evt.timestamp}</span>
                    </div>
                    <div className={`text-[11px] ${textClass}`}>{evt.message}</div>
                    {evt.status && (
                      <div className="text-right">
                        <span
                          className={`text-[9px] px-1.5 py-0.5 rounded-[2px] ${
                            evt.status === 'PERSISTED'
                              ? 'text-[#4FAE86] bg-[#4FAE86]/10 border border-[#4FAE86]/30'
                              : 'text-[#BFA13B] bg-[#BFA13B]/10 border border-[#BFA13B]/30'
                          }`}
                        >
                          {evt.status}
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Desktop Footer Log Bar (>= 768px) */}
      <footer className="hidden md:flex h-8 border-t border-[#232A35] bg-[#10151D] px-4 text-[11px] text-[#6E7A8A] items-center gap-5 shrink-0 overflow-x-auto select-none">
        <div className="flex items-center gap-2 shrink-0">
          <span className="font-mono text-[10px] text-[#454E5C] uppercase tracking-wider">
            JOURNAL STREAM
          </span>
          <span className="w-1.5 h-1.5 rounded-full bg-[#4FAE86]" />
        </div>

        <div className="flex items-center gap-6 overflow-hidden whitespace-nowrap flex-1">
          {displayedEvents.map((evt) => {
            let style = 'text-[#E7EAEE]';
            if (evt.level === 'crit') style = 'text-[#B23B3B] font-medium';
            else if (evt.level === 'warn') style = 'text-[#BFA13B]';

            return (
              <div key={evt.id} className="flex items-center gap-1.5 shrink-0">
                <span className="font-mono text-[10px] text-[#454E5C]">[{evt.eventId}]</span>
                <span className="font-mono text-[9px] px-1 rounded-[2px] bg-[#161C26] text-[#6E7A8A] border border-[#232A35]">
                  {evt.source}
                </span>
                <span className="font-mono text-[#6E7A8A] tabular-nums text-[11px]">
                  {evt.timestamp}
                </span>
                <span className="text-[#454E5C]">—</span>
                <span className={style}>{evt.message}</span>
                {evt.status && (
                  <span
                    className={`font-mono text-[9px] px-1 rounded-[2px] ${
                      evt.status === 'PERSISTED'
                        ? 'text-[#4FAE86] bg-[#4FAE86]/10'
                        : 'text-[#BFA13B] bg-[#BFA13B]/10'
                    }`}
                  >
                    {evt.status}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {/* Operator Hotkey Quick-Reference */}
        <div className="flex items-center gap-2 font-mono text-[10px] text-[#454E5C] border-l border-[#232A35] pl-3 shrink-0">
          <span className="text-[#6E7A8A] font-medium">HOTKEYS:</span>
          <span><strong className="text-[#5B8FBF]">T</strong> Tighten</span>
          <span><strong className="text-[#E7EAEE]">B</strong> Breakeven</span>
          <span><strong className="text-[#C25B6B]">C</strong> Close</span>
          <span><strong className="text-[#6E7A8A]">↑/↓</strong> Select</span>
          <span><strong className="text-[#5B8FBF]">N</strong> News</span>
          <span><strong className="text-[#6E7A8A]">P</strong> Pause</span>
          <span><strong className="text-[#5B8FBF]">Esc</strong> Back to POS</span>
        </div>
      </footer>
    </>
  );
};
