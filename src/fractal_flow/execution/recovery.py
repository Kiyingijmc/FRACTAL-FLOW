"""RecoveryEngine managing explicit recovery states, evidence provenance, sealed authority capabilities, and Gating Strategic Execution."""

import time
import uuid
import hmac
import hashlib
import json
import dataclasses
import threading
from decimal import Decimal
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Dict, List, Optional, Any, TYPE_CHECKING, Mapping, Set
from types import MappingProxyType

if TYPE_CHECKING:
    from src.fractal_flow.execution.reconciliation import ReconciliationReport
    from src.fractal_flow.config.config import EffectiveConfiguration


class RecoveryEvidenceError(Exception):
    """Raised when recovery evidence construction, assembly, session binding, or verification fails."""
    pass


class AuthorityError(RecoveryEvidenceError):
    """Raised when authority root, domain, or capability provenance verification fails."""
    pass


@unique
class RecoveryState(str, Enum):
    NORMAL = "NORMAL"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    RECOVERING = "RECOVERING"
    RECONCILING = "RECONCILING"
    RECOVERY_COMPLETE = "RECOVERY_COMPLETE"
    SAFE = "SAFE"


@unique
class CapabilityRole(str, Enum):
    # Producer Roles
    JOURNAL = "JOURNAL"
    SNAPSHOT = "SNAPSHOT"
    RISK_LEDGER = "RISK_LEDGER"
    INTENT_REPOSITORY = "INTENT_REPOSITORY"
    BROKER_QUERY = "BROKER_QUERY"
    EFFECTIVE_CONFIGURATION = "EFFECTIVE_CONFIGURATION"
    PROTECTIVE_MONITOR = "PROTECTIVE_MONITOR"
    # Validator Roles
    JOURNAL_RECOVERY_VALIDATOR = "JOURNAL_RECOVERY_VALIDATOR"
    SNAPSHOT_RECOVERY_VALIDATOR = "SNAPSHOT_RECOVERY_VALIDATOR"
    RISK_LEDGER_RECOVERY_VALIDATOR = "RISK_LEDGER_RECOVERY_VALIDATOR"
    INTENT_RECOVERY_VALIDATOR = "INTENT_RECOVERY_VALIDATOR"
    BROKER_RECONCILIATION_VALIDATOR = "BROKER_RECONCILIATION_VALIDATOR"
    CONFIGURATION_VALIDATOR = "CONFIGURATION_VALIDATOR"
    PROTECTIVE_MONITORING_VALIDATOR = "PROTECTIVE_MONITORING_VALIDATOR"


# --- Canonical Evidence Digest Computation ---

