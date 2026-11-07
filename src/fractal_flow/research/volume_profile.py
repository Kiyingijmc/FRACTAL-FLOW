"""Deterministic, source-semantic Volume Profile reference calculation.

This module is intentionally isolated and analytical-only. It does not read
wall-clock time, mutate global state, persist snapshots, adapt configuration,
or influence strategy, risk, gate, order, or execution decisions.

The first implementation slice accepts normalized observations only. Feed-
specific adapters, incremental updates, persistence/recovery, and integrations
require separate contracts and are deliberately out of scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from enum import StrEnum
import hashlib
import json
from types import MappingProxyType
from typing import Iterable, Mapping


ZERO = Decimal("0")
ONE = Decimal("1")


class ProfileDomain(StrEnum):
    """Semantically distinct activity measures; never implicitly pool them."""

    FX_QUOTE_ACTIVITY = "FX_QUOTE_ACTIVITY"
    CFD_PROVIDER_ACTIVITY = "CFD_PROVIDER_ACTIVITY"
    FUTURES_EXECUTED_VOLUME = "FUTURES_EXECUTED_VOLUME"
    FUTURES_TRADE_COUNT = "FUTURES_TRADE_COUNT"
    FUTURES_BID_ASK_VOLUME = "FUTURES_BID_ASK_VOLUME"
    PRICE_VISIT_COUNT = "PRICE_VISIT_COUNT"
    BAR_VOLUME_ESTIMATE = "BAR_VOLUME_ESTIMATE"
    UNKNOWN_ACTIVITY_SEMANTICS = "UNKNOWN_ACTIVITY_SEMANTICS"


class QualityState(StrEnum):
    VALID = "VALID"
    WARMING_UP = "WARMING_UP"
    DEGRADED = "DEGRADED"
    INVALID = "INVALID"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"
    DISABLED = "DISABLED"


class VolumeProfileInputError(ValueError):
    """Input-contract violation with a stable machine-readable reason code."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _decimal_text(value: Decimal) -> str:
    """Canonical finite Decimal text without exponent/negative-zero ambiguity."""
    if not value.is_finite():
        raise ValueError("Non-finite Decimal cannot be serialized")
    if value == ZERO:
        return "0"
    normalized = value.normalize()
    return format(normalized, "f")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


_MAX_EXACT_DECIMAL_SPAN = 512
_MAX_DECIMAL_EXPONENT = 512
_MAX_DECIMAL_DIGITS = 512


def _decimal_magnitude_is_bounded(value: Decimal) -> bool:
    if not value.is_finite():
        return False
    parts = value.as_tuple()
    exponent = parts.exponent
    if not isinstance(exponent, int):
        return False
    return (
        len(parts.digits) <= _MAX_DECIMAL_DIGITS
        and abs(exponent) <= _MAX_DECIMAL_EXPONENT
        and (value == ZERO or abs(value.adjusted()) <= _MAX_DECIMAL_EXPONENT)
    )

def _require_bounded_decimal(value: Decimal, field_name: str) -> None:
    if not _decimal_magnitude_is_bounded(value):
        raise VolumeProfileInputError(
            "NUMERIC_MAGNITUDE_LIMIT_EXCEEDED",
            f"{field_name} exceeds the bounded Decimal magnitude/scale policy",
        )


def _exact_decimal_sum(values: Iterable[Decimal]) -> Decimal:
    """Sum finite Decimals exactly, independent of ambient context."""
    items = tuple(values)
    if not items:
        return ZERO
    if any(not value.is_finite() for value in items):
        raise VolumeProfileInputError("INVALID_WEIGHT", "cannot sum non-finite Decimal values")
    exponents: list[int] = []
    for value in items:
        exponent = value.as_tuple().exponent
        if not isinstance(exponent, int):
            raise VolumeProfileInputError("INVALID_WEIGHT", "non-integer Decimal exponent")
        exponents.append(exponent)
    min_exponent = min(exponents)
    max_adjusted = max((value.adjusted() for value in items if value != ZERO), default=0)
    if max_adjusted - min_exponent > _MAX_EXACT_DECIMAL_SPAN:
        raise VolumeProfileInputError(
            "NUMERIC_PRECISION_LIMIT_EXCEEDED",
            "Decimal exponent span exceeds the exact aggregation safety limit",
        )
    total = 0
    for value in items:
        parts = value.as_tuple()
        exponent = parts.exponent
        if not isinstance(exponent, int):
            raise VolumeProfileInputError("INVALID_WEIGHT", "non-integer Decimal exponent")
        coefficient = int("".join(str(digit) for digit in parts.digits) or "0")
        if parts.sign:
            coefficient = -coefficient
        total += coefficient * (10 ** (exponent - min_exponent))
    sign = 1 if total < 0 else 0
    digits = tuple(int(digit) for digit in str(abs(total))) if total else (0,)
    return Decimal((sign, digits, min_exponent))

