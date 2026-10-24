import React, { useState, useEffect, useRef } from 'react';
import { 
  Bell, 
  X, 
  AlertOctagon, 
  ShieldAlert, 
  Activity, 
  Layers, 
  Info, 
  Check, 
  Send,
  Lock
} from 'lucide-react';
import { 
  NotificationEvent, 
  NotificationClass 
} from '../types';

interface NotificationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  notifications: NotificationEvent[];
  onAcknowledge: (id: string) => void;
}

export const NotificationDrawer: React.FC<NotificationDrawerProps> = ({
  isOpen,
  onClose,
  notifications,
  onAcknowledge
}) => {
  const [selectedClass, setSelectedClass] = useState<NotificationClass | 'all'>('all');
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // Focus trap & escape listener
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    closeButtonRef.current?.focus();

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const filtered = selectedClass === 'all' 
    ? notifications 
    : notifications.filter((n) => n.class === selectedClass);

  const getClassIcon = (cls: NotificationClass) => {
    switch (cls) {
      case 'safety_critical':
        return <AlertOctagon className="w-3.5 h-3.5 text-[#C25B6B]" />;
      case 'risk_limit':
        return <ShieldAlert className="w-3.5 h-3.5 text-[#BFA13B]" />;
      case 'trade_lifecycle':
        return <Activity className="w-3.5 h-3.5 text-[#4FAE86]" />;
      case 'calibration_rollout':
        return <Layers className="w-3.5 h-3.5 text-[#5B8FBF]" />;
      case 'informational_daily':
        return <Info className="w-3.5 h-3.5 text-[#6E7A8A]" />;
    }
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-end bg-black/75 backdrop-blur-xs"
      role="dialog"
      aria-modal="true"
      aria-labelledby="notification-drawer-title"
      data-testid="notification-drawer"
    >
      <div className="bg-[#10151D] border-l border-[#232A35] w-full max-w-lg h-full flex flex-col shadow-2xl">
        {/* Drawer Header */}
        <div className="px-5 py-3 border-b border-[#232A35] flex items-center justify-between bg-[#161C26]">
          <div className="flex items-center gap-2">
            <Bell className="w-4 h-4 text-[#5B8FBF]" />
            <h2 id="notification-drawer-title" className="text-sm font-semibold text-[#E7EAEE] tracking-wide">
              NOTIFICATION CENTER & DISPATCH LOG
            </h2>
          </div>
          <button
            ref={closeButtonRef}
            onClick={onClose}
            className="p-1 hover:bg-[#232A35] text-[#6E7A8A] hover:text-[#E7EAEE] transition-colors min-h-[36px] min-w-[36px] flex items-center justify-center"
            aria-label="Close notification center"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Subscription Channels Info Banner */}
        <div className="p-3 bg-[#0A0E14] border-b border-[#232A35] text-[11px] text-[#6E7A8A] flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Lock className="w-3 h-3 text-[#B23B3B]" />
            <span>Safety-Critical Channel: <strong className="text-[#E7EAEE]">PERMANENTLY ACTIVE (NON-MUTABLE)</strong></span>
          </div>
          <span className="font-mono text-[10px] text-[#4FAE86]">TG Bot: SIM_ONLINE</span>
        </div>

        {/* Filter Pills */}
        <div className="p-3 border-b border-[#232A35] bg-[#10151D] flex flex-wrap gap-1.5 text-xs">
          {(['all', 'safety_critical', 'risk_limit', 'trade_lifecycle', 'calibration_rollout', 'informational_daily'] as const).map((cls) => {
            const count = cls === 'all' 
              ? notifications.length 
              : notifications.filter((n) => n.class === cls).length;

            return (
              <button
                key={cls}
                type="button"
                onClick={() => setSelectedClass(cls)}
                className={`px-2.5 py-1.5 border font-mono text-[11px] transition-colors min-h-[32px] flex items-center gap-1.5 ${
                  selectedClass === cls
                    ? 'border-[#5B8FBF] bg-[#161C26] text-[#E7EAEE] font-semibold'
                    : 'border-[#232A35] bg-[#0A0E14] text-[#6E7A8A] hover:text-[#E7EAEE]'
                }`}
              >
                {cls === 'all' ? 'ALL' : cls.toUpperCase().replace('_', ' ')}
                <span className="text-[10px] opacity-75">({count})</span>
              </button>
            );
          })}
        </div>

        {/* Notification Event List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-[#6E7A8A] text-xs font-mono">
              NO NOTIFICATIONS FOR SELECTED TAXONOMY CLASS
            </div>
          ) : (
            filtered.map((item) => (
              <div 
                key={item.id}
                className={`p-3.5 border transition-all text-xs ${
                  item.class === 'safety_critical'
                    ? 'border-[#B23B3B]/60 bg-[#1A0A0E]'
                    : 'border-[#232A35] bg-[#0A0E14]'
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {getClassIcon(item.class)}
                    <span className="font-mono text-[10px] uppercase font-bold text-[#6E7A8A]">
                      {item.class.replace('_', ' ')}
                    </span>
                    <span className="font-mono text-[10px] text-[#454E5C]">
                      [{item.id}]
                    </span>
                    {item.lane && (
                      <span className="font-mono text-[10px] bg-[#161C26] px-1 text-[#E7EAEE] border border-[#232A35]">
                        {item.lane}
                      </span>
                    )}
                  </div>
                  <span className="font-mono text-[10px] text-[#6E7A8A] shrink-0">
                    {new Date(item.timestamp).toLocaleTimeString()}
                  </span>
                </div>

                <div className="font-semibold text-[#E7EAEE] mb-1">
                  {item.title}
                </div>

                <div className="text-[11px] text-[#6E7A8A] leading-relaxed mb-3">
                  {item.detail}
                </div>

                {/* Delivery attempts & Ack action */}
                <div className="pt-2 border-t border-[#232A35] flex items-center justify-between text-[10px] font-mono">
                  <div className="flex items-center gap-2 text-[#6E7A8A]">
                    <span className="flex items-center gap-1">
                      <Send className="w-3 h-3 text-[#5B8FBF]" />
                      Telegram: {item.deliveryAttempts.find(d => d.channel === 'telegram')?.status || 'OFFLINE'}
                    </span>
                    <span>·</span>
                    <span>GUI: {item.deliveryAttempts.find(d => d.channel === 'gui')?.status || 'DISPLAYED'}</span>
                  </div>

                  {item.class === 'safety_critical' && (
                    item.acknowledged ? (
                      <span className="text-[#4FAE86] flex items-center gap-1">
                        <Check className="w-3 h-3" />
                        ACKNOWLEDGED
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => onAcknowledge(item.id)}
                        className="px-2 py-1 bg-[#B23B3B] text-white hover:bg-[#B23B3B]/80 font-bold min-h-[32px] flex items-center gap-1"
                      >
                        ACK
                      </button>
                    )
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Drawer Footer */}
        <div className="px-5 py-3 border-t border-[#232A35] bg-[#161C26] flex items-center justify-between text-xs text-[#6E7A8A]">
          <span className="font-mono text-[11px]">
            Delivery attempts logged per 01_ARCHITECTURE §5
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 border border-[#232A35] bg-[#0A0E14] text-[#E7EAEE] hover:bg-[#232A35] min-h-[36px]"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
