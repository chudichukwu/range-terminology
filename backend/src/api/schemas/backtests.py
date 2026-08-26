from pydantic import BaseModel, Field


class BacktestRunRequest(BaseModel):
    strategy_id: str = Field(min_length=4, max_length=64)
    start_ms: int = Field(gt=0)
    end_ms: int = Field(gt=0)
    initial_capital: float = Field(gt=0)
    fee_rate: float | None = Field(default=None, ge=0, lt=0.1)
    slippage_rate: float | None = Field(default=None, ge=0, lt=0.1)


class StatisticsOut(BaseModel):
    total_trades: int
    completed_trades: int
    wins: int
    losses: int
    breakevens: int
    win_rate: float | None = None
    average_r: float | None = None
    profit_factor: float | None = None
    expectancy: float | None = None
    total_realized_pnl: float = 0.0
    max_drawdown: float | None = None


class TradeOut(BaseModel):
    trade_id: str
    symbol: str
    direction: str
    quantity: float
    entry_price: float
    exit_price: float | None = None
    realized_pnl: float | None = None
    fees: float | None = None
    slippage: float | None = None
    realized_r: float | None = None
    result: str | None = None
    opened_at_ms: int
    closed_at_ms: int | None = None


class BacktestSummaryOut(BaseModel):
    run_id: str
    config_hash: str
    symbol: str
    timeframe: str
    period_start_ms: int
    period_end_ms: int
    initial_capital: float
    final_equity: float
    peak_equity: float
    max_drawdown: float
    total_trades: int
    owner_user_id: str | None = None
    created_at_ms: int


class BacktestDetailOut(BacktestSummaryOut):
    statistics: StatisticsOut
    trades: list[TradeOut] = []
    regime_counts: dict[str, int] = {}
    zone_counts: dict[str, int] = {}
