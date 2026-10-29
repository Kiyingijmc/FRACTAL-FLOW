import React, { useState, useId } from 'react';
import { Position, ActionType } from '../types.ts';

interface ConfirmDialogProps {
  isOpen: boolean;
  action: ActionType | null;
  position: Position | null;
  onConfirm: (shouldReject?: boolean) => void;
  onCancel: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  action,
  position,
  onConfirm,
  onCancel,
}) => {
  const [simulateRejection, setSimulateRejection] = useState(false);
  const rawId = useId();
  const idempotencyKey = `cmd_${rawId.replace(/:/g, '')}_${position?.id || 'pos'}`;

  // Keyboard listener for confirmation modal
  React.useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onCancel();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        onConfirm(simulateRejection);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onCancel, onConfirm, simulateRejection]);

  if (!isOpen || !action || !position) return null;

  let title = '';
  let commandRoute = '';
  let detail = '';
  let isDanger = false;

  switch (action) {
    case 'tighten_stop':
      title = `Tighten Stop Ratchet — ${position.symbol} ${position.side}`;
      commandRoute = 'ExecutionGateway.TIGHTEN_STOP (ratchet_only=true)';
      detail = `Advance trailing anchor on ${position.drivingTimeframe} to current protected swing level. New stop will be ratcheted forward; Gateway rejects any loosening command.`;
      break;
    case 'move_to_breakeven':
      title = `Move to Breakeven — ${position.symbol} ${position.side}`;
      commandRoute = 'ExecutionGateway.MOVE_TO_BREAKEVEN';
      detail = `Relocate stop level to entry price (${position.entryPrice.toFixed(
        position.priceDecimals
      )}) + 0.5 pip slippage buffer. Position risk will transition to 0.0R.`;
      break;
    case 'close_position':
      title = `Execute Full Close — ${position.symbol} ${position.side}`;
      commandRoute = 'ExecutionGateway.FULL_CLOSE';
      detail = `Submit market exit order for ${position.size.toFixed(2)} lots @ current price (${position.currentPrice.toFixed(
        position.priceDecimals
      )}). Realized P&L will be locked into lane ${position.lane}.`;
      isDanger = true;
      break;
    case 'add_size':
      title = `Increase Position Size — ${position.symbol} ${position.side}`;
      commandRoute = 'ExecutionGateway.ADD_SIZE';
      detail = `Submit scale-in addition of +50% size (${(position.size * 0.5).toFixed(2)} lots) @ current price (${position.currentPrice.toFixed(
        position.priceDecimals
      )}). Subject to strict portfolio risk authority gating.`;
      break;
    case 'scale_in':
      title = `Execute Scale In — ${position.symbol} ${position.side}`;
      commandRoute = 'ExecutionGateway.SCALE_IN';
      detail = `Submit pyramid addition for ${position.symbol} ${position.side}. Subject to strict portfolio risk authority gating.`;
      break;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      data-testid="confirm-dialog"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 transition-opacity duration-150"
    >
      <div className="w-[460px] bg-[#10151D] border border-[#232A35] p-4 text-left select-none">
        {/* Header */}
        <div className="flex justify-between items-start pb-2 mb-3 border-b border-[#232A35]">
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-xs font-semibold text-[#E7EAEE] tracking-tight">{title}</h4>
              <span className="font-mono text-[9px] px-1 py-0.5 rounded-[2px] bg-[#BFA13B]/20 text-[#BFA13B] border border-[#BFA13B]/40">
                SANDBOX
              </span>
            </div>
            <div className="font-mono text-[10px] text-[#6E7A8A] mt-0.5">{commandRoute}</div>
          </div>
          <button
            onClick={onCancel}
            className="text-[#6E7A8A] hover:text-[#E7EAEE] text-sm leading-none cursor-pointer p-1"
          >
            ✕
          </button>
        </div>

        <p className="text-xs text-[#E7EAEE] mb-3 leading-relaxed">{detail}</p>

        {/* Verification Parameters & Identity */}
        <div className="bg-[#161C26] p-2.5 border border-[#232A35] mb-3 font-mono text-[11px] space-y-1">
          <div className="flex justify-between text-[#6E7A8A]">
            <span>Idempotency Key</span>
            <span className="text-[#E7EAEE] truncate max-w-[240px]">{idempotencyKey}</span>
          </div>
          <div className="flex justify-between text-[#6E7A8A]">
            <span>Account Lane</span>
            <span className="text-[#E7EAEE]">{position.lane} (v_epoch: 418)</span>
          </div>
          <div className="flex justify-between text-[#6E7A8A]">
            <span>Target Position</span>
            <span className="text-[#E7EAEE]">
              {position.symbol} {position.side} ({position.size.toFixed(2)} lots)
            </span>
          </div>
          <div className="flex justify-between text-[#6E7A8A]">
            <span>Authority Verification</span>
            <span className="text-[#BFA13B]">SIMULATED GATEWAY DISPATCH</span>
          </div>
        </div>

        {/* Prototype Failure State Simulation Toggle (P0 Acceptance Testing) */}
        <div className="flex items-center gap-2 mb-4 p-2 bg-[#0A0E14] border border-[#232A35] text-[11px]">
          <input
            type="checkbox"
            id="sim-reject"
            checked={simulateRejection}
            onChange={(e) => setSimulateRejection(e.target.checked)}
            className="cursor-pointer"
          />
          <label htmlFor="sim-reject" className="text-[#6E7A8A] cursor-pointer">
            Simulate Gateway Rejection (tests failure state; ensures no position change on rejection)
          </label>
        </div>

        {/* Action Controls */}
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            data-testid="confirm-dialog-cancel"
            className="px-3 py-1.5 text-xs text-[#6E7A8A] hover:text-[#E7EAEE] bg-[#161C26] border border-[#232A35] rounded-[2px] transition-colors cursor-pointer flex items-center gap-1.5"
          >
            <span>Cancel</span>
            <span className="font-mono text-[10px] bg-[#232A35] px-1 py-0.5 rounded-[2px]">Esc</span>
          </button>
          <button
            onClick={() => onConfirm(simulateRejection)}
            data-testid="confirm-dialog-confirm"
            className={`px-3 py-1.5 text-xs font-medium rounded-[2px] border transition-colors cursor-pointer flex items-center gap-1.5 ${
              simulateRejection
                ? 'border-[#B23B3B] bg-[#B23B3B]/15 text-[#B23B3B] hover:bg-[#B23B3B]/25'
                : isDanger
                ? 'border-[#C25B6B] bg-[#C25B6B]/15 text-[#C25B6B] hover:bg-[#C25B6B]/25'
                : 'border-[#5B8FBF] bg-[#5B8FBF]/15 text-[#5B8FBF] hover:bg-[#5B8FBF]/25'
            }`}
          >
            <span>{simulateRejection ? 'Test Rejection Dispatch' : 'Confirm Execution'}</span>
            <span className="font-mono text-[10px] bg-black/30 px-1 py-0.5 rounded-[2px]">Enter ↵</span>
          </button>
        </div>
      </div>
    </div>
  );
};
