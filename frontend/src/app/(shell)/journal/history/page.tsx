"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ErrorState, LoadingState, EmptyState } from "@/components/state/StatePrimitives";
import { EquityCurve } from "@/components/backtest/EquityCurve";
import { JournalFilters, DEFAULT_JOURNAL_FILTER, matchesJournalFilter } from "@/components/journal/JournalFilters";
import { TradeDetailDialog } from "@/components/journal/TradeDetail";
import { api, ApiError } from "@/lib/api/client";
import type { StoredTrade, TradeStatistics } from "@/lib/api/types";
import type { Strategy } from "@/lib/api/types";

function fmt(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined) return "—";
  if (!Number.isFinite(n as number)) return "—";
  return (n as number).toFixed(digits);
}

export default function JournalPage() {
  const [trades, setTrades] = useState<StoredTrade[] | null>(null);
  const [stats, setStats] = useState<TradeStatistics | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [error, setError] = useState<{ message: string; requestId: string } | null>(null);
  const [filter, setFilter] = useState(DEFAULT_JOURNAL_FILTER);
  const [sortKey, setSortKey] = useState<"opened_at_ms" | "closed_at_ms" | "realized_pnl" | "realized_r" | "symbol">("opened_at_ms");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [selectedTrade, setSelectedTrade] = useState<StoredTrade | null>(null);
  const [limit, setLimit] = useState(100);

  const nameToId = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of strategies) m.set(s.name, s.id);
    return m;
  }, [strategies]);

  const load = async () => {
    setError(null);
    try {
      const [tradesRes, statsRes] = await Promise.all([
        api.listTrades({ limit }, undefined),
        api.getTradeStatistics(undefined, undefined)
      ]);
      setTrades(tradesRes.data as unknown as StoredTrade[]);
      setStats(statsRes.data as unknown as TradeStatistics);
    } catch (e) {
      if (e instanceof ApiError) setError({ message: `${e.code}: ${e.message}`, requestId: e.requestId });
      else setError({ message: String(e), requestId: "" });
    }
  };

  useEffect(() => {
    load();
    api.listStrategies().then(({ data }) => setStrategies(data)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [limit]);

  const symbols = useMemo(() => Array.from(new Set((trades ?? []).map((t) => t.symbol))).sort(), [trades]);
  const timeframes = useMemo(() => Array.from(new Set((trades ?? []).map((t) => t.timeframe).filter(Boolean) as string[])).sort(), [trades]);

  const filtered = useMemo(() => {
    if (!trades) return null;
    let list = trades.filter((t) => matchesJournalFilter(t, filter, nameToId));
    const dir = sortDir === "asc" ? 1 : -1;
    list = [...list].sort((a, b) => {
      if (sortKey === "realized_pnl") return dir * ((a.realized_pnl ?? -Infinity) - (b.realized_pnl ?? -Infinity));
      if (sortKey === "realized_r") return dir * ((a.realized_r ?? -Infinity) - (b.realized_r ?? -Infinity));
      if (sortKey === "symbol") return dir * a.symbol.localeCompare(b.symbol);
      if (sortKey === "closed_at_ms") return dir * ((a.closed_at_ms ?? 0) - (b.closed_at_ms ?? 0));
      return dir * (a.opened_at_ms - b.opened_at_ms);
    });
    return list;
  }, [trades, filter, nameToId, sortKey, sortDir]);

  const toggle = (k: typeof sortKey) => {
    if (k === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(k); setSortDir(k === "opened_at_ms" ? "desc" : "asc"); }
  };

  if (error) {
    return (
      <>
        <PageHeader title="Journal" description="Historical trades — backend truth, no frontend calculations." breadcrumbs={[{ label: "Journal" }]} />
        <ContentContainer><ErrorState message={error.message} requestId={error.requestId} onRetry={load} /></ContentContainer>
      </>
    );
  }

  if (!trades || !stats) {
    return (
      <>
        <PageHeader title="Journal" description="Historical trades — backend truth, no frontend calculations." breadcrumbs={[{ label: "Journal" }]} />
        <ContentContainer><LoadingState label="Loading journal and performance" /></ContentContainer>
      </>
    );
  }

  const total = trades.length;

  return (
    <>
      <PageHeader
        title="Journal"
        description="Trade Journal & Performance Analytics — performance context → aggregated facts → individual trades → investigation. Backend is source of truth."
        breadcrumbs={[{ label: "Journal" }]}
        actions={
          <div className="flex gap-2">
            <Badge variant="danger">PAPER · READ-ONLY</Badge>
            <Badge variant="neutral">{total} trades</Badge>
          </div>
        }
      />
      <ContentContainer>
        <div className="space-y-4">
          {/* Performance analytics */}
          <div className="space-y-2">
            <h2 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Performance — backend-provided TradeStatistics</h2>
            <div className="grid gap-2 md:grid-cols-4 lg:grid-cols-6">
              <Stat label="Total P&L" value={fmt(stats.total_realized_pnl, 2)} mono tone={(stats.total_realized_pnl ?? 0) >= 0 ? "bull" : "bear"} />
              <Stat label="Trades" value={String(stats.total_trades)} />
              <Stat label="Completed / Open" value={`${stats.completed_trades} / ${stats.open_trades}`} mono />
              <Stat label="Wins" value={String(stats.wins)} mono tone="bull" />
              <Stat label="Losses" value={String(stats.losses)} mono tone="bear" />
              <Stat label="Breakevens" value={String(stats.breakevens)} />
              <Stat label="Win rate" value={stats.win_rate !== null ? `${(stats.win_rate * 100).toFixed(1)}%` : "—"} sub="wins/(wins+losses)" />
              <Stat label="Profit factor" value={stats.profit_factor !== null ? (stats.profit_factor as number).toFixed(2) : "—"} sub="∞ → —" />
              <Stat label="Expectancy" value={fmt(stats.expectancy, 4)} sub="per trade" />
              <Stat label="Avg R" value={fmt(stats.average_r, 3)} />
              <Stat label="Avg win" value={fmt(stats.average_win, 2)} mono tone="bull" />
              <Stat label="Avg loss" value={fmt(stats.average_loss, 2)} mono tone="bear" />
              <Stat label="Max DD" value={fmt(stats.max_drawdown, 2)} mono />
              <Stat label="Fees+Slippage note" value="per-trade" sub="fees/slippage shown per row" />
            </div>
            <div className="mono text-[11px] text-[var(--color-text-tertiary)]">
              All statistics are backend-computed via <span className="text-[var(--color-text-secondary)]">compute_trade_statistics</span>. “—” means null per backend, not 0. No Sharpe/probability/edge score invented.
            </div>
          </div>

          {/* Equity curve — subordinate */}
          <div>
            <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Equity (trade-close granularity)</h3>
            {stats.equity_curve.length === 0 ? (
              <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-4 text-center mono text-[13px] text-[var(--color-text-tertiary)]">No closed trades — equity curve will appear after the first completed trade.</div>
            ) : (
              <EquityCurve points={stats.equity_curve} />
            )}
          </div>

          {/* Filters */}
          <JournalFilters value={filter} onChange={setFilter} symbols={symbols} strategies={strategies} timeframes={timeframes} count={filtered?.length ?? 0} total={total} />

          {/* Journal table */}
          {trades.length === 0 ? (
            <EmptyState title="No trades recorded yet" description="Trades appear after backtests or paper fills. This workspace is observational — PAPER · READ-ONLY. No fake trades are shown." />
          ) : filtered && filtered.length === 0 ? (
            <EmptyState title="No trades match these filters" description="Adjust filters to see more trades. Filters are presentation over backend-provided facts." />
          ) : (
            <>
              <div className="hidden overflow-hidden rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] md:block">
                <div className="overflow-x-auto">
                  <table className="w-full text-left" role="table">
                    <thead className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]">
                      <tr className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                        <th className="px-3 py-2 font-medium"><button onClick={() => toggle("opened_at_ms")} className={sortKey === "opened_at_ms" ? "text-[var(--color-purple-accent)]" : ""}>Opened {sortKey === "opened_at_ms" ? (sortDir === "asc" ? "▲" : "▼") : ""}</button></th>
                        <th className="px-3 py-2 font-medium">Symbol / TF</th>
                        <th className="px-3 py-2 font-medium">Direction</th>
                        <th className="px-3 py-2 font-medium">Strategy</th>
                        <th className="px-3 py-2 font-medium">Entry → Exit</th>
                        <th className="px-3 py-2 font-medium"><button onClick={() => toggle("realized_pnl")} className={sortKey === "realized_pnl" ? "text-[var(--color-purple-accent)]" : ""}>P&L {sortKey === "realized_pnl" ? (sortDir === "asc" ? "▲" : "▼") : ""}</button></th>
                        <th className="px-3 py-2 font-medium"><button onClick={() => toggle("realized_r")} className={sortKey === "realized_r" ? "text-[var(--color-purple-accent)]" : ""}>R {sortKey === "realized_r" ? (sortDir === "asc" ? "▲" : "▼") : ""}</button></th>
                        <th className="px-3 py-2 font-medium">Result</th>
                        <th className="px-3 py-2 font-medium">Fees/slip</th>
                        <th className="px-3 py-2 font-medium">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered!.map((t) => (
                        <tr key={t.trade_id} className="cursor-pointer border-b border-[var(--color-border-subtle)] last:border-0 hover:bg-[var(--color-bg-surface-2)]" onClick={() => setSelectedTrade(t)}>
                          <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-secondary)]">{new Date(t.opened_at_ms).toLocaleDateString()} <span className="text-[var(--color-text-tertiary)]">{new Date(t.opened_at_ms).toLocaleTimeString()}</span></td>
                          <td className="px-3 py-2">
                            <div className="mono text-[12px] font-medium text-[var(--color-text-primary)]">{t.symbol}</div>
                            <div className="mono text-[11px] text-[var(--color-text-tertiary)]">{t.timeframe ?? "—"}</div>
                          </td>
                          <td className="px-3 py-2"><Badge variant={t.direction === "long" ? "bull" : "bear"}>{t.direction.toUpperCase()}</Badge></td>
                          <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-secondary)]">{t.strategy_id ?? "—"} <span className="text-[var(--color-text-tertiary)]">{t.config_hash?.slice(0, 6) ?? ""}</span></td>
                          <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-primary)]">{t.entry_price.toFixed(4)} → {t.exit_price !== null ? (t.exit_price as number).toFixed(4) : "—"}</td>
                          <td className={`mono px-3 py-2 text-[11px] ${t.realized_pnl !== null && (t.realized_pnl as number) >= 0 ? "text-[var(--color-bull)]" : t.realized_pnl !== null ? "text-[var(--color-bear)]" : "text-[var(--color-text-primary)]"}`}>{t.realized_pnl !== null ? (t.realized_pnl as number).toFixed(2) : "—"}</td>
                          <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-secondary)]">{t.realized_r !== null ? (t.realized_r as number).toFixed(2) : "—"}</td>
                          <td className="px-3 py-2"><Badge variant={t.result === "win" ? "success" : t.result === "loss" ? "bear" : t.result === "breakeven" ? "neutral" : "neutral"}>{t.result ?? "—"}</Badge></td>
                          <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-tertiary)]">{t.fees !== null ? (t.fees as number).toFixed(2) : "—"} / {t.slippage !== null ? (t.slippage as number).toFixed(2) : "—"}</td>
                          <td className="px-3 py-2">
                            <button onClick={(e) => { e.stopPropagation(); setSelectedTrade(t); }} className="rounded-sm border border-[var(--color-border-subtle)] px-2 py-1 text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-2)]">Inspect</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Mobile cards */}
              <div className="grid gap-2 md:hidden">
                {filtered!.map((t) => (
                  <div key={t.trade_id} className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3" onClick={() => setSelectedTrade(t)}>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="mono text-[13px] font-semibold text-[var(--color-text-primary)]">{t.symbol} <span className="text-[11px] font-normal text-[var(--color-text-tertiary)]">{t.timeframe ?? ""}</span></div>
                        <div className="mono text-[11px] text-[var(--color-text-tertiary)]">{new Date(t.opened_at_ms).toLocaleString()}</div>
                      </div>
                      <Badge variant={t.result === "win" ? "success" : t.result === "loss" ? "bear" : "neutral"}>{t.result ?? t.status}</Badge>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <Badge variant={t.direction === "long" ? "bull" : "bear"}>{t.direction.toUpperCase()}</Badge>
                      <span className="mono text-[11px] text-[var(--color-text-secondary)]">{t.entry_price.toFixed(2)} → {t.exit_price?.toFixed(2) ?? "—"}</span>
                      <span className={`mono text-[11px] ${t.realized_pnl !== null && (t.realized_pnl as number) >= 0 ? "text-[var(--color-bull)]" : "text-[var(--color-bear)]"}`}>PnL {t.realized_pnl?.toFixed(2) ?? "—"} · R {t.realized_r?.toFixed(2) ?? "—"}</span>
                    </div>
                    <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">{t.strategy_id ?? "—"} · fees {t.fees?.toFixed(2) ?? "—"}</div>
                  </div>
                ))}
              </div>

              {total >= limit && (
                <div className="flex justify-center">
                  <Button variant="secondary" size="sm" onClick={() => setLimit((l) => Math.min(500, l + 100))}>Load more (limit {limit} → {Math.min(500, limit + 100)})</Button>
                </div>
              )}
            </>
          )}

          <TradeDetailDialog trade={selectedTrade} open={!!selectedTrade} onClose={() => setSelectedTrade(null)} strategyIdMap={nameToId} />
        </div>
      </ContentContainer>
    </>
  );
}

function Stat({ label, value, mono, tone, sub }: { label: string; value: string; mono?: boolean; tone?: "bull" | "bear"; sub?: string }) {
  const toneCls = tone === "bull" ? "text-[var(--color-bull)]" : tone === "bear" ? "text-[var(--color-bear)]" : "text-[var(--color-text-primary)]";
  return (
    <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">{label}</div>
      <div className={`${mono ? "mono" : ""} mt-0.5 text-[13px] font-medium ${toneCls}`}>{value}</div>
      {sub && <div className="mono text-[10px] text-[var(--color-text-tertiary)]">{sub}</div>}
    </div>
  );
}
