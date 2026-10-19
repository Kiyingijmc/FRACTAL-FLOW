from dataclasses import dataclass, field

MAX_FRAME = 65536


def valid_utf8(data: bytes) -> bool:
    if not data:
        return False
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8", errors="strict")
        return True
    except UnicodeDecodeError:
        return False


@dataclass
class RxModel:
    max_frame: int = MAX_FRAME
    buffer: bytearray = field(default_factory=bytearray)
    started_ms: int | None = None
    quarantined: bool = False

    def feed(self, chunk: bytes, now_ms: int):
        if self.quarantined:
            return "QUARANTINED", None
        if chunk:
            if not self.buffer:
                self.started_ms = now_ms
            if len(self.buffer) + len(chunk) > self.max_frame + 4:
                self.quarantined = True
                return "RX_BUFFER_OVERFLOW", None
            self.buffer.extend(chunk)
        return self.poll(now_ms)

    def poll(self, now_ms: int):
        if len(self.buffer) >= 4:
            length = int.from_bytes(self.buffer[:4], "big")
            if length == 0:
                self.quarantined = True
                return "ZERO_FRAME_LENGTH", None
            if length > self.max_frame:
                self.quarantined = True
                return "FRAME_LENGTH_EXCEEDS_MAX", None
            if len(self.buffer) >= 4 + length:
                body = bytes(self.buffer[4:4+length])
                if not valid_utf8(body):
                    self.quarantined = True
                    return "INVALID_UTF8", None
                del self.buffer[:4+length]
                self.started_ms = now_ms if self.buffer else None
                return "FRAME", body
        if self.buffer and self.started_ms is not None and now_ms-self.started_ms > 2000:
            self.quarantined = True
            return "FRAME_ASSEMBLY_TIMEOUT", None
        return "IDLE_OR_PARTIAL", None


def frame(body: bytes) -> bytes:
    return len(body).to_bytes(4, "big") + body


def test_fragmented_header_and_body_survive_multiple_polls():
    rx = RxModel()
    wire = frame(b'{"type":"HEARTBEAT"}')
    assert rx.feed(wire[:2], 10)[0] == "IDLE_OR_PARTIAL"
    assert rx.feed(wire[2:7], 20)[0] == "IDLE_OR_PARTIAL"
    status, body = rx.feed(wire[7:], 30)
    assert (status, body) == ("FRAME", b'{"type":"HEARTBEAT"}')
    assert not rx.buffer and rx.started_ms is None


def test_coalesced_frames_are_delivered_one_at_a_time():
    rx = RxModel()
    status, first = rx.feed(frame(b"one") + frame(b"two"), 100)
    assert (status, first) == ("FRAME", b"one")
    assert rx.poll(101) == ("FRAME", b"two")
    assert not rx.buffer


def test_zero_and_oversize_lengths_quarantine():
    zero = RxModel()
    assert zero.feed((0).to_bytes(4, "big"), 0)[0] == "ZERO_FRAME_LENGTH"
    too_big = RxModel(max_frame=8)
    assert too_big.feed((9).to_bytes(4, "big"), 0)[0] == "FRAME_LENGTH_EXCEEDS_MAX"
    assert too_big.feed(frame(b"x"), 1)[0] == "QUARANTINED"


def test_invalid_utf8_and_nul_quarantine_before_decode():
    for bad in (b"\xc0\xaf", b"\xed\xa0\x80", b"\xf4\x90\x80\x80", b"\x80", b"\x00"):
        rx = RxModel()
        assert rx.feed(frame(bad), 0)[0] == "INVALID_UTF8"
        assert rx.quarantined


def test_partial_frame_deadline_quarantines_and_never_resumes():
    rx = RxModel()
    assert rx.feed(frame(b"payload")[:5], 100)[0] == "IDLE_OR_PARTIAL"
    assert rx.poll(2101)[0] == "FRAME_ASSEMBLY_TIMEOUT"
    assert rx.feed(frame(b"payload")[5:], 2102)[0] == "QUARANTINED"


def test_limit_accepts_exact_maximum_frame():
    rx = RxModel(max_frame=8)
    status, body = rx.feed(frame(b"12345678"), 0)
    assert (status, body) == ("FRAME", b"12345678")
