import { IntentFingerprint } from '../types/contracts';

/**
 * Deterministic hash generator (Fowler-Noll-Vo / Murmur inspired dual 32-bit mix).
 * Produces a stable hex string across any JS/Node runtime without external dependencies.
 */
export function createDeterministicHash(input: string): string {
  let h1 = 0xdeadbeef ^ input.length;
  let h2 = 0x41c6ce57 ^ input.length;
  for (let i = 0; i < input.length; i++) {
    const ch = input.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507);
  h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507);
  h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  const combined = 4294967296 * (2097151 & h2) + (h1 >>> 0);
  return combined.toString(16).padStart(16, '0');
}

/**
 * Generates a stable IntentFingerprint according to FRACTAL-FLOW's intent invariant.
 * If the operator triggers the same logical command for the same target with the same params,
 * the idempotencyKey remains identical.
 */
export function generateIntentFingerprint(
  operatorId: string,
  targetPositionId: string,
  symbol: string,
  actionType: 'CLOSE' | 'TIGHTEN_STOP' | 'MOVE_TO_BREAKEVEN' | 'KILL_SWITCH',
  parameters: Record<string, unknown> = {}
): IntentFingerprint {
  // Sort parameter keys for canonical JSON serialization
  const sortedKeys = Object.keys(parameters).sort();
  const canonicalParams: Record<string, unknown> = {};
  for (const key of sortedKeys) {
    canonicalParams[key] = parameters[key];
  }

  const payload = `${operatorId}#${targetPositionId}#${symbol}#${actionType}#${JSON.stringify(canonicalParams)}`;
  const hash = createDeterministicHash(payload);

  return {
    intentId: `intent_${hash.slice(0, 12)}`,
    operatorId,
    targetPositionId,
    symbol,
    actionType,
    parameters: canonicalParams,
    idempotencyKey: `idemp_${actionType.toLowerCase()}_${hash}`,
    createdAt: Date.now()
  };
}
