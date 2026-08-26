"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import type { StoredTrade } from "@/lib/api/types";

export function TradeDetailDialog({
  trade,
  open,
  onClose,
  strategyIdMap
}: {
  trade: StoredTrade | null;
  open: boolean;
  onClose: () => void;
  strategyIdMap: Map<string, string>;
}) {
  if (!trade) return null;
  const stratId = trade.strategy_id ? strategyIdMap.get(trade.strategy_id) ?? null : null;
  const isWin = trade.result === "win";
  const isLoss = trade.result === "loss";
  return (
    <Dialog open={open} onClose={onClose} title={`Trade ${trade.trade_id.slice(0, 8)}`} description="Recorded fact — backend-provided StoredTrade. Derived fields are not recomputed.">
      <div className="space-y-3">
        <div className="grid gap-3 md:grid-cols-2">
          <Fact label="Symbol" value={trade.symbol} mono />
          <Fact label="Timeframe" value={trade.timeframe ?? "—"} mono />
          <Fact label="Direction" value={<Badge variant={trade.direction === "long" ? "bull" : "bear"}>{trade.direction.toUpperCase()}</Badge>} />
          <Fact label="Result" value={<Badge variant={isWin ? "success" : isLoss ? "bear" : "neutral"}>{trade.result ?? "—"}</Badge>} />
          <Fact label="Opened" value={new Date(trade.opened_at_ms).toLocaleString()} mono />
          <Fact label="Closed" value={trade.closed_at_ms ? new Date(trade.closed_at_ms).toLocaleString() : "—"} mono />
          <Fact label="Entry → Exit" value={`${trade.entry_price.toFixed(4)} → ${trade.exit_price !== null ? (trade.exit_price as number).toFixed(4) : "—"}`} mono />
          <Fact label="Quantity" value={trade.quantity.toFixed(4)} mono />
          <Fact label="Realized P&L" value={trade.realized_pnl !== null ? (trade.realized_pnl as number).toFixed(2) : "—"} mono tone={trade.realized_pnl !== null && (trade.realized_pnl as number) >= 0 ? "bull" : "bear"} />
          <Fact label="Realized R" value={trade.realized_r !== null ? (trade.realized_r as number).toFixed(2) : "—"} mono />
          <Fact label="Fees" value={trade.fees !== null ? (trade.fees as number).toFixed(2) : "—"} mono />
          <Fact label="Slippage" value={trade.slippage !== null ? (trade.slippage as number).toFixed(2) : "—"} mono />
          <Fact label="Risk amount" value={trade.risk_amount !== null ? (trade.risk_amount as number).toFixed(2) : "—"} mono />
          <Fact label="Status" value={<Badge variant={trade.status === "closed" ? "neutral" : "info"}>{trade.status}</Badge>} />
        </div>

        <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2">
          <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Strategy traceability</div>
          {trade.strategy_id ? (
            <div className="mono mt-1 text-[11px] text-[var(--color-text-secondary)]">
              Strategy name <span className="font-medium text-[var(--color-text-primary)]">{trade.strategy_id}</span> · config_hash {trade.config_hash?.slice(0, 8) ?? "—"}
              {stratId && (
                <Link href={`/strategies/${stratId}`} className="ml-2 font-medium text-[var(--color-purple-accent)] hover:underline">
                  Open strategy →
                </Link>
              )}
            </div>
          ) : (
            <div className="mono text-[11px] text-[var(--color-text-tertiary)]">No strategy linkage — —</div>
          )}
          <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">Identifiers are backend-authoritative. Do not approximate hash in frontend.</div>
        </div>

        <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2">
          <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Context</div>
          {trade.context ? (
            <pre className="mono mt-1 max-h-28 overflow-auto text-[11px] text-[var(--color-text-secondary)]">{JSON.stringify(trade.context, null, 2)}</pre>
          ) : (
            <div className="mono text-[11px] text-[var(--color-text-tertiary)]">—</div>
          )}
          <div className="mono text-[11px] text-[var(--color-text-tertiary)]">Distinguishes recorded fact vs presentation. Missing fields show “—”.</div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Link href={`/?symbol=${encodeURIComponent(trade.symbol)}${trade.timeframe ? `&timeframe=${trade.timeframe}` : ""}`} className="rounded-sm bg-[var(--color-purple-accent)] px-3 py-1.5 text-[12px] font-medium text-white hover:bg-[#6d4af0]">
            Analyze {trade.symbol}
          </Link>
          {stratId && (
            <Link href={`/strategies/${stratId}`} className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-3 py-1.5 text-[12px] font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]">
              Open strategy
            </Link>
          )}
          <Button variant="ghost" onClick={onClose}>Close</Button>
        </div>
      </div>
    </Dialog>
  );
}

function Fact({ label, value, mono, tone }: { label: string; value: React.ReactNode; mono?: boolean; tone?: "bull" | "bear" }) {
  const toneCls = tone === "bull" ? "text-[var(--color-bull)]" : tone === "bear" ? "text-[var(--color-bear)]" : "text-[var(--color-text-primary)]";
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">{label}</div>
      <div className={`${mono ? "mono" : ""} mt-0.5 text-[13px] font-medium ${tone ? toneCls : "text-[var(--color-text-primary)]"}`}>{value}</div>
    </div>
  );
}
