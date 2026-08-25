"""Unit tests for the exchange layer.

All venue responses come from deterministic fakes — no network, no ccxt
install, no API keys, no real orders.
"""

import json
import os
import stat
from pathlib import Path

import pytest

from exchange import (
    Balance,
    Candle,
    CexCredentials,
    CredentialLookupError,
    ExchangeCapabilities,
    ExchangeError,
    ExchangeErrorCode,
    InMemoryCredentialStore,
    MarketConstraints,
    Order,
    OrderBook,
    OrderSide,
    OrderStatus,
    OrderSubmission,
    OrderType,
    Position,
    PositionDirection,
    SubmissionState,
    Ticker,
    UnsupportedOperationError,
    dump_cex_credentials,
    load_cex_credentials,
    redact,
)
from exchange.adapters.ccxt import CcxtAdapter, CcxtAdapterConfig
from exchange.adapters.ccxt.adapter import (
    normalize_balances,
    normalize_candles,
    normalize_market_constraints,
    normalize_order,
    normalize_order_book,
    normalize_position,
    normalize_ticker,
)
from exchange.base import ExchangePort

# ---------------------------------------------------------------------------
# Deterministic fake ccxt module
# ---------------------------------------------------------------------------


def build_fake_ccxt():
    """Build a fake ``ccxt`` module namespace with a realistic error hierarchy."""

    class BaseError(Exception):
        pass

    class NetworkError(BaseError):
        pass

    class RequestTimeout(NetworkError):
        pass

    class ExchangeNotAvailable(NetworkError):
        pass

    class DDoSProtection(NetworkError):
        pass

    class RateLimitExceeded(DDoSProtection):
        pass

    class AuthenticationError(BaseError):
        pass

    class PermissionDenied(AuthenticationError):
        pass

    class InsufficientFunds(BaseError):
        pass

    class InvalidOrder(BaseError):
        pass

    class OrderNotFound(InvalidOrder):
        pass

    class BadSymbol(BaseError):
        pass

    class NotSupported(BaseError):
        pass

    class BadResponse(BaseError):
        pass

    class FakeExchange:
        def __init__(self, params: dict) -> None:
            self.params = params
            self.has = {
                "spot": True,
                "swap": True,
                "future": False,
                "margin": False,
                "createMarketOrder": True,
                "createLimitOrder": True,
                "createStopOrder": False,
                "short": False,
            }
            self.markets = {"BTC/USDT": {"symbol": "BTC/USDT", "active": True}}
            self.sandbox_calls: list[bool] = []
            self.scripts: dict[str, object] = {}
            self.calls: list[tuple[str, tuple]] = []

        def set_sandbox_mode(self, enabled: bool) -> None:
            self.sandbox_calls.append(enabled)

        def _scripted(self, method: str, *args: object) -> object:
            self.calls.append((method, args))
            script = self.scripts.get(method)
            if isinstance(script, Exception):
                raise script
            return script

        def fetch_ticker(self, symbol: str) -> dict:
            result = self._scripted("fetch_ticker", symbol)
            assert isinstance(result, dict)
            return result

        def fetch_order_book(self, symbol: str, limit: int) -> dict:
            result = self._scripted("fetch_order_book", symbol, limit)
            assert isinstance(result, dict)
            return result

        def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> list:
            result = self._scripted("fetch_ohlcv", symbol, timeframe, limit)
            assert isinstance(result, list)
            return result

        def load_markets(self) -> dict:
            self.calls.append(("load_markets", ()))
            return self.markets

        def fetch_balance(self) -> dict:
            result = self._scripted("fetch_balance")
            assert isinstance(result, dict)
            return result

        def fetch_positions(self) -> list:
            result = self._scripted("fetch_positions")
            assert isinstance(result, list)
            return result

        def fetch_open_orders(self, symbol):  # type: ignore[no-untyped-def]
            return self._scripted("fetch_open_orders", symbol)

        def fetch_order(self, order_id: str, symbol: str, params=None):  # type: ignore[no-untyped-def]
            return self._scripted("fetch_order", order_id, symbol, params or {})

        def create_order(self, symbol, type, side, amount, price, params):  # type: ignore[no-untyped-def]
            return self._scripted("create_order", symbol, type, side, amount, price, params)

        def cancel_order(self, order_id: str, symbol: str) -> dict:
            result = self._scripted("cancel_order", order_id, symbol)
            assert isinstance(result, dict)
            return result

        def cancel_all_orders(self, symbol):  # type: ignore[no-untyped-def]
            result = self._scripted("cancel_all_orders", symbol)
            assert isinstance(result, list)
            return result

    namespace: dict[str, object] = {
        "BaseError": BaseError,
        "NetworkError": NetworkError,
        "RequestTimeout": RequestTimeout,
        "ExchangeNotAvailable": ExchangeNotAvailable,
        "DDoSProtection": DDoSProtection,
        "RateLimitExceeded": RateLimitExceeded,
        "AuthenticationError": AuthenticationError,
        "PermissionDenied": PermissionDenied,
        "InsufficientFunds": InsufficientFunds,
        "InvalidOrder": InvalidOrder,
        "OrderNotFound": OrderNotFound,
        "BadSymbol": BadSymbol,
        "NotSupported": NotSupported,
        "BadResponse": BadResponse,
        "FakeExchange": FakeExchange,
        "fakeex": FakeExchange,
    }
    return type("fake_ccxt_module", (), namespace)()