def compute_evidence_digest(evidence_obj: Any) -> str:
    """Computes deterministic SHA-256 hash over canonical representation of evidence object, failing closed on unsupported types."""
    def _canonicalize(val: Any) -> Any:
        if val is None:
            return None
        if isinstance(val, (bool, int, str)):
            return val
        if isinstance(val, float):
            import math
            if math.isnan(val) or math.isinf(val):
                raise RecoveryEvidenceError(f"Fail-closed: Non-finite float value '{val}' in canonical digest computation.")
            return val
        if isinstance(val, Decimal):
            return str(val.normalize())
        if isinstance(val, Enum):
            return val.value
        if hasattr(val, "__dataclass_fields__"):
            d = {}
            for k in val.__dataclass_fields__:
                if k.startswith("_"):
                    continue
                d[k] = _canonicalize(getattr(val, k))
            return d
        if isinstance(val, (dict, MappingProxyType, Mapping)):
            return {str(k): _canonicalize(v) for k, v in sorted(val.items())}
        if isinstance(val, (list, tuple)):
            return [_canonicalize(x) for x in val]
        raise RecoveryEvidenceError(f"Fail-closed: Unsupported type '{type(val).__name__}' in canonical evidence digest computation.")

    raw_dict = _canonicalize(evidence_obj)
    canonical_json = json.dumps(raw_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


# --- Scoped Capability & Authority Bootstrap Machinery ---

_DOMAIN_PROTECTED_ATTRS = (
    "domain_id",
    "_is_production",
    "_provisioning_token",
    "_master_key",
    "_finalized",
    "_minted_roles",
    "_validator_capabilities",
    "_producer_capabilities",
    "_registered_producers",
    "_producer_bindings",
    "_active_mint_context",
)

_BOOTSTRAP_PROTECTED_ATTRS = (
    "_domain",
    "_provisioning_token",
    "_is_sealed",
)


@dataclass(frozen=True)
class ProducerCapability:
    """Scoped capability holding only role-derived signing key for an authoritative producer bound to an authority domain."""
    authority_domain_id: str
    role: CapabilityRole
    producer_id: str
    _role_key: bytes = field(repr=False, compare=False)
    _domain: Any = field(default=None, repr=False, compare=False)
    _mint_ctx: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self._domain, AuthorityDomain)
            or getattr(self._domain, "_finalized", True)
            or getattr(self._domain, "_active_mint_context", None) is None
            or getattr(self._domain, "_active_mint_context", None) is not self._mint_ctx
            or self.authority_domain_id != getattr(self._domain, "domain_id", None)
        ):
            raise RecoveryEvidenceError("Direct instantiation of ProducerCapability is forbidden. Mint via AuthorityDomain.")

    def __copy__(self) -> None:
        return None

    def __deepcopy__(self, memo: Any) -> None:
        return None

    def __getstate__(self) -> Any:
        raise AuthorityError("Serialization/pickling of authority capabilities is prohibited.")

    def __setstate__(self, state: Any) -> None:
        raise AuthorityError("Deserialization/unpickling of authority capabilities is prohibited.")

    def sign_observation(self, session_id: str, observed_at: int, payload_digest: str) -> str:
        msg = f"FRACTAL_OBS|v2|{self.authority_domain_id}|{self.role.value}|{self.producer_id}|{session_id}|{observed_at}|{payload_digest}".encode("utf-8")
        return hmac.new(self._role_key, msg, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class ValidatorCapability:
    """Scoped capability holding only role-derived signing key for an authoritative validator bound to an authority domain."""
    authority_domain_id: str
    role: CapabilityRole
    validator_id: str
    _role_key: bytes = field(repr=False, compare=False)
    _domain: Any = field(default=None, repr=False, compare=False)
    _mint_ctx: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self._domain, AuthorityDomain)
            or getattr(self._domain, "_finalized", True)
            or getattr(self._domain, "_active_mint_context", None) is None
            or getattr(self._domain, "_active_mint_context", None) is not self._mint_ctx
            or self.authority_domain_id != getattr(self._domain, "domain_id", None)
        ):
            raise RecoveryEvidenceError("Direct instantiation of ValidatorCapability is forbidden. Mint via AuthorityDomain.")

    def __copy__(self) -> None:
        return None

    def __deepcopy__(self, memo: Any) -> None:
        return None

    def __getstate__(self) -> Any:
        raise AuthorityError("Serialization/pickling of authority capabilities is prohibited.")

    def __setstate__(self, state: Any) -> None:
        raise AuthorityError("Deserialization/unpickling of authority capabilities is prohibited.")

    def sign_token(self, session_id: str, evidence_digest: str) -> "_AuthorityToken":
        msg = f"FRACTAL_TOK|v2|{self.authority_domain_id}|{self.role.value}|{self.validator_id}|{session_id}|{evidence_digest}".encode("utf-8")
        sig = hmac.new(self._role_key, msg, hashlib.sha256).hexdigest()
        return _AuthorityToken(
            authority_domain_id=self.authority_domain_id,
            validator_id=self.validator_id,
            session_id=session_id,
            evidence_digest=evidence_digest,
            signature=sig,
        )

    def verify_token(self, token: "_AuthorityToken", expected_session: str, expected_evidence_digest: str) -> bool:
        if (
            token.authority_domain_id != self.authority_domain_id
            or token.validator_id != self.validator_id
            or token.session_id != expected_session
            or token.evidence_digest != expected_evidence_digest
        ):
            return False
        msg = f"FRACTAL_TOK|v2|{self.authority_domain_id}|{self.role.value}|{self.validator_id}|{expected_session}|{expected_evidence_digest}".encode("utf-8")
        expected_sig = hmac.new(self._role_key, msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(token.signature, expected_sig)


@dataclass(frozen=True)
class ProducerBinding:
    """Canonical, immutable binding between an authority domain, capability role, producer ID, producer instance, and capability."""
    authority_domain_id: str
    role: CapabilityRole
    producer_id: str
    producer_instance: Any
    capability: ProducerCapability


class AuthorityDomain:
    """Scoped authority domain holding master key material and producer/validator registries."""

    def __init__(
        self,
        domain_id: Optional[str] = None,
        _is_production: bool = False,
        _provisioning_token: Optional[object] = None,
    ) -> None:
        object.__setattr__(self, "domain_id", domain_id or f"FRACTAL_DOMAIN_{uuid.uuid4().hex[:12]}")
        object.__setattr__(self, "_is_production", _is_production)
        object.__setattr__(self, "_provisioning_token", _provisioning_token)
        object.__setattr__(self, "_master_key", uuid.uuid4().bytes)
        object.__setattr__(self, "_finalized", False)
        object.__setattr__(self, "_minted_roles", set())
        object.__setattr__(self, "_validator_capabilities", {})
        object.__setattr__(self, "_producer_capabilities", {})
        object.__setattr__(self, "_registered_producers", {})
        object.__setattr__(self, "_producer_bindings", {})
        object.__setattr__(self, "_active_mint_context", None)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_finalized", False) or name in _DOMAIN_PROTECTED_ATTRS:
            raise AuthorityError(f"Modification of AuthorityDomain attribute '{name}' is forbidden.")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        raise AuthorityError(f"Deletion of AuthorityDomain attribute '{name}' is forbidden.")

    @classmethod
    def _create_production_domain(cls, domain_id: str, provisioning_token: object) -> "AuthorityDomain":
        return cls(
            domain_id=domain_id,
            _is_production=True,
            _provisioning_token=provisioning_token,
        )

    @property
    def is_production(self) -> bool:
        """Returns True if and only if this domain is the singular production domain instance created by TrustedRuntimeBootstrap."""
        prod_bootstrap = TrustedRuntimeBootstrap._instance
        if prod_bootstrap is None or prod_bootstrap.domain is not self:
            return False
        return self._is_production

    def __copy__(self) -> None:
        return None

    def __deepcopy__(self, memo: Any) -> None:
        return None

    def __getstate__(self) -> Any:
        raise AuthorityError("Serialization/pickling of AuthorityDomain is prohibited.")

    def __setstate__(self, state: Any) -> None:
        raise AuthorityError("Deserialization/unpickling of AuthorityDomain is prohibited.")

    def _derive_role_key(self, role: CapabilityRole, entity_id: str) -> bytes:
        info = f"{self.domain_id}|v2|{role.value}|{entity_id}".encode("utf-8")
        return hmac.new(self._master_key, info, hashlib.sha256).digest()

    def _get_producer_instance_identity(self, producer_instance: Any) -> Optional[str]:
        """Resolves the canonical identity of a producer instance deterministically using explicit producer identity attributes."""
        # Check canonical producer identity properties/attributes explicitly
        for attr in ("producer_id", "subsystem_id", "effective_config_id", "provider_identity"):
            val = getattr(producer_instance, attr, None)
            if isinstance(val, str) and val:
                return val
            if callable(val):
                try:
                    res = val()
                    if isinstance(res, str) and res:
                        return res
                except Exception:
                    pass
        return None

    def mint_producer_capability(
        self,
        role: CapabilityRole,
        producer_id: str,
        _provisioning_token: Optional[object] = None,
    ) -> ProducerCapability:
        if self._finalized:
            raise RecoveryEvidenceError("AuthorityDomain is finalized; cannot mint new producer capabilities.")
        if self._is_production and (_provisioning_token is None or _provisioning_token is not self._provisioning_token):
            raise AuthorityError("Public/unauthorized capability minting on production AuthorityDomain is forbidden.")
        if role in self._minted_roles:
            raise RecoveryEvidenceError(f"Role '{role.value}' capability has already been minted in domain '{self.domain_id}'.")

        if role in self._registered_producers:
            registered_inst = self._registered_producers[role]
            reg_identity = self._get_producer_instance_identity(registered_inst)
            if reg_identity is not None and reg_identity != producer_id:
                raise AuthorityError(
                    f"Capability producer_id '{producer_id}' does not match registered producer identity '{reg_identity}' for role '{role.value}'."
                )

        self._minted_roles.add(role)
        role_key = self._derive_role_key(role, producer_id)
        ctx = object()
        object.__setattr__(self, "_active_mint_context", ctx)
        try:
            cap = ProducerCapability(
                authority_domain_id=self.domain_id,
                role=role,
                producer_id=producer_id,
                _role_key=role_key,
                _domain=self,
                _mint_ctx=ctx,
            )
        finally:
            object.__setattr__(self, "_active_mint_context", None)

        self._producer_capabilities[role] = cap

        if role in self._registered_producers:
            inst = self._registered_producers[role]
            inst_identity = self._get_producer_instance_identity(inst)
            if inst_identity is not None and inst_identity != producer_id:
                raise AuthorityError(
                    f"Capability producer_id '{producer_id}' does not match registered producer identity '{inst_identity}' for role '{role.value}'."
                )
            binding = ProducerBinding(
                authority_domain_id=self.domain_id,
                role=role,
                producer_id=producer_id,
                producer_instance=inst,
                capability=cap,
            )
            self._producer_bindings[role] = binding

        return cap

    def mint_validator_capability(
        self,
        role: CapabilityRole,
        validator_id: str,
        _provisioning_token: Optional[object] = None,
    ) -> ValidatorCapability:
        if self._finalized:
            raise RecoveryEvidenceError("AuthorityDomain is finalized; cannot mint new validator capabilities.")
        if self._is_production and (_provisioning_token is None or _provisioning_token is not self._provisioning_token):
            raise AuthorityError("Public/unauthorized capability minting on production AuthorityDomain is forbidden.")
        if role in self._minted_roles:
            raise RecoveryEvidenceError(f"Role '{role.value}' capability has already been minted in domain '{self.domain_id}'.")
        self._minted_roles.add(role)
        role_key = self._derive_role_key(role, validator_id)
        ctx = object()
        object.__setattr__(self, "_active_mint_context", ctx)
        try:
            cap = ValidatorCapability(
                authority_domain_id=self.domain_id,
                role=role,
                validator_id=validator_id,
                _role_key=role_key,
                _domain=self,
                _mint_ctx=ctx,
            )
        finally:
            object.__setattr__(self, "_active_mint_context", None)

        self._validator_capabilities[validator_id] = cap
        return cap

    def register_producer(
        self,
        role: CapabilityRole,
        producer_instance: Any,
        _provisioning_token: Optional[object] = None,
    ) -> None:
        """Registers a live producer instance with this authority domain."""
        if self._finalized:
            raise AuthorityError("AuthorityDomain is finalized; cannot register new producer instances.")
        if self._is_production and (_provisioning_token is None or _provisioning_token is not self._provisioning_token):
            raise AuthorityError("Public/unauthorized producer registration on production AuthorityDomain is forbidden.")
        if role in self._registered_producers:
            raise AuthorityError(f"Producer for role '{role.value}' is already registered in domain '{self.domain_id}'. Duplicate or replacement registration is forbidden.")

        if role in self._producer_capabilities:
            cap = self._producer_capabilities[role]
            inst_identity = self._get_producer_instance_identity(producer_instance)
            if inst_identity is not None and inst_identity != cap.producer_id:
                raise AuthorityError(
                    f"Registered producer identity '{inst_identity}' does not match capability producer_id '{cap.producer_id}' for role '{role.value}'."
                )

        self._registered_producers[role] = producer_instance

        if role in self._producer_capabilities:
            cap = self._producer_capabilities[role]
            inst_identity = self._get_producer_instance_identity(producer_instance)
            if inst_identity is not None and inst_identity != cap.producer_id:
                raise AuthorityError(
                    f"Registered producer identity '{inst_identity}' does not match capability producer_id '{cap.producer_id}' for role '{role.value}'."
                )
            binding = ProducerBinding(
                authority_domain_id=self.domain_id,
                role=role,
                producer_id=cap.producer_id,
                producer_instance=producer_instance,
                capability=cap,
            )
            self._producer_bindings[role] = binding

    def is_canonical_producer_capability(self, role: CapabilityRole, capability: Any) -> bool:
        """Returns True if and only if capability is strictly identical (is) to the canonical capability registered for role."""
        return self._producer_capabilities.get(role) is capability

    def is_canonical_validator_capability(self, validator_id: str, capability: Any) -> bool:
        """Returns True if and only if capability is strictly identical (is) to the canonical capability registered for validator_id."""
        return self._validator_capabilities.get(validator_id) is capability

    def is_registered_producer(
        self,
        role: CapabilityRole,
        producer_instance: Any,
        producer_id: Optional[str] = None,
    ) -> bool:
        reg_inst = self._registered_producers.get(role)
        if reg_inst is not producer_instance:
            return False
        cap = self._producer_capabilities.get(role)
        if cap is None:
            return False
        if producer_id is not None and cap.producer_id != producer_id:
            return False
        inst_identity = self._get_producer_instance_identity(producer_instance)
        if inst_identity is not None and inst_identity != cap.producer_id:
            return False
        return True

    def get_validator_capability(
        self,
        validator_id: str,
        _provisioning_token: Optional[object] = None,
    ) -> Optional[ValidatorCapability]:
        if self._finalized and self._is_production:
            raise AuthorityError("AuthorityDomain is finalized; cannot retrieve validator capabilities.")
        if self._is_production and (_provisioning_token is None or _provisioning_token is not self._provisioning_token):
            raise AuthorityError("Unrestricted public retrieval of production validator capabilities is forbidden.")
        return self._validator_capabilities.get(validator_id)

    def get_producer_capability(
        self,
        role: CapabilityRole,
        _provisioning_token: Optional[object] = None,
    ) -> Optional[ProducerCapability]:
        if self._finalized and self._is_production:
            raise AuthorityError("AuthorityDomain is finalized; cannot retrieve producer capabilities.")
        if self._is_production and (_provisioning_token is None or _provisioning_token is not self._provisioning_token):
            raise AuthorityError("Unrestricted public retrieval of production producer capabilities is forbidden.")
        return self._producer_capabilities.get(role)

    def finalize(self, _provisioning_token: Optional[object] = None) -> None:
        """Locks domain minting and clears master key material."""
        if self._is_production and (_provisioning_token is None or _provisioning_token is not self._provisioning_token):
            raise AuthorityError("Public/unauthorized finalization on production AuthorityDomain is forbidden.")
        if self._finalized:
            raise AuthorityError("AuthorityDomain is already finalized.")

        if self._is_production:
            required_producer_roles = {
                CapabilityRole.JOURNAL,
                CapabilityRole.SNAPSHOT,
                CapabilityRole.RISK_LEDGER,
                CapabilityRole.INTENT_REPOSITORY,
                CapabilityRole.BROKER_QUERY,
                CapabilityRole.EFFECTIVE_CONFIGURATION,
                CapabilityRole.PROTECTIVE_MONITOR,
            }
            required_validator_roles = {
                CapabilityRole.JOURNAL_RECOVERY_VALIDATOR,
                CapabilityRole.SNAPSHOT_RECOVERY_VALIDATOR,
                CapabilityRole.RISK_LEDGER_RECOVERY_VALIDATOR,
                CapabilityRole.INTENT_RECOVERY_VALIDATOR,
                CapabilityRole.BROKER_RECONCILIATION_VALIDATOR,
                CapabilityRole.CONFIGURATION_VALIDATOR,
                CapabilityRole.PROTECTIVE_MONITORING_VALIDATOR,
            }
            required_registered_producers = {
                CapabilityRole.JOURNAL,
                CapabilityRole.SNAPSHOT,
                CapabilityRole.RISK_LEDGER,
                CapabilityRole.INTENT_REPOSITORY,
                CapabilityRole.BROKER_QUERY,
                CapabilityRole.EFFECTIVE_CONFIGURATION,
                CapabilityRole.PROTECTIVE_MONITOR,
            }

            minted_producers = set(self._producer_capabilities.keys())
            minted_validators = {cap.role for cap in self._validator_capabilities.values()}
            registered_producers = set(self._registered_producers.keys())

            missing_producers = required_producer_roles - minted_producers
            missing_validators = required_validator_roles - minted_validators
            missing_registered = required_registered_producers - registered_producers

            if missing_producers or missing_validators or missing_registered:
                raise AuthorityError(
                    f"Cannot finalize incomplete production authority domain. "
                    f"Missing producer caps: {[r.value for r in sorted(missing_producers, key=lambda x: x.value)]}, "
                    f"Missing validator caps: {[r.value for r in sorted(missing_validators, key=lambda x: x.value)]}, "
                    f"Missing registered producers: {[r.value for r in sorted(missing_registered, key=lambda x: x.value)]}."
                )

            for role in required_producer_roles:
                cap = self._producer_capabilities[role]
                reg_inst = self._registered_producers[role]
                reg_identity = self._get_producer_instance_identity(reg_inst)
                if reg_identity is not None and cap.producer_id != reg_identity:
                    raise AuthorityError(
                        f"Production authority graph binding violation for role '{role.value}': "
                        f"capability producer_id '{cap.producer_id}' != registered producer identity '{reg_identity}'."
                    )

        # Graph consistency validation for all producer capabilities
        for role, cap in list(self._producer_capabilities.items()):
            if cap.authority_domain_id != self.domain_id:
                raise AuthorityError(f"Cross-domain capability substitution detected for role '{role.value}'.")
            if cap.role != role:
                raise AuthorityError(f"Role mismatch in producer capability for role '{role.value}'.")
            if self._is_production or role in self._registered_producers:
                if role not in self._registered_producers:
                    raise AuthorityError(f"Orphan producer capability without registered producer for role '{role.value}'.")
                if role not in self._producer_bindings:
                    raise AuthorityError(f"Orphan producer capability without ProducerBinding for role '{role.value}'.")

        # Graph consistency validation for all registered producers
        for role, inst in list(self._registered_producers.items()):
            if role not in self._producer_capabilities:
                raise AuthorityError(f"Registered producer for role '{role.value}' without capability.")
            if role not in self._producer_bindings:
                raise AuthorityError(f"Registered producer for role '{role.value}' without ProducerBinding.")

        # Graph consistency validation for all producer bindings
        for role, binding in list(self._producer_bindings.items()):
            if binding.authority_domain_id != self.domain_id:
                raise AuthorityError(f"Cross-domain binding substitution detected for role '{role.value}'.")
            if binding.role != role:
                raise AuthorityError(f"Role mismatch in ProducerBinding for role '{role.value}'.")
            if role not in self._producer_capabilities or binding.capability is not self._producer_capabilities[role]:
                raise AuthorityError(f"ProducerBinding capability mismatch for role '{role.value}'.")
            if role not in self._registered_producers or binding.producer_instance is not self._registered_producers[role]:
                raise AuthorityError(f"ProducerBinding producer instance mismatch for role '{role.value}'.")
            if binding.producer_id != binding.capability.producer_id:
                raise AuthorityError(f"ProducerBinding producer_id mismatch for role '{role.value}'.")
            reg_identity = self._get_producer_instance_identity(binding.producer_instance)
            if reg_identity is not None and reg_identity != binding.producer_id:
                raise AuthorityError(f"ProducerBinding identity mismatch for role '{role.value}'.")

        # Graph consistency validation for all validator capabilities
        for val_id, val_cap in list(self._validator_capabilities.items()):
            if val_cap.authority_domain_id != self.domain_id:
                raise AuthorityError(f"Cross-domain validator capability substitution detected for '{val_id}'.")
            if val_cap.validator_id != val_id:
                raise AuthorityError(f"Validator ID mismatch in ValidatorCapability for '{val_id}'.")

        object.__setattr__(self, "_finalized", True)
        object.__setattr__(self, "_master_key", b"\x00" * 32)
        object.__setattr__(self, "_provisioning_token", None)
        object.__setattr__(self, "_validator_capabilities", MappingProxyType(dict(self._validator_capabilities)))
        object.__setattr__(self, "_producer_capabilities", MappingProxyType(dict(self._producer_capabilities)))
        object.__setattr__(self, "_registered_producers", MappingProxyType(dict(self._registered_producers)))
        object.__setattr__(self, "_producer_bindings", MappingProxyType(dict(self._producer_bindings)))
        object.__setattr__(self, "_minted_roles", frozenset(self._minted_roles))


class TrustedRuntimeBootstrap:
    """Singular trusted runtime bootstrap anchoring production authority."""

    _instance: Optional["TrustedRuntimeBootstrap"] = None
    _lock = threading.Lock()

    def __init__(self, _is_internal_call: bool = False) -> None:
        if not _is_internal_call or type(self) is not TrustedRuntimeBootstrap:
            raise AuthorityError("Direct instantiation of TrustedRuntimeBootstrap is forbidden. Use TrustedRuntimeBootstrap.bootstrap_production_runtime().")
        prod_id = f"FRACTAL_PROD_DOMAIN_{uuid.uuid4().hex[:12]}"
        prov_token = object()
        object.__setattr__(self, "_provisioning_token", prov_token)
        object.__setattr__(self, "_is_sealed", False)
        domain = AuthorityDomain._create_production_domain(domain_id=prod_id, provisioning_token=prov_token)
        object.__setattr__(self, "_domain", domain)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_is_sealed", False) or name in _BOOTSTRAP_PROTECTED_ATTRS:
            raise AuthorityError(f"Modification of TrustedRuntimeBootstrap attribute '{name}' is forbidden.")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        raise AuthorityError(f"Deletion of TrustedRuntimeBootstrap attribute '{name}' is forbidden.")

    def __copy__(self) -> None:
        return None

    def __deepcopy__(self, memo: Any) -> None:
        return None

    def __getstate__(self) -> Any:
        raise AuthorityError("Serialization/pickling of TrustedRuntimeBootstrap is prohibited.")

    def __setstate__(self, state: Any) -> None:
        raise AuthorityError("Deserialization/unpickling of TrustedRuntimeBootstrap is prohibited.")

    @classmethod
    def bootstrap_production_runtime(cls, reset: bool = False) -> "TrustedRuntimeBootstrap":
        """Bootstraps or returns the singular trusted production runtime authority root."""
        if cls is not TrustedRuntimeBootstrap:
            raise AuthorityError("Subclass invocation of TrustedRuntimeBootstrap.bootstrap_production_runtime is forbidden.")
        with cls._lock:
            if reset and cls._instance is not None:
                raise AuthorityError("Resetting or replacing an active production authority root is forbidden.")
            if cls._instance is None:
                cls._instance = cls(_is_internal_call=True)
            return cls._instance

    @property
    def domain(self) -> AuthorityDomain:
        return self._domain

    def mint_producer_capability(self, role: CapabilityRole, producer_id: str) -> ProducerCapability:
        if self._is_sealed or self._provisioning_token is None:
            raise RecoveryEvidenceError("AuthorityDomain is finalized; cannot mint new producer capabilities.")
        return self._domain.mint_producer_capability(role, producer_id, _provisioning_token=self._provisioning_token)

    def mint_validator_capability(self, role: CapabilityRole, validator_id: str) -> ValidatorCapability:
        if self._is_sealed or self._provisioning_token is None:
            raise RecoveryEvidenceError("AuthorityDomain is finalized; cannot mint new validator capabilities.")
        return self._domain.mint_validator_capability(role, validator_id, _provisioning_token=self._provisioning_token)

    def register_producer(self, role: CapabilityRole, producer_instance: Any) -> None:
        if self._is_sealed or self._provisioning_token is None:
            raise AuthorityError("AuthorityDomain is finalized; cannot register new producer instances.")
        self._domain.register_producer(role, producer_instance, _provisioning_token=self._provisioning_token)

    def get_producer_capability(self, role: CapabilityRole) -> Optional[ProducerCapability]:
        if self._is_sealed or self._provisioning_token is None:
            raise AuthorityError("AuthorityDomain is finalized; cannot retrieve producer capabilities.")
        return self._domain.get_producer_capability(role, _provisioning_token=self._provisioning_token)

    def get_validator_capability(self, validator_id: str) -> Optional[ValidatorCapability]:
        if self._is_sealed or self._provisioning_token is None:
            raise AuthorityError("AuthorityDomain is finalized; cannot retrieve validator capabilities.")
        return self._domain.get_validator_capability(validator_id, _provisioning_token=self._provisioning_token)

    def finalize(self) -> None:
        if self._is_sealed or self._provisioning_token is None:
            raise AuthorityError("AuthorityDomain is already finalized.")
        prov_tok = self._provisioning_token
        self._domain.finalize(_provisioning_token=prov_tok)
        object.__setattr__(self, "_provisioning_token", None)
        object.__setattr__(self, "_is_sealed", True)

    def create_recovery_engine(self, initial_state: RecoveryState = RecoveryState.NORMAL) -> "RecoveryEngine":
        return RecoveryEngine(authority_domain=self._domain, initial_state=initial_state)


class AuthorityBootstrap(AuthorityDomain):
    """Untrusted / standalone capability bootstrap.

    Instantiating AuthorityBootstrap directly creates an un-trusted, non-production domain that cannot authorize production strategic execution.
    """

    def __init__(self, domain_id: Optional[str] = None) -> None:
        untrusted_id = domain_id or f"UNTRUSTED_BOOTSTRAP_{uuid.uuid4().hex[:12]}"
        super().__init__(domain_id=untrusted_id, _is_production=False)


class TrustedRuntimeAuthority:
    """Public/standalone runtime authority wrapper.

    Direct instantiation creates a non-production test/isolated authority.
    Production strategic authorization requires TrustedRuntimeBootstrap.bootstrap_production_runtime().
    """

    def __init__(self, domain_id: Optional[str] = None) -> None:
        untrusted_id = domain_id or f"STANDALONE_DOMAIN_{uuid.uuid4().hex[:12]}"
        self._domain = AuthorityDomain(domain_id=untrusted_id, _is_production=False)

    @property
    def domain(self) -> AuthorityDomain:
        return self._domain

    def create_recovery_engine(self, initial_state: RecoveryState = RecoveryState.NORMAL) -> "RecoveryEngine":
        return RecoveryEngine(authority_domain=self._domain, initial_state=initial_state)


# --- Sealed Observation Boundary ---

@dataclass(frozen=True)
class SealedObservation:
    """Producer-owned sealed observation created via a ProducerCapability."""
    domain_id: str
    version: str
    producer_role: CapabilityRole
    producer_id: str
    session_id: str
    observed_at: int
    payload_digest: str
    signature: str
    frozen_payload: Mapping[str, Any]

    def __copy__(self) -> None:
        return None

    def __deepcopy__(self, memo: Any) -> None:
        return None

    def __getstate__(self) -> Any:
        raise AuthorityError("Serialization/pickling of SealedObservation is prohibited.")

    def __setstate__(self, state: Any) -> None:
        raise AuthorityError("Deserialization/unpickling of SealedObservation is prohibited.")

    @classmethod
    def create(
        cls,
        capability: ProducerCapability,
        session_id: str,
        observed_at: int,
        raw_payload: Dict[str, Any],
    ) -> "SealedObservation":
        def _freeze(v: Any) -> Any:
            if isinstance(v, dict):
                return MappingProxyType({str(k): _freeze(val) for k, val in sorted(v.items())})
            if isinstance(v, list):
                return tuple(_freeze(x) for x in v)
            if isinstance(v, set):
                return frozenset(_freeze(x) for x in v)
            return v

        frozen = _freeze(raw_payload)
        digest = compute_evidence_digest(frozen)
        sig = capability.sign_observation(session_id, observed_at, digest)

        return cls(
            domain_id=capability.authority_domain_id,
            version="v2",
            producer_role=capability.role,
            producer_id=capability.producer_id,
            session_id=session_id,
            observed_at=observed_at,
            payload_digest=digest,
            signature=sig,
            frozen_payload=frozen,
        )

    def verify(self, expected_domain_id: str, expected_role: CapabilityRole, expected_session: str, role_key: bytes) -> bool:
        if (
            self.domain_id != expected_domain_id
            or self.producer_role != expected_role
            or self.session_id != expected_session
        ):
            return False
        if compute_evidence_digest(self.frozen_payload) != self.payload_digest:
            return False
        msg = f"FRACTAL_OBS|v2|{self.domain_id}|{self.producer_role.value}|{self.producer_id}|{self.session_id}|{self.observed_at}|{self.payload_digest}".encode("utf-8")
        expected_sig = hmac.new(role_key, msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(self.signature, expected_sig)


# --- Sealed Authority Token & Observation Boundary ---

@dataclass(frozen=True)
class _AuthorityToken:
    """Opaque, unforgeable capability token proving evidence was produced by an authorized validator during active session for exact evidence payload.

    Contains NO verification key within itself.
    """
    authority_domain_id: str
    validator_id: str
    session_id: str
    evidence_digest: str
    signature: str

    def __copy__(self) -> None:
        return None

    def __deepcopy__(self, memo: Any) -> None:
        return None

    def __getstate__(self) -> Any:
        raise AuthorityError("Serialization/pickling of _AuthorityToken is prohibited.")

    def __setstate__(self, state: Any) -> None:
        raise AuthorityError("Deserialization/unpickling of _AuthorityToken is prohibited.")


@dataclass(frozen=True)
class _RecoveryAuthorityBundle:
    """Sealed bundle encapsulating verified authority capabilities for all seven recovery subsystems."""
    journal_token: Optional[_AuthorityToken] = None
    snapshot_token: Optional[_AuthorityToken] = None
    risk_token: Optional[_AuthorityToken] = None
    intent_token: Optional[_AuthorityToken] = None
    broker_token: Optional[_AuthorityToken] = None
    config_token: Optional[_AuthorityToken] = None
    protective_token: Optional[_AuthorityToken] = None
    session_id: str = ""

    def __copy__(self) -> None:
        return None

    def __deepcopy__(self, memo: Any) -> None:
        return None

    def is_valid(self, recovery_evidence: "RecoveryEvidence", required_session: str, validator_capabilities: Dict[str, ValidatorCapability]) -> bool:
        if not required_session or self.session_id != required_session:
            return False

        validators = [
            (CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator", self.journal_token, recovery_evidence.journal_evidence),
            (CapabilityRole.SNAPSHOT_RECOVERY_VALIDATOR, "SnapshotRecoveryValidator", self.snapshot_token, recovery_evidence.snapshot_evidence),
            (CapabilityRole.RISK_LEDGER_RECOVERY_VALIDATOR, "RiskLedgerRecoveryValidator", self.risk_token, recovery_evidence.risk_evidence),
            (CapabilityRole.INTENT_RECOVERY_VALIDATOR, "IntentRecoveryValidator", self.intent_token, recovery_evidence.intent_evidence),
            (CapabilityRole.BROKER_RECONCILIATION_VALIDATOR, "BrokerReconciliationValidator", self.broker_token, recovery_evidence.broker_evidence),
            (CapabilityRole.CONFIGURATION_VALIDATOR, "ConfigurationValidator", self.config_token, recovery_evidence.config_evidence),
            (CapabilityRole.PROTECTIVE_MONITORING_VALIDATOR, "ProtectiveMonitoringValidator", self.protective_token, recovery_evidence.protective_evidence),
        ]

        for expected_role, expected_val, tok, ev_obj in validators:
            if tok is None:
                return False
            cap = validator_capabilities.get(expected_val)
            if cap is None:
                return False
            if cap.role != expected_role or cap.validator_id != expected_val:
                return False
            expected_digest = compute_evidence_digest(ev_obj)
            if not cap.verify_token(tok, required_session, expected_digest):
                return False

        return True


@dataclass(frozen=True)
class EvidenceProvenance:
    """Verifiable, immutable metadata capturing the audit trail of produced recovery evidence."""
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_component: str = ""
    source_operation: str = ""
    produced_at: float = field(default_factory=time.time)
    source_session: str = ""
    source_sequence: int = 0
    source_boundary: str = ""
    source_identity: str = ""
    result: str = "SUCCESS"
    failure_reason: Optional[str] = None


@dataclass(frozen=True)
class JournalRecoveryEvidence:
    valid: bool = False
    head_sequence: int = 0
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)
    _authority_token: Optional[_AuthorityToken] = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class SnapshotRecoveryEvidence:
    valid: bool = False
    boundary_sequence: int = 0
    fallback_used: bool = False
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)
    _authority_token: Optional[_AuthorityToken] = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class RiskLedgerRecoveryEvidence:
    valid: bool = False
    reconstructed_entries_count: int = 0
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)
    _authority_token: Optional[_AuthorityToken] = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class IntentRecoveryEvidence:
    valid: bool = False
    reconstructed_intents_count: int = 0
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)
    _authority_token: Optional[_AuthorityToken] = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class BrokerReconciliationEvidence:
    valid: bool = False
    unresolved_unknown_count: int = 0
    orphaned_count: int = 0
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)
    _authority_token: Optional[_AuthorityToken] = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class ConfigurationEvidence:
    valid: bool = False
    config_id: str = ""
    identity_matched: bool = False
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)
    _authority_token: Optional[_AuthorityToken] = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class ProtectiveMonitoringEvidence:
    valid: bool = False
    active: bool = True
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)
    _authority_token: Optional[_AuthorityToken] = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class RecoveryEvidence:
    """Verifiable composite evidence required to authorize system recovery completion."""
    journal_evidence: JournalRecoveryEvidence = field(default_factory=JournalRecoveryEvidence)
    snapshot_evidence: SnapshotRecoveryEvidence = field(default_factory=SnapshotRecoveryEvidence)
    risk_evidence: RiskLedgerRecoveryEvidence = field(default_factory=RiskLedgerRecoveryEvidence)
    intent_evidence: IntentRecoveryEvidence = field(default_factory=IntentRecoveryEvidence)
    broker_evidence: BrokerReconciliationEvidence = field(default_factory=BrokerReconciliationEvidence)
    config_evidence: ConfigurationEvidence = field(default_factory=ConfigurationEvidence)
    protective_evidence: ProtectiveMonitoringEvidence = field(default_factory=ProtectiveMonitoringEvidence)
    _authority_bundle: Optional[_RecoveryAuthorityBundle] = field(default=None, repr=False, compare=False)

    # Legacy attributes maintained purely for backward compatibility/diagnostics.
    # DEPRECATED: These fields CANNOT authorize strategic execution.
    persistence_integrity_valid: bool = False
    journal_integrity_valid: bool = False
    snapshot_integrity_valid: bool = False
    risk_ledger_reconstructed: bool = False
    execution_intents_reconstructed: bool = False
    broker_reconciliation_complete: bool = False
    unresolved_unknown_count: int = 0
    configuration_identity_matched: bool = False
    protective_monitoring_active: bool = True
    additional_details: Dict[str, Any] = field(default_factory=dict)

    def has_valid_authority_capability(self, required_session: str, validator_capabilities: Dict[str, ValidatorCapability]) -> bool:
        """Verifies that this composite evidence object encapsulates a valid, un-forged, active authority bundle matching current evidence payload."""
        if self._authority_bundle is None:
            return False
        return self._authority_bundle.is_valid(self, required_session, validator_capabilities)

    def is_satisfactory(self, required_session: Optional[str] = None) -> bool:
        """Returns True only if all required typed subsystem evidence components and valid provenances are satisfied."""
        subsystem_satisfied = (
            self.journal_evidence.valid
            and self.journal_evidence.provenance is not None
            and self.journal_evidence.provenance.result == "SUCCESS"
            and self.journal_evidence.provenance.source_component == "JournalRecoveryValidator"
            and self.snapshot_evidence.valid
            and self.snapshot_evidence.provenance is not None
            and self.snapshot_evidence.provenance.result == "SUCCESS"
            and self.snapshot_evidence.provenance.source_component == "SnapshotRecoveryValidator"
            and self.risk_evidence.valid
            and self.risk_evidence.provenance is not None
            and self.risk_evidence.provenance.result == "SUCCESS"
            and self.risk_evidence.provenance.source_component == "RiskLedgerRecoveryValidator"
            and self.intent_evidence.valid
            and self.intent_evidence.provenance is not None
            and self.intent_evidence.provenance.result == "SUCCESS"
            and self.intent_evidence.provenance.source_component == "IntentRecoveryValidator"
            and self.broker_evidence.valid
            and self.broker_evidence.provenance is not None
            and self.broker_evidence.provenance.result == "SUCCESS"
            and self.broker_evidence.provenance.source_component == "BrokerReconciliationValidator"
            and isinstance(self.broker_evidence.unresolved_unknown_count, int)
            and self.broker_evidence.unresolved_unknown_count == 0
            and isinstance(self.broker_evidence.orphaned_count, int)
            and self.broker_evidence.orphaned_count == 0
            and self.config_evidence.valid
            and self.config_evidence.identity_matched
            and self.config_evidence.provenance is not None
            and self.config_evidence.provenance.result == "SUCCESS"
            and self.config_evidence.provenance.source_component == "ConfigurationValidator"
            and self.protective_evidence.valid
            and self.protective_evidence.active
            and self.protective_evidence.provenance is not None
            and self.protective_evidence.provenance.result == "SUCCESS"
            and self.protective_evidence.provenance.source_component == "ProtectiveMonitoringValidator"
        )

        if not subsystem_satisfied:
            return False

        if required_session:
            provenances = [
                self.journal_evidence.provenance,
                self.snapshot_evidence.provenance,
                self.risk_evidence.provenance,
                self.intent_evidence.provenance,
                self.broker_evidence.provenance,
                self.config_evidence.provenance,
                self.protective_evidence.provenance,
            ]
            for prov in provenances:
                if prov is None or prov.source_session != required_session:
                    return False

        return True

    @classmethod
    def create_authoritative_evidence(
        cls,
        session_id: str,
        **kwargs: Any,
    ) -> "RecoveryEvidence":
        """DEPRECATED / UNAUTHORIZED FACTORY.

        Caller-supplied booleans cannot manufacture authoritative evidence.
        Returns evidence marked UNAUTHORIZED_FACTORY which fails authorization gates.
        """
        unauth_prov = EvidenceProvenance(
            source_component="CALLER_UNAUTHORIZED_FACTORY",
            source_session=session_id,
            result="UNAUTHORIZED_FACTORY",
            failure_reason="Caller self-attestation is forbidden in authorization pathways.",
        )
        return cls(
            journal_evidence=JournalRecoveryEvidence(valid=False, provenance=unauth_prov),
            snapshot_evidence=SnapshotRecoveryEvidence(valid=False, provenance=unauth_prov),
            risk_evidence=RiskLedgerRecoveryEvidence(valid=False, provenance=unauth_prov),
            intent_evidence=IntentRecoveryEvidence(valid=False, provenance=unauth_prov),
            broker_evidence=BrokerReconciliationEvidence(valid=False, provenance=unauth_prov),
            config_evidence=ConfigurationEvidence(valid=False, provenance=unauth_prov),
            protective_evidence=ProtectiveMonitoringEvidence(valid=False, provenance=unauth_prov),
        )


