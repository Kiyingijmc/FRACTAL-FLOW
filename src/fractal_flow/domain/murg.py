"""User Market Universe, Session Context, Account Resource Context, and Resource Governor for FRACTAL FLOW MURG."""

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Dict, List, Optional, Set
from decimal import Decimal

from src.fractal_flow.domain.reason_codes import ReasonCode


@unique
class AssetClass(str, Enum):
    FX_MAJOR = "FX_MAJOR"
    FX_MINOR = "FX_MINOR"
    FX_CROSS = "FX_CROSS"
    METALS = "METALS"
    INDICES = "INDICES"
    CRYPTO = "CRYPTO"
    ENERGY = "ENERGY"
    COMMODITIES = "COMMODITIES"


@unique
class SymbolTradeMode(str, Enum):
    DISABLED = "DISABLED"
    LONG_ONLY = "LONG_ONLY"
    SHORT_ONLY = "SHORT_ONLY"
    CLOSE_ONLY = "CLOSE_ONLY"
    FULL = "FULL"


@unique
class UniverseMode(str, Enum):
    MANUAL = "MANUAL"
    SMART = "SMART"
    AUTO = "AUTO"
    HYBRID = "HYBRID"


@unique
class ResourceProfile(str, Enum):
    LIGHT = "LIGHT"
    BALANCED = "BALANCED"
    FULL = "FULL"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class InstrumentIdentity:
    canonical_id: str
    asset_class: AssetClass
    base_asset: str
    quote_asset: str
    broker: str
    broker_symbol: str


@dataclass
class InstrumentDescriptor:
    identity: InstrumentIdentity
    trade_mode: SymbolTradeMode
    execution_mode: str
    supported_order_types: List[str]
    supported_fill_policies: List[str]
    supported_time_in_force: List[str]
    tick_size: float
    point_size: float
    pip_size: float
    tick_value: float
    contract_size: float
    digits: int
    min_volume: float
    max_volume: float
    volume_step: float
    stops_level: float
    freeze_level: float
    is_tradable: bool = True
    synchronization_status: str = "SYNCHRONIZED"


class EligibilityEngine:
    """Evaluates broker instrument descriptors for system eligibility in a fail-closed manner."""

    @staticmethod
    def evaluate_eligibility(descriptor: InstrumentDescriptor) -> tuple[bool, List[ReasonCode]]:
        reasons: List[ReasonCode] = []

        if descriptor.trade_mode == SymbolTradeMode.DISABLED or not descriptor.is_tradable:
            reasons.append(ReasonCode.MARKET_INELIGIBLE)
            reasons.append(ReasonCode.MARKET_BROKER_UNSUPPORTED)

        if descriptor.min_volume <= 0.0 or descriptor.volume_step <= 0.0 or descriptor.min_volume > descriptor.max_volume:
            reasons.append(ReasonCode.BROKER_CONSTRAINT_FAILED)

        if descriptor.tick_size <= 0.0 or descriptor.contract_size <= 0.0:
            reasons.append(ReasonCode.BROKER_CONSTRAINT_FAILED)

        if descriptor.synchronization_status != "SYNCHRONIZED":
            reasons.append(ReasonCode.MARKET_DATA_UNAVAILABLE)

        is_eligible = len(reasons) == 0
        if is_eligible:
            reasons.append(ReasonCode.MARKET_ELIGIBLE)

        return is_eligible, reasons


class InstrumentCatalog:
    """Authoritative repository for discovered broker instrument descriptors."""

    def __init__(self) -> None:
        self._descriptors: Dict[str, InstrumentDescriptor] = {}
        self._broker_symbol_map: Dict[str, str] = {}

    def register_instrument(self, descriptor: InstrumentDescriptor) -> None:
        canonical_id = descriptor.identity.canonical_id
        self._descriptors[canonical_id] = descriptor
        self._broker_symbol_map[descriptor.identity.broker_symbol] = canonical_id

    def get_descriptor(self, canonical_id: str) -> Optional[InstrumentDescriptor]:
        return self._descriptors.get(canonical_id)

    def get_by_broker_symbol(self, broker_symbol: str) -> Optional[InstrumentDescriptor]:
        canonical_id = self._broker_symbol_map.get(broker_symbol)
        return self._descriptors.get(canonical_id) if canonical_id else None

    def list_all_canonical_ids(self) -> List[str]:
        return list(self._descriptors.keys())


@dataclass
class UserMarketUniverse:
    mode: UniverseMode = UniverseMode.SMART
    profile: ResourceProfile = ResourceProfile.BALANCED
    pinned_canonical_ids: Set[str] = field(default_factory=set)
    manual_canonical_ids: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class MarketSessionContext:
    session_state: str  # OPEN, CLOSED, BREAK, CLOSING
    broker_server_time_ns: int
    time_to_close_ns: int
    is_tradable_session: bool = True


