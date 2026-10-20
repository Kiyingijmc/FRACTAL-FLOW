import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { 
  Position, 
  PendingOrder, 
  ClosedTrade, 
  GateCandidate, 
  ActionType, 
  CommandExecutionRecord, 
  NavTab, 
  SystemEvent, 
  PositionsSubTab 
} from './types';
import { 
  ApplicationMode, 
  TelemetryProvenance, 
  IntentFingerprint 
} from './types/contracts';
import { SimulationProvider } from './providers/SimulationProvider';
import { LiveCommandAdapter } from './providers/LiveCommandAdapter';
import { generateIntentFingerprint } from './utils/idempotency';
import { isSafeKeyboardShortcutTarget } from './utils/keyboard';
import { Header } from './components/Header';
import { NavRail } from './components/NavRail';
import { GateChainStrip } from './components/GateChainStrip';
import { PositionsTable } from './components/PositionsTable';
import { ContextPanel } from './components/ContextPanel';
import { ConfirmDialog } from './components/ConfirmDialog';
import { FooterLog } from './components/FooterLog';
import { SecondaryViews } from './components/SecondaryViews';
import { 
  INITIAL_POSITIONS, 
  INITIAL_PENDING_ORDERS, 
  GATE_CANDIDATES, 
  INITIAL_SYSTEM_EVENTS, 
  INITIAL_CLOSED_TRADES 
} from './data/mockData';

