"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import type { PairAnalysis, Timeframe } from "@/lib/api/types";
import { Badge } from "@/components/ui/Badge";

const STRIP_TFS: Timeframe[] = ["1h", "4h", "1d", "15m"];

type StripState =
  | { status: "loading" }
  | { status: "success"; analysis: PairAnalysis }
  | { status: "error"; code: string; message: string; requestId: string }
  | { status: "stale"; analysis: PairAnalysis };

export function TimeframeStrip({ symbol, activeTf, strategyId, onSelect }: { symbol: string; activeTf: Timeframe; strategyId?: string; onSelect: (tf: Timeframe) => void }) {
  const [states, setStates] = useState<Record<string, StripState>>({});

  useEffect(() => {
    let cancelled = false;
    const controllers = new Map<string, AbortController>();

    for (const tf of STRIP_TFS) {
      setStates((prev) => ({ ...prev, [tf]: { status: "loading" } }));
      const ac = new AbortController();
      controllers.set(tf, ac);
      api
        .pairAnalysis({ symbol, timeframe: tf, strategy_id: strategyId }, ac.signal)
        .then(({ data }) => {
          if (cancelled) return;
          const entry: StripState = data.freshness.is_stale ? { status: "stale", analysis: data } : { status: "success", analysis: data };
          setStates((prev) => ({ ...prev, [tf]: entry }));
        })
        .catch((e) => {
          if (cancelled) return;
          if (e instanceof ApiError) {
            setStates((prev) => ({ ...prev, [tf]: { status: "error", code: e.code, message: e.message, requestId: e.requestId } }));
          } else if ((e as Error).name === "AbortError") {
            // ignore
          } else {
            setStates((prev) => ({ ...prev, [tf]: { status: "error", code: "unknown", message: String(e), requestId: "" } }));
          }
        });
    }
    return () => {
      cancelled = true;
      for (const ac of controllers.values()) ac.abort();
    };
  }, [symbol, strategyId]);

  return (
    <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-2">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Multi-timeframe — independent backend observations</span>
        <span className="mono text-[11px] text-[var(--color-text-tertiary)]">Each card loads separately · partial failure allowed</span>
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {STRIP_TFS.map((tf) => {
          const st = states[tf];
          const active = tf === activeTf;
          if (!st || st.status === "loading") {
            return (
              <div key={tf} className={`rounded-sm border p-2.5 ${active ? "border-[var(--color-purple-accent)] bg-[var(--color-purple-subtle)]" : "border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]"}`}>
                <div className="mono text-[11px] font-medium text-[var(--color-text-secondary)]">{tf}</div>
                <div className="mt-2 h-3 w-16 animate-pulse rounded-sm bg-[var(--color-bg-surface-3)]" />
                <div className="mt-1 mono text-[11px] text-[var(--color-text-tertiary)]">Loading…</div>
              </div>
            );
          }
          if (st.status === "error") {
            return (
              <div key={tf} className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2.5">
                <div className="flex items-center justify-between">
                  <span className="mono text-[11px] font-medium text-[var(--color-text-tertiary)]">{tf}</span>
                  <Badge variant="neutral">{st.code}</Badge>
                </div>
                <div className="mt-1 text-[11px] leading-tight text-[var(--color-text-secondary)] line-clamp-2">{st.message}</div>
                {st.requestId && <div className="mono mt-1 text-[10px] text-[var(--color-text-tertiary)]">id {st.requestId.slice(0, 8)}</div>}
                <button onClick={() => onSelect(tf)} className="mt-2 text-[11px] font-medium text-[var(--color-purple-accent)] hover:underline">
                  Select →
                </button>
              </div>
            );
          }
          const a = st.analysis;
          return (
            <button
              key={tf}
              onClick={() => onSelect(tf)}
              className={`rounded-sm border p-2.5 text-left transition-colors ${active ? "border-[var(--color-purple-accent)] bg-[var(--color-purple-subtle)]" : "border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] hover:border-[var(--color-border-strong)]"}`}
            >
              <div className="flex items-center justify-between gap-1">
                <span className="mono text-[11px] font-semibold text-[var(--color-text-primary)]">{tf}</span>
                {st.status === "stale" && <Badge variant="danger">Stale</Badge>}
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1">
                <Badge variant={a.range.status === "valid" ? "success" : a.range.status === "degenerate" ? "danger" : "neutral"}>{a.range.status}</Badge>
                <Badge variant="info">{a.regime.value}</Badge>
              </div>
              <div className="mono mt-1.5 text-[11px] text-[var(--color-text-secondary)]">
                {a.signal.direction !== "none" ? `${a.signal.direction.toUpperCase()} · ${a.signal.reason}` : `— ${a.signal.reason}`}
              </div>
              <div className="mono mt-0.5 text-[11px] text-[var(--color-text-tertiary)]">
                conf {a.signal.confidence.toFixed(2)} heuristic · {a.signal.confirmation !== null ? String(a.signal.confirmation) : "—"}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
