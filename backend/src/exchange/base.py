"""ExchangePort: the venue-facing boundary every adapter implements.

The application layer depends only on this interface and the normalized
models — never on CCXT or any venue SDK. The interface is operation-shaped for
CEX-style venues; DEX adapters will implement their own sibling port sharing
these models/errors/capabilities rather than pretending AMMs are order books.
"""

from abc import ABC, abstractmethod

from exchange.capabilities import ExchangeCapabilities
from exchange.constraints import MarketConstraints
from exchange.models import (
    Balance,
    Candle,
    Order,
    OrderBook,
    OrderSide,
    OrderSubmission,
    OrderType,
    Position,
    Ticker,
)


class ExchangePort(ABC):
    """Normalized venue operations for market data, account data and orders."""

    @property
    @abstractmethod
    def venue_id(self) -> str:
        """Stable venue identifier, e.g. ``"binance"``."""

    @property
    @abstractmethod
    def capabilities(self) -> ExchangeCapabilities:
        """What this venue/adapter instance supports."""

    # ----- public market data -----

    @abstractmethod
    def get_ticker(self, symbol: str) -> Ticker:
        """Latest quote snapshot for ``symbol``."""

    @abstractmethod
    def get_order_book(self, symbol: str, depth: int = 50) -> OrderBook:
        """Order book snapshot with up to ``depth`` levels per side."""

    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> tuple[Candle, ...]:
        """Recent candles for ``symbol`` at ``timeframe`` (e.g. ``"1h"``)."""

    @abstractmethod
    def get_markets(self) -> tuple[str, ...]:
        """Symbols of all tradable markets on the venue."""

    @abstractmethod
    def get_market(self, symbol: str) -> MarketConstraints:
        """Per-market trading constraints as reported by the venue."""

    # ----- account data -----

    @abstractmethod
    def get_balances(self) -> tuple[Balance, ...]:
        """All non-zero asset balances."""

    @abstractmethod
    def get_positions(self) -> tuple[Position, ...]:
        """Open derivative/margin positions (empty on spot-only venues)."""

    @abstractmethod
    def get_open_orders(self, symbol: str | None = None) -> tuple[Order, ...]:
        """Open orders, optionally filtered to ``symbol``."""

    @abstractmethod
    def get_order(
        self,
        symbol: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> Order:
        """Fetch one order by venue id and/or client order id.

        Raises:
            ValueError: If neither id is provided.
            exchange.errors.ExchangeError: ORDER_NOT_FOUND when absent.
        """

    # ----- order operations -----

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: float | None = None,
        client_order_id: str | None = None,
    ) -> OrderSubmission:
        """Submit an order; never resubmitted automatically on uncertainty.

        Returns:
            An :class:`~exchange.models.OrderSubmission` whose state is
            ACCEPTED, REJECTED, or UNKNOWN (request possibly executed but
            unconfirmed). UNKNOWN is terminal here — reconciliation belongs to
            the future Execution phase.
        """

    @abstractmethod
    def cancel_order(
        self,
        symbol: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> Order:
        """Cancel one open order and return its final known state."""

    @abstractmethod
    def cancel_all_orders(self, symbol: str | None = None) -> int:
        """Cancel all open orders (optionally per symbol); return count."""