export const App: React.FC = () => {
  // Provider boundaries
  const simulationProvider = useMemo(() => new SimulationProvider(), []);
  const liveCommandAdapter = useMemo(() => new LiveCommandAdapter(), []);

  // Application Mode & Telemetry Provenance State
  const [applicationMode] = useState<ApplicationMode>('SIMULATION_SANDBOX');
  const [telemetry, setTelemetry] = useState<TelemetryProvenance>({
    source: 'SIM_ENGINE',
    status: 'HEALTHY',
    freshnessTimestamp: Date.now(),
    isAuthoritative: false,
    staleThresholdMs: 5000,
    epoch: 418,
    bridgeStatus: 'SIM_VIRTUAL_OK',
    fenceStatus: 'SIM_FENCE_ENFORCED'
  });

  // Navigation & Sub-Tabs
  const [activeNavTab, setActiveNavTab] = useState<NavTab>('POS');
  const [activeSubTab, setActiveSubTab] = useState<PositionsSubTab>('open');
  const [selectedLane, setSelectedLane] = useState<string>('ACT_PRIMARY');

  // Core Data States
  const [positions, setPositions] = useState<Position[]>(INITIAL_POSITIONS);
  const [pendingOrders] = useState<PendingOrder[]>(INITIAL_PENDING_ORDERS);
  const [candidates] = useState<GateCandidate[]>(GATE_CANDIDATES);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string>(GATE_CANDIDATES[0]?.id || '');
  const [selectedPositionId, setSelectedPositionId] = useState<string>(INITIAL_POSITIONS[0]?.id || '');
  const [closedTrades] = useState<ClosedTrade[]>(INITIAL_CLOSED_TRADES);
  const [systemEvents, setSystemEvents] = useState<SystemEvent[]>(INITIAL_SYSTEM_EVENTS);

  // Command & Confirmation Dialog States
  const [activeCommand, setActiveCommand] = useState<CommandExecutionRecord | null>(null);
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    action: ActionType | null;
    targetPosition: Position | null;
  }>({
    isOpen: false,
    action: null,
    targetPosition: null,
  });

  // Ticks Simulation State
  const [isSimPaused, setIsSimPaused] = useState<boolean>(false);

  // Synchronize initial data from SimulationProvider
  useEffect(() => {
    let isMounted = true;
    simulationProvider.getPositions().then(data => {
      if (isMounted) setPositions(data);
    });
    simulationProvider.getHealth().then(health => {
      if (isMounted) setTelemetry(health);
    });
    return () => { isMounted = false; };
  }, [simulationProvider]);

  // Derived Account Metrics (Strictly identified as client-derived simulation math)
  const openRiskR = useMemo(() => {
    return positions.reduce((acc, p) => acc + (p.size * 0.5), 0);
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

  // Telemetry Freshness Check (Evaluates STALE if no tick received within staleThresholdMs)
  useEffect(() => {
    const freshnessChecker = setInterval(() => {
      setTelemetry((prev) => {
        const elapsed = Date.now() - prev.freshnessTimestamp;
        const isStale = elapsed > prev.staleThresholdMs;
        if (isStale && prev.status === 'HEALTHY') {
          return { ...prev, status: 'STALE' };
        } else if (!isStale && prev.status === 'STALE') {
          return { ...prev, status: 'HEALTHY' };
        }
        return prev;
      });
    }, 1500);

    return () => clearInterval(freshnessChecker);
  }, []);

  // Periodic Simulated Ticks via Simulation Provider
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

        // Update telemetry freshness timestamp
        setTelemetry((prev) => ({
          ...prev,
          freshnessTimestamp: Date.now(),
          status: 'HEALTHY',
        }));

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

  // Auditable System Event Logger
  const addEvent = useCallback(
    (
      message: string,
      source: 'JOURNAL' | 'GATEWAY' | 'SIM_ENGINE' | 'CLIENT_INTAKE' = 'SIM_ENGINE',
      level: 'info' | 'warn' | 'crit' = 'info',
      status: 'PERSISTED' | 'DISPATCHED' | 'SIMULATED' = 'SIMULATED'
    ) => {
      const now = new Date();
      const timeStr = [
        String(now.getHours()).padStart(2, '0'),
        String(now.getMinutes()).padStart(2, '0'),
        String(now.getSeconds()).padStart(2, '0'),
      ].join(':');

      const newEvt: SystemEvent = {
        id: `evt_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
        eventId: `EVT-${Date.now().toString().slice(-4)}`,
        timestamp: timeStr,
        message,
        source,
        level,
        status,
        isAuthoritative: false,
      };

      setSystemEvents((prev) => [newEvt, ...prev]);
    },
    []
  );

  // Trigger Action (Opens explicit confirmation dialog)
  const handleTriggerAction = (action: ActionType, pos: Position) => {
    setConfirmModal({
      isOpen: true,
      action,
      targetPosition: pos,
    });
  };

  // Safe Keyboard Shortcut Listener (Guarded against text input focus)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Risk N-01 Guard: Ignore if user is inside an input, textarea, or editable field
      if (!isSafeKeyboardShortcutTarget(e)) {
        return;
      }

      // If confirm dialog is active, dialog manages Enter/Escape
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

      // Escape / Backspace / 0 returns to Positions view
      if (key === 'Escape' || key === 'Backspace' || key === '0') {
        if (activeNavTab !== 'POS') {
          e.preventDefault();
          setActiveNavTab('POS');
          return;
        }
      }

      // Operator hotkeys
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

  // Explicit Command Execution via Provider Boundary
  const handleConfirmAction = async (simulateRejection = false) => {
    const { action, targetPosition } = confirmModal;
    if (!action || !targetPosition) return;

    // Map UI action to canonical ActionType
    const actionMap: Record<ActionType, 'CLOSE' | 'TIGHTEN_STOP' | 'MOVE_TO_BREAKEVEN'> = {
      close_position: 'CLOSE',
      tighten_stop: 'TIGHTEN_STOP',
      move_to_breakeven: 'MOVE_TO_BREAKEVEN',
    };

    // Generate deterministic IntentFingerprint (GUI-HPL-006: Identical across duplicate retries)
    const intent: IntentFingerprint = generateIntentFingerprint(
      'daniel_operator',
      targetPosition.id,
      targetPosition.symbol,
      actionMap[action],
      { side: targetPosition.side, entryPrice: targetPosition.entryPrice, currentPrice: targetPosition.currentPrice }
    );

    const requestedAt = new Date().toTimeString().slice(0, 8);

    // Initial lifecycle state: REQUESTED
    const initialCmdRecord: CommandExecutionRecord = {
      id: intent.intentId,
      action,
      symbol: targetPosition.symbol,
      side: targetPosition.side,
      status: 'REQUESTED',
      idempotencyKey: intent.idempotencyKey,
      requestedAt,
      source: 'SIMULATION_SANDBOX',
      details: `[SANDBOX] Intent ${intent.intentId} prepared for ${targetPosition.symbol} ${action}`,
    };

    setActiveCommand(initialCmdRecord);
    setConfirmModal({ isOpen: false, action: null, targetPosition: null });

    addEvent(
      `[SANDBOX] Intent ${intent.intentId} (${intent.idempotencyKey.slice(0, 16)}...) REQUESTED`,
      'SIM_ENGINE',
      'info',
      'SIMULATED'
    );

    // Operational boundary gate: If in LIVE mode, adapter throws LiveExecutionBlockedError
    if (applicationMode === 'LIVE_OPERATIONAL') {
      try {
        await liveCommandAdapter.submitCommand(intent);
      } catch (err: unknown) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        setActiveCommand((prev) =>
          prev ? { ...prev, status: 'REJECTED', details: errorMsg } : null
        );
        addEvent(`LIVE EXECUTION BLOCKED: ${errorMsg}`, 'GATEWAY', 'crit', 'PERSISTED');
        setTimeout(() => setActiveCommand(null), 5000);
        return;
      }
    }

    // Simulation Sandbox Progression
    setTimeout(async () => {
      setActiveCommand((prev) =>
        prev ? { ...prev, status: 'ACCEPTED', details: 'Sandbox constraint checks verified' } : null
      );

      setTimeout(async () => {
        if (simulateRejection) {
          // Failure path: REJECTED (Zero mutation of positions)
          setActiveCommand((prev) =>
            prev
              ? {
                  ...prev,
                  status: 'REJECTED',
                  details: 'Sandbox REJECTED: Invariant check failed (simulation test)',
                }
              : null
          );
          addEvent(
            `[SANDBOX] Invariant violated: REJECTED intent ${intent.intentId}`,
            'SIM_ENGINE',
            'crit',
            'SIMULATED'
          );
          setTimeout(() => setActiveCommand(null), 4000);
          return;
        }

        // Nominal path: DISPATCHED -> CONFIRMED via SimulationProvider
        setActiveCommand((prev) =>
          prev ? { ...prev, status: 'DISPATCHED', details: 'Dispatched to local memory sandbox' } : null
        );

        setTimeout(async () => {
          const res = await simulationProvider.submitCommand(intent);
          const updatedPositions = await simulationProvider.getPositions();
          setPositions(updatedPositions);

          setActiveCommand((prev) =>
            prev
              ? {
                  ...prev,
                  status: 'CONFIRMED',
                  details: `${res.message} (NON-BROKER)`,
                }
              : null
          );

          addEvent(
            `[SANDBOX] CONFIRMED ${intent.actionType} for ${intent.symbol} (AUTH: NO)`,
            'SIM_ENGINE',
            'info',
            'SIMULATED'
          );

          setTimeout(() => setActiveCommand(null), 3500);
        }, 500);
      }, 400);
    }, 250);
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#10151D] text-[#E7EAEE] font-sans antialiased">
      {/* Dynamic Telemetry & Mode-Aware Header */}
      <Header
        equity={equity}
        dailyPnl={dailyPnl}
        openRiskR={openRiskR}
        lane={selectedLane}
        onLaneChange={setSelectedLane}
        isSimPaused={isSimPaused}
        onToggleSimPause={() => setIsSimPaused((prev) => !prev)}
        telemetry={telemetry}
        applicationMode={applicationMode}
      />

      {/* Signature Eleven-Gate Chain Strip */}
      <GateChainStrip
        candidates={candidates}
        selectedCandidateId={selectedCandidateId}
        onSelectCandidate={setSelectedCandidateId}
      />

      {/* Main Workspace Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Compact Navigation Rail */}
        <NavRail activeTab={activeNavTab} onTabChange={setActiveNavTab} />

        {/* View Routing */}
        {activeNavTab === 'POS' ? (
          <div className="flex-1 flex overflow-hidden">
            <PositionsTable
              positions={positions}
              pendingOrders={pendingOrders}
              closedTrades={closedTrades}
              selectedPositionId={selectedPositionId}
              onSelectPosition={setSelectedPositionId}
              activeSubTab={activeSubTab}
              onSubTabChange={setActiveSubTab}
            />
            <ContextPanel
              position={selectedPosition}
              onTriggerAction={handleTriggerAction}
              activeCommand={activeCommand}
              closedTrades={closedTrades}
            />
          </div>
        ) : (
          <SecondaryViews
            activeTab={activeNavTab}
            onReturnToPositions={() => setActiveNavTab('POS')}
          />
        )}
      </div>

      {/* Auditable System Event Journal Ticker */}
      <FooterLog events={systemEvents} />

      {/* Confirmation Modal */}
      <ConfirmDialog
        isOpen={confirmModal.isOpen}
        action={confirmModal.action}
        position={confirmModal.targetPosition}
        onConfirm={(shouldReject) => handleConfirmAction(shouldReject)}
        onCancel={() => setConfirmModal({ isOpen: false, action: null, targetPosition: null })}
      />
    </div>
  );
};

export default App;
