"""Range-trading signal evaluation.

Consumes an already-approved :class:`~range_engine.base.RangeState` plus the
current market price and decides whether conditions form a range-trading
setup. Pure domain logic: no sizing, no risk, no execution, no I/O.
"""

import math
from collections.abc import Mapping

from range_engine.base import RangeState, get_choice, get_float
from signal_engine.base import ConfirmationPolicy, Signal, SignalDirection, SignalReason

_DEFAULT_EDGE_ZONE = 0.25


def _validate_price(price: object) -> float:
    """Validate that ``price`` is a finite real number."""
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        raise ValueError(f"price must be a real number, got {type(price).__name__}")
    result = float(price)
    if not math.isfinite(result):
        raise ValueError(f"price must be finite, got {result}")
    return result


def _validate_zone(name: str, value: float) -> float:
    """Validate one edge-zone fraction; zones must lie within (0, 0.5]."""
    if value <= 0.0 or value > 0.5:
        raise ValueError(f"Config key {name!r} must be within (0, 0.5], got {value}")
    return value


def _read_confirmation(range_state: RangeState) -> tuple[bool | None, bool]:
    """Read oscillator confirmation metadata.

    Returns:
        ``(value, present)`` where ``value`` is the boolean confirmation when a
        well-formed one exists (else ``None``) and ``present`` reports whether
        such a value was found at all. Malformed values count as absent.
    """
    raw = range_state.metadata.get("confirmation")
    if isinstance(raw, bool):
        return raw, True
    return None, False


