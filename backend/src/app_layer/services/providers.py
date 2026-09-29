"""Public data-source registry. No wallet, signing key or order access required."""

import time
from functools import lru_cache
from threading import RLock

from app_layer.errors import ValidationError
from app_layer.services.markets import MarketDataFacade
from exchange.adapters.ccxt.adapter import CcxtAdapter, CcxtAdapterConfig
from exchange.errors import ExchangeError, ExchangeErrorCode
from market_data.adapters.ccxt.adapter import ExchangeMarketDataProvider
from market_data.errors import MarketDataError, MarketDataErrorCode
from market_data.service import MarketDataService

SOURCES = {
    "hyperliquid": "Hyperliquid · perps & spot",
    "binanceusdm": "Binance · USDT perps",
    "binance": "Binance · spot",
}
_lock = RLock()


_metrics_lock = RLock()
_metrics = {}


def provider_status():
    with _metrics_lock:
        return [{"venue": venue, **_metrics.get(venue, {"requests": 0, "failures": 0,
                 "retries": 0, "last_success_ms": None, "last_error": None,
                 "last_latency_ms": None})} for venue in SOURCES]


class MonitoredProvider(ExchangeMarketDataProvider):
    def fetch_candles(self, symbol, timeframe, *, limit=200, since_ms=None):
        for attempt in range(2):
            started = time.monotonic()
            with _metrics_lock:
                stats = _metrics.setdefault(self.venue_id, dict(requests=0, failures=0,
                    retries=0, last_success_ms=None, last_error=None, last_latency_ms=None))
                stats["requests"] += 1
                stats["retries"] += int(attempt > 0)
            try:
                result = super().fetch_candles(symbol, timeframe, limit=limit, since_ms=since_ms)
                with _metrics_lock:
                    stats["last_success_ms"] = time.time_ns() // 1_000_000
                    stats["last_error"] = None
                return result
            except ExchangeError as exc:
                with _metrics_lock:
                    stats["failures"] += 1
                    stats["last_error"] = exc.code.value
                transient = exc.code in {ExchangeErrorCode.NETWORK_ERROR,
                    ExchangeErrorCode.RATE_LIMITED, ExchangeErrorCode.EXCHANGE_UNAVAILABLE}
                if transient and attempt == 0:
                    time.sleep(1)
                    continue
                message = ("Market unavailable: select the exact venue symbol "
                           "(perps may require :USDC)."
                           if exc.code == ExchangeErrorCode.MARKET_UNAVAILABLE
                           else f"Public data source failed: {exc.code.value}. Try again shortly.")
                raise MarketDataError(MarketDataErrorCode.PROVIDER_ERROR, message) from exc
            finally:
                with _metrics_lock:
                    stats["last_latency_ms"] = round((time.monotonic() - started) * 1000)


class PublicSource:
    def __init__(self, venue: str):
        self.lock = RLock()
        options = {"fetchMarkets": {"types": ["spot", "swap"]}} if venue == "hyperliquid" else {}
        self.adapter = CcxtAdapter(CcxtAdapterConfig(exchange_id=venue, options=options))
        self.service = MarketDataService(
            MonitoredProvider(self.adapter), cache_ttl_ms=60_000
        )
        self.facade = MarketDataFacade(self.service)


@lru_cache(maxsize=8)
def _source(venue: str) -> PublicSource:
    return PublicSource(venue)


def public_source(venue: str) -> PublicSource:
    if venue not in SOURCES:
        raise ValidationError("Choose a supported public data source")
    with _lock:
        return _source(venue)