TICKER_RAW: dict = {
    "symbol": "BTC/USDT",
    "bid": 99.5,
    "ask": 100.5,
    "last": 100.0,
    "baseVolume": 1234.5,
    "timestamp": 1_700_000_000_000,
}

OHLCV_ROWS: list[list[float]] = [
    [1_700_000_000_000, 100.0, 101.0, 99.0, 100.5, 12.0],
    [1_700_003_600_000, 100.5, 102.0, 100.0, 101.5, 15.0],
]

ORDER_RAW: dict = {
    "id": "OID-7",
    "clientOrderId": "CID-9",
    "symbol": "BTC/USDT",
    "side": "buy",
    "type": "limit",
    "status": "open",
    "amount": 2.0,
    "filled": 0.5,
    "remaining": 1.5,
    "price": 100.0,
    "average": None,
    "fee": {"cost": 0.05},
    "timestamp": 1_700_000_000_000,
}


def make_adapter(**config_overrides: object) -> tuple[CcxtAdapter, object]:
    """Adapter wired to a fresh fake ccxt module and exchange instance."""
    module = build_fake_ccxt()
    exchange_instance = module.FakeExchange({})
    config_values: dict[str, object] = {"exchange_id": "fakeex"}
    config_values.update(config_overrides)
    config = CcxtAdapterConfig(**config_values)  # type: ignore[arg-type]

    original_init = module.FakeExchange.__init__

    def patched_init(self: object, params: dict) -> None:
        original_init(self, params)
        vars(self).update(vars(exchange_instance))

    module.FakeExchange.__init__ = patched_init  # type: ignore[method-assign]
    adapter = CcxtAdapter(config, ccxt_module=module)
    module.FakeExchange.__init__ = original_init  # type: ignore[method-assign]
    resolved = adapter._exchange  # noqa: SLF001 - test access to scripted fake
    return adapter, resolved


# ---------------------------------------------------------------------------
# Normalized model validation
# ---------------------------------------------------------------------------


class TestTickerModel:
    def test_full_ticker_accepted(self) -> None:
        ticker = Ticker("BTC/USDT", bid=99.5, ask=100.5, last=100.0, volume=1.0, timestamp=7)
        assert ticker.last == 100.0

    def test_optional_fields_default_to_none(self) -> None:
        ticker = Ticker("BTC/USDT")
        assert ticker.bid is None and ticker.ask is None and ticker.timestamp is None

    def test_crossed_book_rejected(self) -> None:
        with pytest.raises(ValueError, match="crossed"):
            Ticker("BTC/USDT", bid=101.0, ask=100.0)

    def test_negative_field_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            Ticker("BTC/USDT", volume=-1.0)


class TestCandleModel:
    def test_valid_candle(self) -> None:
        candle = Candle(1, open=10.0, high=11.0, low=9.0, close=10.5, volume=3.0)
        assert candle.close == 10.5

    def test_high_below_body_rejected(self) -> None:
        with pytest.raises(ValueError, match="incoherent"):
            Candle(1, open=10.0, high=9.0, low=8.0, close=10.5, volume=1.0)

    def test_non_integer_timestamp_rejected(self) -> None:
        with pytest.raises(ValueError, match="integer"):
            Candle(1.5, open=10.0, high=11.0, low=9.0, close=10.0, volume=1.0)


