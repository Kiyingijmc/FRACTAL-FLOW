"""PGVF Governance Error Taxonomy."""


class GovernanceError(Exception):
    """Base exception for all PGVF governance errors."""

    pass


class ContractError(GovernanceError):
    """Raised when a phase contract is missing, malformed, or violated."""

    pass


class StateTransitionError(GovernanceError):
    """Raised on invalid phase lifecycle state transitions."""

    pass


class ScopeViolationError(GovernanceError):
    """Raised when code or file changes violate the phase scope policy."""

    pass


class AuthorityError(GovernanceError):
    """Raised when authority limits or deltas are violated."""

    pass


class EvidenceError(GovernanceError):
    """Raised when evidence is missing, malformed, or untrusted."""

    pass


class ContradictionError(GovernanceError):
    """Raised when contradictory evidence is detected."""

    pass


class InvariantViolationError(GovernanceError):
    """Raised when an invariant registry or rule is violated."""

    pass
