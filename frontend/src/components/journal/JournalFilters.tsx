"use client";

import { Badge } from "@/components/ui/Badge";

export type JournalFilter = {
  symbol: string; // all or specific
  direction: string; // all | long | short
  result: string; // all | win | loss | breakeven
  strategy: string; // all | id
  timeframe: string; // all or specific
  dateFrom: string; // yyyy-mm-dd or ""
  dateTo: string;
};

export const DEFAULT_JOURNAL_FILTER: JournalFilter = {
  symbol: "all",
  direction: "all",
  result: "all",
  strategy: "all",
  timeframe: "all",
  dateFrom: "",
  dateTo: ""
};

export function JournalFilters({
  value,
  onChange,
  symbols,
  strategies,
  timeframes,
  count,
  total
}: {
  value: JournalFilter;
  onChange: (v: JournalFilter) => void;
  symbols: string[];
  strategies: { id: string; name: string }[];
  timeframes: string[];
  count: number;
  total: number;
}) {
  const set = <K extends keyof JournalFilter>(k: K, v: JournalFilter[K]) => onChange({ ...value, [k]: v });

  const S = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <label className="flex items-center gap-1.5 text-[11px]">
      <span className="font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">{label}</span>
      {children}
    </label>
  );

  const selCls = "rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-1.5 py-1 text-[11px] text-[var(--color-text-secondary)] focus:border-[var(--color-purple-accent)] focus:outline-none";

  return (
    <div className="space-y-2 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="purple">Filters</Badge>
        <span className="mono text-[11px] text-[var(--color-text-tertiary)]">
          {count} of {total} trades
        </span>
        <button onClick={() => onChange(DEFAULT_JOURNAL_FILTER)} className="ml-auto text-[11px] font-medium text-[var(--color-purple-accent)] hover:underline">
          Reset
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        <S label="Symbol">
          <select value={value.symbol} onChange={(e) => set("symbol", e.target.value)} className={selCls}>
            <option value="all">All</option>
            {symbols.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </S>
        <S label="Dir">
          <select value={value.direction} onChange={(e) => set("direction", e.target.value)} className={selCls}>
            <option value="all">All</option>
            <option value="long">Long</option>
            <option value="short">Short</option>
          </select>
        </S>
        <S label="Result">
          <select value={value.result} onChange={(e) => set("result", e.target.value)} className={selCls}>
            <option value="all">All</option>
            <option value="win">Win</option>
            <option value="loss">Loss</option>
            <option value="breakeven">Breakeven</option>
          </select>
        </S>
        <S label="Strategy">
          <select value={value.strategy} onChange={(e) => set("strategy", e.target.value)} className={selCls}>
            <option value="all">All</option>
            {strategies.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </S>
        <S label="TF">
          <select value={value.timeframe} onChange={(e) => set("timeframe", e.target.value)} className={selCls}>
            <option value="all">All</option>
            {timeframes.map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>
        </S>
        <S label="From">
          <input type="date" value={value.dateFrom} onChange={(e) => set("dateFrom", e.target.value)} className={selCls} />
        </S>
        <S label="To">
          <input type="date" value={value.dateTo} onChange={(e) => set("dateTo", e.target.value)} className={selCls} />
        </S>
      </div>
      <div className="mono text-[11px] text-[var(--color-text-tertiary)]">Filters are presentation over backend-provided StoredTrade facts. No new metrics calculated.</div>
    </div>
  );
}

export function matchesJournalFilter(trade: import("@/lib/api/types").StoredTrade, f: JournalFilter, strategyNameToId: Map<string, string>): boolean {
  if (f.symbol !== "all" && trade.symbol !== f.symbol) return false;
  if (f.direction !== "all" && trade.direction !== f.direction) return false;
  if (f.result !== "all" && (trade.result ?? "") !== f.result) return false;
  if (f.strategy !== "all") {
    // trade.strategy_id is name (backend), but filter uses id; map to name
    const strat = Array.from(strategyNameToId.entries()).find(([, id]) => id === f.strategy)?.[0];
    if (trade.strategy_id !== strat) return false;
  }
  if (f.timeframe !== "all" && (trade.timeframe ?? "") !== f.timeframe) return false;
  if (f.dateFrom) {
    const fromMs = new Date(f.dateFrom + "T00:00:00Z").getTime();
    if (trade.opened_at_ms < fromMs) return false;
  }
  if (f.dateTo) {
    const toMs = new Date(f.dateTo + "T23:59:59Z").getTime();
    if (trade.opened_at_ms > toMs) return false;
  }
  return true;
}