# --- Controlled Evidence Assembler ---

class RecoveryEvidenceAssembler:
    """Assembles typed recovery evidence from subsystem producers and enforces provenance, token capabilities, and session consistency."""

    @staticmethod
    def assemble(
        *,
        journal: JournalRecoveryEvidence,
        snapshot: SnapshotRecoveryEvidence,
        risk: RiskLedgerRecoveryEvidence,
        intents: IntentRecoveryEvidence,
        broker: BrokerReconciliationEvidence,
        config: ConfigurationEvidence,
        protective: ProtectiveMonitoringEvidence,
        session_id: str,
        validator_capabilities: Optional[Dict[str, ValidatorCapability]] = None,
    ) -> RecoveryEvidence:

        bundle = _RecoveryAuthorityBundle(
            journal_token=journal._authority_token,
            snapshot_token=snapshot._authority_token,
            risk_token=risk._authority_token,
            intent_token=intents._authority_token,
            broker_token=broker._authority_token,
            config_token=config._authority_token,
            protective_token=protective._authority_token,
            session_id=session_id,
        )

        evidence = RecoveryEvidence(
            journal_evidence=journal,
            snapshot_evidence=snapshot,
            risk_evidence=risk,
            intent_evidence=intents,
            broker_evidence=broker,
            config_evidence=config,
            protective_evidence=protective,
            _authority_bundle=bundle,
        )

        if validator_capabilities is not None and not bundle.is_valid(evidence, session_id, validator_capabilities):
            raise RecoveryEvidenceError("Recovery evidence assembly failed: invalid, forged, or payload-mismatched subsystem authority token(s)")

        if not evidence.is_satisfactory(required_session=session_id):
            raise RecoveryEvidenceError("Recovery evidence assembly failed: evidence is unsatisfactory or session mismatch")

        return evidence