class TestOrderAndPositionModels:
    def test_remaining_quantity_computed(self) -> None:
        order = Order(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            status=OrderStatus.PARTIALLY_FILLED,
            quantity=2.0,
            filled_quantity=0.5,
        )
        assert order.remaining_quantity == pytest.approx(1.5)

    def test_filled_exceeding_quantity_rejected(self) -> None:
        with pytest.raises(ValueError, match="exceeds quantity"):
            Order(
                symbol="BTC/USDT",
                side=OrderSide.SELL,
                type=OrderType.MARKET,
                status=OrderStatus.FILLED,
                quantity=1.0,
                filled_quantity=1.5,
            )

    def test_position_requires_positive_quantity(self) -> None:
        with pytest.raises(ValueError, match="quantity"):
            Position(symbol="BTC/USDT", side=PositionDirection.LONG, quantity=0.0)

    def test_side_and_direction_enums_distinct(self) -> None:
        assert {s.value for s in OrderSide} == {"buy", "sell"}
        assert {d.value for d in PositionDirection} == {"long", "short"}


class TestBalanceModel:
    def test_effective_total_prefers_reported_total(self) -> None:
        balance = Balance("BTC", free=1.0, used=2.0, total=4.0)
        assert balance.effective_total == 4.0

    def test_effective_total_derived_when_missing(self) -> None:
        balance = Balance("BTC", free=1.0, used=2.0)
        assert balance.effective_total == pytest.approx(3.0)

    def test_effective_total_none_when_underivable(self) -> None:
        assert Balance("BTC").effective_total is None


class TestSubmissionModel:
    def test_unknown_state_representable(self) -> None:
        submission = OrderSubmission(state=SubmissionState.UNKNOWN, message="timeout")
        assert submission.state is SubmissionState.UNKNOWN
        assert submission.order is None


# ---------------------------------------------------------------------------
# Errors and capabilities
# ---------------------------------------------------------------------------


class TestErrors:
    def test_error_carries_code_and_venue_type(self) -> None:
        error = ExchangeError(
            ExchangeErrorCode.RATE_LIMITED,
            "slow down",
            venue_error_type="RateLimitExceeded",
        )
        assert "[rate_limited]" in str(error)
        assert "RateLimitExceeded" in str(error)

    def test_all_specified_codes_exist(self) -> None:
        expected = {
            "AUTHENTICATION_FAILED",
            "INVALID_ORDER",
            "INSUFFICIENT_BALANCE",
            "RATE_LIMITED",
            "MARKET_UNAVAILABLE",
            "ORDER_NOT_FOUND",
            "NETWORK_ERROR",
            "EXCHANGE_UNAVAILABLE",
            "UNSUPPORTED_OPERATION",
            "UNKNOWN",
        }
        assert {code.name for code in ExchangeErrorCode} >= expected

    def test_unsupported_operation_error_sets_capability(self) -> None:
        error = UnsupportedOperationError("stop_orders")
        assert error.code is ExchangeErrorCode.UNSUPPORTED_OPERATION
        assert error.metadata["capability"] == "stop_orders"


class TestCapabilities:
    def test_all_flags_default_false(self) -> None:
        caps = ExchangeCapabilities()
        for name in ("spot", "perpetuals", "market_orders", "websocket_private_data"):
            assert caps.supports(name) is False

    def test_supports_unknown_name_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown capability"):
            ExchangeCapabilities().supports("teleport")

    def test_require_raises_unsupported_operation(self) -> None:
        with pytest.raises(UnsupportedOperationError):
            ExchangeCapabilities().require("shorting")

    def test_with_flags_derives_copy(self) -> None:
        base = ExchangeCapabilities(spot=True)
        derived = base.with_flags(shorting=True)
        assert base.shorting is False
        assert derived.shorting is True and derived.spot is True


class TestMarketConstraints:
    def test_conversion_drops_exchange_only_fields(self) -> None:
        constraints = MarketConstraints(
            min_quantity=0.001,
            max_quantity=100.0,
            quantity_step=0.001,
            price_tick=0.01,
            min_notional=10.0,
            max_notional=1_000_000.0,
            max_leverage=20.0,
            supported_order_types=frozenset({OrderType.MARKET}),
        )
        risk_constraints = constraints.to_risk_constraints()
        assert risk_constraints.min_quantity == 0.001
        assert risk_constraints.max_leverage == 20.0
        assert not hasattr(risk_constraints, "max_notional")

    def test_empty_constraints_convert_to_none_risk_model(self) -> None:
        converted = MarketConstraints().to_risk_constraints()
        assert converted.min_quantity is None
        assert converted.price_tick is None


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


