import React, { useState, useEffect, useRef } from 'react';
import { 
  Settings, 
  X, 
  Sliders, 
  ShieldAlert, 
  Database, 
  Check, 
  AlertTriangle,
  Lock,
  Layers
} from 'lucide-react';
import { 
  PresentationPreferences, 
  OperationalRiskConfig 
} from '../types';
import { validateOperationalRiskConfig } from '../utils/riskValidator';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  preferences: PresentationPreferences;
  onUpdatePreferences: (prefs: PresentationPreferences) => void;
  riskConfig: OperationalRiskConfig;
  onUpdateRiskConfig: (draftConfig: OperationalRiskConfig) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  preferences,
  onUpdatePreferences,
  riskConfig,
  onUpdateRiskConfig
}) => {
  const [activeTab, setActiveTab] = useState<'preferences' | 'risk_config' | 'calibration'>('preferences');
  
  // Local presentation draft
  const [localPrefs, setLocalPrefs] = useState<PresentationPreferences>(preferences);
  
  // Operational risk draft
  const [riskDraft, setRiskDraft] = useState<OperationalRiskConfig>(riskConfig);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isSavedFeedback, setIsSavedFeedback] = useState(false);

  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setLocalPrefs(preferences);
  }, [preferences]);

  useEffect(() => {
    setRiskDraft(riskConfig);
    setValidationError(null);
    setIsSavedFeedback(false);
  }, [riskConfig, isOpen]);

  // Trap focus and handle Escape
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

  const handleDensityChange = (density: 'compact' | 'default' | 'spacious') => {
    const updated = { ...localPrefs, layoutDensity: density };
    setLocalPrefs(updated);
    onUpdatePreferences(updated);
  };

  const handleAudioToggle = () => {
    const updated = { ...localPrefs, audioCues: !localPrefs.audioCues };
    setLocalPrefs(updated);
    onUpdatePreferences(updated);
  };

  const handleRiskParamChange = (field: keyof OperationalRiskConfig, value: number) => {
    const updated = { ...riskDraft, [field]: value };
    setRiskDraft(updated);
    setIsSavedFeedback(false);

    const validation = validateOperationalRiskConfig(updated);
    if (!validation.isValid) {
      setValidationError(validation.errors[0] || 'Invalid configuration parameters');
    } else {
      setValidationError(null);
    }
  };

  const handleSaveRiskConfig = () => {
    const validation = validateOperationalRiskConfig(riskDraft);
    if (!validation.isValid) {
      setValidationError(validation.errors.join('; '));
      return;
    }

    onUpdateRiskConfig(riskDraft);
    setIsSavedFeedback(true);
    setTimeout(() => setIsSavedFeedback(false), 3000);
  };

  const hasRiskChanges = 
    riskDraft.maxLaneRiskR !== riskConfig.maxLaneRiskR ||
    riskDraft.maxAccountExposureR !== riskConfig.maxAccountExposureR ||
    riskDraft.dailyLossLimitUsd !== riskConfig.dailyLossLimitUsd ||
    riskDraft.killSwitchThresholdL !== riskConfig.killSwitchThresholdL;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-dialog-title"
      data-testid="settings-modal"
    >
      <div className="bg-[#10151D] border border-[#232A35] w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl">
        {/* Modal Header */}
        <div className="px-5 py-3 border-b border-[#232A35] flex items-center justify-between bg-[#161C26]">
          <div className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-[#5B8FBF]" />
            <h2 id="settings-dialog-title" className="text-sm font-semibold text-[#E7EAEE] tracking-wide">
              CONTROL SURFACE SETTINGS & RISK CONFIGURATION
            </h2>
          </div>
          <button
            ref={closeButtonRef}
            onClick={onClose}
            className="p-1 hover:bg-[#232A35] text-[#6E7A8A] hover:text-[#E7EAEE] transition-colors min-h-[32px] min-w-[32px] flex items-center justify-center"
            aria-label="Close settings dialog"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Sub-Navigation Tabs */}
        <div className="flex border-b border-[#232A35] bg-[#0A0E14] px-4 pt-2 gap-2 text-xs">
          <button
            onClick={() => setActiveTab('preferences')}
            className={`px-3 py-2 border-b-2 font-medium transition-colors min-h-[36px] flex items-center gap-1.5 ${
              activeTab === 'preferences'
                ? 'border-[#5B8FBF] text-[#E7EAEE]'
                : 'border-transparent text-[#6E7A8A] hover:text-[#E7EAEE]'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            Local Preferences
            <span className="text-[10px] bg-[#161C26] px-1 py-0.5 border border-[#232A35] text-[#6E7A8A]">LOCAL</span>
          </button>

          <button
            onClick={() => setActiveTab('risk_config')}
            className={`px-3 py-2 border-b-2 font-medium transition-colors min-h-[36px] flex items-center gap-1.5 ${
              activeTab === 'risk_config'
                ? 'border-[#BFA13B] text-[#E7EAEE]'
                : 'border-transparent text-[#6E7A8A] hover:text-[#E7EAEE]'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5 text-[#BFA13B]" />
            Operational Risk Config
            <span className="text-[10px] bg-[#161C26] px-1 py-0.5 border border-[#232A35] text-[#BFA13B]">SERVER</span>
          </button>

          <button
            onClick={() => setActiveTab('calibration')}
            className={`px-3 py-2 border-b-2 font-medium transition-colors min-h-[36px] flex items-center gap-1.5 ${
              activeTab === 'calibration'
                ? 'border-[#4FAE86] text-[#E7EAEE]'
                : 'border-transparent text-[#6E7A8A] hover:text-[#E7EAEE]'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-[#4FAE86]" />
            Calibration Parameters
            <span className="text-[10px] bg-[#161C26] px-1 py-0.5 border border-[#232A35] text-[#4FAE86]">READ-ONLY</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 overflow-y-auto flex-1 space-y-5 text-xs text-[#E7EAEE]">
          {activeTab === 'preferences' && (
            <div className="space-y-5">
              <div className="p-3 bg-[#0A0E14] border border-[#232A35] text-[#6E7A8A] leading-relaxed">
                <span className="text-[#E7EAEE] font-medium">Local-Only Presentation Layer:</span> Preferences below modify workstation client rendering and are persisted locally in browser storage. They do not alter trading engine authority, server state machines, or risk parameters.
              </div>

              {/* Layout Density */}
              <div>
                <label className="block text-[11px] uppercase tracking-wider text-[#6E7A8A] mb-2 font-semibold">
                  Tabular Layout Density
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(['compact', 'default', 'spacious'] as const).map((density) => (
                    <button
                      key={density}
                      type="button"
                      onClick={() => handleDensityChange(density)}
                      className={`p-2.5 border text-center transition-all min-h-[44px] flex flex-col items-center justify-center ${
                        localPrefs.layoutDensity === density
                          ? 'border-[#5B8FBF] bg-[#161C26] text-[#E7EAEE] font-semibold'
                          : 'border-[#232A35] bg-[#0A0E14] text-[#6E7A8A] hover:text-[#E7EAEE]'
                      }`}
                    >
                      <span className="capitalize">{density}</span>
                      <span className="text-[10px] text-[#454E5C] font-mono">
                        {density === 'compact' ? '24px row' : density === 'default' ? '28px row' : '32px row'}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Audio Cues */}
              <div className="pt-2 border-t border-[#232A35] flex items-center justify-between">
                <div>
                  <div className="font-semibold text-[#E7EAEE]">Operator Telemetry Audio Cues</div>
                  <div className="text-[11px] text-[#6E7A8A]">Sound auditory feedback on critical gate failures and stop ratchets</div>
                </div>
                <button
                  type="button"
                  onClick={handleAudioToggle}
                  className={`px-3 py-1.5 border text-xs font-mono font-medium min-h-[44px] min-w-[70px] transition-colors ${
                    localPrefs.audioCues
                      ? 'border-[#4FAE86] bg-[#4FAE86]/10 text-[#4FAE86]'
                      : 'border-[#232A35] bg-[#0A0E14] text-[#6E7A8A]'
                  }`}
                >
                  {localPrefs.audioCues ? 'ENABLED' : 'MUTED'}
                </button>
              </div>

              {/* Theme Note */}
              <div className="pt-2 border-t border-[#232A35] flex items-center justify-between">
                <div>
                  <div className="font-semibold text-[#E7EAEE]">Color Theme & Visual Tokens</div>
                  <div className="text-[11px] text-[#6E7A8A]">Strict compliance with 02_DESIGN_SYSTEM (No gradients, 1px hairlines)</div>
                </div>
                <span className="font-mono text-[11px] px-2 py-1 bg-[#161C26] border border-[#232A35] text-[#6E7A8A]">
                  OBSIDIAN_BLACK (#0A0E14)
                </span>
              </div>
            </div>
          )}

          {activeTab === 'risk_config' && (
            <div className="space-y-4">
              {/* Provenance Box */}
              <div className="p-3 bg-[#0A0E14] border border-[#BFA13B]/30 flex flex-col gap-1 text-[11px]">
                <div className="flex items-center justify-between text-[#BFA13B] font-semibold">
                  <span className="flex items-center gap-1.5">
                    <Database className="w-3.5 h-3.5" />
                    AUTHORITATIVE RISK BOUNDARY
                  </span>
                  <span className="font-mono text-[10px] bg-[#BFA13B]/10 px-1.5 py-0.5 border border-[#BFA13B]/30">
                    {riskConfig.source}
                  </span>
                </div>
                <div className="text-[#6E7A8A] flex flex-wrap gap-x-4 gap-y-1 font-mono pt-1">
                  <span>Config ID: <strong className="text-[#E7EAEE]">{riskConfig.effectiveConfigId}</strong></span>
                  <span>Version: <strong className="text-[#E7EAEE]">{riskConfig.version}</strong></span>
                  <span>Last Sync: <strong className="text-[#E7EAEE]">{new Date(riskConfig.lastUpdated).toLocaleTimeString()}</strong></span>
                </div>
              </div>

              {/* Notice regarding backend write adapter */}
              <div className="p-2.5 bg-[#161C26] border border-[#232A35] text-[#6E7A8A] text-[11px] leading-relaxed">
                <strong className="text-[#BFA13B]">Fail-Closed Safety Notice:</strong> Live backend Control Service and ExecutionGateway write adapters are currently not provisioned. Edits in this console apply directly to the local off-broker simulation state machine.
              </div>

              {/* Form Fields */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[11px] text-[#6E7A8A] uppercase tracking-wider mb-1">
                    Max Lane Risk per Setup (R)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.5"
                    max="10.0"
                    value={riskDraft.maxLaneRiskR}
                    onChange={(e) => handleRiskParamChange('maxLaneRiskR', parseFloat(e.target.value))}
                    className="w-full bg-[#0A0E14] border border-[#232A35] px-3 py-2 font-mono text-sm text-[#E7EAEE] focus:border-[#5B8FBF] focus:outline-hidden min-h-[44px]"
                  />
                  <div className="text-[10px] text-[#454E5C] mt-1">Default: 2.50R · Invariant: $\le$ Max Account Exposure</div>
                </div>

                <div>
                  <label className="block text-[11px] text-[#6E7A8A] uppercase tracking-wider mb-1">
                    Max Aggregate Account Exposure (R)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    min="1.0"
                    max="20.0"
                    value={riskDraft.maxAccountExposureR}
                    onChange={(e) => handleRiskParamChange('maxAccountExposureR', parseFloat(e.target.value))}
                    className="w-full bg-[#0A0E14] border border-[#232A35] px-3 py-2 font-mono text-sm text-[#E7EAEE] focus:border-[#5B8FBF] focus:outline-hidden min-h-[44px]"
                  />
                  <div className="text-[10px] text-[#454E5C] mt-1">Default: 5.00R · Ceiling across all concurrent lanes</div>
                </div>

                <div>
                  <label className="block text-[11px] text-[#6E7A8A] uppercase tracking-wider mb-1">
                    Daily Loss Circuit Breaker ($ USD)
                  </label>
                  <input
                    type="number"
                    step="100"
                    min="250"
                    max="10000"
                    value={riskDraft.dailyLossLimitUsd}
                    onChange={(e) => handleRiskParamChange('dailyLossLimitUsd', parseFloat(e.target.value))}
                    className="w-full bg-[#0A0E14] border border-[#232A35] px-3 py-2 font-mono text-sm text-[#E7EAEE] focus:border-[#5B8FBF] focus:outline-hidden min-h-[44px]"
                  />
                  <div className="text-[10px] text-[#454E5C] mt-1">Default: $1,500.00 · Halts all new entries on breach</div>
                </div>

                <div>
                  <label className="block text-[11px] text-[#6E7A8A] uppercase tracking-wider mb-1">
                    Automatic Kill-Switch Ladder Trigger Level
                  </label>
                  <select
                    value={riskDraft.killSwitchThresholdL}
                    onChange={(e) => handleRiskParamChange('killSwitchThresholdL', parseInt(e.target.value, 10))}
                    className="w-full bg-[#0A0E14] border border-[#232A35] px-3 py-2 font-mono text-sm text-[#E7EAEE] focus:border-[#5B8FBF] focus:outline-hidden min-h-[44px]"
                  >
                    <option value={1}>L1: Freeze New Signal Ingestion</option>
                    <option value={2}>L2: Cancel Pending Orders (Operator Required)</option>
                    <option value={3}>L3: Emergency Flatten All Positions (Admin Required)</option>
                  </select>
                  <div className="text-[10px] text-[#454E5C] mt-1">Governed by 01_ARCHITECTURE §1 kill ladder</div>
                </div>
              </div>

              {/* Validation Error Banner */}
              {validationError && (
                <div className="p-3 bg-[#B23B3B]/15 border border-[#B23B3B] text-[#C25B6B] flex items-center gap-2 text-xs">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-[#C25B6B]" />
                  <span>{validationError}</span>
                </div>
              )}

              {/* Before/After Diff Preview */}
              {hasRiskChanges && !validationError && (
                <div className="p-3 bg-[#0A0E14] border border-[#232A35] space-y-2">
                  <div className="text-[11px] uppercase tracking-wider text-[#BFA13B] font-semibold">
                    Proposed Configuration Mutation Diff:
                  </div>
                  <div className="font-mono text-xs space-y-1">
                    {riskDraft.maxLaneRiskR !== riskConfig.maxLaneRiskR && (
                      <div className="flex items-center gap-2">
                        <span className="text-[#6E7A8A]">maxLaneRiskR:</span>
                        <span className="text-[#C25B6B] line-through">{riskConfig.maxLaneRiskR}R</span>
                        <span className="text-[#4FAE86]">→ {riskDraft.maxLaneRiskR}R</span>
                      </div>
                    )}
                    {riskDraft.maxAccountExposureR !== riskConfig.maxAccountExposureR && (
                      <div className="flex items-center gap-2">
                        <span className="text-[#6E7A8A]">maxAccountExposureR:</span>
                        <span className="text-[#C25B6B] line-through">{riskConfig.maxAccountExposureR}R</span>
                        <span className="text-[#4FAE86]">→ {riskDraft.maxAccountExposureR}R</span>
                      </div>
                    )}
                    {riskDraft.dailyLossLimitUsd !== riskConfig.dailyLossLimitUsd && (
                      <div className="flex items-center gap-2">
                        <span className="text-[#6E7A8A]">dailyLossLimitUsd:</span>
                        <span className="text-[#C25B6B] line-through">${riskConfig.dailyLossLimitUsd}</span>
                        <span className="text-[#4FAE86]">→ ${riskDraft.dailyLossLimitUsd}</span>
                      </div>
                    )}
                    {riskDraft.killSwitchThresholdL !== riskConfig.killSwitchThresholdL && (
                      <div className="flex items-center gap-2">
                        <span className="text-[#6E7A8A]">killSwitchThresholdL:</span>
                        <span className="text-[#C25B6B] line-through">L{riskConfig.killSwitchThresholdL}</span>
                        <span className="text-[#4FAE86]">→ L{riskDraft.killSwitchThresholdL}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Save Button */}
              <div className="pt-2 flex items-center justify-between">
                <span className="text-[11px] text-[#6E7A8A]">
                  Requires operator role authorization
                </span>
                <button
                  type="button"
                  disabled={!hasRiskChanges || !!validationError}
                  onClick={handleSaveRiskConfig}
                  className={`px-4 py-2 border text-xs font-mono font-medium transition-all min-h-[44px] flex items-center gap-1.5 ${
                    !hasRiskChanges || !!validationError
                      ? 'border-[#232A35] bg-[#0A0E14] text-[#454E5C] cursor-not-allowed'
                      : 'border-[#BFA13B] bg-[#BFA13B]/20 text-[#E7EAEE] hover:bg-[#BFA13B]/30'
                  }`}
                >
                  <ShieldAlert className="w-3.5 h-3.5" />
                  APPLY SIMULATED CONFIG DRAFT
                </button>
              </div>

              {isSavedFeedback && (
                <div className="p-2 bg-[#4FAE86]/10 border border-[#4FAE86] text-[#4FAE86] flex items-center gap-2 text-xs">
                  <Check className="w-4 h-4" />
                  Simulated configuration successfully updated. Audit record logged to local event journal.
                </div>
              )}
            </div>
          )}

          {activeTab === 'calibration' && (
            <div className="space-y-4">
              <div className="p-3 bg-[#0A0E14] border border-[#232A35] text-[#6E7A8A] leading-relaxed flex items-start gap-2">
                <Lock className="w-4 h-4 text-[#4FAE86] shrink-0 mt-0.5" />
                <div>
                  <span className="text-[#E7EAEE] font-medium">Read-Only Calibration Layer:</span> Exit intelligence and regime parameters cannot be edited directly from the console. Parameters below are managed strictly via the automated statistical validation and promotion pipeline per <code className="text-[#E7EAEE]">docs/26 §8</code>.
                </div>
              </div>

              <div className="border border-[#232A35] overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-[#161C26] text-[#6E7A8A] border-b border-[#232A35]">
                    <tr>
                      <th className="p-2.5">Parameter Key</th>
                      <th className="p-2.5">Active Value</th>
                      <th className="p-2.5">Stage</th>
                      <th className="p-2.5">Evidence Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#232A35]">
                    <tr>
                      <td className="p-2.5 text-[#E7EAEE]">pullback_mfe_threshold</td>
                      <td className="p-2.5 text-[#4FAE86]">+0.80R</td>
                      <td className="p-2.5"><span className="px-1.5 py-0.5 bg-[#4FAE86]/10 text-[#4FAE86] border border-[#4FAE86]/30">ACTIVE</span></td>
                      <td className="p-2.5 text-[#6E7A8A]">OOS-20261018 (p &lt; 0.001)</td>
                    </tr>
                    <tr>
                      <td className="p-2.5 text-[#E7EAEE]">half_life_decay_tau</td>
                      <td className="p-2.5 text-[#4FAE86]">120 min</td>
                      <td className="p-2.5"><span className="px-1.5 py-0.5 bg-[#4FAE86]/10 text-[#4FAE86] border border-[#4FAE86]/30">ACTIVE</span></td>
                      <td className="p-2.5 text-[#6E7A8A]">OOS-20261019 (p &lt; 0.001)</td>
                    </tr>
                    <tr>
                      <td className="p-2.5 text-[#E7EAEE]">vol_trail_ratchet_sigma</td>
                      <td className="p-2.5 text-[#BFA13B]">1.85 sigma</td>
                      <td className="p-2.5"><span className="px-1.5 py-0.5 bg-[#BFA13B]/10 text-[#BFA13B] border border-[#BFA13B]/30">CANARY (15%)</span></td>
                      <td className="p-2.5 text-[#6E7A8A]">VAL-20261022 (in canary)</td>
                    </tr>
                    <tr>
                      <td className="p-2.5 text-[#E7EAEE]">regime_entropy_veto_bound</td>
                      <td className="p-2.5 text-[#6E7A8A]">0.75</td>
                      <td className="p-2.5"><span className="px-1.5 py-0.5 bg-[#161C26] text-[#6E7A8A] border border-[#232A35]">SHADOW</span></td>
                      <td className="p-2.5 text-[#6E7A8A]">PAPER-EVAL-418</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-3 border-t border-[#232A35] bg-[#161C26] flex items-center justify-between text-xs">
          <span className="font-mono text-[11px] text-[#6E7A8A]">
            FRACTAL-FLOW GUI Control Console · Operator: <strong className="text-[#E7EAEE]">daniel·OP</strong>
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border border-[#232A35] bg-[#0A0E14] text-[#E7EAEE] hover:bg-[#232A35] transition-colors min-h-[44px]"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
