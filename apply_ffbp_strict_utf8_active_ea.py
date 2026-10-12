#!/usr/bin/env python3
"""Backup-first, exact-baseline strict UTF-8 patch for FRACTAL-FLOW active EA.

Run from the WSL repo root:
  python /mnt/data/apply_ffbp_strict_utf8_active_ea.py

The script refuses to modify anything unless the active EA SHA-256 matches the
forensic baseline recorded for this remediation and required anchors/defaults
are unique and intact. It creates a timestamped sibling backup before writing.
"""
from __future__ import annotations
import difflib
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_SHA256 = "3794e2223f35d566d2e89c194453f1503f4bfe69153c311afdc782e143c9e7b4"
RELATIVE_TARGET = Path("mql5/Phase6Bridge/FractalFlowBridge/FractalFlowBridgeEA.mq5")

VALIDATOR = r'''// Strict RFC 3629 UTF-8 validation over the length-delimited wire bytes.
// Rejects overlong encodings, surrogate code points, values above U+10FFFF,
// stray continuation bytes, and truncated multibyte sequences before decoding.
bool FFBP_IsValidUtf8(const uchar &bytes[],const int offset,const int count)
{
   if(offset<0 || count<0 || offset+count>ArraySize(bytes))
      return false;

   int i=offset;
   int end=offset+count;
   while(i<end)
   {
      uint c=(uint)bytes[i++];
      if(c<=0x7F)
         continue;

      if(c>=0xC2 && c<=0xDF)
      {
         if(i>=end) return false;
         uint c1=(uint)bytes[i++];
         if(c1<0x80 || c1>0xBF) return false;
         continue;
      }

      if(c>=0xE0 && c<=0xEF)
      {
         if(i+1>=end) return false;
         uint c1=(uint)bytes[i++];
         uint c2=(uint)bytes[i++];
         if(c2<0x80 || c2>0xBF) return false;
         if(c==0xE0)
         { if(c1<0xA0 || c1>0xBF) return false; }
         else if(c==0xED)
         { if(c1<0x80 || c1>0x9F) return false; }
         else if(c1<0x80 || c1>0xBF) return false;
         continue;
      }

      if(c>=0xF0 && c<=0xF4)
      {
         if(i+2>=end) return false;
         uint c1=(uint)bytes[i++];
         uint c2=(uint)bytes[i++];
         uint c3=(uint)bytes[i++];
         if(c2<0x80 || c2>0xBF || c3<0x80 || c3>0xBF) return false;
         if(c==0xF0)
         { if(c1<0x90 || c1>0xBF) return false; }
         else if(c==0xF4)
         { if(c1<0x80 || c1>0x8F) return false; }
         else if(c1<0x80 || c1>0xBF) return false;
         continue;
      }

      return false;
   }
   return true;
}
'''

FUNCTION_ANCHOR = '''uint ReadBE32(const uchar &b[],const int offset)
{
   return ((uint)b[offset]<<24)|
          ((uint)b[offset+1]<<16)|
          ((uint)b[offset+2]<<8)|
          (uint)b[offset+3];
}
'''
DECODE_ANCHOR = '''   if(buffered<frame_size)
      return 0;

   body=CharArrayToString(g_rx_buffer,4,(int)len,CP_UTF8);
'''
REPLACEMENT = '''   if(buffered<frame_size)
      return 0;

   // Validate wire bytes before MQL5's decoder can normalize malformed input.
   if(!FFBP_IsValidUtf8(g_rx_buffer,4,(int)len))
      return -1;

   body=CharArrayToString(g_rx_buffer,4,(int)len,CP_UTF8);
'''

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main() -> int:
    repo = Path.cwd()
    target = repo / RELATIVE_TARGET
    if not target.is_file():
        print(f"ABORT: target not found: {target}", file=sys.stderr); return 2
    original_bytes = target.read_bytes()
    actual = sha(original_bytes)
    if actual != EXPECTED_SHA256:
        print(f"ABORT: baseline SHA-256 mismatch; expected {EXPECTED_SHA256}, got {actual}", file=sys.stderr)
        print("No files changed. Reconcile the current active source before patching.", file=sys.stderr)
        return 3
    try:
        source = original_bytes.decode("utf-8")
    except UnicodeDecodeError:
        print("ABORT: active source is not valid UTF-8 text; no files changed.", file=sys.stderr); return 4

    required_defaults = (
        'input string InpAccountId="";',
        'input string InpLaneId="";',
        'input bool   InpAllowReal=false;',
    )
    if any(source.count(x) != 1 for x in required_defaults):
        print("ABORT: expected input defaults are missing or ambiguous; no files changed.", file=sys.stderr); return 5
    if "FFBP_IsValidUtf8(" in source:
        print("ABORT: validator symbol already exists; no files changed.", file=sys.stderr); return 6
    if source.count(FUNCTION_ANCHOR) != 1:
        print("ABORT: ReadBE32 insertion anchor is not unique; no files changed.", file=sys.stderr); return 7
    if source.count(DECODE_ANCHOR) != 1:
        print("ABORT: frame/decode anchor is not unique; no files changed.", file=sys.stderr); return 8

    updated = source.replace(FUNCTION_ANCHOR, FUNCTION_ANCHOR + "\n" + VALIDATOR, 1)
    if updated.count(DECODE_ANCHOR) != 1:
        print("ABORT: decode anchor changed unexpectedly during preparation; no files changed.", file=sys.stderr); return 9
    updated = updated.replace(DECODE_ANCHOR, REPLACEMENT, 1)
    updated_bytes = updated.encode("utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = target.with_name(target.name + f".pre-strict-utf8-{stamp}.bak")
    if backup.exists():
        print(f"ABORT: backup already exists: {backup}; no files changed.", file=sys.stderr); return 10

    # Backup is created exclusively before target is written.
    with backup.open("xb") as f:
        f.write(original_bytes)
    try:
        target.write_bytes(updated_bytes)
    except Exception:
        target.write_bytes(original_bytes)
        print(f"WRITE FAILED: original restored from backup {backup}", file=sys.stderr)
        raise

    # Verify exactly the intended changes and preservation of safety defaults.
    verify = target.read_bytes().decode("utf-8")
    if sha(target.read_bytes()) != sha(updated_bytes) or any(verify.count(x) != 1 for x in required_defaults):
        target.write_bytes(original_bytes)
        print(f"VERIFY FAILED: original restored; backup retained at {backup}", file=sys.stderr)
        return 11
    if verify.count("bool FFBP_IsValidUtf8(") != 1 or verify.index("if(!FFBP_IsValidUtf8(g_rx_buffer,4,(int)len))") > verify.index("body=CharArrayToString(g_rx_buffer,4,(int)len,CP_UTF8);"):
        target.write_bytes(original_bytes)
        print(f"VERIFY FAILED: validator placement incorrect; original restored; backup retained at {backup}", file=sys.stderr)
        return 12

    diff = difflib.unified_diff(source.splitlines(True), updated.splitlines(True),
                                fromfile=str(target) + ".before", tofile=str(target) + ".after")
    print("PATCH_STATUS=PASS")
    print(f"TARGET={target}")
    print(f"BACKUP={backup}")
    print(f"BEFORE_SHA256={actual}")
    print(f"AFTER_SHA256={sha(updated_bytes)}")
    print("SAFETY_DEFAULTS_PRESERVED=true")
    print("VALIDATION_BEFORE_DECODE=true")
    print("DIFF_BEGIN")
    sys.stdout.writelines(diff)
    print("DIFF_END")
    print("NEXT: inspect this diff, then run focused pytest and compile this exact source in MetaEditor. No deployment was performed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