# --- Authoritative Subsystem Recovery Validators / Producers ---

@dataclass(frozen=True)
class ProtectiveMonitoringSubsystem:
    """Authoritative protective monitoring subsystem instance."""
    subsystem_id: str = "ProtectiveMonitoringSubsystem"
    _active: bool = True
    _faulted: bool = False

    def is_active(self) -> bool:
        return self._active and not self._faulted

    def produce_observation(self, session_id: str, capability: ProducerCapability) -> SealedObservation:
        if not isinstance(capability, ProducerCapability) or capability.role != CapabilityRole.PROTECTIVE_MONITOR:
            raise RecoveryEvidenceError("ProtectiveMonitoringSubsystem observation requires a valid PROTECTIVE_MONITOR ProducerCapability.")
        payload = {
            "subsystem_id": self.subsystem_id,
            "active": self.is_active(),
            "faulted": self._faulted,
        }
        return SealedObservation.create(capability, session_id, int(time.time()), payload)


class JournalRecoveryValidator:
    @staticmethod
    def validate(
        journal: Any,
        session_id: str,
        capability: ValidatorCapability,
        observation: Optional[SealedObservation] = None,
        producer_capability: Optional[ProducerCapability] = None,
        authority_domain: Optional[AuthorityDomain] = None,
    ) -> JournalRecoveryEvidence:
        if not isinstance(capability, ValidatorCapability) or capability.role != CapabilityRole.JOURNAL_RECOVERY_VALIDATOR or capability.validator_id != "JournalRecoveryValidator":
            raise RecoveryEvidenceError("JournalRecoveryValidator requires a valid JOURNAL_RECOVERY_VALIDATOR capability.")

        if authority_domain:
            if not authority_domain.is_registered_producer(CapabilityRole.JOURNAL, journal):
                prov = EvidenceProvenance(
                    source_component="JournalRecoveryValidator",
                    source_operation="validate",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Unregistered Journal instance in AuthorityDomain",
                )
                return JournalRecoveryEvidence(valid=False, provenance=prov)
            if producer_capability and not authority_domain.is_canonical_producer_capability(CapabilityRole.JOURNAL, producer_capability):
                prov = EvidenceProvenance(
                    source_component="JournalRecoveryValidator",
                    source_operation="validate",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Non-canonical ProducerCapability for Journal in AuthorityDomain",
                )
                return JournalRecoveryEvidence(valid=False, provenance=prov)
            if not authority_domain.is_canonical_validator_capability("JournalRecoveryValidator", capability):
                prov = EvidenceProvenance(
                    source_component="JournalRecoveryValidator",
                    source_operation="validate",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Non-canonical ValidatorCapability for JournalRecoveryValidator in AuthorityDomain",
                )
                return JournalRecoveryEvidence(valid=False, provenance=prov)

        if observation is None or producer_capability is None:
            prov = EvidenceProvenance(
                source_component="JournalRecoveryValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Missing SealedObservation or ProducerCapability for Journal authority provenance.",
            )
            return JournalRecoveryEvidence(valid=False, provenance=prov)

        if not isinstance(producer_capability, ProducerCapability) or producer_capability.role != CapabilityRole.JOURNAL:
            prov = EvidenceProvenance(
                source_component="JournalRecoveryValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Invalid or unauthorized ProducerCapability for Journal.",
            )
            return JournalRecoveryEvidence(valid=False, provenance=prov)

        if not isinstance(observation, SealedObservation) or not observation.verify(producer_capability.authority_domain_id, CapabilityRole.JOURNAL, session_id, producer_capability._role_key):
            prov = EvidenceProvenance(
                source_component="JournalRecoveryValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="SealedObservation verification failed for Journal.",
            )
            return JournalRecoveryEvidence(valid=False, provenance=prov)

        if observation.producer_id != producer_capability.producer_id:
            prov = EvidenceProvenance(
                source_component="JournalRecoveryValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Producer ID mismatch in Journal observation.",
            )
            return JournalRecoveryEvidence(valid=False, provenance=prov)

        from src.fractal_flow.persistence.journal import DurableEventJournal
        if not isinstance(journal, DurableEventJournal):
            prov = EvidenceProvenance(
                source_component="JournalRecoveryValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Journal object must be an instance of DurableEventJournal.",
            )
            return JournalRecoveryEvidence(valid=False, provenance=prov)

        faulted = journal._faulted
        seq = journal._global_sequence

        obs_payload = observation.frozen_payload
        if obs_payload.get("faulted") != faulted or obs_payload.get("global_sequence") != seq:
            prov = EvidenceProvenance(
                source_component="JournalRecoveryValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Journal live state contradicts sealed observation payload.",
            )
            return JournalRecoveryEvidence(valid=False, provenance=prov)

        valid = not faulted
        prov = EvidenceProvenance(
            source_component="JournalRecoveryValidator",
            source_operation="validate",
            source_session=session_id,
            source_sequence=seq,
            source_boundary=str(getattr(journal, "journal_file_path", "journal")),
            result="SUCCESS" if valid else "FAILED",
            failure_reason="Journal in faulted state" if not valid else None,
        )
        unsealed = JournalRecoveryEvidence(valid=valid, head_sequence=seq, provenance=prov)
        if valid:
            digest = compute_evidence_digest(unsealed)
            token = capability.sign_token(session_id, digest)
            return dataclasses.replace(unsealed, _authority_token=token)
        return unsealed


