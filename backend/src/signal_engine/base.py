"""Signal domain primitives: direction/reason/policy enums and the Signal value type."""

from dataclasses import dataclass, field
from enum import Enum


class SignalDirection(Enum):
    """Trade direction implied by a signal evaluation."""

    LONG = "long"
    SHORT = "short"
    NONE = "none"


class SignalReason(Enum):
    """Why a signal was or was not produced.

    Setup reasons accompany actionable LONG/SHORT directions; the others
    accompany ``SignalDirection.NONE`` and explain the absence of a setup.
    """

    NON_TRADABLE_RANGE = "non_tradable_range"
    PRICE_OUTSIDE_RANGE = "price_outside_range"
    PRICE_MID_RANGE = "price_mid_range"
    CONFIRMATION_NOT_MET = "confirmation_not_met"
    SUPPORT_EDGE_SETUP = "support_edge_setup"
    RESISTANCE_EDGE_SETUP = "resistance_edge_setup"


class ConfirmationPolicy(Enum):
    """How the engine treats oscillator confirmation metadata.

    - ``REQUIRED``: actionable setups need an explicit true confirmation.
    - ``OPTIONAL``: confirmation is surfaced when present but never blocks.
    - ``IGNORED``: confirmation metadata is not read at all.
    """

    REQUIRED = "required"
    OPTIONAL = "optional"
    IGNORED = "ignored"


@dataclass(frozen=True)
class Signal:
    """Immutable result of one signal evaluation.

    Attributes:
        direction: LONG, SHORT, or NONE (no setup).
        reason: Machine-readable cause; setups carry ``SUPPORT_EDGE_SETUP`` /
            ``RESISTANCE_EDGE_SETUP``, non-setups carry the blocking reason.
        price: Market price that was evaluated.
        range_high: Upper bound of the evaluated range; ``None`` when the
            range had no meaningful bounds.
        range_low: Lower bound of the evaluated range; ``None`` when the
            range had no meaningful bounds.
        position_in_range: Normalized position ``(price - low) / width``;
            may fall outside ``[0, 1]`` when price is outside the range;
            ``None`` when undefined (non-tradable range).
        confidence: Heuristic ordinal score in ``[0, 1]`` combining range
            confidence with edge-zone depth. NOT a probability; carries no
            guarantee of profitability.
        confirmation: Oscillator confirmation value when it was read:
            ``True``/``False`` when present, ``None`` when absent or ignored.
        metadata: Evaluation context (policy, zones, oscillator value,
            underlying range info).
    """

    direction: SignalDirection
    reason: SignalReason
    price: float
    range_high: float | None = None
    range_low: float | None = None
    position_in_range: float | None = None
    confidence: float = 0.0
    confirmation: bool | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        """True when the signal proposes a trade direction."""
        return self.direction is not SignalDirection.NONE
