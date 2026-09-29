from types import SimpleNamespace

import pytest

from app_layer.services.providers import MonitoredProvider, _metrics, provider_status
from exchange.errors import ExchangeError, ExchangeErrorCode
from market_data.errors import MarketDataError
from market_data.models import Timeframe
from test_api import auth_headers, bootstrap_owner, client, create_user  # noqa: F401


def test_transient_read_retries_once_and_records_outcome(monkeypatch):
    _metrics.clear()
    calls = []
    def fetch(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise ExchangeError(ExchangeErrorCode.NETWORK_ERROR, 'timeout')
        return ()
    monkeypatch.setattr('app_layer.services.providers.time.sleep', lambda _: None)
    p = MonitoredProvider(SimpleNamespace(venue_id='hyperliquid', get_ohlcv=fetch))
    assert p.fetch_candles('BTC/USDC:USDC', Timeframe.H1) == ()
    stats = provider_status()[0]
    assert stats['requests'] == 2 and stats['failures'] == 1 and stats['retries'] == 1
    assert stats['last_error'] is None and stats['last_success_ms'] is not None


def test_bad_symbol_is_not_retried():
    _metrics.clear()
    def fetch(*args, **kwargs):
        raise ExchangeError(ExchangeErrorCode.MARKET_UNAVAILABLE, 'bad symbol')
    p = MonitoredProvider(SimpleNamespace(venue_id='hyperliquid', get_ohlcv=fetch))
    with pytest.raises(MarketDataError, match='exact venue symbol'):
        p.fetch_candles('NEAR/USDC', Timeframe.H1)
    assert provider_status()[0]['requests'] == 1


def test_provider_stats_require_owner(client):  # noqa: F811
    assert client.get('/admin/providers').status_code == 401
    root = bootstrap_owner(client)
    user = create_user(client, root, 'test@example.com')
    assert client.get('/admin/providers', headers=auth_headers(user)).status_code == 403
    assert client.get('/admin/providers', headers=auth_headers(root)).status_code == 200