class SnapshotRecoveryValidator:
    @staticmethod
    def validate(
        snapshot_engine: Any,
        session_id: str,
        capability: ValidatorCapability,
        journal: Any = None,
        aggregate_type: str = "",
        aggregate_id: str = "",
        observation: Optional[SealedObservation] = None,
        producer_capability: Optional[ProducerCapability] = None,
        authority_domain: Optional[AuthorityDomain] = None,
    ) -> SnapshotRecoveryEvidence:
        if authority_domain:
            if not authority_domain.is_registered_producer(CapabilityRole.SNAPSHOT, snapshot_engine):
                prov = EvidenceProvenance(
                    source_component="SnapshotRecoveryValidator",
                    source_operation="validate",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Unregistered SnapshotEngine instance in AuthorityDomain",
                )
                return SnapshotRecoveryEvidence(valid=False, provenance=prov)
            if producer_capability and not authority_domain.is_canonical_producer_capability(CapabilityRole.SNAPSHOT, producer_capability):
                prov = EvidenceProvenance(
                    source_component="SnapshotRecoveryValidator",
                    source_operation="validate",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Non-canonical ProducerCapability for Snapshot in AuthorityDomain",
                )
                return SnapshotRecoveryEvidence(valid=False, provenance=prov)
            if not authority_domain.is_canonical_validator_capability("SnapshotRecoveryValidator", capability):
                prov = EvidenceProvenance(
                    source_component="SnapshotRecoveryValidator",
                    source_operation="validate",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Non-canonical ValidatorCapability for SnapshotRecoveryValidator in AuthorityDomain",
                )
                return SnapshotRecoveryEvidence(valid=False, provenance=prov)
        if not isinstance(capability, ValidatorCapability) or capability.role != CapabilityRole.SNAPSHOT_RECOVERY_VALIDATOR or capability.validator_id != "SnapshotRecoveryValidator":
            raise RecoveryEvidenceError("SnapshotRecoveryValidator requires a valid SNAPSHOT_RECOVERY_VALIDATOR capability.")

        if observation is None or producer_capability is None:
            prov = EvidenceProvenance(
                source_component="SnapshotRecoveryValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Missing SealedObservation or ProducerCapability for Snapshot authority provenance.",
            )
            return SnapshotRecoveryEvidence(valid=False, provenance=prov)

        if not isinstance(producer_capability, ProducerCapability) or producer_capability.role != CapabilityRole.SNAPSHOT:
            prov = EvidenceProvenance(
                source_component="SnapshotRecoveryValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Invalid or unauthorized ProducerCapability for Snapshot.",
            )
            return SnapshotRecoveryEvidence(valid=False, provenance=prov)

        if not isinstance(observation, SealedObservation) or not observation.verify(producer_capability.authority_domain_id, CapabilityRole.SNAPSHOT, session_id, producer_capability._role_key):
            prov = EvidenceProvenance(
                source_component="SnapshotRecoveryValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="SealedObservation verification failed for Snapshot.",
            )
            return SnapshotRecoveryEvidence(valid=False, provenance=prov)

        from src.fractal_flow.persistence.snapshot import SnapshotEngine
        if not isinstance(snapshot_engine, SnapshotEngine):
            prov = EvidenceProvenance(
                source_component="SnapshotRecoveryValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Snapshot engine must be an instance of SnapshotEngine.",
            )
            return SnapshotRecoveryEvidence(valid=False, provenance=prov)

        obs_payload = observation.frozen_payload
        fallback = getattr(snapshot_engine, "_snapshot_fallback_used", False)
        valid = getattr(snapshot_engine, "_snapshot_valid", True)

        if obs_payload.get("snapshot_valid") != valid or obs_payload.get("snapshot_fallback_used") != fallback:
            prov = EvidenceProvenance(
                source_component="SnapshotRecoveryValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Snapshot live state contradicts sealed observation payload.",
            )
            return SnapshotRecoveryEvidence(valid=False, provenance=prov)

        if snapshot_engine and journal and aggregate_type and aggregate_id:
            try:
                snap = snapshot_engine.load_snapshot(aggregate_type, aggregate_id)
                if snap:
                    snapshot_engine.verify_snapshot_equivalence(
                        snapshot=snap,
                        journal=journal,
                        aggregate_type=aggregate_type,
                        aggregate_id=aggregate_id,
                    )
            except Exception:
                valid = False
                fallback = True

        prov = EvidenceProvenance(
            source_component="SnapshotRecoveryValidator",
            source_operation="validate",
            source_session=session_id,
            result="SUCCESS" if valid else "FAILED",
            failure_reason="Snapshot invalid or corrupt" if not valid else None,
        )
        unsealed = SnapshotRecoveryEvidence(valid=valid, fallback_used=fallback, provenance=prov)
        if valid:
            digest = compute_evidence_digest(unsealed)
            token = capability.sign_token(session_id, digest)
            return dataclasses.replace(unsealed, _authority_token=token)
        return unsealed


