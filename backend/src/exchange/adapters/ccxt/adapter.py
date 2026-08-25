"""CCXT-backed implementation of :class:`~exchange.base.ExchangePort`.

CCXT is isolated entirely inside this adapter. The public surface speaks only
normalized domain models; venue exceptions are translated into
:class:`~exchange.errors.ExchangeError` with secrets scrubbed. The ``ccxt``
module is injected (or lazily imported) so tests run deterministically without
the library, credentials, or network.
"""

import importlib
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from exchange.base import ExchangePort
from exchange.capabilities import ExchangeCapabilities
from exchange.constraints import MarketConstraints
from exchange.credentials import CexCredentials
from exchange.errors import ExchangeError, ExchangeErrorCode
from exchange.models import (
    Balance,
    Candle,
    Order,
    OrderBook,
    OrderBookLevel,
    OrderSide,
    OrderStatus,
    OrderSubmission,
    OrderType,
    Position,
    PositionDirection,
    SubmissionState,
    Ticker,
)

_CCXT_ERROR_CODES: tuple[tuple[str, ExchangeErrorCode], ...] = (
    ("PermissionDenied", ExchangeErrorCode.AUTHENTICATION_FAILED),
    ("AuthenticationError", ExchangeErrorCode.AUTHENTICATION_FAILED),
    ("InsufficientFunds", ExchangeErrorCode.INSUFFICIENT_BALANCE),
    ("OrderNotFound", ExchangeErrorCode.ORDER_NOT_FOUND),
    ("RateLimitExceeded", ExchangeErrorCode.RATE_LIMITED),
    ("DDoSProtection", ExchangeErrorCode.RATE_LIMITED),
    ("MarketClosed", ExchangeErrorCode.MARKET_UNAVAILABLE),
    ("BadSymbol", ExchangeErrorCode.MARKET_UNAVAILABLE),
    ("NotSupported", ExchangeErrorCode.UNSUPPORTED_OPERATION),
    ("RequestTimeout", ExchangeErrorCode.NETWORK_ERROR),
    ("ExchangeNotAvailable", ExchangeErrorCode.EXCHANGE_UNAVAILABLE),
    ("NetworkError", ExchangeErrorCode.NETWORK_ERROR),
    ("BadResponse", ExchangeErrorCode.UNKNOWN),
    ("InvalidOrder", ExchangeErrorCode.INVALID_ORDER),
    ("BaseError", ExchangeErrorCode.UNKNOWN),
)

_STATUS_MAP: dict[str, OrderStatus] = {
    "open": OrderStatus.OPEN,
    "new": OrderStatus.OPEN,
    "closed": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELED,
    "cancelled": OrderStatus.CANCELED,
    "expired": OrderStatus.EXPIRED,
    "rejected": OrderStatus.REJECTED,
}


def _opt_float(raw: Mapping[str, object], key: str) -> float | None:
    """Extract an optional positive/zero number from a venue mapping."""
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) and result >= 0.0 else None


def _req_float(raw: Mapping[str, object], key: str) -> float:
    value = _opt_float(raw, key)
    if value is None or value <= 0.0:
        raise ValueError(f"Missing or invalid required field {key!r} in venue payload")
    return value


def _opt_str(raw: Mapping[str, object], key: str) -> str | None:
    value = raw.get(key)
    return str(value) if value is not None else None


def normalize_ticker(symbol: str, raw: Mapping[str, object]) -> Ticker:
    """Convert a CCXT ticker payload into a normalized :class:`Ticker`."""
    bid = _opt_float(raw, "bid")
    ask = _opt_float(raw, "ask")
    last = _opt_float(raw, "last") or _opt_float(raw, "close")
    volume = _opt_float(raw, "baseVolume") or _opt_float(raw, "quoteVolume")
    timestamp = raw.get("timestamp")
    ts = int(timestamp) if isinstance(timestamp, (int, float)) else None
    try:
        return Ticker(
            symbol=symbol, bid=bid, ask=ask, last=last, volume=volume, timestamp=ts
        )
    except ValueError as exc:
        raise ExchangeError(
            ExchangeErrorCode.UNKNOWN,
            f"Malformed ticker for {symbol}: {exc}",
            metadata={"symbol": symbol},
        ) from exc


