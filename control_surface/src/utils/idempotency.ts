import { IntentFingerprint } from '../types/contracts';

export class CanonicalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CanonicalizationError';
  }
}

/**
 * Standard FIPS 180-4 SHA-256 implementation in pure TypeScript.
 * Produces identical output to standard crypto implementations without external dependencies.
 */
export function sha256Hex(message: string): string {
  // Convert UTF-8 string to byte array
  const bytes: number[] = [];
  for (let i = 0; i < message.length; i++) {
    let charCode = message.charCodeAt(i);
    if (charCode < 0x80) {
      bytes.push(charCode);
    } else if (charCode < 0x800) {
      bytes.push(0xc0 | (charCode >> 6), 0x80 | (charCode & 0x3f));
    } else if (charCode < 0xd800 || charCode >= 0xe000) {
      bytes.push(
        0xe0 | (charCode >> 12),
        0x80 | ((charCode >> 6) & 0x3f),
        0x80 | (charCode & 0x3f)
      );
    } else {
      // Surrogate pair
      i++;
      charCode = 0x10000 + (((charCode & 0x3ff) << 10) | (message.charCodeAt(i) & 0x3ff));
      bytes.push(
        0xf0 | (charCode >> 18),
        0x80 | ((charCode >> 12) & 0x3f),
        0x80 | ((charCode >> 6) & 0x3f),
        0x80 | (charCode & 0x3f)
      );
    }
  }

  // Initial hash values (FIPS 180-4 section 5.3.3)
  const H = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
  ];

  // Round constants (FIPS 180-4 section 4.2.2)
  const K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ];

  const bitLength = bytes.length * 8;
  bytes.push(0x80);
  while ((bytes.length % 64) !== 56) {
    bytes.push(0);
  }

  // 64-bit length big-endian
  bytes.push(0, 0, 0, 0); // High 32 bits
  bytes.push(
    (bitLength >>> 24) & 0xff,
    (bitLength >>> 16) & 0xff,
    (bitLength >>> 8) & 0xff,
    bitLength & 0xff
  );

  const W = new Int32Array(64);
  const rotr = (n: number, x: number) => (x >>> n) | (x << (32 - n));

  for (let chunk = 0; chunk < bytes.length; chunk += 64) {
    for (let t = 0; t < 16; t++) {
      const idx = chunk + t * 4;
      W[t] = (bytes[idx] << 24) | (bytes[idx + 1] << 16) | (bytes[idx + 2] << 8) | bytes[idx + 3];
    }
    for (let t = 16; t < 64; t++) {
      const s0 = rotr(7, W[t - 15]) ^ rotr(18, W[t - 15]) ^ (W[t - 15] >>> 3);
      const s1 = rotr(17, W[t - 2]) ^ rotr(19, W[t - 2]) ^ (W[t - 2] >>> 10);
      W[t] = (W[t - 16] + s0 + W[t - 7] + s1) | 0;
    }

    let a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];

    for (let t = 0; t < 64; t++) {
      const S1 = rotr(6, e) ^ rotr(11, e) ^ rotr(25, e);
      const ch = (e & f) ^ (~e & g);
      const temp1 = (h + S1 + ch + K[t] + W[t]) | 0;
      const S0 = rotr(2, a) ^ rotr(13, a) ^ rotr(22, a);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (S0 + maj) | 0;

      h = g;
      g = f;
      f = e;
      e = (d + temp1) | 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) | 0;
    }

    H[0] = (H[0] + a) | 0;
    H[1] = (H[1] + b) | 0;
    H[2] = (H[2] + c) | 0;
    H[3] = (H[3] + d) | 0;
    H[4] = (H[4] + e) | 0;
    H[5] = (H[5] + f) | 0;
    H[6] = (H[6] + g) | 0;
    H[7] = (H[7] + h) | 0;
  }

  return H.map(val => (val >>> 0).toString(16).padStart(8, '0')).join('');
}

/**
 * Deterministic Canonical JSON Serialization.
 * 
 * Rules:
 * 1. Object keys are recursively sorted at all nesting levels.
 * 2. Explicit null is preserved.
 * 3. Arrays preserve exact element order; sparse arrays are rejected.
 * 4. Strings are strictly JSON-encoded.
 * 5. Numbers must be finite. NaN and Infinity throw CanonicalizationError.
 * 6. BigInt, undefined, functions, symbols, non-plain object instances, and cyclic structures throw CanonicalizationError.
 */
