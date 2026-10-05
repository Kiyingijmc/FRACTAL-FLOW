"""PGVF Command Line Interface."""

import argparse
import json
import sys
from typing import Any, Dict, List, NoReturn, Optional

from tools.pfgv.authority import AuthorityModel
from tools.pfgv.contract import PhaseContract
from tools.pfgv.errors import (
    AuthorityError,
    ContractError,
    EvidenceError,
    InvariantViolationError,
    ScopeViolationError,
    StateTransitionError,
)
from tools.pfgv.evidence import EvidenceRecord
from tools.pfgv.invariants import InvariantRegistry
from tools.pfgv.scope import ScopePolicy
from tools.pfgv.state import PhaseLifecycleState, PhaseStateMachine

EXIT_PASS = 0
EXIT_VALIDATION_FAILURE = 1
EXIT_GOVERNANCE_BLOCK = 2
EXIT_INVALID_INPUT = 3
EXIT_INTERNAL_ERROR = 4


def _respond(result: str, message: str, code: int, json_mode: bool, extra: Optional[Dict[str, Any]] = None) -> NoReturn:
    payload: Dict[str, Any] = {
        "result": result,
        "message": message,
        "exit_code": code,
    }
    if extra:
        payload.update(extra)

    if json_mode:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        status_symbol = "PASS" if code == 0 else "FAIL"
        print(f"[{status_symbol}] {message}")
        if extra:
            for k, v in extra.items():
                print(f"  {k}: {v}")

    sys.exit(code)


def validate_contract_cmd(args: argparse.Namespace) -> None:
    json_mode = getattr(args, "json", False)
    try:
        contract = PhaseContract.from_file(args.contract)
        _respond(
            "PASS",
            f"Contract '{contract.phase_id}' validated successfully",
            EXIT_PASS,
            json_mode,
            {"phase_id": contract.phase_id, "contract_hash": contract.compute_hash()},
        )
    except ContractError as e:
        _respond("VALIDATION_FAILURE", str(e), EXIT_VALIDATION_FAILURE, json_mode)
    except Exception as e:
        _respond("INTERNAL_ERROR", f"Unexpected error: {e}", EXIT_INTERNAL_ERROR, json_mode)


def validate_invariants_cmd(args: argparse.Namespace) -> None:
    json_mode = getattr(args, "json", False)
    try:
        registry = InvariantRegistry.from_file(args.registry)
        _respond(
            "PASS",
            f"Invariant registry validated successfully ({len(registry.invariants)} invariants)",
            EXIT_PASS,
            json_mode,
            {"invariant_count": len(registry.invariants), "registry_hash": registry.compute_hash()},
        )
    except InvariantViolationError as e:
        _respond("VALIDATION_FAILURE", str(e), EXIT_VALIDATION_FAILURE, json_mode)
    except Exception as e:
        _respond("INTERNAL_ERROR", f"Unexpected error: {e}", EXIT_INTERNAL_ERROR, json_mode)


def validate_scope_cmd(args: argparse.Namespace) -> None:
    json_mode = getattr(args, "json", False)
    try:
        policy = ScopePolicy.from_file(args.policy)
        changed_files = args.changed_files or []
        deleted_files = args.deleted_files or []
        policy.validate_changes(changed_files=changed_files, deleted_files=deleted_files)
        _respond(
            "PASS",
            "Scope policy validation passed",
            EXIT_PASS,
            json_mode,
            {"changed_files_count": len(changed_files), "policy_hash": policy.compute_hash()},
        )
    except ScopeViolationError as e:
        _respond("GOVERNANCE_BLOCK", str(e), EXIT_GOVERNANCE_BLOCK, json_mode)
    except Exception as e:
        _respond("INTERNAL_ERROR", f"Unexpected error: {e}", EXIT_INTERNAL_ERROR, json_mode)


def validate_authority_cmd(args: argparse.Namespace) -> None:
    json_mode = getattr(args, "json", False)
    try:
        model = AuthorityModel.from_file(args.model)
        if getattr(args, "before", None) and getattr(args, "after", None):
            before = AuthorityModel.from_file(args.before)
            after = AuthorityModel.from_file(args.after)
            delta = before.compute_delta(after)
            _respond(
                "PASS",
                "Authority model comparison completed",
                EXIT_PASS,
                json_mode,
                {"has_changes": delta.has_changes, "added": delta.added, "removed": delta.removed},
            )
        else:
            _respond(
                "PASS",
                "Authority model validated successfully",
                EXIT_PASS,
                json_mode,
                {"model_hash": model.compute_hash()},
            )
    except AuthorityError as e:
        _respond("GOVERNANCE_BLOCK", str(e), EXIT_GOVERNANCE_BLOCK, json_mode)
    except Exception as e:
        _respond("INTERNAL_ERROR", f"Unexpected error: {e}", EXIT_INTERNAL_ERROR, json_mode)