class RiskLedgerRecoveryValidator:
    @staticmethod
    def reconstruct(
        risk_ledger: Any,
        session_id: str,
        capability: ValidatorCapability,
        observation: Optional[SealedObservation] = None,
        producer_capability: Optional[ProducerCapability] = None,
        authority_domain: Optional[AuthorityDomain] = None,
    ) -> RiskLedgerRecoveryEvidence:
        if authority_domain:
            if not authority_domain.is_registered_producer(CapabilityRole.RISK_LEDGER, risk_ledger):
                prov = EvidenceProvenance(
                    source_component="RiskLedgerRecoveryValidator",
                    source_operation="reconstruct",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Unregistered RiskLedger instance in AuthorityDomain",
                )
                return RiskLedgerRecoveryEvidence(valid=False, provenance=prov)
            if producer_capability and not authority_domain.is_canonical_producer_capability(CapabilityRole.RISK_LEDGER, producer_capability):
                prov = EvidenceProvenance(
                    source_component="RiskLedgerRecoveryValidator",
                    source_operation="reconstruct",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Non-canonical ProducerCapability for Risk Ledger in AuthorityDomain",
                )
                return RiskLedgerRecoveryEvidence(valid=False, provenance=prov)
            if not authority_domain.is_canonical_validator_capability("RiskLedgerRecoveryValidator", capability):
                prov = EvidenceProvenance(
                    source_component="RiskLedgerRecoveryValidator",
                    source_operation="reconstruct",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Non-canonical ValidatorCapability for RiskLedgerRecoveryValidator in AuthorityDomain",
                )
                return RiskLedgerRecoveryEvidence(valid=False, provenance=prov)
        if not isinstance(capability, ValidatorCapability) or capability.role != CapabilityRole.RISK_LEDGER_RECOVERY_VALIDATOR or capability.validator_id != "RiskLedgerRecoveryValidator":
            raise RecoveryEvidenceError("RiskLedgerRecoveryValidator requires a valid RISK_LEDGER_RECOVERY_VALIDATOR capability.")

        if observation is None or producer_capability is None:
            prov = EvidenceProvenance(
                source_component="RiskLedgerRecoveryValidator",
                source_operation="reconstruct",
                source_session=session_id,
                result="FAILED",
                failure_reason="Missing SealedObservation or ProducerCapability for Risk Ledger authority provenance.",
            )
            return RiskLedgerRecoveryEvidence(valid=False, provenance=prov)

        if not isinstance(producer_capability, ProducerCapability) or producer_capability.role != CapabilityRole.RISK_LEDGER:
            prov = EvidenceProvenance(
                source_component="RiskLedgerRecoveryValidator",
                source_operation="reconstruct",
                source_session=session_id,
                result="FAILED",
                failure_reason="Invalid or unauthorized ProducerCapability for Risk Ledger.",
            )
            return RiskLedgerRecoveryEvidence(valid=False, provenance=prov)

        if not isinstance(observation, SealedObservation) or not observation.verify(producer_capability.authority_domain_id, CapabilityRole.RISK_LEDGER, session_id, producer_capability._role_key):
            prov = EvidenceProvenance(
                source_component="RiskLedgerRecoveryValidator",
                source_operation="reconstruct",
                source_session=session_id,
                result="FAILED",
                failure_reason="SealedObservation verification failed for Risk Ledger.",
            )
            return RiskLedgerRecoveryEvidence(valid=False, provenance=prov)

        from src.fractal_flow.domain.risk_ledger import OpportunityRiskLedger
        if not isinstance(risk_ledger, OpportunityRiskLedger):
            prov = EvidenceProvenance(
                source_component="RiskLedgerRecoveryValidator",
                source_operation="reconstruct",
                source_session=session_id,
                result="FAILED",
                failure_reason="Risk ledger must be an instance of OpportunityRiskLedger.",
            )
            return RiskLedgerRecoveryEvidence(valid=False, provenance=prov)

        obs_payload = observation.frozen_payload
        count = len(risk_ledger.entries)
        remaining = risk_ledger.remaining_risk
        faulted = getattr(risk_ledger, "_faulted", False)

        if obs_payload.get("entries_count") != count or obs_payload.get("faulted") != faulted:
            prov = EvidenceProvenance(
                source_component="RiskLedgerRecoveryValidator",
                source_operation="reconstruct",
                source_session=session_id,
                result="FAILED",
                failure_reason="Risk ledger live state contradicts sealed observation payload.",
            )
            return RiskLedgerRecoveryEvidence(valid=False, provenance=prov)

        valid = (not faulted) and (remaining >= 0)
        prov = EvidenceProvenance(
            source_component="RiskLedgerRecoveryValidator",
            source_operation="reconstruct",
            source_session=session_id,
            result="SUCCESS" if valid else "FAILED",
            failure_reason=None if valid else "Risk ledger in faulted state or negative remaining risk",
        )
        unsealed = RiskLedgerRecoveryEvidence(valid=valid, reconstructed_entries_count=count, provenance=prov)
        if valid:
            digest = compute_evidence_digest(unsealed)
            token = capability.sign_token(session_id, digest)
            return dataclasses.replace(unsealed, _authority_token=token)
        return unsealed