export function canonicalizeValue(val: unknown, seen = new WeakSet<object>()): string {
  if (val === null) return 'null';
  if (val === undefined) {
    throw new CanonicalizationError('undefined values are not permitted in canonical payloads');
  }
  if (typeof val === 'bigint') {
    throw new CanonicalizationError('BigInt values are not permitted in canonical payloads');
  }
  if (typeof val === 'number') {
    if (!Number.isFinite(val)) {
      throw new CanonicalizationError(`Non-finite number '${val}' cannot be canonicalized`);
    }
    return JSON.stringify(val);
  }
  if (typeof val === 'boolean' || typeof val === 'string') {
    return JSON.stringify(val);
  }
  if (typeof val === 'symbol' || typeof val === 'function') {
    throw new CanonicalizationError(`Type '${typeof val}' is not permitted in canonical payloads`);
  }
  if (typeof val === 'object') {
    if (seen.has(val)) {
      throw new CanonicalizationError('Cyclic object structure detected');
    }
    seen.add(val);

    if (Array.isArray(val)) {
      // Deterministically reject sparse arrays (SC-02)
      if (Object.keys(val).length !== val.length) {
        throw new CanonicalizationError('Sparse arrays are not permitted in canonical payloads');
      }
      const items = val.map(item => canonicalizeValue(item, seen));
      seen.delete(val);
      return `[${items.join(',')}]`;
    }

    // Deterministically reject non-plain object instances (Date, RegExp, Map, Set, custom classes)
    const proto = Object.getPrototypeOf(val);
    if (proto !== null && proto !== Object.prototype) {
      const className = (val as { constructor?: { name?: string } }).constructor?.name || typeof val;
      throw new CanonicalizationError(`Non-plain object '${className}' is not permitted in canonical payloads`);
    }

    const keys = Object.keys(val as Record<string, unknown>).sort();
    const parts = keys.map(key => {
      const memberVal = (val as Record<string, unknown>)[key];
      if (memberVal === undefined) {
        throw new CanonicalizationError(`Key '${key}' has undefined value`);
      }
      return `${JSON.stringify(key)}:${canonicalizeValue(memberVal, seen)}`;
    });
    seen.delete(val);
    return `{${parts.join(',')}}`;
  }
  throw new CanonicalizationError(`Unsupported value type: ${typeof val}`);
}

let intentCounter = 0;

/**
 * Generates a globally unique Logical Intent ID for a newly initiated operator command.
 * Distinct commands MUST receive distinct intentIds, even if payload/action are identical.
 */
export function createLogicalIntentId(operatorId: string, actionType: string): string {
  intentCounter = (intentCounter + 1) % 1000000;
  const rand = Math.floor(Math.random() * 1000000).toString(36);
  const time = Date.now().toString(36);
  return `intent_${actionType.toLowerCase()}_${operatorId}_${time}_${rand}_${intentCounter}`;
}

/**
 * Computes a deterministic SHA-256 canonical payload fingerprint.
 */
export function computePayloadFingerprint(
  operatorId: string,
  targetPositionId: string,
  symbol: string,
  actionType: 'CLOSE' | 'TIGHTEN_STOP' | 'MOVE_TO_BREAKEVEN' | 'KILL_SWITCH',
  parameters: Record<string, unknown> = {}
): string {
  const normalizedEnvelope = {
    actionType,
    operatorId,
    parameters,
    symbol,
    targetPositionId
  };
  const canonicalString = canonicalizeValue(normalizedEnvelope);
  return sha256Hex(canonicalString);
}

/**
 * Creates an IntentFingerprint adhering to FRACTAL-FLOW safety invariants.
 * 
 * Invariants:
 * 1. A new operator action MUST generate a new logical intentId.
 * 2. Retries of an existing intent MUST supply the existing intentId to preserve idempotency identity.
 * 3. Payload fingerprinting is deterministic SHA-256 over recursively sorted canonical parameters.
 * 4. Idempotency key explicitly binds intentId (SC-01) so distinct actions with identical payloads never collide.
 * 5. NOTICE: Client-side fingerprinting is NOT authoritative server deduplication.
 *    Authoritative deduplication requires backend Control Service persistence.
 */
export function createIntentFingerprint(
  operatorId: string,
  targetPositionId: string,
  symbol: string,
  actionType: 'CLOSE' | 'TIGHTEN_STOP' | 'MOVE_TO_BREAKEVEN' | 'KILL_SWITCH',
  parameters: Record<string, unknown> = {},
  existingIntentId?: string,
  transportAttempt = 1
): IntentFingerprint {
  const payloadFingerprint = computePayloadFingerprint(
    operatorId,
    targetPositionId,
    symbol,
    actionType,
    parameters
  );

  const intentId = existingIntentId || createLogicalIntentId(operatorId, actionType);
  // SC-01: Idempotency key binds intentId to guarantee uniqueness across distinct actions
  const idempotencyKey = `idemp_${actionType.toLowerCase()}_${intentId}_${payloadFingerprint.slice(0, 24)}`;

  return {
    intentId,
    operatorId,
    targetPositionId,
    symbol,
    actionType,
    parameters,
    idempotencyKey,
    createdAt: Date.now(),
    payloadFingerprint,
    transportAttempt
  };
}

// Backward-compatible alias for existing imports
export const generateIntentFingerprint = createIntentFingerprint;
export const createDeterministicHash = sha256Hex;
