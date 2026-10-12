"""Read-only reference oracle for FFBP incremental RX contract.

This does NOT execute MQL5. It defines expected behavior for candidate review.
"""
from __future__ import annotations
import json, struct
from dataclasses import dataclass, field

MAX_FRAME = 65_536
DEADLINE_MS = 2_000

@dataclass
class RxOracle:
    buf: bytearray = field(default_factory=bytearray)
    started_ms: int | None = None
    quarantined: bool = False

    def feed(self, chunk: bytes, now_ms: int) -> list[bytes]:
        if self.quarantined:
            raise RuntimeError('already quarantined')
        if chunk:
            if not self.buf:
                self.started_ms = now_ms
            self.buf.extend(chunk)
        if self.buf and self.started_ms is not None and now_ms - self.started_ms > DEADLINE_MS:
            self.quarantined = True
            raise ValueError('assembly_timeout')
        frames = []
        while len(self.buf) >= 4:
            n = struct.unpack('>I', self.buf[:4])[0]
            if n == 0 or n > MAX_FRAME:
                self.quarantined = True
                raise ValueError('invalid_length')
            if len(self.buf) < n + 4:
                break
            body = bytes(self.buf[4:n+4])
            try:
                body.decode('utf-8', errors='strict')
                json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.quarantined = True
                raise ValueError('invalid_utf8_or_json')
            frames.append(body)
            del self.buf[:n+4]
            self.started_ms = now_ms if self.buf else None
        if len(self.buf) > MAX_FRAME + 4:
            self.quarantined = True
            raise ValueError('buffer_limit')
        return frames

    def peer_closed(self):
        if self.buf:
            self.quarantined = True
            raise ValueError('peer_closed_mid_frame')
        return 'clean_close'

def frame(body: bytes) -> bytes:
    return struct.pack('>I', len(body)) + body

def run():
    body1 = b'{"seq":1,"type":"CHALLENGE"}'
    body2 = b'{"seq":2,"type":"SESSION_ESTABLISHED"}'
    # One byte at a time, including fragmented prefix and body.
    rx = RxOracle(); out=[]
    for i, b in enumerate(frame(body1)):
        out += rx.feed(bytes([b]), i)
    assert out == [body1] and not rx.buf
    # Coalesced frames and trailing partial prefix/body.
    rx = RxOracle(); wire=frame(body1)+frame(body2)
    assert rx.feed(wire, 10) == [body1, body2]
    rx = RxOracle(); assert rx.feed(frame(body1)+frame(body2)[:2], 10) == [body1]
    assert bytes(rx.buf) == frame(body2)[:2]
    assert rx.feed(frame(body2)[2:], 20) == [body2]
    # Incomplete frame deadline and partial disconnect are terminal.
    rx = RxOracle(); rx.feed(frame(body1)[:3], 0)
    try: rx.feed(b'', DEADLINE_MS+1)
    except ValueError as e: assert str(e) == 'assembly_timeout'
    else: raise AssertionError('deadline not enforced')
    rx = RxOracle(); rx.feed(frame(body1)[:2], 0)
    try: rx.peer_closed()
    except ValueError as e: assert str(e) == 'peer_closed_mid_frame'
    else: raise AssertionError('partial close not rejected')
    # Invalid lengths, invalid UTF-8 and invalid JSON are rejected.
    for wire, expected in [(struct.pack('>I',0), 'invalid_length'),
                           (struct.pack('>I',MAX_FRAME+1), 'invalid_length'),
                           (frame(b'{\xff}'), 'invalid_utf8_or_json'),
                           (frame(b'{not-json}'), 'invalid_utf8_or_json')]:
        rx=RxOracle()
        try: rx.feed(wire, 0)
        except ValueError as e: assert str(e) == expected
        else: raise AssertionError(f'{expected} not rejected')
    print('RX_ORACLE_PASS cases=8 fragmented_header_body,coalesced_frames,trailing_partial,deadline,partial_close,zero_length,oversize,invalid_utf8_json')

if __name__ == '__main__': run()