@dataclass(frozen=True)
class AccountResourceContext:
    equity: float
    balance: float
    free_margin: float
    used_margin: float
    margin_utilization_pct: float
    drawdown_pct: float
    open_position_count: int
    pending_order_count: int
    resource_mode: str = "NORMAL"  # NORMAL, CONSTRAINED, CRITICAL

    @property
    def capacity_multiplier(self) -> float:
        if self.resource_mode == "CRITICAL" or self.margin_utilization_pct > 80.0:
            return 0.25
        elif self.resource_mode == "CONSTRAINED" or self.drawdown_pct > 10.0:
            return 0.50
        return 1.0


@dataclass
class MarketActivationDecision:
    canonical_id: str
    activation_state: str  # ACTIVE, WARMING, QUEUED, DORMANT, BLOCKED
    reason_codes: List[ReasonCode]
    priority_score: float
    entry_analysis_enabled: bool
    position_monitoring_enabled: bool
    pending_order_monitoring_enabled: bool


class ResourceGovernor:
    """Resource Governor enforcing hard active caps, warm-up queues, and hysteresis thresholds."""

    def __init__(
        self,
        max_active_symbols: int = 8,
        max_warming_symbols: int = 3,
        activation_threshold: float = 75.0,
        deactivation_threshold: float = 65.0,
    ) -> None:
        self.max_active_symbols = max_active_symbols
        self.max_warming_symbols = max_warming_symbols
        self.activation_threshold = activation_threshold
        self.deactivation_threshold = deactivation_threshold

        self.active_markets: Set[str] = set()
        self.warming_markets: Set[str] = set()
        self.queued_markets: List[str] = []

    def evaluate_universe_activation(
        self,
        catalog: InstrumentCatalog,
        universe: UserMarketUniverse,
        account_context: AccountResourceContext,
        session_context: MarketSessionContext,
        has_open_position: Dict[str, bool],
        has_pending_order: Dict[str, bool],
    ) -> Dict[str, MarketActivationDecision]:
        decisions: Dict[str, MarketActivationDecision] = {}

        # Adjust capacity using account capacity multiplier
        effective_active_cap = max(1, int(self.max_active_symbols * account_context.capacity_multiplier))

        # Candidate canonical IDs
        candidate_ids = catalog.list_all_canonical_ids()

        for canonical_id in candidate_ids:
            desc = catalog.get_descriptor(canonical_id)
            if not desc:
                continue

            # Hard eligibility check
            eligible, el_reasons = EligibilityEngine.evaluate_eligibility(desc)
            if not eligible:
                decisions[canonical_id] = MarketActivationDecision(
                    canonical_id=canonical_id,
                    activation_state="BLOCKED",
                    reason_codes=el_reasons,
                    priority_score=0.0,
                    entry_analysis_enabled=False,
                    position_monitoring_enabled=has_open_position.get(canonical_id, False),
                    pending_order_monitoring_enabled=has_pending_order.get(canonical_id, False),
                )
                continue

            # Check if session is closed
            if not session_context.is_tradable_session:
                decisions[canonical_id] = MarketActivationDecision(
                    canonical_id=canonical_id,
                    activation_state="DORMANT",
                    reason_codes=[ReasonCode.MARKET_SESSION_CLOSED],
                    priority_score=0.0,
                    entry_analysis_enabled=False,
                    # INVARIANT: Position and pending-order monitoring are NEVER disabled!
                    position_monitoring_enabled=has_open_position.get(canonical_id, False) or True,
                    pending_order_monitoring_enabled=has_pending_order.get(canonical_id, False) or True,
                )
                continue

            # Priority Scoring
            score = 50.0
            if canonical_id in universe.pinned_canonical_ids:
                score += 30.0
            if canonical_id in universe.manual_canonical_ids:
                score += 20.0

            # Activation decision based on cap and hysteresis
            is_currently_active = canonical_id in self.active_markets
            threshold = self.deactivation_threshold if is_currently_active else self.activation_threshold

            reasons: List[ReasonCode] = []
            if score >= threshold and len(self.active_markets) < effective_active_cap:
                self.active_markets.add(canonical_id)
                state = "ACTIVE"
                entry_analysis = True
                reasons.append(ReasonCode.MARKET_ACTIVE)
            else:
                if is_currently_active and score < self.deactivation_threshold:
                    self.active_markets.discard(canonical_id)
                state = "DORMANT"
                entry_analysis = False
                reasons.append(ReasonCode.MARKET_DORMANT)
                if len(self.active_markets) >= effective_active_cap:
                    reasons.append(ReasonCode.MARKET_SYMBOL_LIMIT)

            decisions[canonical_id] = MarketActivationDecision(
                canonical_id=canonical_id,
                activation_state=state,
                reason_codes=reasons,
                priority_score=score,
                entry_analysis_enabled=entry_analysis,
                # CRITICAL INVARIANT: Monitoring obligations remain protected!
                position_monitoring_enabled=has_open_position.get(canonical_id, False) or True,
                pending_order_monitoring_enabled=has_pending_order.get(canonical_id, False) or True,
            )

        return decisions