def _exact_decimal_times_int(value: Decimal, multiplier: int) -> Decimal:
    """Multiply a finite Decimal by an integer without context rounding."""
    if not value.is_finite():
        raise VolumeProfileInputError("INVALID_WEIGHT", "cannot multiply non-finite Decimal values")
    parts = value.as_tuple()
    exponent = parts.exponent
    if not isinstance(exponent, int):
        raise VolumeProfileInputError("INVALID_WEIGHT", "non-integer Decimal exponent")
    coefficient = int("".join(str(digit) for digit in parts.digits) or "0")
    if parts.sign:
        coefficient = -coefficient
    product = coefficient * multiplier
    sign = 1 if product < 0 else 0
    digits = tuple(int(digit) for digit in str(abs(product))) if product else (0,)
    return Decimal((sign, digits, exponent))


@dataclass(frozen=True, slots=True)
class PriceGrid:
    """Instrument grid; prices must be exactly on this grid in the reference path."""

    tick_size: Decimal
    grid_origin: Decimal = ZERO
    price_unit: str = "price"

    def __post_init__(self) -> None:
        if not isinstance(self.tick_size, Decimal) or not self.tick_size.is_finite() or self.tick_size <= ZERO:
            raise VolumeProfileInputError("INVALID_TICK_SIZE", "tick_size must be a finite positive Decimal")
        if not isinstance(self.grid_origin, Decimal) or not self.grid_origin.is_finite():
            raise VolumeProfileInputError("INVALID_GRID_ORIGIN", "grid_origin must be a finite Decimal")
        _require_bounded_decimal(self.tick_size, "tick_size")
        _require_bounded_decimal(self.grid_origin, "grid_origin")
        if not self.price_unit.strip():
            raise VolumeProfileInputError("INVALID_PRICE_UNIT", "price_unit must be non-empty")

    def to_tick_index(self, price: Decimal) -> int:
        if not isinstance(price, Decimal) or not price.is_finite():
            raise VolumeProfileInputError("INVALID_PRICE", "price must be a finite Decimal")
        try:
            ticks = (price - self.grid_origin) / self.tick_size
        except (InvalidOperation, ZeroDivisionError) as exc:
            raise VolumeProfileInputError("INVALID_PRICE_GRID", "price cannot be represented on this grid") from exc
        integral = ticks.to_integral_value()
        if ticks != integral:
            raise VolumeProfileInputError(
                "OFF_GRID_PRICE",
                "price is not an exact multiple of tick_size from grid_origin: "
                f"price={price}, tick_size={self.tick_size}, grid_origin={self.grid_origin}",
            )
        return int(integral)

    def price_at_tick(self, tick_index: int) -> Decimal:
        return self.grid_origin + self.tick_size * tick_index


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """Identity fields that prevent semantically incompatible profile pooling."""

    source_id: str
    symbol: str
    domain: ProfileDomain
    activity_unit: str
    data_version: str
    calendar_id: str = "UNSPECIFIED"
    calendar_version: str = "UNSPECIFIED"
    contract_id: str = "UNSPECIFIED"
    venue: str = "UNSPECIFIED"

    def __post_init__(self) -> None:
        for field_name in ("source_id", "symbol", "activity_unit", "data_version"):
            if not getattr(self, field_name).strip():
                raise VolumeProfileInputError("INVALID_SOURCE_IDENTITY", f"{field_name} must be non-empty")
        if not isinstance(self.domain, ProfileDomain):
            raise VolumeProfileInputError("UNKNOWN_DOMAIN", "domain must be a ProfileDomain enum value")
        if self.domain is ProfileDomain.UNKNOWN_ACTIVITY_SEMANTICS:
            raise VolumeProfileInputError(
                "UNKNOWN_ACTIVITY_SEMANTICS",
                "unknown activity semantics cannot produce a valid profile",
            )
        if self.domain is ProfileDomain.FUTURES_EXECUTED_VOLUME and self.activity_unit.lower() in {
            "event", "events", "tick", "ticks", "quote_events", "trade_count"
        }:
            raise VolumeProfileInputError(
                "SEMANTIC_UNIT_MISMATCH",
                "executed-volume domain cannot use an event-count unit",
            )
        if self.domain is ProfileDomain.FX_QUOTE_ACTIVITY and self.activity_unit.lower() in {
            "contracts", "contract", "executed_volume", "traded_volume"
        }:
            raise VolumeProfileInputError(
                "SEMANTIC_UNIT_MISMATCH",
                "FX quote activity cannot be labeled as executed/traded volume",
            )