class TestInMemoryStore:
    def test_roundtrip_delete_and_exists(self) -> None:
        store = InMemoryCredentialStore()
        store.store("venue:binance", "s3cret")
        assert store.exists("venue:binance")
        assert store.retrieve("venue:binance") == "s3cret"
        store.delete("venue:binance")
        assert not store.exists("venue:binance")

    def test_missing_ref_raises_lookup_error(self) -> None:
        with pytest.raises(CredentialLookupError):
            InMemoryCredentialStore().retrieve("nope")


class TestKeychainStore:
    def make_fake_keyring_and_store(self) -> tuple[object, object]:
        recorded: dict[str, str] = {}

        class FakeKeyringModule:
            def set_password(self, service: str, ref: str, secret: str) -> None:
                recorded[f"{service}:{ref}"] = secret

            def get_password(self, service: str, ref: str) -> str | None:
                return recorded.get(f"{service}:{ref}")

            def delete_password(self, service: str, ref: str) -> None:
                recorded.pop(f"{service}:{ref}", None)

        return FakeKeyringModule(), recorded

    def test_keychain_roundtrip_via_injected_module(self) -> None:
        from exchange.credentials import KeychainCredentialStore

        fake_keyring, _recorded = self.make_fake_keyring_and_store()
        store = KeychainCredentialStore(service_name="test-svc", keyring_module=fake_keyring)
        store.store("binance:key", "abc")
        assert store.retrieve("binance:key") == "abc"
        assert store.exists("binance:key")
        store.delete("binance:key")
        assert not store.exists("binance:key")


class TestEncryptedFileStore:
    def make_store(self, tmp_path: Path) -> tuple[object, Path, bytes]:
        from cryptography.fernet import Fernet

        from exchange.credentials import EncryptedFileCredentialStore

        key = Fernet.generate_key()
        path = tmp_path / "creds.json"
        store = EncryptedFileCredentialStore(path, master_key_provider=lambda: key.decode())
        return store, path, key

    def test_encrypted_at_rest(self, tmp_path: Path) -> None:
        store, path, _key = self.make_store(tmp_path)
        secret = "super-secret-api-key-42"
        store.store("venue:secret", secret)
        raw_bytes = path.read_bytes()
        assert secret.encode() not in raw_bytes
        assert store.retrieve("venue:secret") == secret

    def test_file_permissions_owner_only(self, tmp_path: Path) -> None:
        store, path, _key = self.make_store(tmp_path)
        store.store("ref", "value")
        mode = stat.S_IMODE(os.stat(path).st_mode)
        assert mode == 0o600

    def test_wrong_master_key_cannot_decrypt(self, tmp_path: Path) -> None:
        from cryptography.fernet import InvalidToken

        store, path, _key = self.make_store(tmp_path)
        store.store("ref", "value")
        from cryptography.fernet import Fernet as FernetClass

        from exchange.credentials import EncryptedFileCredentialStore

        other = EncryptedFileCredentialStore(
            path, master_key_provider=lambda: FernetClass.generate_key().decode()
        )
        with pytest.raises(InvalidToken):
            other.retrieve("ref")

    def test_delete_removes_entry(self, tmp_path: Path) -> None:
        store, _path, _key = self.make_store(tmp_path)
        store.store("ref", "value")
        store.delete("ref")
        assert not store.exists("ref")
        assert not store.exists("missing")


class TestCredentialSerialization:
    def test_dump_load_roundtrip(self) -> None:
        credentials = CexCredentials(api_key="k", secret="s", password="p", uid="u")
        blob = dump_cex_credentials(credentials)
        loaded = load_cex_credentials(_store_from_blob(blob), "ref")
        assert loaded == credentials

    def test_repr_never_contains_secrets(self) -> None:
        credentials = CexCredentials(api_key="KEY123", secret="SECRET456")
        rendered = repr(credentials)
        assert "KEY123" not in rendered and "SECRET456" not in rendered

    def test_load_rejects_unknown_fields(self) -> None:
        blob = json.dumps({"api_key": "k", "hacker_field": "x"})
        with pytest.raises(ValueError, match="unexpected fields"):
            load_cex_credentials(_store_from_blob(blob), "ref")

    def test_load_rejects_non_json_blob(self) -> None:
        with pytest.raises(ValueError, match="not valid JSON"):
            load_cex_credentials(_store_from_blob("{not json"), "ref")

    def test_redact_masks_anything(self) -> None:
        assert redact("anything") == "[redacted]"


