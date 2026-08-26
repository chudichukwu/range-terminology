"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { api, ApiError } from "@/lib/api/client";
import type { WatchlistItem, PairAnalysis } from "@/lib/api/types";

export type ScanEntryState =
  | { kind: "loading" }
  | { kind: "success"; analysis: PairAnalysis }
  | { kind: "stale"; analysis: PairAnalysis }
  | { kind: "error"; code: string; message: string; requestId: string; status: number }
  | { kind: "insufficient" }
  | { kind: "idle" };

export type ScanMap = Record<string, ScanEntryState>; // key = WatchlistItem.id

const CONCURRENCY = 4;

function classify(entry: PairAnalysis): ScanEntryState {
  if (!entry) return { kind: "error", code: "unknown", message: "Empty response", requestId: "", status: 500 };
  // Insufficient data is distinct: both range and regime say insufficient
  if (entry.range.status === "insufficient_data") return { kind: "success", analysis: entry }; // still success but row will flag; keep as success for rendering
  if (entry.freshness.is_stale) return { kind: "stale", analysis: entry };
  if (!entry.is_analysis_safe && entry.quality_issues.length > 0) {
    // still success but unsafe — handled via row tint, keep as stale-like
    return { kind: "success", analysis: entry };
  }
  return { kind: "success", analysis: entry };
}

export function useWatchlistScan(
  items: WatchlistItem[] | null,
  opts: { timeframe: string; strategyId?: string; enabled?: boolean }
) {
  const [scan, setScan] = useState<ScanMap>({});
  const [isScanning, setIsScanning] = useState(false);
  const abortControllers = useRef<Map<string, AbortController>>(new Map());

  const scanAll = useCallback(async () => {
    if (!items || items.length === 0) {
      setScan({});
      setIsScanning(false);
      return;
    }
    // cancel previous
    for (const ac of abortControllers.current.values()) ac.abort();
    abortControllers.current.clear();

    const initial: ScanMap = {};
    for (const it of items) initial[it.id] = { kind: "loading" };
    setScan(initial);
    setIsScanning(true);

    // simple concurrency pool
    const queue = [...items];
    let active = 0;
    let idx = 0;

    return new Promise<void>((resolve) => {
      const next = () => {
        if (idx >= queue.length && active === 0) {
          setIsScanning(false);
          resolve();
          return;
        }
        while (active < CONCURRENCY && idx < queue.length) {
          const item = queue[idx++]!;
          active++;
          const ac = new AbortController();
          abortControllers.current.set(item.id, ac);
          api
            .pairAnalysis({ symbol: item.symbol, timeframe: opts.timeframe, strategy_id: opts.strategyId }, ac.signal)
            .then(({ data }) => {
              if (ac.signal.aborted) return;
              setScan((prev) => ({ ...prev, [item.id]: classify(data) }));
            })
            .catch((e) => {
              if (ac.signal.aborted) return;
              if (e instanceof ApiError) {
                // provider_error, insufficient_data via 422 etc map to error state
                setScan((prev) => ({
                  ...prev,
                  [item.id]: { kind: "error", code: e.code, message: e.message, requestId: e.requestId, status: e.status }
                }));
              } else if ((e as Error).name === "AbortError") {
                // ignore
              } else {
                setScan((prev) => ({
                  ...prev,
                  [item.id]: { kind: "error", code: "unknown", message: String(e), requestId: "", status: 0 }
                }));
              }
            })
            .finally(() => {
              active--;
              next();
            });
        }
      };
      next();
    });
  }, [items, opts.timeframe, opts.strategyId]);

  useEffect(() => {
    if (opts.enabled === false) return;
    scanAll();
    return () => {
      // eslint-disable-next-line react-hooks/exhaustive-deps
      const ctrls = abortControllers.current;
      for (const ac of ctrls.values()) ac.abort();
    };
  }, [scanAll, opts.enabled]);

  return { scan, isScanning, refresh: scanAll };
}
