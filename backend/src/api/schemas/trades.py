from pydantic import BaseModel


class TradeDetailOut(BaseModel):
    trade_id: str
    symbol: str
    timeframe: str | None = None
    direction: str
    quantity: float
    entry_price: float
    exit_price: float | None = None
    opened_at_ms: int
    closed_at_ms: int | None = None
    status: str
    realized_pnl: float | None = None
    fees: float | None = None
    slippage: float | None = None
    risk_amount: float | None = None
    realized_r: float | None = None
    result: str | None = None
    strategy_id: str | None = None
    config_hash: str | None = None
    context: dict[str, object] | None = None