def validate_evidence_cmd(args: argparse.Namespace) -> None:
    json_mode = getattr(args, "json", False)
    try:
        evidence = EvidenceRecord.from_file(args.evidence)
        expected_commit = getattr(args, "expected_commit", None)
        expected_tree = getattr(args, "expected_tree", None)
        evidence.verify_provenance(expected_commit=expected_commit, expected_tree=expected_tree)
        _respond(
            "PASS",
            f"Evidence record '{evidence.evidence_id}' validated successfully",
            EXIT_PASS,
            json_mode,
            {"evidence_id": evidence.evidence_id, "verification_level": evidence.verification_level.name},
        )
    except EvidenceError as e:
        _respond("VALIDATION_FAILURE", str(e), EXIT_VALIDATION_FAILURE, json_mode)
    except Exception as e:
        _respond("INTERNAL_ERROR", f"Unexpected error: {e}", EXIT_INTERNAL_ERROR, json_mode)


def state_cmd(args: argparse.Namespace) -> None:
    json_mode = getattr(args, "json", False)
    try:
        raw_state = args.current_state.upper()
        current_enum = PhaseLifecycleState[raw_state]
        sm = PhaseStateMachine(initial_state=current_enum)

        if args.transition:
            target_enum = PhaseLifecycleState[args.transition.upper()]
            sm.transition_to(target_enum)
            _respond(
                "PASS",
                f"State transitioned from {current_enum.name} to {sm.current_state.name}",
                EXIT_PASS,
                json_mode,
                {"previous_state": current_enum.name, "current_state": sm.current_state.name},
            )
        else:
            _respond(
                "PASS",
                f"Current state is {sm.current_state.name}",
                EXIT_PASS,
                json_mode,
                {"current_state": sm.current_state.name},
            )
    except KeyError as e:
        _respond("INVALID_INPUT", f"Unknown state: {e}", EXIT_INVALID_INPUT, json_mode)
    except StateTransitionError as e:
        _respond("GOVERNANCE_BLOCK", str(e), EXIT_GOVERNANCE_BLOCK, json_mode)
    except Exception as e:
        _respond("INTERNAL_ERROR", f"Unexpected error: {e}", EXIT_INTERNAL_ERROR, json_mode)


def build_parser() -> argparse.ArgumentParser:
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")

    parser = argparse.ArgumentParser(
        prog="pfgv", description="PGVF Phase Governance & Verification CLI", parents=[parent_parser]
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate-contract
    p_contract = subparsers.add_parser("validate-contract", help="Validate a Phase Contract", parents=[parent_parser])
    p_contract.add_argument("contract", type=str, help="Path to contract file")

    # validate-invariants
    p_inv = subparsers.add_parser("validate-invariants", help="Validate an Invariant Registry", parents=[parent_parser])
    p_inv.add_argument("registry", type=str, help="Path to invariant registry file")

    # validate-scope
    p_scope = subparsers.add_parser(
        "validate-scope", help="Validate file changes against Scope Policy", parents=[parent_parser]
    )
    p_scope.add_argument("policy", type=str, help="Path to scope policy file")
    p_scope.add_argument("--changed-files", nargs="*", help="List of changed file paths")
    p_scope.add_argument("--deleted-files", nargs="*", help="List of deleted file paths")

    # validate-authority
    p_auth = subparsers.add_parser(
        "validate-authority", help="Validate Authority Model or Delta", parents=[parent_parser]
    )
    p_auth.add_argument("model", type=str, help="Path to authority model file")
    p_auth.add_argument("--before", type=str, help="Path to before authority model")
    p_auth.add_argument("--after", type=str, help="Path to after authority model")

    # validate-evidence
    p_ev = subparsers.add_parser("validate-evidence", help="Validate Evidence Record", parents=[parent_parser])
    p_ev.add_argument("evidence", type=str, help="Path to evidence record file")
    p_ev.add_argument("--expected-commit", type=str, help="Expected target commit SHA")
    p_ev.add_argument("--expected-tree", type=str, help="Expected target tree SHA")

    # state
    p_state = subparsers.add_parser("state", help="Inspect or transition phase state", parents=[parent_parser])
    p_state.add_argument("current_state", type=str, help="Current phase state name")
    p_state.add_argument("--transition", type=str, help="Target phase state to transition to")

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "validate-contract": validate_contract_cmd,
        "validate-invariants": validate_invariants_cmd,
        "validate-scope": validate_scope_cmd,
        "validate-authority": validate_authority_cmd,
        "validate-evidence": validate_evidence_cmd,
        "state": state_cmd,
    }

    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        _respond("INVALID_INPUT", f"Unknown command: {args.command}", EXIT_INVALID_INPUT, False)


if __name__ == "__main__":
    main()
