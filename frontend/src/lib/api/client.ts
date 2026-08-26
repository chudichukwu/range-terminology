/**
 * API client boundary — respects backend conventions:
 *  - Base URL via NEXT_PUBLIC_API_URL (defaults to http://localhost:8000)
 *  - Authorization: Bearer <token> when available
 *  - X-Request-Id echoed/honored (generated client-side for traceability)
 *  - Uniform error envelope: { error: { code, message, request_id } }
 *  - 500s never leak stack traces; all errors surface as ApiError.
 *
 * No domain logic is implemented here; this layer only transports backend truth.
 */

import type { ApiErrorEnvelope } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const REQUEST_ID_HEADER = "X-Request-Id";

export class ApiError extends Error {
  code: string;
  requestId: string;
  status: number;
  constructor(message: string, opts: { code: string; requestId: string; status: number }) {
    super(message);
    this.name = "ApiError";
    this.code = opts.code;
    this.requestId = opts.requestId;
    this.status = opts.status;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("rt.accessToken");
}

function newRequestId(): string {
  // crypto.randomUUID is available in modern browsers
  try {
    return (crypto as unknown as { randomUUID: () => string }).randomUUID?.() ?? Math.random().toString(36).slice(2);
  } catch {
    return Math.random().toString(36).slice(2);
  }
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<{ data: T; requestId: string }> {
  const token = getToken();
  const requestId = newRequestId();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    [REQUEST_ID_HEADER]: requestId,
    ...opts.headers
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal
  });

  const responseRequestId = res.headers.get(REQUEST_ID_HEADER) ?? requestId;

  if (!res.ok) {
    let envelope: ApiErrorEnvelope | null = null;
    try {
      envelope = (await res.json()) as ApiErrorEnvelope;
    } catch {
      // non-JSON error
    }
    const code = envelope?.error.code ?? (res.status >= 500 ? "internal_error" : "request_failed");
    const message = envelope?.error.message ?? res.statusText ?? "Request failed";
    const rid = envelope?.error.request_id ?? responseRequestId;
    throw new ApiError(message, { code, requestId: rid, status: res.status });
  }

  // 204 No Content
  if (res.status === 204) {
    return { data: undefined as unknown as T, requestId: responseRequestId };
  }
  const data = (await res.json()) as T;
  return { data, requestId: responseRequestId };
}

// High-level typed helpers — thin wrappers over apiFetch
export const api = {
  get: <T>(path: string, signal?: AbortSignal) => apiFetch<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "PATCH", body }),
  del: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
  health: () => apiFetch<{ status: string }>("/health"),
  me: () => apiFetch<import("./types").UserOut>("/auth/me"),
  // Pair analysis — backend-provided market+range+regime+signal+risk
  pairAnalysis: (params: { symbol: string; timeframe: string; strategy_id?: string; limit?: number }, signal?: AbortSignal) => {
    const sp = new URLSearchParams({ symbol: params.symbol, timeframe: params.timeframe });
    if (params.strategy_id) sp.set("strategy_id", params.strategy_id);
    if (params.limit) sp.set("limit", String(params.limit));
    return apiFetch<import("./types").PairAnalysis>(`/analysis/pair?${sp.toString()}`, { signal });
  },
  listWatchlists: (signal?: AbortSignal) => apiFetch<import("./types").Watchlist[]>("/watchlists", { signal }),
  getWatchlist: (id: string, signal?: AbortSignal) =>
    apiFetch<import("./types").Watchlist & { items: import("./types").WatchlistItem[] }>(`/watchlists/${id}`, { signal }),
  createWatchlist: (name: string) => apiFetch<import("./types").Watchlist>("/watchlists", { method: "POST", body: { name } }),
  renameWatchlist: (id: string, name: string) => apiFetch<import("./types").Watchlist>(`/watchlists/${id}`, { method: "PATCH", body: { name } }),
  deleteWatchlist: (id: string) => apiFetch<void>(`/watchlists/${id}`, { method: "DELETE" }),
  addWatchlistItem: (watchlistId: string, body: { symbol: string; venue_id: string; notes?: string; sort_order?: number; enabled?: boolean }) =>
    apiFetch<import("./types").WatchlistItem>(`/watchlists/${watchlistId}/items`, { method: "POST", body }),
  removeWatchlistItem: (watchlistId: string, itemId: string) => apiFetch<void>(`/watchlists/${watchlistId}/items/${itemId}`, { method: "DELETE" }),
  listStrategies: (signal?: AbortSignal) => apiFetch<import("./types").Strategy[]>("/strategies", { signal }),
  getStrategy: (id: string, signal?: AbortSignal) => apiFetch<import("./types").Strategy>(`/strategies/${id}`, { signal }),
  createStrategy: (body: { name: string; payload: { range_config: Record<string, unknown>; signal_config: Record<string, unknown>; risk_config: Record<string, unknown> }; active?: boolean }) =>
    apiFetch<import("./types").Strategy>("/strategies", { method: "POST", body }),
  updateStrategy: (id: string, body: { name?: string; payload?: { range_config: Record<string, unknown>; signal_config: Record<string, unknown>; risk_config: Record<string, unknown> }; active?: boolean }) =>
    apiFetch<import("./types").Strategy>(`/strategies/${id}`, { method: "PATCH", body }),
  deleteStrategy: (id: string) => apiFetch<void>(`/strategies/${id}`, { method: "DELETE" }),
  listBacktests: (signal?: AbortSignal) => apiFetch<import("./types").BacktestRunSummary[]>("/backtests", { signal }),
  getBacktest: (runId: string, signal?: AbortSignal) => apiFetch<import("./types").BacktestDetail>(`/backtests/${runId}`, { signal }),
  runBacktest: (body: { strategy_id: string; start_ms: number; end_ms: number; initial_capital: number; fee_rate?: number; slippage_rate?: number }) =>
    apiFetch<import("./types").BacktestDetail>("/backtests", { method: "POST", body }),
  listTimeframes: (signal?: AbortSignal) => apiFetch<{ timeframes: string[] }>("/markets/timeframes", { signal }),
};