class RangeSignalEngine:
    """Turns market price + RangeState into LONG/SHORT/NONE trading signals.

    Evaluation gates on ``RangeState.is_tradable`` — non-tradable ranges
    (degenerate structure, insufficient data, zero width) always yield a NONE
    signal regardless of price. For tradable ranges the engine computes
    ``position_in_range`` and classifies:

    - lower edge zone (``[0, lower_edge_zone]``) → potential LONG setup
    - upper edge zone (``[1 - upper_edge_zone, 1]``) → potential SHORT setup
    - middle of the range / outside of it → NONE

    Oscillator confirmation is read from ``range_state.metadata["confirmation"]``
    (produced by ``OscillatorConfirmedRangeDetector``) and treated purely as a
    confirmation layer, never as the range definition. Its handling follows the
    configured :class:`ConfirmationPolicy`.

    Signal confidence is a heuristic ordinal score: range confidence scaled by
    how close price sits to the boundary (deepest zone entry scores highest).
    It is not a probability and implies nothing about profitability.
    """

    def __init__(self, config: Mapping[str, object] | None = None) -> None:
        """Store and validate default configuration.

        Args:
            config: Same keys as accepted by :meth:`evaluate`; per-call config
                overrides these defaults.

        Raises:
            ValueError: On invalid configuration values.
        """
        self._config: dict[str, object] = dict(config or {})
        self._parse_config(self._config)

    @staticmethod
    def _parse_config(
        cfg: Mapping[str, object],
    ) -> tuple[float, float, ConfirmationPolicy]:
        """Validate and resolve zones plus confirmation policy from config."""
        lower_zone = _validate_zone(
            "lower_edge_zone", get_float(cfg, "lower_edge_zone", _DEFAULT_EDGE_ZONE)
        )
        upper_zone = _validate_zone(
            "upper_edge_zone", get_float(cfg, "upper_edge_zone", _DEFAULT_EDGE_ZONE)
        )
        if lower_zone + upper_zone > 1.0:
            raise ValueError(
                f"Edge zones must not overlap: lower ({lower_zone}) + upper ({upper_zone}) > 1"
            )
        policies = tuple(p.value for p in ConfirmationPolicy)
        policy = ConfirmationPolicy(get_choice(cfg, "confirmation_policy", policies))
        return lower_zone, upper_zone, policy

    def evaluate(
        self,
        price: float,
        range_state: RangeState,
        config: Mapping[str, object] | None = None,
    ) -> Signal:
        """Evaluate one market price against one detected range state.

        Args:
            price: Current/last market price; must be a finite number.
            range_state: Range detection result to consume.
            config: Optional per-call overrides of the constructor defaults.
                Supported keys: ``lower_edge_zone``, ``upper_edge_zone``
                (fractions of the width within ``(0, 0.5]``), and
                ``confirmation_policy`` (``"required" | "optional" |
                "ignored"``, default ``"optional"``).

        Returns:
            A single immutable :class:`Signal`. Market conditions meaning "no
            setup" produce NONE signals with an explanatory reason rather than
            exceptions.

        Raises:
            ValueError: On invalid price values or invalid configuration.
        """
        cfg: dict[str, object] = {**self._config, **dict(config or {})}
        validated_price = _validate_price(price)
        lower_zone, upper_zone, policy = self._parse_config(cfg)

        shared_metadata: dict[str, object] = {
            "range_mode": range_state.mode,
            "range_status": range_state.status.value,
            "confirmation_policy": policy.value,
            "lower_edge_zone": lower_zone,
            "upper_edge_zone": upper_zone,
        }
        bounds_high: float | None = self._finite_or_none(range_state.range_high)
        bounds_low: float | None = self._finite_or_none(range_state.range_low)

        if not range_state.is_tradable:
            return self._no_signal(
                validated_price,
                SignalReason.NON_TRADABLE_RANGE,
                bounds_high,
                bounds_low,
                None,
                {
                    **shared_metadata,
                    "range_reason": range_state.metadata.get("reason"),
                    "range_confidence": range_state.confidence,
                },
            )

        width = range_state.range_width
        position = (validated_price - range_state.range_low) / width
        if position < 0.0 or position > 1.0:
            return self._no_signal(
                validated_price,
                SignalReason.PRICE_OUTSIDE_RANGE,
                bounds_high,
                bounds_low,
                position,
                shared_metadata,
            )
        if position <= lower_zone:
            return self._edge_setup(
                SignalDirection.LONG,
                SignalReason.SUPPORT_EDGE_SETUP,
                validated_price,
                range_state,
                position,
                policy,
                depth=1.0 - position / lower_zone,
                shared_metadata=shared_metadata,
                bounds_high=bounds_high,
                bounds_low=bounds_low,
            )
        if position >= 1.0 - upper_zone:
            return self._edge_setup(
                SignalDirection.SHORT,
                SignalReason.RESISTANCE_EDGE_SETUP,
                validated_price,
                range_state,
                position,
                policy,
                depth=(position - (1.0 - upper_zone)) / upper_zone,
                shared_metadata=shared_metadata,
                bounds_high=bounds_high,
                bounds_low=bounds_low,
            )
        return self._no_signal(
            validated_price,
            SignalReason.PRICE_MID_RANGE,
            bounds_high,
            bounds_low,
            position,
            shared_metadata,
        )

    @staticmethod
    def _finite_or_none(value: float) -> float | None:
        """Convert possibly-nan bound values into optional floats."""
        return value if not math.isnan(value) else None

    def _confirmation_decision(
        self, range_state: RangeState, policy: ConfirmationPolicy
    ) -> tuple[bool | None, dict[str, object]]:
        """Resolve confirmation under the configured policy.

        Returns:
            ``(confirmation_for_signal, extra_metadata)``. ``None`` means no
            usable confirmation was read; policies decide whether that blocks
            the setup.
        """
        value, present = _read_confirmation(range_state)
        extra: dict[str, object] = {"confirmation_present": present}
        if policy is ConfirmationPolicy.IGNORED:
            extra["confirmation_source"] = "ignored"
            return None, extra
        extra["oscillator_value"] = range_state.metadata.get("oscillator_value")
        if not present:
            extra["confirmation_source"] = "missing"
            return None, extra
        extra["confirmation_source"] = "oscillator"
        return value, extra

    def _edge_setup(
        self,
        direction: SignalDirection,
        reason: SignalReason,
        validated_price: float,
        range_state: RangeState,
        position: float,
        policy: ConfirmationPolicy,
        depth: float,
        shared_metadata: dict[str, object],
        bounds_high: float | None,
        bounds_low: float | None,
    ) -> Signal:
        """Build an actionable setup, applying the confirmation policy gate.

        ``depth`` is the normalized proximity to the boundary (1.0 at the
        boundary itself, approaching 0.0 at the zone's inner edge).
        """
        confirmation, confirm_extra = self._confirmation_decision(range_state, policy)
        merged_metadata: dict[str, object] = {
            **shared_metadata,
            **confirm_extra,
            "zone_depth": round(min(1.0, max(0.0, depth)), 6),
            "range_confidence": range_state.confidence,
        }
        if policy is ConfirmationPolicy.REQUIRED and confirmation is not True:
            merged_metadata["blocked_by"] = "confirmation"
            return Signal(
                direction=SignalDirection.NONE,
                reason=SignalReason.CONFIRMATION_NOT_MET,
                price=validated_price,
                range_high=bounds_high,
                range_low=bounds_low,
                position_in_range=round(position, 4),
                confidence=0.0,
                confirmation=confirmation,
                metadata=merged_metadata,
            )
        strength = 0.5 + 0.5 * min(1.0, max(0.0, depth))
        confidence = round(min(1.0, max(0.0, range_state.confidence * strength)), 4)
        return Signal(
            direction=direction,
            reason=reason,
            price=validated_price,
            range_high=bounds_high,
            range_low=bounds_low,
            position_in_range=round(position, 4),
            confidence=confidence,
            confirmation=confirmation,
            metadata=merged_metadata,
        )

    @staticmethod
    def _no_signal(
        validated_price: float,
        reason: SignalReason,
        bounds_high: float | None,
        bounds_low: float | None,
        position: float | None,
        metadata: dict[str, object],
    ) -> Signal:
        """Build a NONE signal with diagnostic context."""
        return Signal(
            direction=SignalDirection.NONE,
            reason=reason,
            price=validated_price,
            range_high=bounds_high,
            range_low=bounds_low,
            position_in_range=None if position is None else round(position, 4),
            confidence=0.0,
            confirmation=None,
            metadata=metadata,
        )
