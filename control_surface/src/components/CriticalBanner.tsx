import React from 'react';
import { AlertOctagon, CheckCircle2 } from 'lucide-react';
import { NotificationEvent } from '../types';

interface CriticalBannerProps {
  criticalAlert: NotificationEvent | null;
  onAcknowledge: (alertId: string) => void;
}

export const CriticalBanner: React.FC<CriticalBannerProps> = ({
  criticalAlert,
  onAcknowledge
}) => {
  if (!criticalAlert || criticalAlert.resolved) return null;

  return (
    <div
      className="bg-[#1A0A0E] border-y border-[#B23B3B] px-4 py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
      role="alert"
      aria-live="assertive"
      data-testid="critical-safety-banner"
    >
      <div className="flex items-start sm:items-center gap-2.5">
        <div className="p-1 bg-[#B23B3B]/20 text-[#C25B6B] shrink-0 border border-[#B23B3B]/40">
          <AlertOctagon className="w-4 h-4 text-[#C25B6B] animate-pulse" />
        </div>
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-[10px] bg-[#B23B3B] text-white px-1.5 py-0.2 font-bold tracking-wider uppercase">
              SAFETY-CRITICAL
            </span>
            <span className="font-mono text-[11px] text-[#6E7A8A]">
              [{criticalAlert.id}]
            </span>
            <span className="font-semibold text-[#E7EAEE]">
              {criticalAlert.title}
            </span>
            {criticalAlert.lane && (
              <span className="font-mono text-[10px] px-1 bg-[#232A35] text-[#E7EAEE]">
                {criticalAlert.lane}
              </span>
            )}
          </div>
          <div className="text-[11px] text-[#C25B6B] mt-0.5 leading-relaxed">
            {criticalAlert.detail}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 shrink-0 self-end sm:self-center">
        {criticalAlert.acknowledged ? (
          <div className="flex items-center gap-1.5 text-[#4FAE86] font-mono text-[11px] bg-[#4FAE86]/10 px-2 py-1 border border-[#4FAE86]/30">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>ACKNOWLEDGED {criticalAlert.acknowledgedAt ? new Date(criticalAlert.acknowledgedAt).toLocaleTimeString() : ''}</span>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => onAcknowledge(criticalAlert.id)}
            className="px-3 py-1.5 bg-[#B23B3B] hover:bg-[#B23B3B]/80 text-white font-mono text-xs font-semibold tracking-wider transition-colors min-h-[44px] sm:min-h-[32px] flex items-center gap-1.5"
            aria-label={`Acknowledge safety critical alert ${criticalAlert.id}`}
          >
            ACKNOWLEDGE (ACK)
          </button>
        )}
        <span className="hidden md:inline-block text-[10px] text-[#6E7A8A] font-mono">
          Non-mutable · Ack ≠ Resolution
        </span>
      </div>
    </div>
  );
};
