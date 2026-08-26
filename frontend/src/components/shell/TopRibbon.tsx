"use client";

import { cn } from "@/lib/utils";

type RibbonItem = {
  symbol: string;
  last: string;
  change: string; // e.g. +1.24%
  rangeStatus: "VALID" | "DEGENERATE" | "INSUFFICIENT_DATA";
  regime: "RANGING" | "TRENDING_UP" | "TRENDING_DOWN" | "TRANSITIONAL" | "INSUFFICIENT_DATA";
};

const MOCK: RibbonItem[] = [
  { symbol: "BTC/USDT", last: "67,421.10", change: "+1.24%", rangeStatus: "VALID", regime: "RANGING" },
  { symbol: "ETH/USDT", last: "3,412.05", change: "-0.82%", rangeStatus: "DEGENERATE", regime: "TRENDING_UP" },
  { symbol: "SOL/USDT", last: "142.80", change: "+2.11%", rangeStatus: "VALID", regime: "TRANSITIONAL" },
  { symbol: "AVAX/USDT", last: "28.44", change: "+0.40%", rangeStatus: "INSUFFICIENT_DATA", regime: "INSUFFICIENT_DATA" }
];

function statusColor(s: RibbonItem["rangeStatus"]) {
  if (s === "VALID") return "text-[var(--color-success)]";
  if (s === "DEGENERATE") return "text-[var(--color-warning)]";
  return "text-[var(--color-neutral)]";
}

export function TopRibbon() {
  return (
    <div
      role="region"
      aria-label="Market ribbon"
      className="flex h-[36px] shrink-0 items-center gap-1 overflow-x-auto border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-subtle)] px-3"
      style={{ scrollbarWidth: "none" }}
    >
      <span className="mr-2 hidden shrink-0 items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.08em] text-[var(--color-text-tertiary)] md:flex">
        <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-purple-accent)] shadow-[0_0_6px_rgba(124,92,255,0.6)]" aria-hidden />
        Markets
      </span>
      <div className="flex items-center gap-1.5">
        {MOCK.map((item) => (
          <div
            key={item.symbol}
            className={cn(
              "flex shrink-0 items-center gap-2.5 rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-2.5 py-1",
              "hover:border-[var(--color-border-strong)]"
            )}
          >
            <span className="mono text-[12px] font-medium tracking-tight text-[var(--color-text-primary)]">{item.symbol}</span>
            <span className="mono text-[12px] text-[var(--color-text-primary)]">{item.last}</span>
            <span
              className={cn(
                "mono text-[11px]",
                item.change.startsWith("+") ? "text-[var(--color-bull)]" : "text-[var(--color-bear)]"
              )}
            >
              {item.change}
            </span>
            <span className={cn("flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide", statusColor(item.rangeStatus))}>
              <span aria-hidden>{item.rangeStatus === "VALID" ? "●" : item.rangeStatus === "DEGENERATE" ? "◐" : "○"}</span>
              {item.rangeStatus}
            </span>
            <span className="hidden text-[10px] tracking-wide text-[var(--color-text-tertiary)] md:inline">{item.regime}</span>
          </div>
        ))}
        <span
          className="shrink-0 rounded-sm border border-dashed border-[var(--color-border-subtle)] px-2 py-1 text-[11px] text-[var(--color-text-tertiary)]"
          aria-label="Ribbon placeholder — live data connects via backend"
        >
          + live via API
        </span>
      </div>
      <div className="ml-auto hidden shrink-0 items-center gap-2 pl-3 md:flex">
        <span className="rounded-pill bg-[var(--color-danger-bg)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--color-danger)]">
          Paper · Read-Only
        </span>
      </div>
    </div>
  );
}
