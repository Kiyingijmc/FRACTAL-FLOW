/**
 * Deterministic Canonical SHA-256 Digest Utility
 * FRACTAL-FLOW Forensic Engineering
 * Priority: SURVIVAL > CORRECTNESS > DETERMINISM > AUDITABILITY
 * 
 * Used for computing reproducible digests over session-local event payloads.
 * DISCLAIMER: This digest covers the session-local JSON payload; it is session-only
 * and does not guarantee tamper-resistance against browser memory modification.
 */

function rightRotate(value: number, amount: number): number {
  return (value >>> amount) | (value << (32 - amount));
}

function sha256Bytes(ascii: string): Uint8Array {
  const mathPow = Math.pow;
  const maxWord = mathPow(2, 32);
  const words: number[] = [];
  const asciiBitLength = ascii.length * 8;

  const hash: number[] = [];
  const k: number[] = [];
  let primeCounter = 0;

  const isPrime = (n: number) => {
    for (let factor = 2; factor <= Math.sqrt(n); factor++) {
      if (n % factor === 0) return false;
    }
    return true;
  };

  for (let candidate = 2; primeCounter < 64; candidate++) {
    if (isPrime(candidate)) {
      if (primeCounter < 8) {
        hash[primeCounter] = ((mathPow(candidate, 1 / 2) * maxWord) | 0);
      }
      k[primeCounter] = ((mathPow(candidate, 1 / 3) * maxWord) | 0);
      primeCounter++;
    }
  }

  for (let i = 0; i < ascii.length; i++) {
    const j = i >> 2;
    words[j] = (words[j] || 0) | (ascii.charCodeAt(i) << ((3 - (i % 4)) * 8));
  }

  // Padding
  words[ascii.length >> 2] = (words[ascii.length >> 2] || 0) | (0x80 << ((3 - (ascii.length % 4)) * 8));
  words[(((ascii.length + 8) >> 6) << 4) + 15] = asciiBitLength;

  for (let j = 0; j < words.length; j += 16) {
    const w: number[] = [];
    for (let i = 0; i < 16; i++) {
      w[i] = words[j + i] || 0;
    }
    for (let i = 16; i < 64; i++) {
      const s0 = rightRotate(w[i - 15], 7) ^ rightRotate(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rightRotate(w[i - 2], 17) ^ rightRotate(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (((w[i - 16] + s0) | 0) + ((w[i - 7] + s1) | 0)) | 0;
    }

    let [a, b, c, d, e, f, g, h] = hash;

    for (let i = 0; i < 64; i++) {
      const s1 = rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25);
      const ch = (e & f) ^ (~e & g);
      const temp1 = ((((h + s1) | 0) + ch | 0) + ((k[i] + w[i]) | 0)) | 0;
      const s0 = rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (s0 + maj) | 0;

      h = g;
      g = f;
      f = e;
      e = (d + temp1) | 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) | 0;
    }

    hash[0] = (hash[0] + a) | 0;
    hash[1] = (hash[1] + b) | 0;
    hash[2] = (hash[2] + c) | 0;
    hash[3] = (hash[3] + d) | 0;
    hash[4] = (hash[4] + e) | 0;
    hash[5] = (hash[5] + f) | 0;
    hash[6] = (hash[6] + g) | 0;
    hash[7] = (hash[7] + h) | 0;
  }

  const result = new Uint8Array(32);
  for (let i = 0; i < 8; i++) {
    result[i * 4] = (hash[i] >>> 24) & 0xff;
    result[i * 4 + 1] = (hash[i] >>> 16) & 0xff;
    result[i * 4 + 2] = (hash[i] >>> 8) & 0xff;
    result[i * 4 + 3] = hash[i] & 0xff;
  }
  return result;
}

/**
 * Deterministically serialize any object with lexicographically sorted keys.
 */
export function canonicalJsonStringify(val: unknown): string {
  if (val === null || typeof val !== 'object') {
    return JSON.stringify(val);
  }
  if (Array.isArray(val)) {
    return '[' + val.map(canonicalJsonStringify).join(',') + ']';
  }
  const obj = val as Record<string, unknown>;
  const sortedKeys = Object.keys(obj).sort();
  const pairs = sortedKeys.map((k) => `${JSON.stringify(k)}:${canonicalJsonStringify(obj[k])}`);
  return '{' + pairs.join(',') + '}';
}

/**
 * Computes a standard 64-character lowercase hex SHA-256 digest
 * over the canonical JSON representation of the input.
 */
export function computeCanonicalSha256(payload: unknown): string {
  const canonicalStr = canonicalJsonStringify(payload);
  const bytes = sha256Bytes(canonicalStr);
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}
