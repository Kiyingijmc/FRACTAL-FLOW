from pathlib import Path
import subprocess

CANDIDATE = Path('/mnt/data/ffbp_forensic_inputs/FractalFlowBridgeEA_utf8_strict_candidate.mq5')
s = CANDIDATE.read_text()
assert 'bool FFBP_IsValidUtf8(const uchar &bytes[],const int offset,const int count)' in s
assert 'if(!FFBP_IsValidUtf8(g_rx_buffer,4,(int)len))' in s
assert s.index('if(!FFBP_IsValidUtf8(g_rx_buffer,4,(int)len))') < s.index('body=CharArrayToString(g_rx_buffer,4,(int)len,CP_UTF8)')

# Byte vectors against RFC 3629 validity contract, mirrored by the MQL5 validator branches.
valid = [b'', b'{}', '"café"'.encode(), '"€"'.encode(), '"😀"'.encode(), bytes([0x7f])]
invalid = [b'\x80', b'\xc0\xaf', b'\xc1\xbf', b'\xe0\x80\x80', b'\xed\xa0\x80', b'\xf0\x80\x80\x80', b'\xf4\x90\x80\x80', b'\xf5\x80\x80\x80', b'\xe2\x82', b'\xf0\x9f\x98']
for b in valid: b.decode('utf-8', 'strict')
for b in invalid:
    try: b.decode('utf-8', 'strict')
    except UnicodeDecodeError: pass
    else: raise AssertionError(f'Python oracle accepted invalid vector {b!r}')
print(f'UTF8_VECTOR_ORACLE_PASS valid={len(valid)} invalid={len(invalid)}')
print('MQL5_STATIC_GUARD_PASS strict-validator-present-before-decode')
print('NOTE: vectors validate the contract and source placement; they do not execute MQL5.')