class IntentRecoveryValidator:
    @staticmethod
    def reconstruct(
        intent_repo: Any,
        session_id: str,
        capability: ValidatorCapability,
        observation: Optional[SealedObservation] = None,
        producer_capability: Optional[ProducerCapability] = None,
        authority_domain: Optional[AuthorityDomain] = None,
    ) -> IntentRecoveryEvidence:
        if authority_domain:
            if not authority_domain.is_registered_producer(CapabilityRole.INTENT_REPOSITORY, intent_repo):
                prov = EvidenceProvenance(
                    source_component="IntentRecoveryValidator",
                    source_operation="reconstruct",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Unregistered IntentRepository instance in AuthorityDomain",
                )
                return IntentRecoveryEvidence(valid=False, provenance=prov)
            if producer_capability and not authority_domain.is_canonical_producer_capability(CapabilityRole.INTENT_REPOSITORY, producer_capability):
                prov = EvidenceProvenance(
                    source_component="IntentRecoveryValidator",
                    source_operation="reconstruct",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Non-canonical ProducerCapability for Intent Repository in AuthorityDomain",
                )
                return IntentRecoveryEvidence(valid=False, provenance=prov)
            if not authority_domain.is_canonical_validator_capability("IntentRecoveryValidator", capability):
                prov = EvidenceProvenance(
                    source_component="IntentRecoveryValidator",
                    source_operation="reconstruct",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Non-canonical ValidatorCapability for IntentRecoveryValidator in AuthorityDomain",
                )
                return IntentRecoveryEvidence(valid=False, provenance=prov)
        if not isinstance(capability, ValidatorCapability) or capability.role != CapabilityRole.INTENT_RECOVERY_VALIDATOR or capability.validator_id != "IntentRecoveryValidator":
            raise RecoveryEvidenceError("IntentRecoveryValidator requires a valid INTENT_RECOVERY_VALIDATOR capability.")

        if observation is None or producer_capability is None:
            prov = EvidenceProvenance(
                source_component="IntentRecoveryValidator",
                source_operation="reconstruct",
                source_session=session_id,
                result="FAILED",
                failure_reason="Missing SealedObservation or ProducerCapability for Intent Repository authority provenance.",
            )
            return IntentRecoveryEvidence(valid=False, provenance=prov)

        if not isinstance(producer_capability, ProducerCapability) or producer_capability.role != CapabilityRole.INTENT_REPOSITORY:
            prov = EvidenceProvenance(
                source_component="IntentRecoveryValidator",
                source_operation="reconstruct",
                source_session=session_id,
                result="FAILED",
                failure_reason="Invalid or unauthorized ProducerCapability for Intent Repository.",
            )
            return IntentRecoveryEvidence(valid=False, provenance=prov)

        if not isinstance(observation, SealedObservation) or not observation.verify(producer_capability.authority_domain_id, CapabilityRole.INTENT_REPOSITORY, session_id, producer_capability._role_key):
            prov = EvidenceProvenance(
                source_component="IntentRecoveryValidator",
                source_operation="reconstruct",
                source_session=session_id,
                result="FAILED",
                failure_reason="SealedObservation verification failed for Intent Repository.",
            )
            return IntentRecoveryEvidence(valid=False, provenance=prov)

        from src.fractal_flow.persistence.interfaces import DurableExecutionIntentRepository
        if not isinstance(intent_repo, DurableExecutionIntentRepository):
            prov = EvidenceProvenance(
                source_component="IntentRecoveryValidator",
                source_operation="reconstruct",
                source_session=session_id,
                result="FAILED",
                failure_reason="Intent repository must be an instance of DurableExecutionIntentRepository.",
            )
            return IntentRecoveryEvidence(valid=False, provenance=prov)

        obs_payload = observation.frozen_payload
        count = len(intent_repo._intents)
        if obs_payload.get("intents_count") != count:
            prov = EvidenceProvenance(
                source_component="IntentRecoveryValidator",
                source_operation="reconstruct",
                source_session=session_id,
                result="FAILED",
                failure_reason="Intent repository live state contradicts sealed observation payload.",
            )
            return IntentRecoveryEvidence(valid=False, provenance=prov)

        valid = True
        prov = EvidenceProvenance(
            source_component="IntentRecoveryValidator",
            source_operation="reconstruct",
            source_session=session_id,
            result="SUCCESS",
        )
        unsealed = IntentRecoveryEvidence(valid=valid, reconstructed_intents_count=count, provenance=prov)
        digest = compute_evidence_digest(unsealed)
        token = capability.sign_token(session_id, digest)
        return dataclasses.replace(unsealed, _authority_token=token)


class BrokerReconciliationValidator:
    @staticmethod
    def reconcile(reconciliation_report: Any, session_id: str, capability: ValidatorCapability) -> BrokerReconciliationEvidence:
        if not isinstance(capability, ValidatorCapability) or capability.role != CapabilityRole.BROKER_RECONCILIATION_VALIDATOR or capability.validator_id != "BrokerReconciliationValidator":
            raise RecoveryEvidenceError("BrokerReconciliationValidator requires a valid BROKER_RECONCILIATION_VALIDATOR capability.")

        from src.fractal_flow.execution.reconciliation import ReconciliationReport
        if (
            not isinstance(reconciliation_report, ReconciliationReport)
            or not reconciliation_report.has_valid_authority_stamp(expected_session_id=session_id)
            or (reconciliation_report._authority_stamp and reconciliation_report._authority_stamp.authority_domain_id != capability.authority_domain_id)
        ):
            prov = EvidenceProvenance(
                source_component="BrokerReconciliationValidator",
                source_operation="reconcile",
                source_session=session_id,
                result="FAILED",
                failure_reason="Authorization requires an authentic ReconciliationReport instance with valid ReconciliationAuthorityStamp matching session_id and authority_domain_id",
            )
            return BrokerReconciliationEvidence(
                valid=False,
                unresolved_unknown_count=-1,
                orphaned_count=-1,
                provenance=prov,
            )

        unknown = reconciliation_report.unknown_count
        orphaned = reconciliation_report.orphaned_count
        valid = (
            reconciliation_report.authoritative
            and reconciliation_report.complete
            and unknown == 0
            and orphaned == 0
        )
        prov = EvidenceProvenance(
            source_component="BrokerReconciliationValidator",
            source_operation="reconcile",
            source_session=session_id,
            source_sequence=reconciliation_report.temporal_boundary,
            source_boundary=str(reconciliation_report.temporal_boundary),
            result="SUCCESS" if valid else "FAILED",
            failure_reason=None if valid else f"Reconciliation invalid (auth={reconciliation_report.authoritative}, comp={reconciliation_report.complete}, unknown={unknown}, orphaned={orphaned})",
        )
        unsealed = BrokerReconciliationEvidence(
            valid=valid,
            unresolved_unknown_count=unknown,
            orphaned_count=orphaned,
            provenance=prov,
        )
        if valid:
            digest = compute_evidence_digest(unsealed)
            token = capability.sign_token(session_id, digest)
            return dataclasses.replace(unsealed, _authority_token=token)
        return unsealed


class ConfigurationValidator:
    @staticmethod
    def validate(
        config_obj_or_id: Any,
        session_id: str,
        capability: ValidatorCapability,
        expected_config_id: Optional[str] = None,
        observation: Optional[SealedObservation] = None,
        producer_capability: Optional[ProducerCapability] = None,
        authority_domain: Optional[AuthorityDomain] = None,
    ) -> ConfigurationEvidence:
        if authority_domain:
            if not authority_domain.is_registered_producer(CapabilityRole.EFFECTIVE_CONFIGURATION, config_obj_or_id):
                prov = EvidenceProvenance(
                    source_component="ConfigurationValidator",
                    source_operation="validate",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Unregistered Configuration instance in AuthorityDomain",
                )
                return ConfigurationEvidence(valid=False, provenance=prov)
            if producer_capability and not authority_domain.is_canonical_producer_capability(CapabilityRole.EFFECTIVE_CONFIGURATION, producer_capability):
                prov = EvidenceProvenance(
                    source_component="ConfigurationValidator",
                    source_operation="validate",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Non-canonical ProducerCapability for Configuration in AuthorityDomain",
                )
                return ConfigurationEvidence(valid=False, provenance=prov)
            if not authority_domain.is_canonical_validator_capability("ConfigurationValidator", capability):
                prov = EvidenceProvenance(
                    source_component="ConfigurationValidator",
                    source_operation="validate",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Non-canonical ValidatorCapability for ConfigurationValidator in AuthorityDomain",
                )
                return ConfigurationEvidence(valid=False, provenance=prov)
        if not isinstance(capability, ValidatorCapability) or capability.role != CapabilityRole.CONFIGURATION_VALIDATOR or capability.validator_id != "ConfigurationValidator":
            raise RecoveryEvidenceError("ConfigurationValidator requires a valid CONFIGURATION_VALIDATOR capability.")

        if isinstance(config_obj_or_id, str):
            prov = EvidenceProvenance(
                source_component="ConfigurationValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Raw string identity assertion rejected. Configuration authority requires EffectiveConfiguration with SealedObservation.",
            )
            return ConfigurationEvidence(valid=False, provenance=prov)

        if observation is None or producer_capability is None:
            prov = EvidenceProvenance(
                source_component="ConfigurationValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Missing SealedObservation or ProducerCapability for Configuration authority provenance.",
            )
            return ConfigurationEvidence(valid=False, provenance=prov)

        if not isinstance(producer_capability, ProducerCapability) or producer_capability.role != CapabilityRole.EFFECTIVE_CONFIGURATION:
            prov = EvidenceProvenance(
                source_component="ConfigurationValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Invalid or unauthorized ProducerCapability for Configuration.",
            )
            return ConfigurationEvidence(valid=False, provenance=prov)

        if not isinstance(observation, SealedObservation) or not observation.verify(producer_capability.authority_domain_id, CapabilityRole.EFFECTIVE_CONFIGURATION, session_id, producer_capability._role_key):
            prov = EvidenceProvenance(
                source_component="ConfigurationValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="SealedObservation verification failed for Configuration.",
            )
            return ConfigurationEvidence(valid=False, provenance=prov)

        from src.fractal_flow.config.config import EffectiveConfiguration
        if not isinstance(config_obj_or_id, EffectiveConfiguration):
            prov = EvidenceProvenance(
                source_component="ConfigurationValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Configuration object must be an instance of EffectiveConfiguration.",
            )
            return ConfigurationEvidence(valid=False, provenance=prov)

        config_id = config_obj_or_id.effective_config_id
        obs_payload = observation.frozen_payload

        if obs_payload.get("effective_config_id") != config_id:
            prov = EvidenceProvenance(
                source_component="ConfigurationValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Configuration object contradicts sealed observation payload.",
            )
            return ConfigurationEvidence(valid=False, provenance=prov)

        identity_matched = (expected_config_id is None) or (config_id == expected_config_id)
        valid = bool(config_id) and identity_matched

        prov = EvidenceProvenance(
            source_component="ConfigurationValidator",
            source_operation="validate",
            source_session=session_id,
            source_identity=config_id,
            result="SUCCESS" if valid else "FAILED",
            failure_reason=None if valid else "Configuration identity mismatch or empty config_id",
        )
        unsealed = ConfigurationEvidence(
            valid=valid,
            config_id=config_id,
            identity_matched=identity_matched,
            provenance=prov,
        )
        if valid:
            digest = compute_evidence_digest(unsealed)
            token = capability.sign_token(session_id, digest)
            return dataclasses.replace(unsealed, _authority_token=token)
        return unsealed


