"""Provider adapters for the market data layer.

Each adapter implements :class:`market_data.base.MarketDataPort`. The CCXT
adapter composes the Phase 4 exchange port; future providers (e.g.
TradingView) implement :class:`MarketDataPort` directly without touching any
domain engine.
"""
