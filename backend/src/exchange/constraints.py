"""Market-level trading constraints produced by the exchange layer.

Extends the Phase 3 concept with venue-only fields (``max_notional``,
``supported_order_types``) and converts losslessly into
:class:`risk_engine.base.TradingConstraints` for the risk engine. Values the
venue does not report stay ``None`` — nothing is invented.
"""

from dataclasses import dataclass, field

from exchange.models import OrderType
from risk_engine.base import TradingConstraints


@dataclass(frozen=True)
class MarketConstraints:
    """Normalized per-market constraints as reported by a venue adapter."""

    min_quantity: float | None = None
    max_quantity: float | None = None
    quantity_step: float | None = None
    price_tick: float | None = None
    min_notional: float | None = None
    max_notional: float | None = None
    max_leverage: float | None = None
    supported_order_types: frozenset[OrderType] = field(default_factory=frozenset)

    def to_risk_constraints(self) -> TradingConstraints:
        """Project onto the Phase 3 risk-engine constraint model.

        ``max_notional`` and ``supported_order_types`` have no counterpart in
        the risk model and are intentionally dropped here.
        """
        return TradingConstraints(
            min_quantity=self.min_quantity,
            max_quantity=self.max_quantity,
            quantity_step=self.quantity_step,
            price_tick=self.price_tick,
            min_notional=self.min_notional,
            max_leverage=self.max_leverage,
        )
