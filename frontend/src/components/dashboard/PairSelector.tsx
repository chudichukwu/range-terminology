"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import type { Watchlist, WatchlistItem } from "@/lib/api/types";

export function PairSelector({
  value,
  onChange
}: {
  value: string;
  onChange: (symbol: string) => void;
}) {
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [activeWl, setActiveWl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listWatchlists()
      .then(({ data }) => {
        if (cancelled) return;
        setWatchlists(data);
        if (data.length > 0 && !activeWl) setActiveWl(data[0]!.id);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [activeWl]);

  useEffect(() => {
    if (!activeWl) return;
    let cancelled = false;
    api
      .getWatchlist(activeWl)
      .then(({ data }) => {
        if (cancelled) return;
        setItems(data.items ?? []);
      })
      .catch(() => setItems([]));
    return () => {
      cancelled = true;
    };
  }, [activeWl]);

  const symbols = items.filter((i) => i.enabled).map((i) => i.symbol);
  const allSymbols = symbols.length > 0 ? symbols : ["BTC/USDT", "ETH/USDT", "SOL/USDT"];

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="pair-select" className="sr-only">
        Symbol
      </label>
      <select
        id="pair-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mono min-w-[140px] rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-2.5 py-1.5 text-[13px] font-medium text-[var(--color-text-primary)] focus:border-[var(--color-purple-accent)] focus:outline-none focus:ring-1 focus:ring-[var(--color-purple-accent)]"
      >
        {allSymbols.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
      {watchlists.length > 1 && (
        <select
          value={activeWl ?? ""}
          onChange={(e) => setActiveWl(e.target.value)}
          className="hidden rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-2 py-1.5 text-[11px] text-[var(--color-text-secondary)] md:block"
          aria-label="Watchlist"
        >
          {watchlists.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
      )}
      <span className="mono hidden text-[11px] text-[var(--color-text-tertiary)] md:inline">via watchlist · backend</span>
    </div>
  );
}