@dataclass(frozen=True, slots=True)
class ProfileEvent:
    """One normalized source observation, including event and availability times."""

    event_id: str
    source_id: str
    symbol: str
    domain: ProfileDomain
    event_time_ns: int
    available_at_ns: int
    source_sequence: int
    price: Decimal
    weight: Decimal

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.source_id.strip() or not self.symbol.strip():
            raise VolumeProfileInputError("INVALID_EVENT_IDENTITY", "event_id, source_id and symbol must be non-empty")
        if not isinstance(self.domain, ProfileDomain):
            raise VolumeProfileInputError("UNKNOWN_DOMAIN", "event domain must be a ProfileDomain enum value")
        if self.event_time_ns < 0 or self.available_at_ns < 0 or self.source_sequence < 0:
            raise VolumeProfileInputError("INVALID_EVENT_TIME", "timestamps and source_sequence must be non-negative")
        if self.available_at_ns < self.event_time_ns:
            raise VolumeProfileInputError("INVALID_EVENT_TIME", "available_at_ns cannot precede event_time_ns")
        if not isinstance(self.weight, Decimal) or not self.weight.is_finite() or self.weight < ZERO:
            raise VolumeProfileInputError("INVALID_WEIGHT", "weight must be a finite non-negative Decimal")
        _require_bounded_decimal(self.weight, "weight")
        if not isinstance(self.price, Decimal) or not self.price.is_finite():
            raise VolumeProfileInputError("INVALID_PRICE", "price must be a finite Decimal")
        _require_bounded_decimal(self.price, "price")

    def canonical_payload(self) -> tuple[object, ...]:
        return (
            self.source_id,
            self.symbol,
            self.domain.value,
            self.event_time_ns,
            self.available_at_ns,
            self.source_sequence,
            _decimal_text(self.price),
            _decimal_text(self.weight),
        )


@dataclass(frozen=True, slots=True)
class VolumeProfileConfig:
    """Immutable configuration snapshot for one reference calculation."""

    config_version: int = 1
    algorithm_version: str = "vp-reference-v1"
    feature_set_version: str = "vp-features-v1"
    enabled: bool = True
    window_start_ns: int = 0
    window_end_ns: int | None = None
    bin_ticks: int = 1
    anchor_tick_index: int = 0
    value_area_fraction: Decimal = Decimal("0.70")
    min_events: int = 1
    max_events: int = 100_000
    max_bins: int = 4_096

    def __post_init__(self) -> None:
        if self.config_version < 1:
            raise VolumeProfileInputError("INVALID_CONFIG_VERSION", "config_version must be >= 1")
        if not self.algorithm_version.strip() or not self.feature_set_version.strip():
            raise VolumeProfileInputError(
                "INVALID_CONFIG_IDENTITY",
                "algorithm and feature-set versions must be non-empty",
            )
        if self.window_start_ns < 0 or (self.window_end_ns is not None and self.window_end_ns < self.window_start_ns):
            raise VolumeProfileInputError("INVALID_WINDOW", "window boundaries must be non-negative and ordered")
        if not isinstance(self.bin_ticks, int) or isinstance(self.bin_ticks, bool) or self.bin_ticks <= 0:
            raise VolumeProfileInputError("INVALID_BIN_WIDTH", "bin_ticks must be a positive integer")
        if not isinstance(self.anchor_tick_index, int) or isinstance(self.anchor_tick_index, bool):
            raise VolumeProfileInputError("INVALID_BIN_ANCHOR", "anchor_tick_index must be an integer")
        if (
            not isinstance(self.value_area_fraction, Decimal)
            or not self.value_area_fraction.is_finite()
            or not (ZERO < self.value_area_fraction <= ONE)
        ):
            raise VolumeProfileInputError(
                "INVALID_VALUE_AREA_FRACTION",
                "value_area_fraction must be in (0, 1]",
            )
        _require_bounded_decimal(self.value_area_fraction, "value_area_fraction")
        if self.min_events < 1 or self.max_events < self.min_events or self.max_bins < 1:
            raise VolumeProfileInputError(
                "INVALID_RESOURCE_LIMIT",
                "require 1 <= min_events <= max_events and max_bins >= 1",
            )


