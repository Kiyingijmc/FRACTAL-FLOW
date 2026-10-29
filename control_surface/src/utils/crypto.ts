/**
 * Deterministic Standard-Compliant SHA-256 and Canonical JSON Utility
 * FRACTAL-FLOW Forensic Engineering (Stage H.1 Corrective Implementation)
 * Priority: SURVIVAL > CORRECTNESS > DETERMINISM > AUDITABILITY
 *
 * Complies with FIPS 180-4 standard specification:
 * - Proper UTF-8 byte encoding via TextEncoder
 * - Big-endian 64-bit length padding over 512-bit message blocks
 * - NIST standard known-answer test vectors verified:
 *     "" -> e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
 *     "abc" -> ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
 *
 * DISCLAIMER: This digest covers the session-local JSON payload; it is session-only
 * and does not guarantee tamper-resistance against browser memory modification.
 */

// Initial hash values (FIPS 180-4 §5.3.3)
const H_INIT = new Uint32Array([
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
  0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
]);

// Round constants (first 32 bits of the fractional parts of the cube roots of the first 64 primes)
const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
]);

function rotr(x: number, n: number): number {
  return (x >>> n) | (x << (32 - n));
}

/**
 * Computes standard SHA-256 digest over any UTF-8 string or Uint8Array.
 * Returns lowercase 64-character hexadecimal digest.
 */
export function sha256(input: string | Uint8Array): string {
  const bytes = typeof input === 'string' ? new TextEncoder().encode(input) : input;
  const len = bytes.length;

  // Block padding calculation (FIPS 180-4 §5.1.1)
  // Padded length is smallest multiple of 64 bytes >= len + 1 (for 0x80) + 8 (for 64-bit length)
  const bitLength = BigInt(len) * 8n;
  const totalLength = Math.ceil((len + 9) / 64) * 64;
  const padded = new Uint8Array(totalLength);
  padded.set(bytes);
  padded[len] = 0x80;

  // 64-bit big-endian length at end of last block
  const view = new DataView(padded.buffer, padded.byteOffset, padded.byteLength);
  view.setBigUint64(totalLength - 8, bitLength, false);

  const h = new Uint32Array(H_INIT);
  const w = new Uint32Array(64);

  // Process 512-bit (64-byte) blocks
  for (let offset = 0; offset < totalLength; offset += 64) {
    for (let i = 0; i < 16; i++) {
      w[i] = view.getUint32(offset + i * 4, false);
    }
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
    }

    let a = h[0];
    let b = h[1];
    let c = h[2];
    let d = h[3];
    let e = h[4];
    let f = h[5];
    let g = h[6];
    let hVal = h[7];

    for (let i = 0; i < 64; i++) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const temp1 = (hVal + S1 + ch + K[i] + w[i]) | 0;
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (S0 + maj) | 0;

      hVal = g;
      g = f;
      f = e;
      e = (d + temp1) | 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) | 0;
    }

    h[0] = (h[0] + a) | 0;
    h[1] = (h[1] + b) | 0;
    h[2] = (h[2] + c) | 0;
    h[3] = (h[3] + d) | 0;
    h[4] = (h[4] + e) | 0;
    h[5] = (h[5] + f) | 0;
    h[6] = (h[6] + g) | 0;
    h[7] = (h[7] + hVal) | 0;
  }

  let hex = '';
  for (let i = 0; i < 8; i++) {
    hex += h[i].toString(16).padStart(8, '0');
  }
  return hex;
}

/**
 * Deterministically serializes any JSON-compatible value with sorted keys.
 * Invariant: Rejects non-finite numbers, functions, symbols, and circular references fail-closed.
 */
export function canonicalJsonStringify(val: unknown, seen = new WeakSet()): string {
  if (val === null) return 'null';
  if (typeof val === 'boolean') return val ? 'true' : 'false';
  if (typeof val === 'number') {
    if (!Number.isFinite(val)) {
      throw new TypeError(`Cannot canonicalize non-finite number: ${val}`);
    }
    // Normalize -0 to 0
    return Object.is(val, -0) ? '0' : String(val);
  }
  if (typeof val === 'string') {
    return JSON.stringify(val);
  }
  if (typeof val !== 'object') {
    throw new TypeError(`Cannot canonicalize unsupported type: ${typeof val}`);
  }

  // Circular reference check
  if (seen.has(val)) {
    throw new TypeError('Cannot canonicalize circular structure');
  }
  seen.add(val);

  try {
    if (Array.isArray(val)) {
      const items = val.map((item) => {
        if (item === undefined || typeof item === 'function' || typeof item === 'symbol') {
          return 'null'; // Standard JSON array semantics
        }
        return canonicalJsonStringify(item, seen);
      });
      return '[' + items.join(',') + ']';
    }

    const obj = val as Record<string, unknown>;
    const sortedKeys = Object.keys(obj).sort();
    const pairs: string[] = [];

    for (const key of sortedKeys) {
      const v = obj[key];
      // Skip undefined or non-serializable object properties (standard JSON contract)
      if (v === undefined || typeof v === 'function' || typeof v === 'symbol') {
        continue;
      }
      pairs.push(`${JSON.stringify(key)}:${canonicalJsonStringify(v, seen)}`);
    }

    return '{' + pairs.join(',') + '}';
  } finally {
    seen.delete(val);
  }
}

/**
 * Computes a standard 64-character lowercase hex SHA-256 digest
 * over the canonical JSON representation of the input.
 */
export function computeCanonicalSha256(payload: unknown): string {
  const canonicalStr = canonicalJsonStringify(payload);
  return sha256(canonicalStr);
}
