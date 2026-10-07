# FRACTAL-FLOW Phase 6 — Pre-Commit / Pre-Push Gate

Run from:

```bash
cd /home/kiyingijmc/projects/FractalFlow
```

## 1. Inspect repository state

```bash
git status --short
git --no-pager diff --stat
git --no-pager diff --check
```

`git diff --check` must produce no output.

## 2. Review production changes

```bash
git --no-pager diff --   mql5/Phase6Bridge/FractalFlowBridge/FractalFlowBridgeEA.mq5   mql5/Phase6Bridge/FractalFlowBridge/Include/FFBP_Crypto.mqh
```

## 3. Verify canonical crypto source

```bash
sha256sum   mql5/Phase6Bridge/FractalFlowBridge/Include/FFBP_Crypto.mqh
```

Expected canonical crypto SHA-256:

```text
de6bfe36a13280f492936b141845f396c00ba1b472fa555a318da148895994f5
```

## 4. Run Python verification

```bash
python -m pytest -q -o addopts=   tests/test_ffbp_protocol.py   tests/test_ffbp_session.py   tests/test_ffbp_interop_vector.py   tests/test_command_ledger.py   tests/test_broker_truth.py   tests/test_protective_authority.py   tests/test_ffbp_mt5_smoke_server.py
```

Previously observed baseline:

```text
23 passed in 12.78s
```

A fresh run is required for final closure.

Then:

```bash
python -m compileall -q src tools tests
```

## 5. Live MT5 evidence

Confirm the evidence package contains:

- RFC crypto self-test GREEN output;
- live EA session smoke output;
- Python `FFBP_SMOKE_PASS`.

## 6. HPL

Update the canonical Phase 6 HPL only after reconciling every claim against direct evidence.

## 7. Commit discipline

Do not commit secrets, private credentials, or transient runtime material.

Do not claim Phase 6 fully closed solely from the smoke test.

The milestone is the successful live cryptographic interoperability/session gate; full closure requires the remaining repository-level checks to be green or explicitly recorded as environmental exceptions.
