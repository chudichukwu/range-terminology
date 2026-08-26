import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import type { BacktestTrade } from "@/lib/api/types";

type SortKey = "opened_at_ms" | "realized_pnl" | "realized_r" | "result" | "direction";

export function TradeTable({ trades }: { trades: BacktestTrade[] }) {
  const [filterResult, setFilterResult] = useState<string>("all");
  const [filterDirection, setFilterDirection] = useState<string>("all");
  const [sortKey, setSortKey] = useState<SortKey>("opened_at_ms");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const filtered = useMemo(() => {
    let list = trades;
    if (filterResult !== "all") list = list.filter((t) => (t.result ?? "") === filterResult);
    if (filterDirection !== "all") list = list.filter((t) => t.direction === filterDirection);
    const dir = sortDir === "asc" ? 1 : -1;
    return [...list].sort((a, b) => {
      if (sortKey === "realized_pnl") return dir * ((a.realized_pnl ?? -Infinity) - (b.realized_pnl ?? -Infinity));
      if (sortKey === "realized_r") return dir * ((a.realized_r ?? -Infinity) - (b.realized_r ?? -Infinity));
      if (sortKey === "result") return dir * String(a.result ?? "").localeCompare(String(b.result ?? ""));
      if (sortKey === "direction") return dir * a.direction.localeCompare(b.direction);
      return dir * (a.opened_at_ms - b.opened_at_ms);
    });
  }, [trades, filterResult, filterDirection, sortKey, sortDir]);

  const toggle = (k: SortKey) => {
    if (k === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(k);
      setSortDir("asc");
    }
  };

  if (trades.length === 0) {
    return <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-6 text-center mono text-[13px] text-[var(--color-text-tertiary)]">No simulated trades retained for this run. This can happen when the window had insufficient opportunities or the strategy produced no entries.</div>;
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-2">
        <label className="flex items-center gap-1.5 text-[11px]">
          <span className="font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Result</span>
          <select value={filterResult} onChange={(e) => setFilterResult(e.target.value)} className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-1.5 py-1 text-[11px] text-[var(--color-text-secondary)]">
            <option value="all">All</option>
            <option value="win">Win</option>
            <option value="loss">Loss</option>
            <option value="breakeven">Breakeven</option>
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-[11px]">
          <span className="font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Direction</span>
          <select value={filterDirection} onChange={(e) => setFilterDirection(e.target.value)} className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-1.5 py-1 text-[11px] text-[var(--color-text-secondary)]">
            <option value="all">All</option>
            <option value="long">Long</option>
            <option value="short">Short</option>
          </select>
        </label>
        <span className="ml-auto mono text-[11px] text-[var(--color-text-tertiary)]">{filtered.length} of {trades.length} trades</span>
      </div>

      <div className="overflow-hidden rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)]">
        <div className="hidden overflow-x-auto md:block">
          <table className="w-full text-left" role="table">
            <thead className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]">
              <tr className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                <th className="px-3 py-2 font-medium"><button onClick={() => toggle("opened_at_ms")} className={sortKey === "opened_at_ms" ? "text-[var(--color-purple-accent)]" : ""}>Opened {sortKey === "opened_at_ms" ? (sortDir === "asc" ? "▲" : "▼") : ""}</button></th>
                <th className="px-3 py-2 font-medium"><button onClick={() => toggle("direction")} className={sortKey === "direction" ? "text-[var(--color-purple-accent)]" : ""}>Dir {sortKey === "direction" ? (sortDir === "asc" ? "▲" : "▼") : ""}</button></th>
                <th className="px-3 py-2 font-medium">Entry → Exit</th>
                <th className="px-3 py-2 font-medium"><button onClick={() => toggle("realized_pnl")} className={sortKey === "realized_pnl" ? "text-[var(--color-purple-accent)]" : ""}>P&L {sortKey === "realized_pnl" ? (sortDir === "asc" ? "▲" : "▼") : ""}</button></th>
                <th className="px-3 py-2 font-medium"><button onClick={() => toggle("realized_r")} className={sortKey === "realized_r" ? "text-[var(--color-purple-accent)]" : ""}>R {sortKey === "realized_r" ? (sortDir === "asc" ? "▲" : "▼") : ""}</button></th>
                <th className="px-3 py-2 font-medium"><button onClick={() => toggle("result")} className={sortKey === "result" ? "text-[var(--color-purple-accent)]" : ""}>Result {sortKey === "result" ? (sortDir === "asc" ? "▲" : "▼") : ""}</button></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr key={t.trade_id} className="border-b border-[var(--color-border-subtle)] last:border-0 hover:bg-[var(--color-bg-surface-2)]">
                  <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-secondary)]">{new Date(t.opened_at_ms).toLocaleDateString()} <span className="text-[var(--color-text-tertiary)]">{new Date(t.opened_at_ms).toLocaleTimeString()}</span></td>
                  <td className="px-3 py-2"><Badge variant={t.direction === "long" ? "bull" : "bear"}>{t.direction.toUpperCase()}</Badge></td>
                  <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-primary)]">{t.entry_price.toFixed(2)} → {t.exit_price !== null ? (t.exit_price as number).toFixed(2) : "—"}</td>
                  <td className={`mono px-3 py-2 text-[11px] ${t.realized_pnl !== null && (t.realized_pnl as number) >= 0 ? "text-[var(--color-bull)]" : "text-[var(--color-bear)]"}`}>{t.realized_pnl !== null ? (t.realized_pnl as number).toFixed(2) : "—"} <span className="text-[var(--color-text-tertiary)]">fees {t.fees?.toFixed(2) ?? "—"} slip {t.slippage?.toFixed(2) ?? "—"}</span></td>
                  <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-secondary)]">{t.realized_r !== null ? (t.realized_r as number).toFixed(2) : "—"}</td>
                  <td className="px-3 py-2"><Badge variant={t.result === "win" ? "success" : t.result === "loss" ? "bear" : t.result === "breakeven" ? "neutral" : "neutral"}>{t.result ?? "—"}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="grid gap-2 p-2 md:hidden">
          {filtered.map((t) => (
            <div key={t.trade_id} className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2">
              <div className="flex items-center justify-between gap-2">
                <Badge variant={t.direction === "long" ? "bull" : "bear"}>{t.direction}</Badge>
                <Badge variant={t.result === "win" ? "success" : t.result === "loss" ? "bear" : "neutral"}>{t.result ?? "—"}</Badge>
              </div>
              <div className="mono mt-1 text-[11px] text-[var(--color-text-primary)]">{t.entry_price.toFixed(2)} → {t.exit_price?.toFixed(2) ?? "—"}</div>
              <div className="mono text-[11px] text-[var(--color-text-secondary)]">PnL {t.realized_pnl?.toFixed(2) ?? "—"} · R {t.realized_r?.toFixed(2) ?? "—"}</div>
              <div className="mono text-[10px] text-[var(--color-text-tertiary)]">{new Date(t.opened_at_ms).toLocaleString()}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="mono text-[11px] text-[var(--color-text-tertiary)]">Trades are backend-provided StoredTrade facts. Classification (win/loss/breakeven) is backend-derived; breakevens excluded from win-rate per backend definition. Fees/slippage/drawdown not recomputed in React.</div>
    </div>
  );
}
