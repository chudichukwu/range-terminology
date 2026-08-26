"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { PairAnalysisHeader } from "@/components/dashboard/PairAnalysisHeader";
import { TradingChart } from "@/components/dashboard/TradingChart";
import { SignalPanel } from "@/components/dashboard/SignalPanel";
import { RsiPanel } from "@/components/dashboard/RsiPanel";
import { RiskSummary } from "@/components/dashboard/RiskSummary";
import { TimeframeStrip } from "@/components/dashboard/TimeframeStrip";
import { ErrorState, LoadingState, EmptyState, PaperReadOnlyBanner } from "@/components/state/StatePrimitives";
import { usePairAnalysis } from "@/hooks/usePairAnalysis";
import type { Timeframe } from "@/lib/api/types";
import { api } from "@/lib/api/client";

const DEFAULT_SYMBOL = "BTC/USDT";
const DEFAULT_TF: Timeframe = "1h";

export function DashboardClient() {
  const search = useSearchParams();
  const router = useRouter();
  const initialSymbol = search.get("symbol") ?? DEFAULT_SYMBOL;
  const initialTf = (search.get("timeframe") as Timeframe) ?? DEFAULT_TF;

  const [symbol, setSymbol] = useState(initialSymbol);
  const [timeframe, setTimeframe] = useState<Timeframe>(initialTf);
  const [strategyId, setStrategyId] = useState<string | undefined>(undefined);
  const [availableTfs, setAvailableTfs] = useState<string[] | undefined>(undefined);
  const [strategies, setStrategies] = useState<{ id: string; name: string }[]>([]);

  useEffect(() => {
    const params = new URLSearchParams(search.toString());
    const curS = params.get("symbol");
    const curTf = params.get("timeframe");
    if (curS !== symbol || curTf !== timeframe) {
      params.set("symbol", symbol);
      params.set("timeframe", timeframe);
      router.replace(`?${params.toString()}`);
    }
  }, [symbol, timeframe, router, search]);

  useEffect(() => {
    api
      .listTimeframes()
      .then(({ data }) => setAvailableTfs(data.timeframes))
      .catch(() => setAvailableTfs(undefined));
    api
      .listStrategies()
      .then(({ data }) => setStrategies(data.map((s) => ({ id: s.id, name: s.name }))))
      .catch(() => setStrategies([]));
  }, []);

  const analysisState = usePairAnalysis(symbol, timeframe, strategyId);

  return (
    <div className="flex min-h-0 flex-col">
      <PairAnalysisHeader
        analysis={analysisState.status === "success" ? analysisState.data : null}
        symbol={symbol}
        timeframe={timeframe}
        onSymbolChange={setSymbol}
        onTimeframeChange={setTimeframe}
        availableTimeframes={availableTfs}
      />

      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-subtle)] px-4 py-2">
        <label htmlFor="strategy-pick" className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">
          Strategy context
        </label>
        <select
          id="strategy-pick"
          value={strategyId ?? ""}
          onChange={(e) => setStrategyId(e.target.value || undefined)}
          className="min-w-[180px] rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-2 py-1 text-[12px] text-[var(--color-text-secondary)] focus:border-[var(--color-purple-accent)] focus:outline-none"
        >
          <option value="">Default (structural)</option>
          {strategies.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <span className="mono text-[11px] text-[var(--color-text-tertiary)]">range/signal/risk configs from backend payload</span>
        <span className="ml-auto hidden md:inline-flex">
          <PaperReadOnlyBanner compact />
        </span>
      </div>

      <div className="mx-auto w-full max-w-[1920px] flex-1 p-4">
        {analysisState.status === "idle" && (
          <EmptyState
            title="No pair selected"
            description="Pick a symbol from your watchlist or use the pair selector above to open Pair Analysis. Analysis is backend-provided; nothing is computed in React."
          />
        )}
        {analysisState.status === "loading" && (
          <div className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
              <div className="h-[420px] animate-pulse rounded-md bg-[var(--color-bg-surface-1)] md:h-[52vh]" />
              <LoadingState label="Loading signal and confirmation" />
            </div>
            <LoadingState label="Loading risk and oscillator" />
          </div>
        )}
        {analysisState.status === "error" && (
          <ErrorState
            title={
              analysisState.code === "unauthenticated"
                ? "Sign in required"
                : analysisState.code === "provider_error"
                  ? "Market data unavailable"
                  : analysisState.code === "validation_error"
                    ? "Invalid request"
                    : "Could not load analysis"
            }
            message={
              analysisState.code === "unauthenticated"
                ? "This workstation requires authentication. Sign in to view analysis."
                : `${analysisState.message} — backend returned ${analysisState.code}.`
            }
            requestId={analysisState.requestId}
            onRetry={() => window.location.reload()}
          />
        )}
        {analysisState.status === "success" && (
          <div className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
              <div className="min-w-0 space-y-4">
                <TradingChart analysis={analysisState.data} />
                <RsiPanel analysis={analysisState.data} />
                <RiskSummary analysis={analysisState.data} />
              </div>
              <div className="space-y-4">
                <SignalPanel analysis={analysisState.data} />
                <PaperReadOnlyBanner />
                <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
                  <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Backend-provided facts</div>
                  <ul className="mono mt-2 space-y-1 text-[11px] text-[var(--color-text-secondary)]">
                    <li>
                      Range: <span className="text-[var(--color-text-primary)]">{analysisState.data.range.status}</span> · {analysisState.data.range.is_tradable ? "tradable" : "not tradable"}
                    </li>
                    <li>
                      Regime: <span className="text-[var(--color-text-primary)]">{analysisState.data.regime.value}</span> · ER {analysisState.data.regime.efficiency_ratio?.toFixed(2) ?? "—"}
                    </li>
                    <li>
                      Signal: <span className="text-[var(--color-text-primary)]">{analysisState.data.signal.direction}</span> · {analysisState.data.signal.reason}
                    </li>
                    <li>
                      Quality: {analysisState.data.quality_issues.length ? analysisState.data.quality_issues.join(", ") : "clean"} · {analysisState.data.is_analysis_safe ? "analysis-safe" : "not analysis-safe"}
                    </li>
                    <li>
                      Strategy: {analysisState.data.strategy_name ?? "default"} · {analysisState.data.strategy_id?.slice(0, 8) ?? "—"}
                    </li>
                  </ul>
                </div>
              </div>
            </div>
            <TimeframeStrip symbol={symbol} activeTf={timeframe} strategyId={strategyId} onSelect={setTimeframe} />
            <div className="rounded-md border border-dashed border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)]/40 px-3 py-2 text-[11px] text-[var(--color-text-tertiary)]">
              Watchlist → Dashboard flow: open a watchlist, select a pair, and append <span className="mono text-[var(--color-text-secondary)]">?symbol=BTC/USDT&timeframe=1h</span> to deep-link into this Pair Analysis. No watchlist business logic is duplicated here.
            </div>
            {(analysisState.data.range.status === "insufficient_data" || analysisState.data.regime.value === "insufficient_data") && (
              <div className="rounded-md border border-[rgba(245,158,11,0.18)] bg-[var(--color-danger-bg)] p-3 text-[13px] leading-relaxed text-[var(--color-text-secondary)]">
                Insufficient data — backend reports <span className="font-medium text-[var(--color-text-primary)]">{analysisState.data.range.status}</span> /{" "}
                <span className="font-medium text-[var(--color-text-primary)]">{analysisState.data.regime.value}</span>. Add more history, reduce lookback, or check ingestion. No bounds are fabricated.
              </div>
            )}
          </div>
        )}
      </div>
      <div className="border-t border-[var(--color-border-subtle)] bg-[var(--color-bg-subtle)] px-4 py-2 text-[11px] text-[var(--color-text-tertiary)]">
        Hierarchy: <span className="text-[var(--color-text-secondary)]">Market → Range/Regime → Signal/Confirmation → Risk → Execution (paper)</span> · Chart is dominant; supporting panels recede.
      </div>
    </div>
  );
}
