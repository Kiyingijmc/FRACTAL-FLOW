#!/usr/bin/env python3
"""Targeted semantic mutation campaign for the Phase 4 authority kernel.

Each mutant changes one authority-bearing semantic and runs the hostile + assurance
suites. A mutant is "killed" only when the verification suite detects it.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src/fractal_flow/domain/phase4.py"
SUITES = ["tests/test_phase4_hostile_authority.py", "tests/phase4_assurance"]


@dataclass(frozen=True)
class Mutant:
    name: str
    needle: str
    replacement: str


MUTANTS = [
    Mutant(
        "opportunity_lifecycle_bypass",
        'if not opportunity.is_live(created_at, parent_opportunity):',
        'if False:',
    ),
    Mutant(
        "tradeability_status_bypass",
        'if tradeability.status != TradeabilityStatus.PASS:',
        'if False:',
    ),
    Mutant(
        "future_tradeability_bypass",
        'if tradeability.observed_timestamp > created_at:',
        'if False:',
    ),
    Mutant(
        "confidence_escalation_bypass",
        'if confidence.value > opportunity.confidence:',
        'if False:',
    ),
    Mutant(
        "mandatory_gate_set_bypass",
        'if {g.gate for g in ordered} != set(Phase4GateType):',
        'if False:',
    ),
    Mutant(
        "gate_temporal_bypass",
        'if any(g.observed_timestamp < opportunity.created_at or g.observed_timestamp > created_at for g in ordered):',
        'if False:',
    ),
    Mutant(
        "direct_authority_proof_bypass",
        'self._authority_proof is _AUTHORITY_PROOF\n            and self.decision_id',
        'True\n            and self.decision_id',
    ),
    Mutant(
        "fingerprint_integrity_bypass",
        'if self.decision_id != canonical:',
        'if False:',
    ),
]


def run(repo: Path) -> bool:
    cmd = [
        "python",
        "-m",
        "pytest",
        *SUITES,
        "--override-ini=addopts=",
        "-q",
    ]
    result = subprocess.run(cmd, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return result.returncode == 0, result.stdout


def main() -> int:
    killed = 0
    survived: list[str] = []
    invalid: list[str] = []
    for mutant in MUTANTS:
        with tempfile.TemporaryDirectory(prefix="ff-phase4-mutant-") as tmp:
            work = Path(tmp) / "repo"
            shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git", ".coverage", "__pycache__", ".pytest_cache"))
            target = work / TARGET.relative_to(ROOT)
            source = target.read_text(encoding="utf-8")
            occurrences = source.count(mutant.needle)
            if occurrences != 1:
                invalid.append(mutant.name)
                continue
            target.write_text(source.replace(mutant.needle, mutant.replacement, 1), encoding="utf-8")
            ok, output = run(work)
            if ok:
                survived.append(mutant.name)
                print(f"SURVIVED {mutant.name}\n{output}")
            else:
                killed += 1
                print(f"KILLED {mutant.name}")
    total = len(MUTANTS)
    print(f"MUTATION_SUMMARY killed={killed} survived={len(survived)} invalid={len(invalid)} total={total}")
    if survived or invalid:
        print(f"SURVIVED_MUTANTS={survived}")
        print(f"INVALID_MUTANTS={invalid}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
