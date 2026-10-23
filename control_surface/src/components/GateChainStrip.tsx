import React from 'react';
import { GateCandidate } from '../types';

interface GateChainStripProps {
  candidates: GateCandidate[];
  selectedCandidateId: string;
  onSelectCandidate: (id: string) => void;
}

export const GateChainStrip: React.FC<GateChainStripProps> = ({
  candidates,
  selectedCandidateId,
  onSelectCandidate,
}) => {
  const currentCandidate = candidates.find((c) => c.id === selectedCandidateId) || candidates[0];

  return (
    <div className="flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-2 border-b border-[#232A35] bg-[#0A0E14] select-none text-[11px] overflow-x-auto shrink-0 w-full">
      {/* Explicit Distinction: Candidate Intake Pipeline vs Active Managed Position */}
      <div className="flex items-center gap-1.5 text-[#6E7A8A] whitespace-nowrap shrink-0">
        <span className="text-[#454E5C] text-[9px] sm:text-[10px] uppercase font-mono tracking-wider border-r border-[#232A35] pr-2">
          CANDIDATES
        </span>
        <select
          value={currentCandidate.id}
          onChange={(e) => onSelectCandidate(e.target.value)}
          className="min-h-[32px] bg-[#10151D] text-[#E7EAEE] font-mono text-[11px] border border-[#232A35] hover:border-[#5B8FBF] px-2 py-0.5 rounded-[2px] outline-none cursor-pointer"
        >
          {candidates.map((c) => (
            <option key={c.id} value={c.id} className="bg-[#10151D] text-[#E7EAEE]">
              {c.symbol} {c.setup} ({c.evaluatedAt})
            </option>
          ))}
        </select>
      </div>

      {/* 11 Gates: Q E R P L O T N K A X */}
      <div className="flex items-center gap-1 shrink-0">
        {currentCandidate.gates.map((g) => {
          let cellStyle = 'border-[#232A35] text-[#454E5C] bg-transparent';
          if (g.status === 'pass') {
            cellStyle = 'bg-[#4FAE86]/[0.16] text-[#4FAE86] border-[#4FAE86]/40';
          } else if (g.status === 'fail') {
            cellStyle = 'bg-[#B23B3B]/[0.18] text-[#B23B3B] border-[#B23B3B]/45 font-semibold';
          }
          return (
            <div
              key={g.letter}
              title={`${g.letter}: ${g.name} [${g.status.toUpperCase()}] — ${g.detail || ''}`}
              className={`w-[22px] h-[22px] sm:w-[24px] sm:h-[24px] flex items-center justify-center font-mono text-[10px] sm:text-[11px] rounded-[2px] border transition-colors cursor-default ${cellStyle}`}
            >
              {g.letter}
            </div>
          );
        })}
      </div>

      {/* Detailed Failure Reason / Outcome */}
      <div className="text-[#6E7A8A] truncate ml-1 text-xs shrink-0 max-w-[260px] sm:max-w-none">
        {currentCandidate.summaryStatus === 'blocked' && currentCandidate.failureNotice ? (
          <span>
            blocked at{' '}
            <strong className="text-[#C25B6B] font-semibold">
              {currentCandidate.failureNotice.letter} — {currentCandidate.failureNotice.title}
            </strong>
            : {currentCandidate.failureNotice.detail}
          </span>
        ) : (
          <span className="text-[#4FAE86]">
            <strong>all gates cleared</strong>: candidate authorized for ExecutionGateway dispatch
          </span>
        )}
      </div>

      <div className="flex-1" />

      <div className="font-mono text-[10px] text-[#454E5C] whitespace-nowrap shrink-0 hidden sm:block">
        GATE EVAL: {currentCandidate.evaluatedAt}
      </div>
    </div>
  );
};