@dataclass(frozen=True, slots=True)
class ProfileBin:
    bin_index: int
    lower_tick_index: int
    upper_tick_index_exclusive: int
    lower_price: Decimal
    upper_price_exclusive: Decimal
    representative_price: Decimal
    weight: Decimal


@dataclass(frozen=True, slots=True)
class VolumeProfileResult:
    """Immutable analytical result. It is not a regime or decision state."""

    quality_state: QualityState
    reason_codes: tuple[str, ...]
    source: SourceIdentity
    config: VolumeProfileConfig
    grid: PriceGrid
    watermark_ns: int
    included_event_count: int
    duplicate_event_count: int
    total_weight: Decimal
    occupied_bin_count: int
    bins: tuple[ProfileBin, ...]
    features: Mapping[str, Decimal | int | str | bool | None]
    fingerprint: str
    authority: str = "ANALYTICAL_ONLY"

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema": "vp-feature-envelope-v1",
            "authority": self.authority,
            "quality_state": self.quality_state.value,
            "reason_codes": list(self.reason_codes),
            "source": _source_payload(self.source),
            "config": _config_payload(self.config),
            "grid": {
                "tick_size": _decimal_text(self.grid.tick_size),
                "grid_origin": _decimal_text(self.grid.grid_origin),
                "price_unit": self.grid.price_unit,
            },
            "watermark_ns": self.watermark_ns,
            "included_event_count": self.included_event_count,
            "duplicate_event_count": self.duplicate_event_count,
            "total_weight": _decimal_text(self.total_weight),
            "occupied_bin_count": self.occupied_bin_count,
            "bins": [
                {
                    "bin_index": b.bin_index,
                    "lower_tick_index": b.lower_tick_index,
                    "upper_tick_index_exclusive": b.upper_tick_index_exclusive,
                    "lower_price": _decimal_text(b.lower_price),
                    "upper_price_exclusive": _decimal_text(b.upper_price_exclusive),
                    "representative_price": _decimal_text(b.representative_price),
                    "weight": _decimal_text(b.weight),
                }
                for b in self.bins
            ],
            "features": {
                key: _decimal_text(value) if isinstance(value, Decimal) else value
                for key, value in sorted(self.features.items())
            },
            "fingerprint": self.fingerprint,
        }


def _source_payload(source: SourceIdentity) -> dict[str, str]:
    return {
        "source_id": source.source_id,
        "symbol": source.symbol,
        "domain": source.domain.value,
        "activity_unit": source.activity_unit,
        "data_version": source.data_version,
        "calendar_id": source.calendar_id,
        "calendar_version": source.calendar_version,
        "contract_id": source.contract_id,
        "venue": source.venue,
    }


def _config_payload(config: VolumeProfileConfig) -> dict[str, object]:
    return {
        "config_version": config.config_version,
        "algorithm_version": config.algorithm_version,
        "feature_set_version": config.feature_set_version,
        "enabled": config.enabled,
        "window_start_ns": config.window_start_ns,
        "window_end_ns": config.window_end_ns,
        "bin_ticks": config.bin_ticks,
        "anchor_tick_index": config.anchor_tick_index,
        "value_area_fraction": _decimal_text(config.value_area_fraction),
        "min_events": config.min_events,
        "max_events": config.max_events,
        "max_bins": config.max_bins,
    }


def _event_sort_key(event: ProfileEvent) -> tuple[int, int, str]:
    return (event.event_time_ns, event.source_sequence, event.event_id)


def _result_fingerprint(payload_without_fingerprint: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json(payload_without_fingerprint)).hexdigest()