def _store_from_blob(blob: str) -> InMemoryCredentialStore:
    store = InMemoryCredentialStore()
    store.store("ref", blob)
    return store


def load_cex_credentials_from(store: InMemoryCredentialStore, ref: str):  # type: ignore[no-untyped-def]
    return load_cex_credentials(store, ref)


class TestLoadFromStore:
    def test_roundtrip_through_store(self) -> None:
        credentials = CexCredentials(api_key="k", secret="s")
        store = InMemoryCredentialStore()
        store.store("ref", dump_cex_credentials(credentials))
        assert load_cex_credentials_from(store, "ref").api_key == "k"


# ---------------------------------------------------------------------------
# ExchangePort contract
# ---------------------------------------------------------------------------


class MinimalFakePort(ExchangePort):
    """Structural check: the ABC can be implemented against our models only."""

    @property
    def venue_id(self) -> str:
        return "fake"

    @property
    def capabilities(self) -> ExchangeCapabilities:
        return ExchangeCapabilities()

    def get_market(self, symbol: str):  # type: ignore[no-untyped-def]
        return MarketConstraints()

    def get_ticker(self, symbol: str):  # type: ignore[no-untyped-def]
        return Ticker(symbol)

    def get_order_book(self, symbol: str, depth: int = 50):  # type: ignore[no-untyped-def]
        return OrderBook(symbol)

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200):  # type: ignore[no-untyped-def]
        return ()

    def get_markets(self):  # type: ignore[no-untyped-def]
        return ()

    def get_balances(self):  # type: ignore[no-untyped-def]
        return ()

    def get_positions(self):  # type: ignore[no-untyped-def]
        return ()

    def get_open_orders(self, symbol: str | None = None):  # type: ignore[no-untyped-def]
        return ()

    def get_order(self, symbol: str, order_id=None, client_order_id=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError()

    def place_order(self, symbol, side, order_type, quantity, price=None, client_order_id=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError()

    def cancel_order(self, symbol, order_id=None, client_order_id=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError()

    def cancel_all_orders(self, symbol: str | None = None):  # type: ignore[no-untyped-def]
        return 0


def test_exchange_port_contract_is_implementable() -> None:
    port = MinimalFakePort()
    assert port.venue_id == "fake"
    assert port.get_ticker("X/Y").symbol == "X/Y"


# ---------------------------------------------------------------------------
# CCXT normalization functions
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_ticker_normalization(self) -> None:
        ticker = normalize_ticker("BTC/USDT", TICKER_RAW)
        assert ticker.bid == 99.5 and ticker.ask == 100.5 and ticker.last == 100.0
        assert ticker.volume == 1234.5 and ticker.timestamp == 1_700_000_000_000

    def test_ticker_missing_optional_fields(self) -> None:
        ticker = normalize_ticker("BTC/USDT", {"symbol": "BTC/USDT"})
        assert ticker.bid is None and ticker.volume is None

    def test_ticker_degrades_bad_fields_to_none(self) -> None:
        ticker = normalize_ticker("BTC/USDT", {"bid": -5.0, "ask": "high"})
        assert ticker.bid is None and ticker.ask is None

    def test_candle_normalization(self) -> None:
        candles = normalize_candles(OHLCV_ROWS)
        assert len(candles) == 2
        assert candles[0].close == 100.5 and candles[1].high == 102.0

    def test_malformed_candle_row_raises(self) -> None:
        with pytest.raises(ExchangeError, match="Malformed OHLCV row"):
            normalize_candles([[1_700_000_000_000, 100.0, 101.0]])

    def test_non_list_ohlcv_raises(self) -> None:
        with pytest.raises(ExchangeError, match="expected list"):
            normalize_candles({"oops": True})

    def test_order_book_normalization(self) -> None:
        book = normalize_order_book(
            "BTC/USDT",
            {"bids": [[99.5, 1.0], [99.0, 2.0]], "asks": [[100.5, 1.5]], "timestamp": 5},
        )
        assert book.bids[0].price == 99.5 and len(book.asks) == 1 and book.timestamp == 5

    def test_balance_normalization_unions_assets(self) -> None:
        balances = normalize_balances(
            {"free": {"BTC": 1.0, "ETH": 2.0}, "used": {"BTC": 0.5}, "total": {"BTC": 1.5}}
        )
        by_asset = {b.asset: b for b in balances}
        assert by_asset["BTC"].free == 1.0 and by_asset["BTC"].used == 0.5
        assert by_asset["ETH"].total is None

    def test_order_normalization_partial_fill(self) -> None:
        order = normalize_order(ORDER_RAW)
        assert order.status is OrderStatus.PARTIALLY_FILLED
        assert order.remaining_quantity == pytest.approx(1.5)
        assert order.fee == pytest.approx(0.05)
        assert order.average_fill_price is None

    def test_order_closed_maps_to_filled(self) -> None:
        closed = {**ORDER_RAW, "status": "closed", "filled": 2.0}
        assert normalize_order(closed).status is OrderStatus.FILLED

    def test_order_bad_side_raises(self) -> None:
        with pytest.raises(ExchangeError, match="side/type"):
            normalize_order({**ORDER_RAW, "side": "sideways"})

    def test_position_normalization(self) -> None:
        position = normalize_position(
            {
                "symbol": "BTC/USDT:USDT",
                "side": "short",
                "contracts": 3.0,
                "entryPrice": 100.0,
                "markPrice": 98.0,
                "unrealizedPnl": 6.0,
                "leverage": 5.0,
                "liquidationPrice": 120.0,
                "timestamp": 9,
            }
        )
        assert position.side is PositionDirection.SHORT
        assert position.quantity == 3.0 and position.leverage == 5.0
        assert position.unrealized_pnl == pytest.approx(6.0)

    def test_market_constraints_extraction(self) -> None:
        caps = ExchangeCapabilities(market_orders=True, limit_orders=True, leverage=True)
        constraints = normalize_market_constraints(
            {
                "limits": {
                    "amount": {"min": 0.001, "max": 100.0},
                    "cost": {"min": 10.0},
                },
                "precision": {"price": 2, "amount": 3},
                "maxLeverage": 25,
            },
            caps,
        )
        assert constraints.min_quantity == 0.001 and constraints.max_quantity == 100.0
        assert constraints.quantity_step == pytest.approx(0.001)
        assert constraints.price_tick == pytest.approx(0.01)
        assert constraints.min_notional == 10.0
        assert constraints.max_leverage == 25.0
        assert OrderType.MARKET in constraints.supported_order_types
        assert OrderType.STOP_MARKET not in constraints.supported_order_types

    def test_market_constraints_absent_data_stays_none(self) -> None:
        constraints = normalize_market_constraints({}, ExchangeCapabilities())
        assert constraints.min_quantity is None
        assert constraints.price_tick is None
        assert constraints.supported_order_types == frozenset()


# ---------------------------------------------------------------------------
# CCXT adapter behaviors
# ---------------------------------------------------------------------------


class TestCcxtAdapterPublicData:
    def test_ticker_flow(self) -> None:
        adapter, fake = make_adapter()
        fake.scripts["fetch_ticker"] = TICKER_RAW
        expected = Ticker(
            "BTC/USDT", bid=99.5, ask=100.5, last=100.0, volume=1234.5, timestamp=1_700_000_000_000
        )
        assert adapter.get_ticker("BTC/USDT") == expected

    def test_ohlcv_flow(self) -> None:
        adapter, fake = make_adapter()
        fake.scripts["fetch_ohlcv"] = OHLCV_ROWS
        candles = adapter.get_ohlcv("BTC/USDT", "1h", limit=2)
        assert candles[1].open == 100.5

    def test_order_book_flow(self) -> None:
        adapter, fake = make_adapter()
        fake.scripts["fetch_order_book"] = {
            "bids": [[99.5, 1.0]],
            "asks": [[100.5, 2.0]],
            "timestamp": 3,
        }
        book = adapter.get_order_book("BTC/USDT", depth=10)
        assert book.asks[0].quantity == 2.0
        assert ("fetch_order_book", ("BTC/USDT", 10)) in fake.calls

    def test_market_symbols_and_constraints(self) -> None:
        adapter, _fake = make_adapter()
        assert "BTC/USDT" in adapter.get_markets()
        assert adapter.get_market("BTC/USDT").supported_order_types >= {OrderType.MARKET}

    def test_sandbox_mode_applied(self) -> None:
        adapter_config = CcxtAdapterConfig(exchange_id="fakeex", sandbox=True)
        module = build_fake_ccxt()
        holder = module.FakeExchange({})

        original = module.FakeExchange.__init__

        def init(self, params):  # type: ignore[no-untyped-def]
            original(self, params)
            vars(self).update(vars(holder))

        module.FakeExchange.__init__ = init  # type: ignore[method-assign]
        adapter = CcxtAdapter(adapter_config, ccxt_module=module)
        module.FakeExchange.__init__ = original  # type: ignore[method-assign]
        assert adapter._exchange.sandbox_calls == [True]  # noqa: SLF001

    def test_capabilities_detected_from_has_map(self) -> None:
        adapter, _fake = make_adapter()
        caps = adapter.capabilities
        assert caps.spot and caps.perpetuals and caps.market_orders
        assert caps.stop_orders is False and caps.futures is False
        assert caps.websocket_private_data is False

    def test_unknown_exchange_id_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown ccxt exchange id"):
            module = build_fake_ccxt()
            CcxtAdapter(CcxtAdapterConfig(exchange_id="doesnotexist"), ccxt_module=module)


class TestCcxtAdapterAccountData:
    def test_balances_flow(self) -> None:
        adapter, fake = make_adapter()
        fake.scripts["fetch_balance"] = {
            "free": {"BTC": 2.0},
            "used": {"BTC": 1.0},
            "total": {"BTC": 3.0},
        }
        balances = adapter.get_balances()
        assert balances[0].asset == "BTC" and balances[0].effective_total == 3.0

    def test_positions_flow(self) -> None:
        adapter, fake = make_adapter()
        fake.scripts["fetch_positions"] = [
            {"symbol": "BTC/USDT:USDT", "side": "long", "contracts": 1.0, "entryPrice": 90.0}
        ]
        positions = adapter.get_positions()
        assert positions[0].side is PositionDirection.LONG

    def test_get_order_by_id(self) -> None:
        adapter, fake = make_adapter()
        fake.scripts["fetch_order"] = ORDER_RAW
        order = adapter.get_order("BTC/USDT", order_id="OID-7")
        assert order.id == "OID-7" and order.status is OrderStatus.PARTIALLY_FILLED

    def test_get_order_without_ids_raises_value_error(self) -> None:
        adapter, _fake = make_adapter()
        with pytest.raises(ValueError, match="order_id or client_order_id"):
            adapter.get_order("BTC/USDT")


class TestCcxtAdapterOrders:
    def test_place_limit_order_success(self) -> None:
        adapter, fake = make_adapter()
        fake.scripts["create_order"] = ORDER_RAW
        submission = adapter.place_order(
            "BTC/USDT", OrderSide.BUY, OrderType.LIMIT, 2.0, price=100.0, client_order_id="CID-9"
        )
        assert submission.state is SubmissionState.ACCEPTED
        assert submission.order is not None and submission.order.id == "OID-7"

    def test_limit_order_without_price_raises(self) -> None:
        adapter, _fake = make_adapter()
        with pytest.raises(ValueError, match="require a price"):
            adapter.place_order("BTC/USDT", OrderSide.BUY, OrderType.LIMIT, 1.0)

    def test_unsupported_stop_order_blocked_by_capability(self) -> None:
        adapter, _fake = make_adapter()
        with pytest.raises(UnsupportedOperationError):
            adapter.place_order("BTC/USDT", OrderSide.SELL, OrderType.STOP_MARKET, 1.0)

    def test_network_timeout_yields_unknown_never_retry(self) -> None:
        adapter, fake = make_adapter()
        fake.scripts["create_order"] = build_fake_ccxt().RequestTimeout("connection lost")
        submission = adapter.place_order(
            "BTC/USDT", OrderSide.BUY, OrderType.MARKET, 1.0
        )
        assert submission.state is SubmissionState.UNKNOWN
        assert submission.metadata["reconciliation_required"] is True
        create_calls = [call for call in fake.calls if call[0] == "create_order"]
        assert len(create_calls) == 1

    def test_invalid_order_yields_rejected_submission(self) -> None:
        adapter, fake = make_adapter()
        fake.scripts["create_order"] = build_fake_ccxt().InvalidOrder("amount too small")
        submission = adapter.place_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, 0.0000001)
        assert submission.state is SubmissionState.REJECTED
        assert submission.metadata["error_code"] == ExchangeErrorCode.INVALID_ORDER.value

    def test_acceptance_without_order_id_is_unknown(self) -> None:
        adapter, fake = make_adapter()
        fake.scripts["create_order"] = {"symbol": "BTC/USDT", "side": "buy", "type": "market",
                                         "status": "open", "amount": 1.0}
        submission = adapter.place_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, 1.0)
        assert submission.state is SubmissionState.UNKNOWN

    def test_cancel_order_returns_final_state(self) -> None:
        adapter, fake = make_adapter()
        canceled = {**ORDER_RAW, "status": "canceled"}
        fake.scripts["cancel_order"] = canceled
        order = adapter.cancel_order("BTC/USDT", order_id="OID-7")
        assert order.status is OrderStatus.CANCELED

    def test_cancel_missing_order_raises_normalized_error(self) -> None:
        adapter, fake = make_adapter()
        fake.scripts["cancel_order"] = build_fake_ccxt().OrderNotFound("no such order")
        with pytest.raises(ExchangeError) as excinfo:
            adapter.cancel_order("BTC/USDT", order_id="ghost")
        assert excinfo.value.code is ExchangeErrorCode.ORDER_NOT_FOUND

    def test_cancel_all_counts(self) -> None:
        adapter, fake = make_adapter()
        fake.scripts["cancel_all_orders"] = [{"id": "a"}, {"id": "b"}]
        assert adapter.cancel_all_orders("BTC/USDT") == 2


class TestErrorNormalizationThroughAdapter:
    @pytest.mark.parametrize(
        ("exception_name", "expected_code"),
        [
            ("AuthenticationError", ExchangeErrorCode.AUTHENTICATION_FAILED),
            ("InsufficientFunds", ExchangeErrorCode.INSUFFICIENT_BALANCE),
            ("RateLimitExceeded", ExchangeErrorCode.RATE_LIMITED),
            ("BadSymbol", ExchangeErrorCode.MARKET_UNAVAILABLE),
            ("RequestTimeout", ExchangeErrorCode.NETWORK_ERROR),
            ("ExchangeNotAvailable", ExchangeErrorCode.EXCHANGE_UNAVAILABLE),
            ("NotSupported", ExchangeErrorCode.UNSUPPORTED_OPERATION),
            ("BadResponse", ExchangeErrorCode.UNKNOWN),
        ],
    )
    def test_market_data_errors_normalize(
        self, exception_name: str, expected_code: ExchangeErrorCode
    ) -> None:
        adapter, fake = make_adapter()
        fake.scripts["fetch_ticker"] = getattr(build_fake_ccxt(), exception_name)("boom")
        with pytest.raises(ExchangeError) as excinfo:
            adapter.get_ticker("BTC/USDT")
        assert excinfo.value.code is expected_code
        assert excinfo.value.venue_error_type == exception_name

    def test_secrets_scrubbed_from_error_messages(self) -> None:
        module = build_fake_ccxt()
        holder = module.FakeExchange({})
        original = module.FakeExchange.__init__

        def init(self, params):  # type: ignore[no-untyped-def]
            original(self, params)
            vars(self).update(vars(holder))

        module.FakeExchange.__init__ = init  # type: ignore[method-assign]
        config = CcxtAdapterConfig(
            exchange_id="fakeex",
            credentials=CexCredentials(api_key="APIKEY-XYZ", secret="SECRET-XYZ"),
        )
        adapter = CcxtAdapter(config, ccxt_module=module)
        module.FakeExchange.__init__ = original  # type: ignore[method-assign]
        adapter._exchange.scripts["fetch_ticker"] = module.AuthenticationError(
            "auth failed for key SECRET-XYZ on route /t"
        )
        with pytest.raises(ExchangeError) as excinfo:
            adapter.get_ticker("BTC/USDT")
        assert "SECRET-XYZ" not in str(excinfo.value)
        assert "[redacted]" in str(excinfo.value)

    def test_credentials_repr_masked_in_config(self) -> None:
        config = CcxtAdapterConfig(
            exchange_id="fakeex", credentials=CexCredentials(api_key="K", secret="S")
        )
        assert "K" not in repr(config) and "S" not in repr(config)


class TestDeterminism:
    def test_repeated_public_calls_identical(self) -> None:
        results = []
        for _ in range(2):
            adapter, fake = make_adapter()
            fake.scripts["fetch_ticker"] = TICKER_RAW
            fake.scripts["fetch_ohlcv"] = OHLCV_ROWS
            results.append(
                (
                    adapter.get_ticker("BTC/USDT"),
                    adapter.get_ohlcv("BTC/USDT", "1h"),
                    adapter.capabilities,
                )
            )
        assert results[0] == results[1]
