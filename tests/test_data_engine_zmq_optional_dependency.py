"""Fail-closed contract for unavailable optional transport dependencies."""
from __future__ import annotations

import importlib.util

import pytest

from src.fractal_flow.data_engine.zmq_protobuf_transport import (
    ProtobufJournalEnvelopeCodec,
    ZmqProtobufTransportError,
)


@pytest.mark.skipif(
    importlib.util.find_spec("zmq") is not None and importlib.util.find_spec("google.protobuf") is not None,
    reason="the missing-optional-dependency path is not active",
)
def test_optional_transport_dependencies_fail_closed_when_unavailable() -> None:
    with pytest.raises(ZmqProtobufTransportError, match="optional dependencies are unavailable"):
        ProtobufJournalEnvelopeCodec.decode(b"")