def _empty_result(
    source: SourceIdentity,
    config: VolumeProfileConfig,
    grid: PriceGrid,
    watermark_ns: int,
    quality: QualityState,
    reasons: tuple[str, ...],
    *,
    duplicate_count: int = 0,
) -> VolumeProfileResult:
    payload: dict[str, object] = {
        "schema": "vp-feature-envelope-v1",
        "authority": "ANALYTICAL_ONLY",
        "quality_state": quality.value,
        "reason_codes": list(reasons),
        "source": _source_payload(source),
        "config": _config_payload(config),
        "grid": {
            "tick_size": _decimal_text(grid.tick_size),
            "grid_origin": _decimal_text(grid.grid_origin),
            "price_unit": grid.price_unit,
        },
        "watermark_ns": watermark_ns,
        "included_event_count": 0,
        "duplicate_event_count": duplicate_count,
        "total_weight": "0",
        "occupied_bin_count": 0,
        "bins": [],
        "features": {},
    }
    fingerprint = _result_fingerprint(payload)
    return VolumeProfileResult(
        quality_state=quality,
        reason_codes=reasons,
        source=source,
        config=config,
        grid=grid,
        watermark_ns=watermark_ns,
        included_event_count=0,
        duplicate_event_count=duplicate_count,
        total_weight=ZERO,
        occupied_bin_count=0,
        bins=(),
        features=MappingProxyType({}),
        fingerprint=fingerprint,
    )


