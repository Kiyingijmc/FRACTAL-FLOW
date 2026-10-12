# FRACTAL FLOW — PHASE 1C EVIDENCE REPORT

**Phase**: 1C — Deterministic Clock and Replay
**Status**: COMPLETE

---

## 1. Test Commands & Exit Statuses

| Command | Exit Code | Test Count | Status / Notes |
| :--- | :--- | :--- | :--- |
| `poetry run pytest --no-cov -q tests/phase1c` | 0 | 5 | All Phase 1C clock & replay tests passed |
| `poetry run pytest --no-cov -q tests/phase1c/test_clock_injection.py` | 0 | 2 | Simulation clock & wall-clock audit passed |
| `poetry run pytest --no-cov -q tests/phase1c/test_replay_determinism.py` | 0 | 2 | Deterministic event ID & replay digest passed |
| `poetry run pytest --no-cov -q tests/phase1c/test_restart_equivalence.py` | 0 | 1 | Continuous vs restart replay equivalence passed |
| `poetry run pytest` | 0 | 332 | Full test suite passed (Coverage: 87.92%, exceeds 85% requirement) |

---

## 2. Artifact Paths

- **Implementation**:
  - `src/fractal_flow/simulation/clock.py` — Injected deterministic `SimulationClock`
  - `src/fractal_flow/simulation/replay.py` — `DeterministicReplayHarness` and `generate_deterministic_event_id`
- **Test Suite**:
  - `tests/phase1c/test_clock_injection.py`
  - `tests/phase1c/test_replay_determinism.py`
  - `tests/phase1c/test_restart_equivalence.py`
- **Evidence Record**:
  - `artifacts/phase1/phase1c_evidence.md`

---

## 3. Clock Audit Output

Wall-clock calls in production code were audited using `grep -rn -E "time\.time\(|datetime\.now\(|datetime\.utcnow\(" src/`:

- **Strategy Engine Call Sites**: 0 (zero direct wall-clock calls in Flow, Structure, Volatility, Opportunity, Risk, or Entry strategy paths).
- **Approved Non-Strategy Call Sites**:
  - `src/fractal_flow/config/config.py` — SealedObservation fallback timestamp
  - `src/fractal_flow/persistence/interfaces.py` — Diagnostic observation timestamp
  - `src/fractal_flow/persistence/snapshot.py` — Snapshot observation fallback
  - `src/fractal_flow/persistence/journal.py` — Journal observation fallback
  - `src/fractal_flow/domain/risk_ledger.py` — Risk Ledger observation fallback
  - `src/fractal_flow/domain/entry.py` — Diagnostic entry timestamp fallback
  - `src/fractal_flow/execution/recovery.py` — Recovery engine observation fallback
  - `src/fractal_flow/execution/reconciliation.py` — Broker reconciliation observation fallback

---

## 4. Replay Determinism & Restart Equivalence

1. **Deterministic Identity**: `generate_deterministic_event_id` derives hex SHA-256 event keys strictly from aggregate inputs, sequence number, source timestamp, and canonical payload, eliminating random UUIDs.
2. **Replay Determinism**: Repeated identical execution of replay streams yields byte-identical event records and replay digests.
3. **Restart Equivalence**: Proved that `continuous_replay(events[0..N])` produces identical state and event records to `replay_prefix(events[0..K]) -> checkpoint -> restart -> replay_tail(events[K..N])`.
