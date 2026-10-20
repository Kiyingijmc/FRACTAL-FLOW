import { ICommandProvider } from './interfaces';
import { 
  IntentFingerprint, 
  CommandResult, 
  LiveExecutionBlockedError 
} from '../types/contracts';

/**
 * LiveCommandAdapter
 * 
 * Boundary adapter for connecting to the FRACTAL-FLOW backend Control Service.
 * Governed by the Universal Forensic Engineering Protocol (Survival > Authority Integrity).
 * 
 * INVARIANT: Because no backend Control Service or ExecutionGateway daemon is currently
 * provisioned in the repository, any attempt to dispatch live commands MUST fail closed
 * immediately. Live execution can NEVER silently proceed or fake success.
 */
export class LiveCommandAdapter implements ICommandProvider {
  readonly isLiveAuthorized = false;

  async submitCommand(intent: IntentFingerprint): Promise<CommandResult> {
    // Fail-closed gate: live execution is strictly blocked
    throw new LiveExecutionBlockedError(
      `LIVE_EXECUTION_BLOCKED: Cannot dispatch command '${intent.actionType}' for position '${intent.targetPositionId}'. ` +
      `Authoritative backend Control Service is not provisioned in the runtime environment.`
    );
  }

  async reconcileCommand(intentId: string): Promise<CommandResult> {
    throw new LiveExecutionBlockedError(
      `LIVE_EXECUTION_BLOCKED: Cannot reconcile intent '${intentId}'. Backend Control Service is offline.`
    );
  }
}