def normalize_candles(rows: object) -> tuple[Candle, ...]:
    """Convert CCXT OHLCV rows (``[ts, o, h, l, c, v]``) into candles."""
    typed_rows: list[object]
    if not isinstance(rows, list):
        raise ExchangeError(ExchangeErrorCode.UNKNOWN, "Malformed OHLCV payload: expected list")
    typed_rows = rows
    candles: list[Candle] = []
    for index, row in enumerate(typed_rows):
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            raise ExchangeError(
                ExchangeErrorCode.UNKNOWN,
                f"Malformed OHLCV row at index {index}: expected 6 fields",
                metadata={"row_index": index},
            )
        try:
            candles.append(
                Candle(
                    timestamp=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )
        except (TypeError, ValueError) as exc:
            raise ExchangeError(
                ExchangeErrorCode.UNKNOWN,
                f"Malformed OHLCV row at index {index}: {exc}",
                metadata={"row_index": index},
            ) from exc
    return tuple(candles)


def normalize_order_book(symbol: str, raw: Mapping[str, object]) -> OrderBook:
    """Convert a CCXT order book payload into a normalized :class:`OrderBook`."""
    def levels(side_key: str) -> tuple[OrderBookLevel, ...]:
        raw_entries = raw.get(side_key)
        entries: list[object] = raw_entries if isinstance(raw_entries, list) else []
        out: list[OrderBookLevel] = []
        for entry in entries:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                price = float(entry[0])
                quantity = float(entry[1])
                out.append(OrderBookLevel(price=price, quantity=quantity))
        return tuple(out)

    timestamp = raw.get("timestamp")
    ts = int(timestamp) if isinstance(timestamp, (int, float)) else None
    try:
        return OrderBook(
            symbol=symbol, bids=levels("bids"), asks=levels("asks"), timestamp=ts
        )
    except ValueError as exc:
        raise ExchangeError(
            ExchangeErrorCode.UNKNOWN,
            f"Malformed order book for {symbol}: {exc}",
            metadata={"symbol": symbol},
        ) from exc


def normalize_balances(raw: Mapping[str, object]) -> tuple[Balance, ...]:
    """Convert a CCXT balance payload into per-asset balances."""
    raw_free = raw.get("free")
    raw_used = raw.get("used")
    raw_total = raw.get("total")
    free_map: Mapping[str, object] = raw_free if isinstance(raw_free, Mapping) else {}
    used_map: Mapping[str, object] = raw_used if isinstance(raw_used, Mapping) else {}
    total_map: Mapping[str, object] = raw_total if isinstance(raw_total, Mapping) else {}
    assets: set[str] = set()
    for section in (free_map, used_map, total_map):
        assets.update(str(k) for k in section)
    balances = [
        Balance(
            asset=asset,
            free=_opt_float(free_map, asset),
            used=_opt_float(used_map, asset),
            total=_opt_float(total_map, asset),
        )
        for asset in sorted(assets)
    ]
    return tuple(balances)


def normalize_order(raw: Mapping[str, object], fallback_symbol: str | None = None) -> Order:
    """Convert a CCXT order payload into a normalized :class:`Order`."""
    symbol = _opt_str(raw, "symbol") or fallback_symbol or ""
    side_name = (_opt_str(raw, "side") or "").lower()
    type_name = (_opt_str(raw, "type") or "").lower()
    status_name = (_opt_str(raw, "status") or "").lower()
    side = OrderSide.BUY if side_name == "buy" else OrderSide.SELL if side_name == "sell" else None
    order_type = next((t for t in OrderType if t.value == type_name), None)
    quantity = _req_float(raw, "amount")
    filled = _opt_float(raw, "filled") or 0.0
    remaining = _opt_float(raw, "remaining")
    if remaining is None:
        remaining = max(0.0, quantity - filled)
    if status_name in ("closed", "open") and 0.0 < filled < quantity:
        status = OrderStatus.PARTIALLY_FILLED
    elif status_name == "unknown":
        status = OrderStatus.UNKNOWN
    else:
        status = _STATUS_MAP.get(status_name, OrderStatus.UNKNOWN)
    fee_raw = raw.get("fee")
    fee_value = None
    if isinstance(fee_raw, Mapping):
        fee_value = _opt_float(fee_raw, "cost")
    elif fee_raw is not None:
        fee_value = _opt_float({"fee": fee_raw}, "fee")
    timestamp = raw.get("timestamp")
    ts = int(timestamp) if isinstance(timestamp, (int, float)) else None
    if side is None or order_type is None:
        raise ExchangeError(
            ExchangeErrorCode.UNKNOWN,
            f"Malformed order payload: unrecognizable side/type ({side_name!r}/{type_name!r})",
            metadata={"symbol": symbol},
        )
    try:
        return Order(
            id=_opt_str(raw, "id"),
            client_order_id=_opt_str(raw, "clientOrderId"),
            symbol=symbol,
            side=side,
            type=order_type,
            status=status,
            quantity=quantity,
            filled_quantity=filled,
            price=_opt_float(raw, "price"),
            average_fill_price=_opt_float(raw, "average"),
            fee=fee_value,
            timestamp=ts,
            metadata={"remaining_from_venue": remaining is not None},
        )
    except ValueError as exc:
        raise ExchangeError(
            ExchangeErrorCode.UNKNOWN,
            f"Malformed order payload: {exc}",
            metadata={"symbol": symbol},
        ) from exc


def normalize_position(raw: Mapping[str, object]) -> Position:
    """Convert a CCXT position payload into a normalized :class:`Position`."""
    symbol = _opt_str(raw, "symbol") or ""
    side_name = (_opt_str(raw, "side") or "").lower()
    direction = PositionDirection.LONG if side_name == "long" else PositionDirection.SHORT
    quantity = _req_float(raw, "contracts")
    timestamp = raw.get("timestamp")
    ts = int(timestamp) if isinstance(timestamp, (int, float)) else None
    try:
        return Position(
            symbol=symbol,
            side=direction,
            quantity=quantity,
            entry_price=_opt_float(raw, "entryPrice"),
            mark_price=_opt_float(raw, "markPrice"),
            unrealized_pnl=_signed_float(raw, "unrealizedPnl"),
            realized_pnl=_signed_float(raw, "realizedPnl"),
            leverage=_opt_float(raw, "leverage"),
            liquidation_price=_opt_float(raw, "liquidationPrice"),
            timestamp=ts,
        )
    except ValueError as exc:
        raise ExchangeError(
            ExchangeErrorCode.UNKNOWN,
            f"Malformed position payload for {symbol}: {exc}",
            metadata={"symbol": symbol},
        ) from exc


def _signed_float(raw: Mapping[str, object], key: str) -> float | None:
    value = raw.get(key)
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def normalize_market_constraints(
    raw: Mapping[str, object], capabilities: ExchangeCapabilities
) -> MarketConstraints:
    """Extract normalized constraints from a CCXT market description.

    CCXT precisions are decimal-place counts; ticks/steps become powers of ten.
    Absent venue data stays None — nothing invented.
    """
    raw_limits = raw.get("limits")
    limits: Mapping[str, object] = raw_limits if isinstance(raw_limits, Mapping) else {}
    raw_amount = limits.get("amount")
    amount_limits: Mapping[str, object] = (
        raw_amount if isinstance(raw_amount, Mapping) else {}
    )
    raw_cost = limits.get("cost")
    cost_limits: Mapping[str, object] = raw_cost if isinstance(raw_cost, Mapping) else {}

    def limit_value(section: Mapping[str, object], key: str) -> float | None:
        value = section.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        result = float(value)
        return result if math.isfinite(result) and result > 0.0 else None

    raw_precision = raw.get("precision")
    precision: Mapping[str, object] = (
        raw_precision if isinstance(raw_precision, Mapping) else {}
    )
    price_precision = precision.get("price")
    amount_precision = precision.get("amount")

    def decimals_to_step(value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return float(10**-value)

    supported: set[OrderType] = set()
    if capabilities.market_orders:
        supported.add(OrderType.MARKET)
    if capabilities.limit_orders:
        supported.add(OrderType.LIMIT)
    if capabilities.stop_orders:
        supported.update({OrderType.STOP_MARKET, OrderType.STOP_LIMIT})
    leverage_enabled = capabilities.leverage
    market_max_leverage = None
    if leverage_enabled:
        max_lev = raw.get("maxLeverage")
        if isinstance(max_lev, (int, float)) and not isinstance(max_lev, bool):
            lev = float(max_lev)
            market_max_leverage = lev if math.isfinite(lev) and lev > 0.0 else None
    return MarketConstraints(
        min_quantity=limit_value(amount_limits, "min"),
        max_quantity=limit_value(amount_limits, "max"),
        quantity_step=decimals_to_step(amount_precision),
        price_tick=decimals_to_step(price_precision),
        min_notional=limit_value(cost_limits, "min"),
        max_notional=None,
        max_leverage=market_max_leverage,
        supported_order_types=frozenset(supported),
    )


class CcxtExchangeLike(Protocol):
    """Structural subset of a ccxt exchange instance used by the adapter."""

    has: dict[str, bool]
    markets: dict[str, object]

    def set_sandbox_mode(self, enabled: bool) -> None: ...
    def fetch_ticker(self, symbol: str) -> dict[str, object]: ...
    def fetch_order_book(self, symbol: str, limit: int) -> dict[str, object]: ...
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> list[object]: ...
    def load_markets(self) -> object: ...
    def fetch_balance(self) -> dict[str, object]: ...
    def fetch_positions(self) -> list[object]: ...
    def fetch_open_orders(self, symbol: str | None) -> list[object]: ...
    def fetch_order(self, order_id: str, symbol: str) -> dict[str, object]: ...
    def create_order(
        self,
        symbol: str,
        type: str,
        side: str,
        amount: float,
        price: float | None,
        params: dict[str, object],
    ) -> dict[str, object]: ...
    def cancel_order(self, order_id: str, symbol: str) -> dict[str, object]: ...
    def cancel_all_orders(self, symbol: str | None) -> list[object]: ...


@dataclass(frozen=True)
class CcxtAdapterConfig:
    """Clean configuration object for the CCXT adapter.

    ``__repr__`` never exposes credential material.
    """

    exchange_id: str
    credentials: CexCredentials | None = None
    sandbox: bool = False
    timeout_ms: int = 15_000
    options: dict[str, object] = field(default_factory=dict)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        auth = "authenticated" if self.credentials else "public"
        return (
            f"CcxtAdapterConfig(exchange_id={self.exchange_id!r}, {auth}, "
            f"sandbox={self.sandbox})"
        )


class CcxtAdapter(ExchangePort):
    """Generic CCXT adapter: any ccxt-supported CEX, no venue hardcoding."""

    def __init__(
        self,
        config: CcxtAdapterConfig,
        ccxt_module: object | None = None,
    ) -> None:
        self._config = config
        self._ccxt_module = (
            ccxt_module if ccxt_module is not None else importlib.import_module("ccxt")
        )
        self._secrets: tuple[str, ...] = tuple(
            filter(None, config.credentials.as_secret_values()) if config.credentials else ()
        )
        klass = getattr(self._ccxt_module, config.exchange_id, None)
        if klass is None:
            raise ValueError(f"Unknown ccxt exchange id {config.exchange_id!r}")
        params: dict[str, object] = {
            "enableRateLimit": True,
            "timeout": config.timeout_ms,
            "options": dict(config.options),
        }
        if config.credentials is not None:
            params["apiKey"] = config.credentials.api_key
            params["secret"] = config.credentials.secret
            params["password"] = config.credentials.password
            params["uid"] = config.credentials.uid
        exchange_instance = klass(params)
        self._exchange = exchange_instance
        if config.sandbox:
            exchange_instance.set_sandbox_mode(True)
        self._capabilities = self._detect_capabilities()

    # ----- plumbing -----

    @property
    def venue_id(self) -> str:
        return self._config.exchange_id

    @property
    def capabilities(self) -> ExchangeCapabilities:
        return self._capabilities

    def _detect_capabilities(self) -> ExchangeCapabilities:
        has = getattr(self._exchange, "has", {}) or {}

        def flag(key: str) -> bool:
            return bool(has.get(key, False))

        return ExchangeCapabilities(
            spot=flag("spot"),
            margin=flag("margin"),
            perpetuals=flag("swap"),
            futures=flag("future"),
            market_orders=flag("createMarketOrder"),
            limit_orders=flag("createLimitOrder"),
            stop_orders=flag("createStopOrder") or flag("stopOrder"),
            shorting=flag("short"),
            leverage=flag("swap") or flag("future") or flag("margin"),
            websocket_market_data=False,
            websocket_private_data=False,
        )

    def _sanitize(self, text: object) -> str:
        message = str(text)
        for secret in self._secrets:
            if secret:
                message = message.replace(secret, "[redacted]")
        return message

    def _classify(self, error: Exception) -> ExchangeErrorCode:
        names = {cls.__name__ for cls in type(error).__mro__}
        for prefix, code in _CCXT_ERROR_CODES:
            if any(name.startswith(prefix) for name in names):
                return code
        return ExchangeErrorCode.UNKNOWN

    def _call(self, method: str, *args: object, **kwargs: object) -> object:
        try:
            return getattr(self._exchange, method)(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - normalized below by design
            if isinstance(exc, ExchangeError):
                raise
            raise ExchangeError(
                self._classify(exc),
                self._sanitize(exc),
                venue_error_type=type(exc).__name__,
                metadata={"venue": self.venue_id, "operation": method},
            ) from exc

    def _require_market_support(self, order_type: OrderType) -> None:
        capability_by_type = {
            OrderType.MARKET: "market_orders",
            OrderType.LIMIT: "limit_orders",
            OrderType.STOP_MARKET: "stop_orders",
            OrderType.STOP_LIMIT: "stop_orders",
        }
        self._capabilities.require(capability_by_type[order_type])

    # ----- public market data -----

    def _call_mapping(self, method: str, *args: object) -> Mapping[str, object]:
        result = self._call(method, *args)
        if not isinstance(result, Mapping):
            raise ExchangeError(
                ExchangeErrorCode.UNKNOWN,
                f"Malformed venue response from {method}: expected mapping",
                metadata={"venue": self.venue_id},
            )
        return result

    def get_ticker(self, symbol: str) -> Ticker:
        return normalize_ticker(symbol, self._call_mapping("fetch_ticker", symbol))

    def get_order_book(self, symbol: str, depth: int = 50) -> OrderBook:
        return normalize_order_book(symbol, self._call_mapping("fetch_order_book", symbol, depth))

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> tuple[Candle, ...]:
        return normalize_candles(self._call("fetch_ohlcv", symbol, timeframe, limit))

    def get_markets(self) -> tuple[str, ...]:
        self._call("load_markets")
        raw_markets = getattr(self._exchange, "markets", None)
        markets: Mapping[str, object] = (
            raw_markets if isinstance(raw_markets, Mapping) else {}
        )
        return tuple(sorted(str(key) for key in markets))

    def get_market(self, symbol: str) -> MarketConstraints:
        self._call("load_markets")
        raw_markets = getattr(self._exchange, "markets", None)
        markets: Mapping[str, object] = (
            raw_markets if isinstance(raw_markets, Mapping) else {}
        )
        raw = markets.get(symbol)
        if raw is None or not isinstance(raw, Mapping):
            raise ExchangeError(
                ExchangeErrorCode.MARKET_UNAVAILABLE,
                f"Unknown market {symbol!r}",
                metadata={"venue": self.venue_id, "symbol": symbol},
            )
        return normalize_market_constraints(raw, self.capabilities)

    # ----- account data -----

    def _call_sequence(self, method: str, *args: object) -> list[Mapping[str, object]]:
        result = self._call(method, *args)
        if not isinstance(result, list):
            raise ExchangeError(
                ExchangeErrorCode.UNKNOWN,
                f"Malformed venue response from {method}: expected list",
                metadata={"venue": self.venue_id},
            )
        rows: list[Mapping[str, object]] = []
        for row in result:
            if not isinstance(row, Mapping):
                raise ExchangeError(
                    ExchangeErrorCode.UNKNOWN,
                    f"Malformed venue response from {method}: expected mapping rows",
                    metadata={"venue": self.venue_id},
                )
            rows.append(row)
        return rows

    def get_balances(self) -> tuple[Balance, ...]:
        return normalize_balances(self._call_mapping("fetch_balance"))

    def get_positions(self) -> tuple[Position, ...]:
        return tuple(
            normalize_position(row) for row in self._call_sequence("fetch_positions")
        )

    def get_open_orders(self, symbol: str | None = None) -> tuple[Order, ...]:
        return tuple(
            normalize_order(row, fallback_symbol=symbol)
            for row in self._call_sequence("fetch_open_orders", symbol)
        )

    def get_order(
        self,
        symbol: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> Order:
        if order_id is None and client_order_id is None:
            raise ValueError("get_order requires order_id or client_order_id")
        lookup_id = order_id if order_id is not None else client_order_id
        assert lookup_id is not None
        params: dict[str, object] = (
            {"clientOrderId": client_order_id} if client_order_id else {}
        )
        raw = self._call_mapping("fetch_order", lookup_id, symbol, params)
        return normalize_order(raw, fallback_symbol=symbol)

    # ----- order operations -----

    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: float | None = None,
        client_order_id: str | None = None,
    ) -> OrderSubmission:
        """Submit one order with strict unknown-state safety.

        Network timeouts during submission yield state UNKNOWN — the request
        may have executed. This method NEVER retries such submissions.
        """
        self._require_market_support(order_type)
        if order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and price is None:
            raise ValueError(f"{order_type.value} orders require a price")
        ccxt_type = "market" if order_type in (OrderType.MARKET, OrderType.STOP_MARKET) else "limit"
        params: dict[str, object] = {}
        if order_type in (OrderType.STOP_MARKET, OrderType.STOP_LIMIT):
            params["stopPrice"] = price
        if client_order_id is not None:
            params["clientOrderId"] = client_order_id
        try:
            raw = self._exchange.create_order(
                symbol, ccxt_type, side.value, quantity, price, params
            )
        except ExchangeError:
            raise
        except Exception as exc:  # noqa: BLE001 - classified below
            code = self._classify(exc)
            sanitized = self._sanitize(exc)
            if code in (ExchangeErrorCode.NETWORK_ERROR, ExchangeErrorCode.EXCHANGE_UNAVAILABLE):
                return OrderSubmission(
                    state=SubmissionState.UNKNOWN,
                    message=sanitized,
                    metadata={
                        "venue": self.venue_id,
                        "venue_error_type": type(exc).__name__,
                        "error_code": code.value,
                        "reconciliation_required": True,
                    },
                )
            return OrderSubmission(
                state=SubmissionState.REJECTED,
                message=sanitized,
                metadata={
                    "venue": self.venue_id,
                    "venue_error_type": type(exc).__name__,
                    "error_code": code.value,
                },
            )
        if not _opt_str(raw, "id"):
            return OrderSubmission(
                state=SubmissionState.UNKNOWN,
                message="Venue accepted the request but returned no order id",
                metadata={"reconciliation_required": True, "venue": self.venue_id},
            )
        order = normalize_order(raw, fallback_symbol=symbol)
        return OrderSubmission(state=SubmissionState.ACCEPTED, order=order)

    def cancel_order(
        self,
        symbol: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> Order:
        if order_id is None and client_order_id is None:
            raise ValueError("cancel_order requires order_id or client_order_id")
        lookup_id = order_id if order_id is not None else client_order_id
        assert lookup_id is not None
        raw = self._call("cancel_order", lookup_id, symbol)
        if isinstance(raw, Mapping) and raw:
            return normalize_order(raw, fallback_symbol=symbol)
        fetched = self._call_mapping("fetch_order", lookup_id, symbol, {})
        return normalize_order(fetched, fallback_symbol=symbol)

    def cancel_all_orders(self, symbol: str | None = None) -> int:
        rows = self._call_sequence("cancel_all_orders", symbol)
        return len(rows)


__all__ = [
    "CcxtAdapter",
    "CcxtAdapterConfig",
    "CcxtExchangeLike",
    "ExchangeError",
    "ExchangeErrorCode",
    "SubmissionState",
    "normalize_balances",
    "normalize_candles",
    "normalize_market_constraints",
    "normalize_order",
    "normalize_order_book",
    "normalize_position",
    "normalize_ticker",
]
