"""User Market Universe, Session Context, Account Resource Context, and Resource Governor for FRACTAL FLOW MURG."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, unique

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
    supported_order_types: list[str]
    supported_fill_policies: list[str]
    supported_time_in_force: list[str]
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
    def evaluate_eligibility(
        descriptor: InstrumentDescriptor,
    ) -> tuple[bool, list[ReasonCode]]:
        reasons: list[ReasonCode] = []

        if (
            descriptor.trade_mode == SymbolTradeMode.DISABLED
            or not descriptor.is_tradable
        ):
            reasons.append(ReasonCode.MARKET_INELIGIBLE)
            reasons.append(ReasonCode.MARKET_BROKER_UNSUPPORTED)

        if (
            descriptor.min_volume <= 0.0
            or descriptor.volume_step <= 0.0
            or descriptor.min_volume > descriptor.max_volume
        ):
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
        self._descriptors: dict[str, InstrumentDescriptor] = {}
        self._broker_symbol_map: dict[str, str] = {}

    def register_instrument(self, descriptor: InstrumentDescriptor) -> None:
        canonical_id = descriptor.identity.canonical_id
        self._descriptors[canonical_id] = descriptor
        self._broker_symbol_map[descriptor.identity.broker_symbol] = canonical_id

    def get_descriptor(self, canonical_id: str) -> InstrumentDescriptor | None:
        return self._descriptors.get(canonical_id)

    def get_by_broker_symbol(
        self, broker_symbol: str
    ) -> InstrumentDescriptor | None:
        canonical_id = self._broker_symbol_map.get(broker_symbol)
        return self._descriptors.get(canonical_id) if canonical_id else None

    def list_all_canonical_ids(self) -> list[str]:
        return list(self._descriptors.keys())


@dataclass
class UserMarketUniverse:
    mode: UniverseMode = UniverseMode.SMART
    profile: ResourceProfile = ResourceProfile.BALANCED
    pinned_canonical_ids: set[str] = field(default_factory=set)
    manual_canonical_ids: set[str] = field(default_factory=set)


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
class MarketActivationLease:
    canonical_id: str
    activated_at_ns: int
    minimum_dwell_until_ns: int
    lease_expiry_ns: int
    priority_score_snapshot: float


@dataclass
class MarketActivationDecision:
    canonical_id: str
    activation_state: str  # ACTIVE, WARMING, QUEUED, DORMANT, BLOCKED
    reason_codes: list[ReasonCode]
    priority_score: float
    entry_analysis_enabled: bool
    position_monitoring_enabled: bool
    pending_order_monitoring_enabled: bool


@dataclass(frozen=True)
class MarketProcessingCost:
    base_cost: float = 1.0
    active_timeframes_cost: float = 0.5
    indicator_cost: float = 0.2

    @property
    def total_cost(self) -> float:
        return float(
            Decimal(str(self.base_cost))
            + Decimal(str(self.active_timeframes_cost))
            + Decimal(str(self.indicator_cost))
        )


class ResourceGovernor:
    """Resource Governor enforcing hard active caps, warm-up queues, leases, and hysteresis thresholds."""

    def __init__(
        self,
        max_active_symbols: int = 8,
        max_warming_symbols: int = 3,
        activation_threshold: float = 75.0,
        deactivation_threshold: float = 65.0,
        minimum_dwell_ns: int = 60_000_000_000,  # 60s
    ) -> None:
        self.max_active_symbols = max_active_symbols
        self.max_warming_symbols = max_warming_symbols
        self.activation_threshold = activation_threshold
        self.deactivation_threshold = deactivation_threshold
        self.minimum_dwell_ns = minimum_dwell_ns

        self.active_markets: set[str] = set()
        self.warming_markets: set[str] = set()
        self.queued_markets: list[str] = []
        self.leases: dict[str, MarketActivationLease] = {}

    def evaluate_universe_activation(
        self,
        catalog: InstrumentCatalog,
        universe: UserMarketUniverse,
        account_context: AccountResourceContext,
        session_context: MarketSessionContext,
        has_open_position: dict[str, bool],
        has_pending_order: dict[str, bool],
        current_time_ns: int = 0,
    ) -> dict[str, MarketActivationDecision]:
        decisions: dict[str, MarketActivationDecision] = {}

        # Adjust capacity using account capacity multiplier
        effective_active_cap = max(
            1, int(self.max_active_symbols * account_context.capacity_multiplier)
        )

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
                    position_monitoring_enabled=has_open_position.get(
                        canonical_id, False
                    ),
                    pending_order_monitoring_enabled=has_pending_order.get(
                        canonical_id, False
                    ),
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
                    position_monitoring_enabled=has_open_position.get(
                        canonical_id, False
                    )
                    or True,
                    pending_order_monitoring_enabled=has_pending_order.get(
                        canonical_id, False
                    )
                    or True,
                )
                continue

            # Priority Scoring with Universe Mode Awareness
            score = 50.0
            if (
                universe.mode == UniverseMode.MANUAL
                and canonical_id not in universe.manual_canonical_ids
            ):
                score = 0.0
            else:
                if canonical_id in universe.pinned_canonical_ids:
                    score += 30.0
                if canonical_id in universe.manual_canonical_ids:
                    score += 20.0

            # Lease / Hysteresis check
            is_currently_active = canonical_id in self.active_markets
            lease = self.leases.get(canonical_id)

            if (
                is_currently_active
                and lease
                and current_time_ns < lease.minimum_dwell_until_ns
            ):
                # Protected by active lease dwell time
                state = "ACTIVE"
                entry_analysis = True
                reasons = [ReasonCode.MARKET_ACTIVE, ReasonCode.MARKET_PINNED]
            else:
                threshold = (
                    self.deactivation_threshold
                    if is_currently_active
                    else self.activation_threshold
                )

                reasons: list[ReasonCode] = []
                if (
                    score >= threshold
                    and len(self.active_markets) < effective_active_cap
                ):
                    self.active_markets.add(canonical_id)
                    self.leases[canonical_id] = MarketActivationLease(
                        canonical_id=canonical_id,
                        activated_at_ns=current_time_ns,
                        minimum_dwell_until_ns=current_time_ns + self.minimum_dwell_ns,
                        lease_expiry_ns=current_time_ns + self.minimum_dwell_ns * 5,
                        priority_score_snapshot=score,
                    )
                    state = "ACTIVE"
                    entry_analysis = True
                    reasons.append(ReasonCode.MARKET_ACTIVE)
                else:
                    if is_currently_active and score < self.deactivation_threshold:
                        self.active_markets.discard(canonical_id)
                        self.leases.pop(canonical_id, None)
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
                position_monitoring_enabled=has_open_position.get(canonical_id, False)
                or True,
                pending_order_monitoring_enabled=has_pending_order.get(
                    canonical_id, False
                )
                or True,
            )

        return decisions
