"""Normalized exchange capabilities.

Capability flags let the application inspect what a venue supports before
requesting an operation. No flag is assumed true by default — venues differ,
and DEXs in particular will not look like API-key REST exchanges.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from exchange.errors import UnsupportedOperationError

_CAPABILITY_NAMES: tuple[str, ...] = (
    "spot",
    "margin",
    "perpetuals",
    "futures",
    "market_orders",
    "limit_orders",
    "stop_orders",
    "shorting",
    "leverage",
    "websocket_market_data",
    "websocket_private_data",
)


@dataclass(frozen=True)
class ExchangeCapabilities:
    """Feature flags for one venue/adapter instance.

    Every field defaults to False; adapters set only flags they can honestly
    support. ``replace()`` composes derived instances from a base template.
    """

    spot: bool = False
    margin: bool = False
    perpetuals: bool = False
    futures: bool = False
    market_orders: bool = False
    limit_orders: bool = False
    stop_orders: bool = False
    shorting: bool = False
    leverage: bool = False
    websocket_market_data: bool = False
    websocket_private_data: bool = False

    def supports(self, capability: str) -> bool:
        """Return True when the named capability flag is enabled."""
        if capability not in _CAPABILITY_NAMES:
            raise ValueError(
                f"Unknown capability {capability!r}; valid: {_CAPABILITY_NAMES}"
            )
        return bool(getattr(self, capability))

    def require(self, capability: str) -> None:
        """Raise UnsupportedOperationError when the capability is missing."""
        if not self.supports(capability):
            raise UnsupportedOperationError(capability)

    def with_flags(self, **flags: bool) -> ExchangeCapabilities:
        """Derive a new instance with the given flags toggled."""
        return replace(self, **flags)


ALL_CAPABILITY_NAMES: tuple[str, ...] = _CAPABILITY_NAMES
