#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python -m compileall -q src tests tools
python -m pytest -q -o addopts= \
  tests/test_ffbp_protocol.py \
  tests/test_ffbp_session.py \
  tests/test_ffbp_interop_vector.py \
  tests/test_command_ledger.py \
  tests/test_broker_truth.py \
  tests/test_protective_authority.py
python -m pytest -q -o addopts= \
  --ignore=tests/regression/test_phase5_r5_real_campaign.py \
  --ignore=tests/regression/test_phase5_state_machine_hardening.py
