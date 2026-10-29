import React, { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import {
  Position,
  PendingOrder,
  ClosedTrade,
  GateCandidate,
  ActionType,
  CommandExecutionRecord,
  CommandLifecycleState,
  NavTab,
  ExtendedNavTab,
  SystemEvent,
  PositionsSubTab,
  NotificationEvent,
  PresentationPreferences,
  OperationalRiskConfig,
  QuantModelRecord,
  ModelAdviceRecord,
  RolloutPromotionEvent,
  LabRunArtifact,
  RemediationBlockerRecord,
  AuditTrailRecord,
  LatencyMetrics
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
import { SettingsModal } from './components/SettingsModal';
import { CriticalBanner } from './components/CriticalBanner';
import { NotificationDrawer } from './components/NotificationDrawer';
import {
  INITIAL_POSITIONS,
  INITIAL_PENDING_ORDERS,
  GATE_CANDIDATES,
  INITIAL_SYSTEM_EVENTS,
  INITIAL_CLOSED_TRADES,
  INITIAL_NOTIFICATIONS,
  INITIAL_OPERATIONAL_RISK_CONFIG,
  INITIAL_QUANT_MODELS,
  INITIAL_MODEL_ADVICE_STREAM,
  INITIAL_ROLLOUT_PROMOTIONS,
  INITIAL_LAB_RUNS,
  INITIAL_REMEDIATION_BLOCKERS,
  INITIAL_AUDIT_TRAIL
} from './data/mockData';
import {
  validateOperationalRiskConfig,
  evaluatePortfolioRisk,
  validatePositionModification
} from './utils/riskValidator';
import { computeCanonicalSha256 } from './utils/crypto';

// Fallback for Node/tsx test runner environments where Vite does not inject import.meta.env
if (typeof import.meta !== 'undefined' && !(import.meta as any).env) {
  (import.meta as any).env = { DEV: process.env.NODE_ENV !== 'production' };
}

export interface AppTestControlHandle {
  setPositions: React.Dispatch<React.SetStateAction<Position[]>>;
  setRiskConfig: (cfg: OperationalRiskConfig) => void;
  triggerAction: (action: ActionType, pos: Position) => void;
  confirmAction: (simulateRejection?: boolean) => Promise<void>;
  setActiveNavTab: (tab: ExtendedNavTab) => void;
  getPositions: () => Position[];
  getRiskConfig: () => OperationalRiskConfig;
  getOpenRiskR: () => number | null;
  getPortfolioRiskEval: () => ReturnType<typeof evaluatePortfolioRisk>;
  getActiveCommand: () => CommandExecutionRecord | null;
  getAuditTrail: () => AuditTrailRecord[];
  getSimulationProvider: () => SimulationProvider;
}

export interface AppProps {
  initialPositions?: Position[];
  initialRiskConfig?: OperationalRiskConfig;
  initialNavTab?: ExtendedNavTab;
  onPositionsChange?: (positions: Position[]) => void;
  testRef?: React.MutableRefObject<AppTestControlHandle | null>;
}

export const App: React.FC<AppProps> = ({
  initialPositions,
  initialRiskConfig,
  initialNavTab,
  onPositionsChange,
  testRef
}) => {
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
  const [activeNavTab, setActiveNavTab] = useState<ExtendedNavTab>(initialNavTab || 'POS');
  const [activeSubTab, setActiveSubTab] = useState<PositionsSubTab>('open');
  const [isMoreNavOpen, setIsMoreNavOpen] = useState(false);

  // Settings & Notification Center Modal/Drawer State
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);

  // Local Presentation Preferences
  const [preferences, setPreferences] = useState<PresentationPreferences>({
    layoutDensity: 'default',
    audioCues: false,
    colorTheme: 'obsidian_black'
  });

  // Operational Risk Configuration State
  const [riskConfig, setRiskConfig] = useState<OperationalRiskConfig>(
    initialRiskConfig || INITIAL_OPERATIONAL_RISK_CONFIG
  );

  // Notification Event Feeds
  const [notifications, setNotifications] = useState<NotificationEvent[]>(INITIAL_NOTIFICATIONS);

  // Quant Models, Advice, Promotions, Lab, Blockers & Audit Trail State
  const [quantModels] = useState<QuantModelRecord[]>(INITIAL_QUANT_MODELS);
  const [modelAdvice] = useState<ModelAdviceRecord[]>(INITIAL_MODEL_ADVICE_STREAM);
  const [rolloutPromotions] = useState<RolloutPromotionEvent[]>(INITIAL_ROLLOUT_PROMOTIONS);
  const [labRuns] = useState<LabRunArtifact[]>(INITIAL_LAB_RUNS);
  const [blockers] = useState<RemediationBlockerRecord[]>(INITIAL_REMEDIATION_BLOCKERS);
  const [auditTrail, setAuditTrail] = useState<AuditTrailRecord[]>(INITIAL_AUDIT_TRAIL);
  const [latencyMetrics, setLatencyMetrics] = useState<LatencyMetrics>({
    lastRttMs: null,
    avgRttMs: null,
    minRttMs: null,
    maxRttMs: null,
    sampleCount: 0,
    warningThresholdMs: 250,
    criticalThresholdMs: 500,
    status: 'NO_DATA',
    lastMeasuredAt: null,
    injectedDelayMs: 0,
    measuredExecutionTimeMs: null,
    metricName: 'SIMULATED COMMAND-PROCESSING TIME',
  });

  // Mobile View Switcher for Positions: 'table' vs 'detail'
  const [mobileViewTab, setMobileViewTab] = useState<'table' | 'detail'>('table');

  // Lane selection
  const [selectedLane, setSelectedLane] = useState<string>('ACT_PRIMARY');

  // Simulation Controls & Data State
  const [isSimPaused, setIsSimPaused] = useState<boolean>(false);
  const [positions, setPositions] = useState<Position[]>(
    initialPositions || INITIAL_POSITIONS
  );
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
  const confirmModalRef = useRef(confirmModal);
  confirmModalRef.current = confirmModal;

  const positionsRef = useRef(positions);
  positionsRef.current = positions;

  const riskConfigRef = useRef(riskConfig);
  riskConfigRef.current = riskConfig;

  const activeCommandRef = useRef(activeCommand);
  activeCommandRef.current = activeCommand;

  const auditTrailRef = useRef(auditTrail);
  auditTrailRef.current = auditTrail;

  // Active Critical Alert & Unread Notifications
  const criticalAlert = useMemo(() => {
    return notifications.find((n) => n.class === 'safety_critical' && !n.resolved) || null;
  }, [notifications]);

  const unreadNotificationsCount = useMemo(() => {
    return notifications.filter((n) => !n.acknowledged && !n.resolved).length;
  }, [notifications]);

  // Acknowledge Notification
  const handleAcknowledgeNotification = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) =>
        n.id === id ? { ...n, acknowledged: true, acknowledgedAt: Date.now() } : n
      )
    );

    const now = Date.now();
    const auditPayload = {
      action: 'ACKNOWLEDGE_NOTIFICATION',
      target: id,
      timestamp: now,
      note: 'Ack does not resolve condition'
    };

    const auditEntry: AuditTrailRecord = {
      id: `aud_${now}`,
      timestamp: now,
      actor: 'session:local_operator',
      action: 'ACKNOWLEDGE_NOTIFICATION',
      target: id,
      outcome: 'SUCCESS_SIMULATED',
      correlationId: `corr_ack_${id}`,
      intentDigestSha256: computeCanonicalSha256(auditPayload),
      details: `[SESSION ONLY] Operator acknowledged notification [${id}]. Note: Acknowledgement does not resolve condition.`,
      isSessionOnly: true
    };
    setAuditTrail((prev) => [auditEntry, ...prev]);

    setSystemEvents((prev) => [
      {
        id: `evt_${Date.now()}`,
        eventId: `EVT-${Date.now().toString().slice(-4)}`,
        timestamp: new Date().toLocaleTimeString(),
        message: `Notification [${id}] acknowledged by session operator (Ack ≠ Resolution)`,
        source: 'CLIENT_INTAKE',
        level: 'info',
        status: 'SIMULATED',
        isAuthoritative: false
      },
      ...prev
    ]);
  }, []);

  // Update Operational Risk Configuration with mandatory boundary validation
  const handleUpdateRiskConfig = useCallback((draftConfig: OperationalRiskConfig) => {
    const validation = validateOperationalRiskConfig(draftConfig);
    const now = Date.now();

    if (!validation.isValid) {
      // Fail closed: preserve prior configuration exactly, zero state mutation
      const rejectPayload = {
        action: 'UPDATE_RISK_CONFIG_REJECTED',
        target: draftConfig?.effectiveConfigId || 'UNKNOWN',
        errors: validation.errors,
        timestamp: now
      };

      const rejectEntry: AuditTrailRecord = {
        id: `aud_reject_${now}`,
        timestamp: now,
        actor: 'session:local_operator',
        action: 'UPDATE_RISK_CONFIG_REJECTED',
        target: draftConfig?.effectiveConfigId || 'UNKNOWN',
        outcome: 'MUTATION_BLOCKED',
        correlationId: `corr_cfg_reject_${now}`,
        intentDigestSha256: computeCanonicalSha256(rejectPayload),
        details: `[MUTATION BLOCKED] Configuration draft rejected fail-closed: ${validation.errors.join('; ')}`,
        isSessionOnly: true
      };
      setAuditTrail((prev) => [rejectEntry, ...prev]);

      setSystemEvents((prev) => [
        {
          id: `evt_${Date.now()}`,
          eventId: `EVT-${Date.now().toString().slice(-4)}`,
          timestamp: new Date().toLocaleTimeString(),
          message: `OperationalRiskConfig draft rejected fail-closed: ${validation.errors.join('; ')}`,
          source: 'CLIENT_INTAKE',
          level: 'warn',
          status: 'REJECTED',
          isAuthoritative: false
        },
        ...prev
      ]);
      return;
    }

    setRiskConfig({
      ...draftConfig,
      lastUpdated: now,
      source: 'SIM_ENGINE'
    });

    const auditPayload = {
      action: 'UPDATE_RISK_CONFIG_DRAFT',
      effectiveConfigId: draftConfig.effectiveConfigId,
      maxLaneRiskR: draftConfig.maxLaneRiskR,
      maxAccountExposureR: draftConfig.maxAccountExposureR,
      dailyLossLimitUsd: draftConfig.dailyLossLimitUsd,
      timestamp: now
    };

    const auditEntry: AuditTrailRecord = {
      id: `aud_${now}`,
      timestamp: now,
      actor: 'session:local_operator',
      action: 'UPDATE_RISK_CONFIG_DRAFT',
      target: draftConfig.effectiveConfigId,
      outcome: 'SUCCESS_SIMULATED',
      correlationId: `corr_cfg_${draftConfig.effectiveConfigId}`,
      intentDigestSha256: computeCanonicalSha256(auditPayload),
      details: `[SIMULATION ONLY] MaxLaneRisk=${draftConfig.maxLaneRiskR}R, MaxExposure=${draftConfig.maxAccountExposureR}R, DailyLossLimit=$${draftConfig.dailyLossLimitUsd}`,
      isSessionOnly: true
    };
    setAuditTrail((prev) => [auditEntry, ...prev]);

    setSystemEvents((prev) => [
      {
        id: `evt_${Date.now()}`,
        eventId: `EVT-${Date.now().toString().slice(-4)}`,
        timestamp: new Date().toLocaleTimeString(),
        message: `Simulated risk configuration updated: MaxLaneRisk=${draftConfig.maxLaneRiskR}R, MaxExposure=${draftConfig.maxAccountExposureR}R`,
        source: 'CLIENT_INTAKE',
        level: 'info',
        status: 'SIMULATED',
        isAuthoritative: false
      },
      ...prev
    ]);
  }, []);

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

  const portfolioRiskEval = useMemo(() => {
    return evaluatePortfolioRisk(positions);
  }, [positions]);

  const openRiskR = useMemo(() => {
    return portfolioRiskEval.status === 'VALID' && portfolioRiskEval.totalRiskR !== null
      ? portfolioRiskEval.totalRiskR
      : null;
  }, [portfolioRiskEval]);

  useEffect(() => {
    if (onPositionsChange) {
      onPositionsChange(positions);
    }
  }, [positions, onPositionsChange]);

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
    confirmModalRef.current = {
      isOpen: true,
      action,
      targetPosition: pos,
    };
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
      } else if (key === '+' || key === '=' || key === 'a' || key === 'A') {
        if (selectedPosition && activeNavTab === 'POS') {
          e.preventDefault();
          handleTriggerAction('add_size', selectedPosition);
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
  const handleConfirmAction = async (
    simulateRejection = false,
    actionOverride?: ActionType,
    targetPositionOverride?: Position
  ) => {
    const action = actionOverride || confirmModalRef.current.action || confirmModal.action;
    const targetPosition = targetPositionOverride || confirmModalRef.current.targetPosition || confirmModal.targetPosition;
    if (!action || !targetPosition) return;

    // PRODUCTION AUTHORIZATION BOUNDARY:
    // Validate position modification against risk policy and portfolio state
    const currentPositions = positionsRef.current || positions;
    const currentRiskConfig = riskConfigRef.current || riskConfig;
    const modValidation = validatePositionModification(
      action,
      targetPosition,
      currentRiskConfig,
      dailyPnl,
      currentPositions
    );

    if (!modValidation.isAllowed) {
      // Authorization boundary rejection: fail closed immediately with zero submission
      const rejectionReason = modValidation.violations.map(v => v.message).join('; ') || 'RISK_AUTHORIZATION_REJECTED';
      const rejectedCmdRecord: CommandExecutionRecord = {
        id: `CMD-REJ-${Date.now()}`,
        action,
        symbol: targetPosition.symbol,
        side: targetPosition.side,
        status: 'REJECTED',
        idempotencyKey: `REJ_${Date.now()}`,
        requestedAt: new Date().toTimeString().slice(0, 8),
        source: 'PRODUCTION_RISK_GATE',
        details: `[REJECTED FAIL-CLOSED] Action ${action} rejected: ${rejectionReason}`,
      };

      setActiveCommand(rejectedCmdRecord);
      setConfirmModal({ isOpen: false, action: null, targetPosition: null });

      const auditPayload = {
        action: `REJECT_${action.toUpperCase()}`,
        target: targetPosition.id,
        reason: rejectionReason,
        timestamp: Date.now()
      };

      const auditEntry: AuditTrailRecord = {
        id: `aud_rej_${Date.now()}`,
        timestamp: Date.now(),
        actor: 'PRODUCTION_AUTHORITY_GATE',
        action: `REJECT_${action.toUpperCase()}`,
        target: targetPosition.id,
        outcome: 'REJECTED_FAIL_CLOSED',
        correlationId: `corr_rej_${targetPosition.id}`,
        intentDigestSha256: computeCanonicalSha256(auditPayload),
        details: `[AUTHORIZATION REJECTED] ${action} on ${targetPosition.id} (${targetPosition.symbol}) rejected: ${rejectionReason}`,
        isSessionOnly: true
      };
      setAuditTrail((prev) => [auditEntry, ...prev]);

      addEvent(
        `[AUTHORIZATION REJECTED] ${action} on ${targetPosition.id}: ${rejectionReason}`,
        'GATEWAY',
        'crit',
        'REJECTED'
      );

      setTimeout(() => setActiveCommand(null), 4000);
      return;
    }

    // Map UI action to canonical ActionType
    const actionMap: Record<ActionType, 'CLOSE' | 'TIGHTEN_STOP' | 'MOVE_TO_BREAKEVEN' | 'ADD_SIZE' | 'SCALE_IN'> = {
      close_position: 'CLOSE',
      tighten_stop: 'TIGHTEN_STOP',
      move_to_breakeven: 'MOVE_TO_BREAKEVEN',
      add_size: 'ADD_SIZE',
      scale_in: 'SCALE_IN',
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

    const commandStartTime = performance.now();

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

    // Record latency helper with honest separation of measured execution and injected delay
    const recordLatencyMeasurement = (measuredSimMs: number, injectedDelay: number) => {
      const totalDuration = measuredSimMs + injectedDelay;
      if (!Number.isFinite(totalDuration) || totalDuration < 0) {
        setLatencyMetrics((prev) => ({
          ...prev,
          status: 'INVALID',
        }));
        return;
      }

      setLatencyMetrics((prev) => {
        const count = prev.sampleCount + 1;
        const avg = prev.avgRttMs !== null
          ? Math.round((prev.avgRttMs * prev.sampleCount + totalDuration) / count)
          : totalDuration;
        const min = prev.minRttMs !== null ? Math.min(prev.minRttMs, totalDuration) : totalDuration;
        const max = prev.maxRttMs !== null ? Math.max(prev.maxRttMs, totalDuration) : totalDuration;
        const status =
          totalDuration >= prev.criticalThresholdMs
            ? 'EXCEEDED'
            : totalDuration >= prev.warningThresholdMs
            ? 'ELEVATED'
            : 'NOMINAL';
        return {
          ...prev,
          lastRttMs: totalDuration,
          avgRttMs: avg,
          minRttMs: min,
          maxRttMs: max,
          sampleCount: count,
          status,
          lastMeasuredAt: Date.now(),
          measuredExecutionTimeMs: measuredSimMs,
        };
      });
    };

    // Simulation Sandbox Progression owned entirely by SimulationProvider
    try {
      const delayMs = latencyMetrics.injectedDelayMs || 0;
      if (delayMs > 0) {
        await new Promise((res) => setTimeout(res, delayMs));
      }

      simulationProvider.setPositions(currentPositions);
      const simStartTime = performance.now();
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
      const measuredSimTimeMs = Math.round(performance.now() - simStartTime);

      recordLatencyMeasurement(measuredSimTimeMs, delayMs);

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
      recordLatencyMeasurement(0, latencyMetrics.injectedDelayMs || 0);
      const msg = err instanceof Error ? err.message : String(err);
      setActiveCommand((prev) =>
        prev ? { ...prev, status: 'REJECTED', details: msg } : null
      );
      setTimeout(() => setActiveCommand(null), 4000);
    }
  };

  if (import.meta.env.DEV && testRef) {
    testRef.current = {
      setPositions,
      setRiskConfig: handleUpdateRiskConfig,
      triggerAction: handleTriggerAction,
      confirmAction: handleConfirmAction,
      setActiveNavTab,
      getPositions: () => positionsRef.current,
      getRiskConfig: () => riskConfigRef.current,
      getOpenRiskR: () => {
        const evalRes = evaluatePortfolioRisk(positionsRef.current);
        return evalRes.status === 'VALID' && evalRes.totalRiskR !== null ? evalRes.totalRiskR : null;
      },
      getPortfolioRiskEval: () => evaluatePortfolioRisk(positionsRef.current),
      getActiveCommand: () => activeCommandRef.current,
      getAuditTrail: () => auditTrailRef.current,
      getSimulationProvider: () => simulationProvider
    };
  }

  return (
    <div className="flex flex-col h-screen w-full max-w-full overflow-hidden bg-[#10151D] text-[#E7EAEE] font-sans antialiased pb-14 md:pb-0">
      {/* Dynamic Telemetry & Mode-Aware Header with Real-Time Latency Monitor */}
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
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenNotifications={() => setIsNotificationsOpen(true)}
        unreadNotificationsCount={unreadNotificationsCount}
        latency={latencyMetrics}
        onUpdateLatencyDelay={(d) => setLatencyMetrics((prev) => ({ ...prev, injectedDelayMs: d }))}
      />

      {/* Safety-Critical Incident Banner (Persistent, Non-Blocking, Ack ≠ Resolution) */}
      <CriticalBanner
        criticalAlert={criticalAlert}
        onAcknowledge={handleAcknowledgeNotification}
      />

      {/* Signature Element 1: Gate-Chain Strip (Candidate Intake Pipeline + Automated Risk Validator) */}
      <GateChainStrip
        candidates={candidates}
        selectedCandidateId={selectedCandidateId}
        onSelectCandidate={setSelectedCandidateId}
        riskConfig={riskConfig}
        positions={positions}
        dailyPnl={dailyPnl}
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
            quantModels={quantModels}
            modelAdvice={modelAdvice}
            rolloutPromotions={rolloutPromotions}
            labRuns={labRuns}
            blockers={blockers}
            auditTrail={auditTrail}
            positions={positions}
            riskConfig={riskConfig}
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

      {/* Settings & Operational Risk Configuration Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        preferences={preferences}
        onUpdatePreferences={setPreferences}
        riskConfig={riskConfig}
        onUpdateRiskConfig={handleUpdateRiskConfig}
      />

      {/* Notification Center & Delivery Log Drawer */}
      <NotificationDrawer
        isOpen={isNotificationsOpen}
        onClose={() => setIsNotificationsOpen(false)}
        notifications={notifications}
        onAcknowledge={handleAcknowledgeNotification}
      />
    </div>
  );
};

export default App;