class ProtectiveMonitoringValidator:
    @staticmethod
    def validate(
        protective_subsystem: Any,
        session_id: str,
        capability: ValidatorCapability,
        observation: Optional[SealedObservation] = None,
        producer_capability: Optional[ProducerCapability] = None,
        authority_domain: Optional[AuthorityDomain] = None,
    ) -> ProtectiveMonitoringEvidence:
        if authority_domain:
            if not authority_domain.is_registered_producer(CapabilityRole.PROTECTIVE_MONITOR, protective_subsystem):
                prov = EvidenceProvenance(
                    source_component="ProtectiveMonitoringValidator",
                    source_operation="validate",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Unregistered ProtectiveMonitoringSubsystem instance in AuthorityDomain",
                )
                return ProtectiveMonitoringEvidence(valid=False, active=False, provenance=prov)
            if producer_capability and not authority_domain.is_canonical_producer_capability(CapabilityRole.PROTECTIVE_MONITOR, producer_capability):
                prov = EvidenceProvenance(
                    source_component="ProtectiveMonitoringValidator",
                    source_operation="validate",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Non-canonical ProducerCapability for Protective Monitoring in AuthorityDomain",
                )
                return ProtectiveMonitoringEvidence(valid=False, active=False, provenance=prov)
            if not authority_domain.is_canonical_validator_capability("ProtectiveMonitoringValidator", capability):
                prov = EvidenceProvenance(
                    source_component="ProtectiveMonitoringValidator",
                    source_operation="validate",
                    source_session=session_id,
                    result="FAILED",
                    failure_reason="Non-canonical ValidatorCapability for ProtectiveMonitoringValidator in AuthorityDomain",
                )
                return ProtectiveMonitoringEvidence(valid=False, active=False, provenance=prov)
        if not isinstance(capability, ValidatorCapability) or capability.role != CapabilityRole.PROTECTIVE_MONITORING_VALIDATOR or capability.validator_id != "ProtectiveMonitoringValidator":
            raise RecoveryEvidenceError("ProtectiveMonitoringValidator requires a valid PROTECTIVE_MONITORING_VALIDATOR capability.")

        if isinstance(protective_subsystem, bool):
            prov = EvidenceProvenance(
                source_component="ProtectiveMonitoringValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Raw boolean assertion rejected. Protective monitoring authority requires ProtectiveMonitoringSubsystem with SealedObservation.",
            )
            return ProtectiveMonitoringEvidence(valid=False, active=False, provenance=prov)

        if observation is None or producer_capability is None:
            prov = EvidenceProvenance(
                source_component="ProtectiveMonitoringValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Missing SealedObservation or ProducerCapability for Protective Monitoring authority provenance.",
            )
            return ProtectiveMonitoringEvidence(valid=False, active=False, provenance=prov)

        if not isinstance(producer_capability, ProducerCapability) or producer_capability.role != CapabilityRole.PROTECTIVE_MONITOR:
            prov = EvidenceProvenance(
                source_component="ProtectiveMonitoringValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Invalid or unauthorized ProducerCapability for Protective Monitoring.",
            )
            return ProtectiveMonitoringEvidence(valid=False, active=False, provenance=prov)

        if not isinstance(observation, SealedObservation) or not observation.verify(producer_capability.authority_domain_id, CapabilityRole.PROTECTIVE_MONITOR, session_id, producer_capability._role_key):
            prov = EvidenceProvenance(
                source_component="ProtectiveMonitoringValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="SealedObservation verification failed for Protective Monitoring.",
            )
            return ProtectiveMonitoringEvidence(valid=False, active=False, provenance=prov)

        if not isinstance(protective_subsystem, ProtectiveMonitoringSubsystem):
            prov = EvidenceProvenance(
                source_component="ProtectiveMonitoringValidator",
                source_operation="validate",
                source_session=session_id,
                result="FAILED",
                failure_reason="Subsystem must be an instance of ProtectiveMonitoringSubsystem.",
            )
            return ProtectiveMonitoringEvidence(valid=False, active=False, provenance=prov)

        obs_payload = observation.frozen_payload
        active = protective_subsystem.is_active() and obs_payload.get("active") is True

        prov = EvidenceProvenance(
            source_component="ProtectiveMonitoringValidator",
            source_operation="validate",
            source_session=session_id,
            result="SUCCESS" if active else "FAILED",
            failure_reason=None if active else "Protective monitoring is inactive or faulty",
        )
        unsealed = ProtectiveMonitoringEvidence(valid=active, active=active, provenance=prov)
        if active:
            digest = compute_evidence_digest(unsealed)
            token = capability.sign_token(session_id, digest)
            return dataclasses.replace(unsealed, _authority_token=token)
        return unsealed


class RecoveryEngine:
    """Manages system recovery lifecycle and gates strategic execution authorization based on verifiable sealed evidence capabilities."""

    def __init__(
        self,
        initial_state: RecoveryState = RecoveryState.NORMAL,
        validator_capabilities: Optional[Dict[str, ValidatorCapability]] = None,
        authority_domain: Optional[AuthorityDomain] = None,
    ) -> None:
        self.authority_domain: Optional[AuthorityDomain] = authority_domain
        self.state = initial_state
        self.strategic_authorization_enabled = (
            initial_state == RecoveryState.NORMAL
            and self.is_production_recovery
        )
        self.last_evidence: Optional[RecoveryEvidence] = None
        self.session_id: str = str(uuid.uuid4())
        self.validator_capabilities: Dict[str, ValidatorCapability] = validator_capabilities or (
            authority_domain._validator_capabilities.copy() if authority_domain else {}
        )

    @property
    def is_production_recovery(self) -> bool:
        """Returns True if and only if self.authority_domain is strictly identical (is) to the singular runtime production domain and finalized."""
        prod_bootstrap = TrustedRuntimeBootstrap._instance
        if prod_bootstrap is None or self.authority_domain is None:
            return False
        return (
            self.authority_domain is prod_bootstrap.domain
            and self.authority_domain.is_production
            and self.authority_domain._finalized
        )

    def trigger_system_restart(self) -> None:
        """Triggers recovery mode on system restart and disables strategic authorization."""
        self.state = RecoveryState.RECOVERY_REQUIRED
        self.strategic_authorization_enabled = False
        self.session_id = str(uuid.uuid4())

    def start_recovery(self) -> None:
        if self.state not in (RecoveryState.RECOVERY_REQUIRED, RecoveryState.RECONCILING):
            raise ValueError(f"Cannot start recovery from state '{self.state}'")
        self.state = RecoveryState.RECOVERING

    def start_reconciliation(self) -> None:
        if self.state not in (RecoveryState.RECOVERY_REQUIRED, RecoveryState.RECOVERING):
            raise ValueError(f"Cannot start reconciliation from state '{self.state}'")
        self.state = RecoveryState.RECONCILING

    def complete_recovery_with_evidence(self, evidence: RecoveryEvidence) -> None:
        """Completes recovery using verifiable evidence object containing sealed authority capability bundle."""
        if self.state not in (RecoveryState.RECONCILING, RecoveryState.RECOVERING):
            raise ValueError(f"Cannot complete recovery with evidence from state '{self.state}'")

        if not isinstance(evidence, RecoveryEvidence):
            self.state = RecoveryState.SAFE
            self.strategic_authorization_enabled = False
            raise RecoveryEvidenceError("Recovery evidence must be an instance of RecoveryEvidence")

        if not self.is_production_recovery:
            self.state = RecoveryState.SAFE
            self.strategic_authorization_enabled = False
            raise RecoveryEvidenceError("Strategic authorization requires genuine production authority root provenance. System placed in SAFE state.")

        val_caps = self.authority_domain._validator_capabilities if self.authority_domain else self.validator_capabilities
        if not evidence.has_valid_authority_capability(required_session=self.session_id, validator_capabilities=val_caps):
            self.state = RecoveryState.SAFE
            self.strategic_authorization_enabled = False
            raise RecoveryEvidenceError("Recovery evidence authority capability invalid or un-forged. System placed in SAFE state.")

        if not evidence.is_satisfactory(required_session=self.session_id):
            self.state = RecoveryState.SAFE
            self.strategic_authorization_enabled = False
            raise RecoveryEvidenceError(
                "Recovery evidence validation failed. System placed in SAFE state."
            )

        self.last_evidence = evidence
        self.state = RecoveryState.RECOVERY_COMPLETE
        self.strategic_authorization_enabled = True

    def complete_recovery(self, reconciliation_successful: bool) -> None:
        """Deprecated boolean recovery method. Places system in SAFE state or RECOVERY_COMPLETE without enabling strategic authorization."""
        if not reconciliation_successful:
            self.state = RecoveryState.SAFE
            self.strategic_authorization_enabled = False
            raise ValueError("Reconciliation failed. System placed in SAFE recovery state.")

        # Boolean shortcut alone CANNOT authorize strategic execution!
        self.state = RecoveryState.RECOVERY_COMPLETE
        self.strategic_authorization_enabled = False

    def can_authorize_strategic_action(self) -> bool:
        return (
            self.strategic_authorization_enabled
            and self.is_production_recovery
            and self.state in (RecoveryState.NORMAL, RecoveryState.RECOVERY_COMPLETE)
        )
