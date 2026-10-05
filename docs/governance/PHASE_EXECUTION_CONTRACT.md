# PGVF Phase Execution Contract Specification

PGVF (Phase Governance & Verification Fabric) is an AI-tool-agnostic governance and verification system designed to govern work performed by Jules, Claude Code, Codex, OpenCode, Aider, Cursor agents, human developers, or any other implementation actor.

«PGVF is tool-agnostic. Jules is one possible implementation actor, not a privileged participant in the governance model.»

## Trust Model

1. Human Intent
2. Phase Contract
3. AI/Human Implementation
4. Repository State
5. Independent Verification
6. Evidence
7. Acceptance
8. Merge
9. Post-Merge Verification
10. Closure

## Phase 0 Contract Definition

```yaml
phase:
  id: "PGVF-PHASE-0"
  name: "Governance Kernel"
  version: "1.0.0"
  description: "Phase 0 Governance Kernel establishing contract validation, lifecycle state machine, invariant registry, scope policy, authority model, evidence trust levels, and governance self-integrity."

intent:
  objectives:
    - "Establish PGVF governance foundation and directory topology"
    - "Implement deterministic contract validation and state machine"
    - "Implement invariant registry, scope policy, authority model, and evidence trust levels"
    - "Provide pfgv CLI and comprehensive self-integrity tests"

allowed:
  paths:
    - "docs/governance/**"
    - "tools/pfgv/**"
    - "tests/governance/**"
    - "artifacts/governance/**"
    - "pyproject.toml"
  capabilities:
    - "governance_kernel_implementation"
    - "deterministic_cli"
    - "governance_tests"
  symbols:
    - "pfgv"
    - "PhaseContract"
    - "PhaseStateMachine"
    - "InvariantRegistry"
    - "ScopePolicy"
    - "AuthorityModel"
    - "EvidenceRecord"

forbidden:
  paths:
    - "src/fractal_flow/domain/**"
    - "src/fractal_flow/execution/**"
    - "src/fractal_flow/persistence/**"
    - "src/fractal_flow/simulation/**"
    - "src/fractal_flow/config/**"
  capabilities:
    - "live_trading"
    - "order_execution"
    - "strategy_mutation"
    - "unilateral_status_override"
  symbols:
    - "OrderSend"
    - "StructureEngine"
    - "FlowEngine"
    - "RecoveryEngine"

required_invariants:
  - "PGVF-001"
  - "PGVF-002"
  - "PGVF-003"
  - "PGVF-004"
  - "PGVF-005"
  - "PGVF-006"
  - "PGVF-007"
  - "PGVF-008"
  - "PGVF-009"
  - "PGVF-010"

required_gates:
  - "contract_validation"
  - "scope_validation"
  - "authority_validation"
  - "invariant_validation"
  - "evidence_validation"
  - "local_verification"

required_evidence:
  - "contract_hash"
  - "invariant_registry_hash"
  - "scope_policy_hash"
  - "authority_model_hash"
  - "test_results"
  - "static_analysis_results"

authority:
  informational:
    - "read_codebase"
    - "read_git_history"
  strategy: []
  risk: []
  execution: []
  governance:
    - "validate_contract"
    - "validate_invariants"
    - "validate_scope"
    - "validate_authority"
    - "validate_evidence"
    - "manage_phase_state"
  verification:
    - "verify_local_tests"
    - "verify_static_analysis"

verification:
  minimum_level: "E2"

closure:
  required:
    - exact_head
    - clean_tree
    - invariant_pass
    - evidence_reconciliation
```
