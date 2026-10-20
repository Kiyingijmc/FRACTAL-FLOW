import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { 
  Position, 
  PendingOrder, 
  ClosedTrade, 
  GateCandidate, 
  ActionType, 
  CommandExecutionRecord, 
  CommandLifecycleState,
  NavTab, 
  SystemEvent, 
  PositionsSubTab 
} from './types';
import { 
  ApplicationMode, 
  TelemetryProvenance, 
  IntentFingerprint,
  CommandLifecycle 
} from './types/contracts';
import { SimulationProvider } from './providers/SimulationProvider';
import { LiveCommandAdapter } from './providers/LiveCommandAdapter';
import { createIntentFingerprint } from './utils/idempotency';
import { isKeyboardShortcutAllowed } from './utils/keyboard';
import { evaluateTelemetryFreshness } from './utils/telemetry';
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

  // Ticks Simulation Pause State
  const [isSimPaused, setIsSimPaused] = useState<boolean>(false);

  // Synchronize pause state to SimulationProvider
  useEffect(() => {
    simulationProvider.setPaused(isSimPaused);
  }, [simulationProvider, isSimPaused]);

  // Synchronize initial data and subscribe to provider-owned ticks
  useEffect(() => {
    let isMounted = true;

    simulationProvider.getPositions().then(data => {
      if (isMounted) setPositions(data);
    });

    simulationProvider.getHealth().then(health => {
      if (isMounted) setTelemetry(health);
    });

    // Provider owns tick updates and internal position pricing
    const unsubscribeTicks = simulationProvider.subscribeTicks((_symbol, tick, updatedPositions) => {
      if (!isMounted) return;
      setPositions(updatedPositions);
      setTelemetry((prev) => ({
        ...prev,
        freshnessTimestamp: tick.timestamp,
        status: 'HEALTHY'
      }));
    });

    return () => {
      isMounted = false;
      unsubscribeTicks();
    };
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

  // Periodic Telemetry Freshness Evaluation using production utility
  useEffect(() => {
    const freshnessChecker = setInterval(() => {
      setTelemetry((prev) => {
        const evaluation = evaluateTelemetryFreshness(prev, Date.now());
        if (evaluation.status !== prev.status) {
          return { ...prev, status: evaluation.status };
        }
        return prev;
      });
    }, 1500);

    return () => clearInterval(freshnessChecker);
  }, []);

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

  // Safe Keyboard Shortcut Listener (Guarded against text focus, IME, repeat, modal, in-flight)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isCommandBusy = Boolean(
        activeCommand &&
        activeCommand.status !== 'CONFIRMED' &&
        activeCommand.status !== 'REJECTED'
      );

      // Verify safety context
      const isAllowed = isKeyboardShortcutAllowed(
        e,
        {
          isModalOpen: confirmModal.isOpen,
          isCommandInFlight: isCommandBusy,
        },
        {
          allowRepeat: false,
        }
      );

      if (!isAllowed) {
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

  const mapProgressStatus = (status: CommandLifecycle): CommandLifecycleState => {
    switch (status) {
      case 'ACCEPTED_BY_GATEWAY':
        return 'ACCEPTED';
      case 'DISPATCHED_TO_BROKER':
        return 'DISPATCHED';
      case 'CONFIRMED':
        return 'CONFIRMED';
      case 'REJECTED':
        return 'REJECTED';
      case 'UNKNOWN_PENDING_RECONCILIATION':
        return 'UNKNOWN';
      default:
        return 'ACCEPTED';
    }
  };

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

    // Generate canonical intent and fingerprint
    const intent: IntentFingerprint = createIntentFingerprint(
      'daniel_operator',
      targetPosition.id,
      targetPosition.symbol,
      actionMap[action],
      { 
        side: targetPosition.side, 
        entryPrice: targetPosition.entryPrice, 
        currentPrice: targetPosition.currentPrice,
        simulateRejection 
      }
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

    // Simulation Sandbox Progression owned entirely by SimulationProvider
    try {
      const res = await simulationProvider.submitCommand(
        intent,
        (progress) => {
          setActiveCommand((prev) =>
            prev
              ? {
                  ...prev,
                  status: mapProgressStatus(progress.status),
                  details: progress.details,
                }
              : null
          );
        }
      );

      const updatedPositions = await simulationProvider.getPositions();
      setPositions(updatedPositions);

      addEvent(
        `[SANDBOX] ${res.status}: ${res.message} (AUTH: NO)`,
        'SIM_ENGINE',
        res.status === 'CONFIRMED' ? 'info' : 'crit',
        'SIMULATED'
      );

      setTimeout(() => setActiveCommand(null), 3500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setActiveCommand((prev) =>
        prev ? { ...prev, status: 'REJECTED', details: msg } : null
      );
      setTimeout(() => setActiveCommand(null), 4000);
    }
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

      {/* Signature Element 1: Gate-Chain Strip (Candidate Intake Pipeline) */}
      <GateChainStrip
        candidates={candidates}
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
};

export default App;
