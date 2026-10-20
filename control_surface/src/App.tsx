/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Position,
  PendingOrder,
  ClosedTrade,
  GateCandidate,
  SystemEvent,
  NavTab,
  PositionsSubTab,
  ActionType,
  CommandExecutionRecord,
} from './types.ts';
import {
  INITIAL_POSITIONS,
  INITIAL_PENDING_ORDERS,
  INITIAL_CLOSED_TRADES,
  GATE_CANDIDATES,
  INITIAL_SYSTEM_EVENTS,
} from './data/mockData.ts';
import { Header } from './components/Header.tsx';
import { GateChainStrip } from './components/GateChainStrip.tsx';
import { NavRail } from './components/NavRail.tsx';
import { PositionsTable } from './components/PositionsTable.tsx';
import { ContextPanel } from './components/ContextPanel.tsx';
import { FooterLog } from './components/FooterLog.tsx';
import { ConfirmDialog } from './components/ConfirmDialog.tsx';
import { SecondaryViews } from './components/SecondaryViews.tsx';

let eventCounter = 7105;

export default function App() {
  const [positions, setPositions] = useState<Position[]>(INITIAL_POSITIONS);
  const [selectedPositionId, setSelectedPositionId] = useState<string>('pos_eurusd_01');
  const [pendingOrders, setPendingOrders] = useState<PendingOrder[]>(INITIAL_PENDING_ORDERS);
  const [closedTrades, setClosedTrades] = useState<ClosedTrade[]>(INITIAL_CLOSED_TRADES);
  const [gateCandidates] = useState<GateCandidate[]>(GATE_CANDIDATES);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string>('cand_eurusd_01');
  const [systemEvents, setSystemEvents] = useState<SystemEvent[]>(INITIAL_SYSTEM_EVENTS);

  const [activeNavTab, setActiveNavTab] = useState<NavTab>('POS');
  const [activeSubTab, setActiveSubTab] = useState<PositionsSubTab>('open');
  const [lane, setLane] = useState<string>('ACT_PRIMARY');
  const [isSimPaused, setIsSimPaused] = useState<boolean>(false);

  // In-flight command lifecycle tracker
  const [activeCommand, setActiveCommand] = useState<CommandExecutionRecord | null>(null);

  // Modal State
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    action: ActionType | null;
    targetPosition: Position | null;
  }>({
    isOpen: false,
    action: null,
    targetPosition: null,
  });

  // Calculate dynamic metrics
  const openRiskR = useMemo(() => {
    return positions.reduce((acc, p) => {
      if (p.breakevenStatus.includes('confirmed')) return acc + 0.1;
      return acc + (p.unrealizedR < 0 ? Math.min(1.0, Math.abs(p.unrealizedR) + 0.3) : 0.5);
    }, 0.2);
  }, [positions]);

  const dailyPnl = useMemo(() => {
    const closedPnl = closedTrades.slice(0, 4).reduce((acc, t) => acc + t.realizedPnl, 0);
    const openPnl = positions.reduce((acc, p) => acc + p.unrealizedR * 120, 0);
    return Math.round((closedPnl + openPnl) * 100) / 100;
  }, [positions, closedTrades]);

  const equity = useMemo(() => {
    return 48210.33 + (dailyPnl - 312.08);
  }, [dailyPnl]);

  const selectedPosition = useMemo(() => {
    return positions.find((p) => p.id === selectedPositionId) || positions[0] || null;
  }, [positions, selectedPositionId]);

  // Subtle periodic simulated ticks with fading color tint highlights
  useEffect(() => {
    if (isSimPaused) return;

    const interval = setInterval(() => {
      setPositions((prevPositions) => {
        if (prevPositions.length === 0) return prevPositions;

        const targetIndex = Math.floor(Math.random() * prevPositions.length);
        const target = prevPositions[targetIndex];

        const isTickUp = Math.random() > 0.48;
        const tickStep = target.priceDecimals === 3 ? 0.008 : 0.00004;
        const delta = isTickUp ? tickStep : -tickStep;
        const newPrice = Number((target.currentPrice + delta).toFixed(target.priceDecimals));

        const rDelta = (isTickUp ? 1 : -1) * (target.side === 'LONG' ? 0.02 : -0.02);
        const newUnrealizedR = Number((target.unrealizedR + rDelta).toFixed(2));
        const newMfe = Math.max(target.mfe, newUnrealizedR);
        const newMae = Math.min(target.mae, newUnrealizedR);

        return prevPositions.map((p, idx) => {
          if (idx !== targetIndex) return p;
          return {
            ...p,
            currentPrice: newPrice,
            unrealizedR: newUnrealizedR,
            mfe: newMfe,
            mae: newMae,
            lastTickDir: isTickUp ? 'up' : 'down',
            lastTickTimestamp: Date.now(),
          };
        });
      });
    }, 3200);

    return () => clearInterval(interval);
  }, [isSimPaused]);

  const addEvent = useCallback(
    (
      message: string,
      source: 'JOURNAL' | 'GATEWAY' | 'SIM_ENGINE' | 'CLIENT_INTAKE' = 'GATEWAY',
      level: 'info' | 'warn' | 'crit' = 'info',
      status: 'PERSISTED' | 'DISPATCHED' | 'SIMULATED' = 'PERSISTED'
    ) => {
      const now = new Date();
      const timeStr = [
        String(now.getHours()).padStart(2, '0'),
        String(now.getMinutes()).padStart(2, '0'),
        String(now.getSeconds()).padStart(2, '0'),
      ].join(':');

      const newEvt: SystemEvent = {
        id: `evt_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
        eventId: `EVT-${eventCounter++}`,
        timestamp: timeStr,
        message,
        source,
        level,
        status,
      };

      setSystemEvents((prev) => [newEvt, ...prev]);
    },
    []
  );

  // Action Triggers
  const handleTriggerAction = (action: ActionType, pos: Position) => {
    setConfirmModal({
      isOpen: true,
      action,
      targetPosition: pos,
    });
  };

  // Keyboard shortcut listener for rapid operator response
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is inside an interactive input, select, or textarea
      const targetTag = (e.target as HTMLElement)?.tagName;
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(targetTag)) {
        return;
      }

      // If modal is open, let ConfirmDialog manage Enter / Escape
      if (confirmModal.isOpen) {
        return;
      }

      // Guard against double-dispatch while a command is actively in flight
      const isCommandBusy =
        activeCommand &&
        activeCommand.status !== 'CONFIRMED' &&
        activeCommand.status !== 'REJECTED';
      if (isCommandBusy) {
        return;
      }

      const key = e.key;

      // Hotkey for "Back to Positions (POS)" from any secondary view
      if (key === 'Escape' || key === 'Backspace' || key === '0' || key === '`') {
        if (activeNavTab !== 'POS') {
          e.preventDefault();
          setActiveNavTab('POS');
          return;
        }
      }

      if (key === 't' || key === 'T') {
        if (selectedPosition && activeNavTab === 'POS') {
          e.preventDefault();
          handleTriggerAction('tighten_stop', selectedPosition);
        }
      } else if (key === 'b' || key === 'B') {
        if (selectedPosition && activeNavTab === 'POS') {
          e.preventDefault();
          handleTriggerAction('move_to_breakeven', selectedPosition);
        }
      } else if (key === 'c' || key === 'C') {
        if (selectedPosition && activeNavTab === 'POS') {
          e.preventDefault();
          handleTriggerAction('close_position', selectedPosition);
        }
      } else if (key === 'ArrowDown' || key === 'j') {
        if (activeNavTab === 'POS' && positions.length > 0) {
          e.preventDefault();
          const currentIndex = positions.findIndex((p) => p.id === selectedPositionId);
          const nextIndex = (currentIndex + 1) % positions.length;
          setSelectedPositionId(positions[nextIndex].id);
        }
      } else if (key === 'ArrowUp' || key === 'k') {
        if (activeNavTab === 'POS' && positions.length > 0) {
          e.preventDefault();
          const currentIndex = positions.findIndex((p) => p.id === selectedPositionId);
          const prevIndex = (currentIndex - 1 + positions.length) % positions.length;
          setSelectedPositionId(positions[prevIndex].id);
        }
      } else if (key === '1') {
        setActiveSubTab('open');
      } else if (key === '2') {
        setActiveSubTab('pending');
      } else if (key === '3') {
        setActiveSubTab('closed');
      } else if (key === 'p' || key === 'P') {
        setIsSimPaused((prev) => !prev);
      } else if (key === 'n' || key === 'N') {
        e.preventDefault();
        setActiveNavTab('NEWS');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    confirmModal.isOpen,
    activeCommand,
    selectedPosition,
    activeNavTab,
    positions,
    selectedPositionId,
  ]);

  // Explicit Command Lifecycle Execution (REQUESTED -> ACCEPTED -> DISPATCHED -> CONFIRMED | REJECTED)
  const handleConfirmAction = (simulateRejection = false) => {
    const { action, targetPosition } = confirmModal;
    if (!action || !targetPosition) return;

    const commandId = `cmd_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const idempotencyKey = `idemp_${targetPosition.symbol}_${action}_${Date.now()}`;
    const requestedAt = new Date().toTimeString().slice(0, 8);

    // Initial lifecycle state: REQUESTED
    const initialCmdRecord: CommandExecutionRecord = {
      id: commandId,
      action,
      symbol: targetPosition.symbol,
      side: targetPosition.side,
      status: 'REQUESTED',
      idempotencyKey,
      requestedAt,
      source: 'SIMULATION_SANDBOX',
      details: `Operator dispatch confirmed for ${targetPosition.symbol} ${action}`,
    };

    setActiveCommand(initialCmdRecord);
    setConfirmModal({ isOpen: false, action: null, targetPosition: null });

    addEvent(
      `ExecutionGateway: Command ${idempotencyKey} REQUESTED by operator`,
      'GATEWAY',
      'info',
      'DISPATCHED'
    );

    // Transition to ACCEPTED after 250ms
    setTimeout(() => {
      setActiveCommand((prev) =>
        prev ? { ...prev, status: 'ACCEPTED', details: 'Gateway pre-flight constraints verified' } : null
      );

      // Transition to DISPATCHED after 500ms
      setTimeout(() => {
        if (simulateRejection) {
          // Failure path: REJECTED (Zero mutation of positions)
          setActiveCommand((prev) =>
            prev
              ? {
                  ...prev,
                  status: 'REJECTED',
                  details: 'ExecutionGateway REJECTED: Constraint check failed (simulation test)',
                }
              : null
          );
          addEvent(
            `ExecutionGateway REJECTED command ${idempotencyKey}: Invariant violated`,
            'GATEWAY',
            'crit',
            'PERSISTED'
          );

          // Clear active command status after 4 seconds
          setTimeout(() => setActiveCommand(null), 4000);
          return;
        }

        // Nominal path: DISPATCHED -> CONFIRMED
        setActiveCommand((prev) =>
          prev ? { ...prev, status: 'DISPATCHED', details: 'Order dispatched to matching engine stub' } : null
        );

        setTimeout(() => {
          const confirmedAt = new Date().toTimeString().slice(0, 8);
          setActiveCommand((prev) =>
            prev
              ? {
                  ...prev,
                  status: 'CONFIRMED',
                  confirmedAt,
                  details: 'Confirmed by GatewayJournal; local state synchronized',
                }
              : null
          );

          // Perform authoritative state update ONLY when CONFIRMED
          if (action === 'tighten_stop') {
            setPositions((prev) =>
              prev.map((p) => {
                if (p.id !== targetPosition.id) return p;
                return {
                  ...p,
                  structuralAnchor: `${p.drivingTimeframe} tightened swing anchor`,
                  trailDistance: '2.8σ (tightened)',
                };
              })
            );
            addEvent(
              `GatewayJournal: ${targetPosition.symbol} stop tightened to 2.8σ [ACK: ${idempotencyKey}]`,
              'JOURNAL',
              'info',
              'PERSISTED'
            );
          } else if (action === 'move_to_breakeven') {
            setPositions((prev) =>
              prev.map((p) => {
                if (p.id !== targetPosition.id) return p;
                return {
                  ...p,
                  breakevenStatus: 'confirmed @ BE (0.0R)',
                };
              })
            );
            addEvent(
              `GatewayJournal: ${targetPosition.symbol} stop relocated to entry price (BE confirmed)`,
              'JOURNAL',
              'info',
              'PERSISTED'
            );
          } else if (action === 'close_position') {
            const realizedPnl = Math.round(targetPosition.unrealizedR * 200 * 100) / 100;
            const closedTrade: ClosedTrade = {
              id: `cls_${Date.now()}`,
              symbol: targetPosition.symbol,
              side: targetPosition.side,
              setup: targetPosition.setup,
              mode: targetPosition.mode,
              entryPrice: targetPosition.entryPrice,
              exitPrice: targetPosition.currentPrice,
              size: targetPosition.size,
              realizedR: targetPosition.unrealizedR,
              realizedPnl,
              exitReason: 'manual operator close',
              duration: targetPosition.age,
              closedAt: confirmedAt,
              priceDecimals: targetPosition.priceDecimals,
              isSimulated: true,
            };

            setClosedTrades((prev) => [closedTrade, ...prev]);
            setPositions((prev) => {
              const remaining = prev.filter((p) => p.id !== targetPosition.id);
              if (remaining.length > 0 && selectedPositionId === targetPosition.id) {
                setSelectedPositionId(remaining[0].id);
              }
              return remaining;
            });

            addEvent(
              `GatewayJournal: FULL_CLOSE ${targetPosition.symbol} ${targetPosition.side} executed @ ${targetPosition.currentPrice.toFixed(
                targetPosition.priceDecimals
              )} (${targetPosition.unrealizedR >= 0 ? '+' : ''}${targetPosition.unrealizedR.toFixed(2)}R)`,
              'JOURNAL',
              'crit',
              'PERSISTED'
            );
          }

          // Clear active command status after 3.5 seconds
          setTimeout(() => setActiveCommand(null), 3500);
        }, 350);
      }, 300);
    }, 250);
  };

  return (
    <div className="flex flex-col h-screen w-full min-w-[1100px] overflow-x-auto overflow-y-hidden bg-[#0A0E14] text-[#E7EAEE]">
      {/* Header with Simulation Sandbox Warning & Controls */}
      <Header
        equity={equity}
        dailyPnl={dailyPnl}
        openRiskR={openRiskR}
        lane={lane}
        onLaneChange={setLane}
        isSimPaused={isSimPaused}
        onToggleSimPause={() => setIsSimPaused(!isSimPaused)}
      />

      {/* Signature Element 1: Gate-Chain Strip (Candidate Intake Pipeline) */}
      <GateChainStrip
        candidates={gateCandidates}
        selectedCandidateId={selectedCandidateId}
        onSelectCandidate={setSelectedCandidateId}
      />

      {/* Main Body Grid */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* Navigation Rail */}
        <NavRail activeTab={activeNavTab} onTabChange={setActiveNavTab} />

        {/* Primary Viewport Area */}
        {activeNavTab === 'POS' ? (
          <>
            <PositionsTable
              positions={positions}
              pendingOrders={pendingOrders}
              closedTrades={closedTrades}
              selectedPositionId={selectedPositionId}
              onSelectPosition={setSelectedPositionId}
              activeSubTab={activeSubTab}
              onSubTabChange={setActiveSubTab}
            />

            {/* Signature Element 2: Context Panel & Timeframe Cascade */}
            <ContextPanel
              position={selectedPosition}
              onTriggerAction={handleTriggerAction}
              activeCommand={activeCommand}
              closedTrades={closedTrades}
            />
          </>
        ) : (
          <SecondaryViews
            activeTab={activeNavTab}
            onReturnToPositions={() => setActiveNavTab('POS')}
          />
        )}
      </div>

      {/* Footer Log with Authoritative Journal Stream Metadata */}
      <FooterLog events={systemEvents} />

      {/* Action Confirmation Modal with Idempotency & Rejection Testing */}
      <ConfirmDialog
        isOpen={confirmModal.isOpen}
        action={confirmModal.action}
        position={confirmModal.targetPosition}
        onConfirm={handleConfirmAction}
        onCancel={() => setConfirmModal({ isOpen: false, action: null, targetPosition: null })}
      />
    </div>
  );
}
