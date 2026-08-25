"""Infrastructure adapters for the exchange layer.

Each subpackage wraps one venue integration (CCXT today; DEX SDKs/RPC/wallet
signing in future phases) behind :class:`exchange.base.ExchangePort` or a
sibling port sharing the same normalized models.
"""