def calculate_volume_profile(
    events: Iterable[ProfileEvent],
    *,
    source: SourceIdentity,
    grid: PriceGrid,
    config: VolumeProfileConfig,
    watermark_ns: int,
) -> VolumeProfileResult:
    """Calculate a causal, deterministic profile from normalized observations.

    Only records with both event_time_ns <= watermark_ns and
    available_at_ns <= watermark_ns are eligible. Exact duplicate event IDs
    are idempotent; conflicting duplicate payloads fail closed by exception.
    Window end is inclusive. No silent off-grid normalization is performed.
    """
    if watermark_ns < 0:
        raise VolumeProfileInputError("INVALID_WATERMARK", "watermark_ns must be non-negative")
    if not config.enabled:
        return _empty_result(source, config, grid, watermark_ns, QualityState.DISABLED, ("FEATURE_DISABLED",))

    by_id: dict[str, ProfileEvent] = {}
    duplicate_count = 0
    eligible_input_count = 0
    for event in events:
        # Filter by causal availability/window BEFORE validation, deduplication,
        # and resource accounting. Future or out-of-window records must not
        # change a result for an earlier watermark.
        if (
            event.event_time_ns > watermark_ns
            or event.available_at_ns > watermark_ns
            or event.event_time_ns < config.window_start_ns
            or (config.window_end_ns is not None and event.event_time_ns > config.window_end_ns)
        ):
            continue
        eligible_input_count += 1
        if eligible_input_count > config.max_events:
            return _empty_result(
                source, config, grid, watermark_ns, QualityState.RESOURCE_LIMIT,
                ("MAX_EVENTS_EXCEEDED",), duplicate_count=duplicate_count,
            )
        if event.source_id != source.source_id or event.symbol != source.symbol or event.domain is not source.domain:
            raise VolumeProfileInputError(
                "SOURCE_IDENTITY_MISMATCH",
                "eligible event source/symbol/domain does not match SourceIdentity",
            )
        prior = by_id.get(event.event_id)
        if prior is not None:
            if prior.canonical_payload() != event.canonical_payload():
                raise VolumeProfileInputError(
                    "CONFLICTING_DUPLICATE_EVENT_ID",
                    f"event_id {event.event_id!r} was reused with a conflicting payload",
                )
            duplicate_count += 1
            continue
        by_id[event.event_id] = event

    eligible = sorted(by_id.values(), key=_event_sort_key)
    if len(eligible) < config.min_events:
        return _empty_result(
            source, config, grid, watermark_ns, QualityState.WARMING_UP,
            ("INSUFFICIENT_EVENTS",), duplicate_count=duplicate_count,
        )

    ticked: list[tuple[ProfileEvent, int, int]] = []
    weights_by_bin_parts: dict[int, list[Decimal]] = {}
    for event in eligible:
        tick_index = grid.to_tick_index(event.price)
        bin_index = (tick_index - config.anchor_tick_index) // config.bin_ticks
        ticked.append((event, tick_index, bin_index))
        # Zero-weight observations remain part of input lineage/counts but do
        # not create occupied histogram bins or consume the occupied-bin cap.
        if event.weight > ZERO:
            weights_by_bin_parts.setdefault(bin_index, []).append(event.weight)
        if len(weights_by_bin_parts) > config.max_bins:
            return _empty_result(
                source, config, grid, watermark_ns, QualityState.RESOURCE_LIMIT,
                ("MAX_BINS_EXCEEDED",), duplicate_count=duplicate_count,
            )

    weights_by_bin = {
        index: _exact_decimal_sum(parts)
        for index, parts in weights_by_bin_parts.items()
    }
    total_weight = _exact_decimal_sum(weights_by_bin.values())
    if total_weight <= ZERO:
        return _empty_result(
            source, config, grid, watermark_ns, QualityState.DEGRADED,
            ("ZERO_TOTAL_WEIGHT",), duplicate_count=duplicate_count,
        )

    bin_indices = sorted(weights_by_bin)
    weighted_tick_sum = _exact_decimal_sum(
        _exact_decimal_times_int(event.weight, tick) for event, tick, _ in ticked
    )
    weighted_mean_tick = weighted_tick_sum / total_weight
    max_weight = max(weights_by_bin.values())
    poc_candidates = [index for index in bin_indices if weights_by_bin[index] == max_weight]
    poc_index = min(
        poc_candidates,
        key=lambda index: (abs(_bin_center_tick(index, config) - weighted_mean_tick), index),
    )

    selected = {poc_index}
    accumulated = weights_by_bin[poc_index]
    with localcontext() as context:
        context.prec = max(
            28,
            len(total_weight.as_tuple().digits)
            + len(config.value_area_fraction.as_tuple().digits)
            + 4,
        )
        target_value_area_weight = config.value_area_fraction * total_weight
    while accumulated < target_value_area_weight:
        below = min(selected) - 1
        above = max(selected) + 1
        below_weight = weights_by_bin.get(below, ZERO)
        above_weight = weights_by_bin.get(above, ZERO)
        has_lower_mass = any(index < min(selected) and weight > ZERO for index, weight in weights_by_bin.items())
        has_upper_mass = any(index > max(selected) and weight > ZERO for index, weight in weights_by_bin.items())
        if below_weight == ZERO and above_weight == ZERO:
            if has_lower_mass:
                chosen = below
            elif has_upper_mass:
                chosen = above
            else:
                break
        elif above_weight > below_weight:
            chosen = above
        elif below_weight > above_weight:
            chosen = below
        else:
            # Frozen deterministic tie rule: prefer the lower adjacent bin.
            chosen = below
        selected.add(chosen)
        accumulated = _exact_decimal_sum(weights_by_bin.get(index, ZERO) for index in selected)
        continue
    # Include zero-weight gaps between the selected extremes in the VA interval.
    val_index = min(selected)
    vah_index = max(selected)
    lower_tick = config.anchor_tick_index + val_index * config.bin_ticks
    upper_tick_exclusive = config.anchor_tick_index + (vah_index + 1) * config.bin_ticks
    poc_lower_tick = config.anchor_tick_index + poc_index * config.bin_ticks
    poc_center_tick = Decimal(poc_lower_tick) + Decimal(config.bin_ticks) / Decimal(2)
    val_price = grid.price_at_tick(lower_tick)
    vah_price = grid.price_at_tick(upper_tick_exclusive)
    poc_price = grid.grid_origin + grid.tick_size * poc_center_tick

    profile_bins: list[ProfileBin] = []
    for index in bin_indices:
        lo_tick = config.anchor_tick_index + index * config.bin_ticks
        hi_tick = lo_tick + config.bin_ticks
        center_tick = Decimal(lo_tick) + Decimal(config.bin_ticks) / Decimal(2)
        profile_bins.append(ProfileBin(
            bin_index=index,
            lower_tick_index=lo_tick,
            upper_tick_index_exclusive=hi_tick,
            lower_price=grid.price_at_tick(lo_tick),
            upper_price_exclusive=grid.price_at_tick(hi_tick),
            representative_price=grid.grid_origin + grid.tick_size * center_tick,
            weight=weights_by_bin[index],
        ))

    shares = [weight / total_weight for weight in weights_by_bin.values() if weight > ZERO]
    hhi = sum((share * share for share in shares), ZERO)
    if len(shares) <= 1:
        entropy = ZERO
    else:
        with localcontext() as context:
            context.prec = 28
            entropy = -sum((share * share.ln() for share in shares), ZERO) / Decimal(len(shares)).ln()

    features: dict[str, Decimal | int | str | bool | None] = {
        "poc_bin_index": poc_index,
        "poc_price": poc_price,
        "poc_tie_count": len(poc_candidates),
        "poc_is_unique": len(poc_candidates) == 1,
        "val_price": val_price,
        "vah_price": vah_price,
        "value_area_width": vah_price - val_price,
        "value_area_fraction_requested": config.value_area_fraction,
        "value_area_fraction_achieved": accumulated / total_weight,
        "concentration_hhi": hhi,
        "normalized_entropy": entropy,
        "weighted_mean_price": grid.grid_origin + grid.tick_size * weighted_mean_tick,
        "source_domain": source.domain.value,
        "activity_unit": source.activity_unit,
        "window_start_ns": config.window_start_ns,
        "window_end_ns": config.window_end_ns if config.window_end_ns is not None else watermark_ns,
        "available_at_watermark_ns": watermark_ns,
    }

    reasons: list[str] = []
    quality = QualityState.VALID
    if duplicate_count:
        reasons.append("IDENTICAL_DUPLICATES_IGNORED")
    if len(eligible) < 2:
        reasons.append("LOW_SAMPLE_COUNT")
        quality = QualityState.WARMING_UP

    base_payload: dict[str, object] = {
        "schema": "vp-feature-envelope-v1",
        "authority": "ANALYTICAL_ONLY",
        "quality_state": quality.value,
        "reason_codes": reasons,
        "source": _source_payload(source),
        "config": _config_payload(config),
        "grid": {
            "tick_size": _decimal_text(grid.tick_size),
            "grid_origin": _decimal_text(grid.grid_origin),
            "price_unit": grid.price_unit,
        },
        "watermark_ns": watermark_ns,
        "included_event_count": len(eligible),
        "duplicate_event_count": duplicate_count,
        "total_weight": _decimal_text(total_weight),
        "occupied_bin_count": len(profile_bins),
        "bins": [
            {
                "bin_index": b.bin_index,
                "lower_tick_index": b.lower_tick_index,
                "upper_tick_index_exclusive": b.upper_tick_index_exclusive,
                "lower_price": _decimal_text(b.lower_price),
                "upper_price_exclusive": _decimal_text(b.upper_price_exclusive),
                "representative_price": _decimal_text(b.representative_price),
                "weight": _decimal_text(b.weight),
            }
            for b in profile_bins
        ],
        "features": {
            key: _decimal_text(value) if isinstance(value, Decimal) else value
            for key, value in sorted(features.items())
        },
    }
    fingerprint = _result_fingerprint(base_payload)
    return VolumeProfileResult(
        quality_state=quality,
        reason_codes=tuple(reasons),
        source=source,
        config=config,
        grid=grid,
        watermark_ns=watermark_ns,
        included_event_count=len(eligible),
        duplicate_event_count=duplicate_count,
        total_weight=total_weight,
        occupied_bin_count=len(profile_bins),
        bins=tuple(profile_bins),
        features=MappingProxyType(features),
        fingerprint=fingerprint,
    )


