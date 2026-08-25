"""Normalized, exchange-independent domain models.

Every model is a frozen dataclass built from adapter-normalized venue data.
Fields a particular market does not provide are Optional and left as None —
values are never invented. Order side (BUY/SELL) and position direction
(LONG/SHORT) are deliberately distinct enums.
"""

import math
from dataclasses import dataclass, field
from enum import Enum


class OrderSide(Enum):
    """Direction of an ORDER (not a position)."""

    BUY = "buy"
    SELL = "sell"


class PositionDirection(Enum):
    """Direction of a POSITION (not an order)."""

    LONG = "long"
    SHORT = "short"


class OrderType(Enum):
    """Order types supported across venues."""

    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"


class OrderStatus(Enum):
    """Normalized lifecycle status of an order."""

    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


def _set(instance: object, name: str, value: object) -> None:
    """Assign to a frozen dataclass field from within __post_init__."""
    object.__setattr__(instance, name, value)


def _optional_number(value: object, name: str, *, allow_zero: bool = False) -> float | None:
    """Coerce an optional numeric model field; reject non-finite numbers."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number, got {type(value).__name__}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite, got {result}")
    if result < 0.0 or (result == 0.0 and not allow_zero):
        raise ValueError(f"{name} must be non-negative, got {result}")
    return result


def _required_positive(value: object, name: str) -> float:
    """Require a finite positive number for a mandatory model field."""
    result = _optional_number(value, name)
    if result is None or result <= 0.0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return result


@dataclass(frozen=True)
class Ticker:
    """Latest quote snapshot for one symbol."""

    symbol: str
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: float | None = None
    timestamp: int | None = None

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Ticker.symbol must be non-empty")
        _set(self, "bid", _optional_number(self.bid, "Ticker.bid"))
        _set(self, "ask", _optional_number(self.ask, "Ticker.ask"))
        _set(self, "last", _optional_number(self.last, "Ticker.last"))
        _set(self, "volume", _optional_number(self.volume, "Ticker.volume", allow_zero=True))
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise ValueError(f"Ticker crossed book: bid {self.bid} > ask {self.ask}")


@dataclass(frozen=True)
class Candle:
    """One normalized OHLCV bar (ms epoch timestamp)."""

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if isinstance(self.timestamp, bool) or not isinstance(self.timestamp, int):
            raise ValueError("Candle.timestamp must be an integer ms epoch value")
        _set(self, "open", _required_positive(self.open, "Candle.open"))
        _set(self, "high", _required_positive(self.high, "Candle.high"))
        _set(self, "low", _required_positive(self.low, "Candle.low"))
        _set(self, "close", _required_positive(self.close, "Candle.close"))
        volume = _optional_number(self.volume, "Candle.volume", allow_zero=True)
        _set(self, "volume", 0.0 if volume is None else volume)
        body_high = max(self.open, self.close)
        body_low = min(self.open, self.close)
        if self.high < body_high or self.low > body_low:
            raise ValueError(
                f"Candle OHLC incoherent: high {self.high}, low {self.low}, "
                f"open {self.open}, close {self.close}"
            )


@dataclass(frozen=True)
class OrderBookLevel:
    """One price level in an order book."""

    price: float
    quantity: float

    def __post_init__(self) -> None:
        _set(self, "price", _required_positive(self.price, "OrderBookLevel.price"))
        _set(self, "quantity", _required_positive(self.quantity, "OrderBookLevel.quantity"))


@dataclass(frozen=True)
class OrderBook:
    """Snapshot of resting bids and asks for one symbol."""

    symbol: str
    bids: tuple[OrderBookLevel, ...] = ()
    asks: tuple[OrderBookLevel, ...] = ()
    timestamp: int | None = None

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("OrderBook.symbol must be non-empty")


@dataclass(frozen=True)
class Balance:
    """Per-asset account balance; components optional when unreported."""

    asset: str
    free: float | None = None
    used: float | None = None
    total: float | None = None

    def __post_init__(self) -> None:
        if not self.asset:
            raise ValueError("Balance.asset must be non-empty")
        _set(self, "free", _optional_number(self.free, "Balance.free", allow_zero=True))
        _set(self, "used", _optional_number(self.used, "Balance.used", allow_zero=True))
        _set(self, "total", _optional_number(self.total, "Balance.total", allow_zero=True))

    @property
    def effective_total(self) -> float | None:
        """Reported total, else free + used when both exist, else None."""
        if self.total is not None:
            return self.total
        if self.free is not None and self.used is not None:
            return self.free + self.used
        return None


@dataclass(frozen=True)
class Order:
    """Normalized order state; unknown venue details stay None."""

    symbol: str
    side: OrderSide
    type: OrderType
    status: OrderStatus
    quantity: float
    filled_quantity: float = 0.0
    id: str | None = None
    client_order_id: str | None = None
    price: float | None = None
    average_fill_price: float | None = None
    fee: float | None = None
    timestamp: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Order.symbol must be non-empty")
        _set(self, "quantity", _required_positive(self.quantity, "Order.quantity"))
        filled = _optional_number(
            self.filled_quantity, "Order.filled_quantity", allow_zero=True
        )
        _set(self, "filled_quantity", 0.0 if filled is None else filled)
        if self.filled_quantity > self.quantity:
            raise ValueError(
                f"Order filled {self.filled_quantity} exceeds quantity {self.quantity}"
            )
        _set(self, "price", _optional_number(self.price, "Order.price"))
        _set(
            self,
            "average_fill_price",
            _optional_number(self.average_fill_price, "Order.average_fill_price"),
        )
        _set(self, "fee", _optional_number(self.fee, "Order.fee", allow_zero=True))

    @property
    def remaining_quantity(self) -> float:
        """Quantity not yet filled."""
        return round(self.quantity - self.filled_quantity, 12)


class SubmissionState(Enum):
    """Outcome of an order submission attempt.

    ``UNKNOWN`` means the request may have reached the venue and executed even
    though no confirmation came back. It is terminal for this submission call:
    callers must NEVER resubmit blindly; reconciliation resolves it later.
    """

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class OrderSubmission:
    """Result of one place_order attempt."""

    state: SubmissionState
    order: Order | None = None
    message: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Position:
    """Normalized open position (derivatives/margin venues)."""

    symbol: str
    side: PositionDirection
    quantity: float
    entry_price: float | None = None
    mark_price: float | None = None
    unrealized_pnl: float | None = None
    realized_pnl: float | None = None
    leverage: float | None = None
    liquidation_price: float | None = None
    timestamp: int | None = None

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Position.symbol must be non-empty")
        _set(self, "quantity", _required_positive(self.quantity, "Position.quantity"))
        _set(self, "entry_price", _optional_number(self.entry_price, "Position.entry_price"))
        _set(self, "mark_price", _optional_number(self.mark_price, "Position.mark_price"))
        _set(self, "leverage", _optional_number(self.leverage, "Position.leverage"))
