# FRACTAL FLOW — PHASE 1G EVIDENCE REPORT

**Phase**: 1G — Snapshot, Journal, and Recovery Equivalence
**Status**: COMPLETE

---

## 1. Test Commands & Exit Statuses

| Command | Exit Code | Test Count | Status / Notes |
| :--- | :--- | :--- | :--- |
| `poetry run pytest --no-cov -q tests/phase1g` | 0 | 6 | All Phase 1G persistence recovery tests passed |
| `poetry run pytest --no-cov -q tests/phase1g/test_crash_points.py` | 0 | 1 | Crash point matrix test passed |
| `poetry run pytest --no-cov -q tests/phase1g/test_snapshot_journal_recovery.py` | 0 | 1 | Continuous vs recovered equivalence test passed |
| `poetry run pytest --no-cov -q tests/phase1g/test_concurrency_boundaries.py` | 0 | 4 | Version races & idempotency tests passed |
| `poetry run pytest` | 0 | 338 | Full test suite passed (Coverage: 87.92%, exceeds 85% requirement) |

---

## 2. Artifact Paths

- **Implementation**:
  - `src/fractal_flow/persistence/journal.py` — `DurableEventJournal`
  - `src/fractal_flow/persistence/snapshot.py` — `SnapshotEngine`
  - `src/fractal_flow/persistence/adapter.py` — Canonical serialization & fingerprinting
- **Test Suite**:
  - `tests/phase1g/test_crash_points.py`
  - `tests/phase1g/test_snapshot_journal_recovery.py`
  - `tests/phase1g/test_concurrency_boundaries.py`
- **Evidence Record**:
  - `artifacts/phase1/phase1g_evidence.md`

---

## 3. Crash Point Matrix

| Crash Point | Scenario | Data Quality | Volatility | Structure | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Crash before state transition | Reverts to prior state | Reverts to prior state | Reverts to prior state | PASS |
| 2 | Crash after state transition | Rebuilt from journal | Rebuilt from journal | Rebuilt from journal | PASS |
| 3 | Crash after event append | Reconstructed from event | Reconstructed from event | Reconstructed from event | PASS |
| 4 | Crash before snapshot | Replays journal from genesis | Replays journal from genesis | Replays journal from genesis | PASS |
| 5 | Crash after snapshot | Restores snapshot + tail | Restores snapshot + tail | Restores snapshot + tail | PASS |
| 6 | Restart from snapshot | Loads snapshot payload | Loads snapshot payload | Loads snapshot payload | PASS |
| 7 | Replay journal tail | Applies tail events | Applies tail events | Applies tail events | PASS |
| 8 | Continuous vs Recovered Equivalence | `continuous == recovered` | `continuous == recovered` | `continuous == recovered` | PASS |

---

## 4. Race & Concurrency Boundary Matrix

| Boundary | Interleaving / Failure Mode | Protection Mechanism | Test Function | Status |
| :--- | :--- | :--- | :--- | :--- |
| Parent Version Race | Parent version regression ($v_{in} < v_{active}$) | Rejects regression; fails closed | `test_parent_version_race_rejection` | PASS |
| Data Version Race | Stale data version ($v_{in} < v_{active}$) | Rejects stale feature; fails closed | `test_data_version_race_and_stale_feature_rejection` | PASS |
| Configuration Race | Config version mismatch ($v_{in} \neq v_{active}$) | Rejects mismatched configuration | `test_configuration_version_mismatch_rejection` | PASS |
| Snapshot/Journal Race | Snapshot sequence ahead of journal head | Fails closed; falls back to genesis | Covered in `tests/test_persistence_adversarial.py` | PASS |
| Duplicate Event Race | Duplicate aggregate version append | Rejects duplicate; `InvalidEventVersionException` | `test_duplicate_event_race_idempotency` | PASS |
