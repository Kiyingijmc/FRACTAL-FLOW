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
import { updateTelemetryState } from './utils/telemetry';
import { Header } from './components/Header';
import { NavRail } from './components/NavRail';
import { MobileBottomNav } from './components/MobileBottomNav';
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
  const [isMoreNavOpen, setIsMoreNavOpen] = useState(false);

  // Mobile View Switcher for Positions: 'table' vs 'detail'
  const [mobileViewTab, setMobileViewTab] = useState<'table' | 'detail'>('table');

  // Lane selection
  const [selectedLane, setSelectedLane] = useState<string>('ACT_PRIMARY');

  // Simulation Controls & Data State
  const [isSimPaused, setIsSimPaused] = useState<boolean>(false);
  const [positions, setPositions] = useState<Position[]>(INITIAL_POSITIONS);
  const [pendingOrders] = useState<PendingOrder[]>(INITIAL_PENDING_ORDERS);
  const [closedTrades] = useState<ClosedTrade[]>(INITIAL_CLOSED_TRADES);
  const [candidates] = useState<GateCandidate[]>(GATE_CANDIDATES);
  const [systemEvents, setSystemEvents] = useState<SystemEvent[]>(INITIAL_SYSTEM_EVENTS);

  // Selection state
  const [selectedPositionId, setSelectedPositionId] = useState<string>(
    INITIAL_POSITIONS[0]?.id || ''
  );
  const [selectedCandidateId, setSelectedCandidateId] = useState<string>(
    GATE_CANDIDATES[0]?.id || ''
  );

  // Active Command in flight
  const [activeCommand, setActiveCommand] = useState<CommandExecutionRecord | null>(null);

  // Confirmation modal state
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    action: ActionType | null;
    targetPosition: Position | null;
  }>({
    isOpen: false,
    action: null,
    targetPosition: null,
  });

  // Compute live KPIs
  const selectedPosition = useMemo(() => {
    return positions.find((p) => p.id === selectedPositionId) || positions[0] || null;
  }, [positions, selectedPositionId]);

  const equity = useMemo(() => {
    const baseEquity = 48250.0;
    const totalUnrealizedDollar = positions.reduce((acc, pos) => {
      const pipValue = pos.priceDecimals === 3 ? 10.0 : 10.0;
      const rDollar = pos.unrealizedR * (pos.size * 100 * pipValue);
      return acc + rDollar;
    }, 0);
    return baseEquity + totalUnrealizedDollar;
  }, [positions]);

  const dailyPnl = useMemo(() => {
    return positions.reduce((acc, pos) => acc + pos.unrealizedR * 125.0, 312.5);
  }, [positions]);

  const openRiskR = useMemo(() => {
    return positions.length * 0.6;
  }, [positions]);

  // Synchronize tick stream from SimulationProvider
  useEffect(() => {
    simulationProvider.setPaused(isSimPaused);
  }, [isSimPaused, simulationProvider]);

  useEffect(() => {
    const unsubscribe = simulationProvider.subscribeTicks((symbol, tick, updatedPositions) => {
      setPositions((prev) =>
        prev.map((p) => {
          if (p.symbol === symbol) {
            const up = updatedPositions.find((item) => item.id === p.id);
            return up
              ? {
                  ...p,
                  currentPrice: up.currentPrice,
                  unrealizedR: up.unrealizedR,
                  lastTickDir: up.currentPrice >= p.currentPrice ? 'up' : 'down',
                  lastTickTimestamp: tick.timestamp,
                }
              : p;
          }
          return p;
        })
      );

      // Periodically update heartbeat telemetry using source-provenance updater (SC-01)
      setTelemetry((prev) =>
        updateTelemetryState(prev, {
          source: 'SIM_ENGINE',
          freshnessTimestamp: tick.timestamp,
          status: 'HEALTHY'
        })
      );
    });

    return () => unsubscribe();
  }, [simulationProvider]);

  // Append audit event safely with proper non-persisted labeling (SC-09)
  const addEvent = useCallback(
    (
      message: string, 
      source: 'JOURNAL' | 'GATEWAY' | 'SIM_ENGINE' | 'CLIENT_INTAKE' = 'SIM_ENGINE', 
      level: 'info' | 'warn' | 'crit' = 'info', 
      status: 'SESSION' | 'IN_MEMORY' | 'SIMULATED' | 'DISPATCHED' | 'CONFIRMED' | 'REJECTED' = 'SESSION'
    ) => {
      const newEvt: SystemEvent = {
        id: `evt_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
        eventId: `EVT-${Math.floor(1000 + Math.random() * 9000)}`,
        timestamp: new Date().toLocaleTimeString(),
        message,
        source,
        level,
        status,
        isAuthoritative: false
      };
      setSystemEvents((prev) => [newEvt, ...prev.slice(0, 49)]);
    },
    []
  );

  // Trigger modal for confirmation
  const handleTriggerAction = (action: ActionType, pos: Position) => {
    setConfirmModal({
      isOpen: true,
      action,
      targetPosition: pos,
    });
  };

  // Keyboard Navigation & Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isKeyboardShortcutAllowed(e, { isModalOpen: confirmModal.isOpen, isCommandInFlight: Boolean(activeCommand) })) {
        return;
      }

      const key = e.key;

      if (key === 'Escape') {
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
        addEvent(`LIVE EXECUTION BLOCKED: ${errorMsg}`, 'GATEWAY', 'crit', 'SESSION');
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
    <div className="flex flex-col h-screen w-full max-w-full overflow-hidden bg-[#10151D] text-[#E7EAEE] font-sans antialiased pb-14 md:pb-0">
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

      {/* Main Body Area */}
      <div className="flex-1 flex min-h-0 overflow-hidden w-full">
        {/* Navigation Rail for Desktop */}
        <NavRail activeTab={activeNavTab} onTabChange={setActiveNavTab} />

        {/* Primary Viewport Area */}
        {activeNavTab === 'POS' ? (
          <>
            {/* Desktop View: Side-by-side Table + Context Panel */}
            <div className="hidden md:flex flex-1 min-h-0 overflow-hidden">
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

            {/* Mobile View (< 768px): Toggleable Table vs Diagnostics Panel */}
            <div className="flex md:hidden flex-1 min-h-0 overflow-hidden w-full">
              {mobileViewTab === 'table' ? (
                <PositionsTable
                  positions={positions}
                  pendingOrders={pendingOrders}
                  closedTrades={closedTrades}
                  selectedPositionId={selectedPositionId}
                  onSelectPosition={(id) => {
                    setSelectedPositionId(id);
                    setMobileViewTab('detail');
                  }}
                  activeSubTab={activeSubTab}
                  onSubTabChange={setActiveSubTab}
                  onOpenDetail={() => setMobileViewTab('detail')}
                />
              ) : (
                <ContextPanel
                  position={selectedPosition}
                  onTriggerAction={handleTriggerAction}
                  activeCommand={activeCommand}
                  closedTrades={closedTrades}
                  onBackToTable={() => setMobileViewTab('table')}
                />
              )}
            </div>
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

      {/* Docked Mobile Bottom Navigation Bar (< 768px) */}
      <MobileBottomNav
        activeTab={activeNavTab}
        onTabChange={(tab) => {
          setActiveNavTab(tab);
          if (tab === 'POS') setMobileViewTab('table');
        }}
        isMoreOpen={isMoreNavOpen}
        onToggleMore={setIsMoreNavOpen}
      />

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
