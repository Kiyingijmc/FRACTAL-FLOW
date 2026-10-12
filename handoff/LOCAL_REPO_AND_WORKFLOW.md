# Local Repository / Workflow Notes — Phase 6

## Active WSL working directory

`/home/kiyingijmc/projects/phase6-work`

## Windows download/source location

`C:\Users\danie\Downloads\FRACTAL-FLOW-PHASE6-LOCAL-WSL-MT5-SESSION-GATE-20261007.zip`

## Important

The handoff ZIP is a forensic development snapshot. It is not evidence that the WSL working directory contains a Git repository or that Git provenance is available in the package. If Git metadata is absent, classify Git provenance as `UNVERIFIED / ENVIRONMENTAL EXCEPTION`, not as passed.

## Normal Python verification

```bash
cd /home/kiyingijmc/projects/phase6-work
python -m pytest -q -o addopts= tests/test_ffbp_protocol.py tests/test_ffbp_session.py tests/test_ffbp_interop_vector.py tests/test_command_ledger.py tests/test_broker_truth.py tests/test_protective_authority.py tests/test_ffbp_mt5_smoke_server.py
python -m compileall -q src tests tools
```

## Runtime bridge

Python smoke server:

`tools/ffbp_mt5_session_smoke_server.py`

Listener:

`0.0.0.0:39001`

MT5 input:

`InpBridgeHost=127.0.0.1`
`InpBridgePort=39001`
`InpAllowReal=false`

## MT5 files

Primary EA:

`mql5/Phase6Bridge/FractalFlowBridge/FractalFlowBridgeEA.mq5`

Crypto:

`mql5/Phase6Bridge/FractalFlowBridge/Include/FFBP_Crypto.mqh`

Session self-test:

`mql5/Phase6Bridge/FractalFlowBridgeTests/FFBP_SessionSelfTest.mq5`

Socket connectivity probe:

`mql5/Phase6Bridge/FractalFlowBridgeTests/FFBP_SocketSelfTest.mq5`

## Safe development sequence

1. Python unit/protocol tests.
2. Raw wire diagnosis.
3. Minimal framing fix.
4. Cross-language HELLO.
5. Challenge/AUTH.
6. Session establishment.
7. Reconciliation/observation.
8. Protective authority.
9. Recovery/adversarial.
10. Only after explicit gate closure, review effectful execution.

Never skip a prerequisite gate.
