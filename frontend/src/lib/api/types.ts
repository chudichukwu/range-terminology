/**
 * Frontend API types — derived from backend contracts in backend/src/api/schemas/*
 * and backend/src/{range_engine,market_data,backtesting,persistence,app_layer}.
 *
 * These are display types. No domain calculations are reimplemented here;
 * values are rendered as received from the backend.
 */

// — Auth / Users —
export type Role = "user" | "owner";
export type UserOut = {
  id: string;
  email: string;
  role: Role;
  active: boolean;
  created_at_ms: number;
  updated_at_ms: number;
  last_login_at_ms: number | null;
};
export type TokenResponse = { access_token: string; token_type: "bearer"; user: UserOut };

// — Range / Regime — backend source of truth (must match DESIGN.md §6)
export type RangeStatus = "valid" | "degenerate" | "insufficient_data";
export type MarketRegime = "ranging" | "trending_up" | "trending_down" | "transitional" | "insufficient_data";

// — Watchlists —
export type Watchlist = { id: string; name: string; owner_user_id: string; created_at_ms: number; updated_at_ms: number };
export type WatchlistItem = {
  id: string;
  watchlist_id: string;
  symbol: string;
  venue_id: string;
  notes: string;
  sort_order: number;
  enabled: boolean;
  created_at_ms: number;
};

// — Strategies —
export type Strategy = {
  id: string;
  name: string;
  owner_user_id: string;
  payload: Record<string, unknown>;
  schema_version: string;
  active: boolean;
  created_at_ms: number;
  updated_at_ms: number;
};

// — Market data —
export type Timeframe = "1m" | "5m" | "15m" | "30m" | "1h" | "4h" | "1d";
export type MarketCandle = {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_closed: boolean;
};
export type CandleDataset = {
  symbol: string;
  timeframe: Timeframe;
  quality_issues: string[];
  candles: MarketCandle[];
};

// — Trades / Persistence —
export type TradeStatus = "open" | "closed";
export type TradeResult = "win" | "loss" | "breakeven";
export type StoredTrade = {
  trade_id: string;
  symbol: string;
  timeframe: string | null;
  direction: "long" | "short";
  quantity: number;
  entry_price: number;
  exit_price: number | null;
  opened_at_ms: number;
  closed_at_ms: number | null;
  status: TradeStatus;
  realized_pnl: number | null;
  fees: number | null;
  slippage: number | null;
  risk_amount: number | null;
  realized_r: number | null;
  result: TradeResult | null;
  strategy_id: string | null;
  config_hash: string | null;
};

// — Backtests — backend-provided (no frontend recomputation)
export type BacktestRunSummary = {
  run_id: string;
  config_hash: string;
  symbol: string;
  timeframe: string;
  period_start_ms: number;
  period_end_ms: number;
  initial_capital: number;
  final_equity: number;
  peak_equity: number;
  max_drawdown: number;
  total_trades: number;
  owner_user_id: string | null;
  created_at_ms: number;
};
export type BacktestStatistics = {
  total_trades: number;
  completed_trades: number;
  wins: number;
  losses: number;
  breakevens: number;
  win_rate: number | null;
  average_r: number | null;
  profit_factor: number | null;
  expectancy: number | null;
  total_realized_pnl: number;
  max_drawdown: number | null;
};
export type BacktestTrade = {
  trade_id: string;
  symbol: string;
  direction: string;
  quantity: number;
  entry_price: number;
  exit_price: number | null;
  realized_pnl: number | null;
  fees: number | null;
  slippage: number | null;
  realized_r: number | null;
  result: string | null;
  opened_at_ms: number;
  closed_at_ms: number | null;
};
export type EquityPoint = { timestamp_ms: number; equity: number; peak_equity: number; drawdown: number };
export type BacktestDetail = BacktestRunSummary & {
  statistics: BacktestStatistics;
  trades: BacktestTrade[];
  regime_counts: Record<string, number>;
  zone_counts: Record<string, number>;
  equity_curve: EquityPoint[];
  config: Record<string, unknown>;
  engine_version: string;
};

// — Exchange connections —
export type ExchangeConnection = {
  id: string;
  venue_id: string;
  display_name: string;
  status: string;
  sandbox: boolean;
  created_at_ms: number;
  updated_at_ms: number;
};

// — Admin —
export type SystemHealth = {
  status: string;
  schema_version: number;
  engine_versions: Record<string, string>;
  user_count: number;
  dataset_count: number;
  market_data_provider: string;
  time: number;
};
export type AuditEvent = {
  id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  timestamp_ms: number;
  outcome: string;
  metadata: Record<string, unknown>;
};

// — Pair analysis — backend-provided (analysis service)
export type RangeAnalysis = {
  high: number | null;
  low: number | null;
  width: number | null;
  status: RangeStatus;
  confidence: number;
  is_tradable: boolean;
  mode: string;
  metadata: Record<string, unknown>;
};
export type RegimeAnalysis = {
  value: MarketRegime;
  lookback: number;
  threshold: number;
  efficiency_ratio: number | null;
};
export type SignalDirection = "long" | "short" | "none";
export type SignalReason =
  | "non_tradable_range"
  | "price_outside_range"
  | "price_mid_range"
  | "confirmation_not_met"
  | "support_edge_setup"
  | "resistance_edge_setup";
export type SignalAnalysis = {
  direction: SignalDirection;
  reason: SignalReason;
  price: number | null;
  position_in_range: number | null;
  confidence: number;
  confirmation: boolean | null;
  confirmation_policy: string | null;
  range_high: number | null;
  range_low: number | null;
  metadata: Record<string, unknown>;
};
export type OscillatorAnalysis = {
  value: number | null;
  type: string | null;
  overbought: number | null;
  oversold: number | null;
  is_confirmation: boolean | null;
};
export type RiskAnalysis = {
  approved: boolean;
  status: "approved" | "rejected";
  rejection_reason: string | null;
  entry_price: number | null;
  stop_price: number | null;
  target_price: number | null;
  position_quantity: number | null;
  requested_quantity: number | null;
  position_notional: number | null;
  risk_amount: number | null;
  reward_risk_ratio: number | null;
  fees_estimate: number | null;
  slippage_estimate: number | null;
  leverage: number | null;
  binding_constraint: string | null;
  metadata: Record<string, unknown>;
};
export type FreshnessInfo = {
  retrieved_at_ms: number;
  age_ms: number | null;
  is_stale: boolean;
  has_forming_candle: boolean;
  last_closed_timestamp_ms: number | null;
};
export type PairAnalysis = {
  symbol: string;
  timeframe: Timeframe;
  strategy_id: string | null;
  strategy_name: string | null;
  ticker_last: number | null;
  ticker_bid: number | null;
  ticker_ask: number | null;
  ticker_timestamp_ms: number | null;
  candles: MarketCandle[];
  quality_issues: string[];
  is_analysis_safe: boolean;
  range: RangeAnalysis;
  regime: RegimeAnalysis;
  signal: SignalAnalysis;
  oscillator: OscillatorAnalysis;
  risk: RiskAnalysis | null;
  freshness: FreshnessInfo;
};

// — Shared error envelope — must match backend/src/api/errors.py
export type ApiErrorEnvelope = {
  error: { code: string; message: string; request_id: string };
};
