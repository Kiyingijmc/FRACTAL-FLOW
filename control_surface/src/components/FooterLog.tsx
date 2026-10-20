import React from 'react';
import { SystemEvent } from '../types.ts';

interface FooterLogProps {
  events: SystemEvent[];
}

export const FooterLog: React.FC<FooterLogProps> = ({ events }) => {
  const displayedEvents = events.slice(0, 3);

  return (
    <footer className="h-8 border-t border-[#232A35] bg-[#10151D] px-4 text-[11px] text-[#6E7A8A] flex items-center gap-5 shrink-0 overflow-x-auto select-none">
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
  );
};