def _bin_center_tick(bin_index: int, config: VolumeProfileConfig) -> Decimal:
    return Decimal(config.anchor_tick_index + bin_index * config.bin_ticks) + Decimal(config.bin_ticks) / Decimal(2)


def profiles_comparable(left: VolumeProfileResult, right: VolumeProfileResult) -> bool:
    """Return whether profile weights share the minimum semantic/grid contract.

    Window and data versions may differ intentionally for temporal comparisons;
    source/domain/unit, symbol, calendar, contract and grid/bin semantics must match.
    """
    return (
        left.source.source_id == right.source.source_id
        and left.source.symbol == right.source.symbol
        and left.source.domain is right.source.domain
        and left.source.activity_unit == right.source.activity_unit
        and left.source.calendar_id == right.source.calendar_id
        and left.source.calendar_version == right.source.calendar_version
        and left.source.contract_id == right.source.contract_id
        and left.source.venue == right.source.venue
        and left.config.bin_ticks == right.config.bin_ticks
        and left.config.anchor_tick_index == right.config.anchor_tick_index
        and left.config.algorithm_version == right.config.algorithm_version
        and left.grid.tick_size == right.grid.tick_size
        and left.grid.grid_origin == right.grid.grid_origin
        and left.grid.price_unit == right.grid.price_unit
    )
