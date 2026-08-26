"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorState, LoadingState } from "@/components/state/StatePrimitives";
import { PerformanceSummary } from "@/components/backtest/PerformanceSummary";
import { EquityCurve } from "@/components/backtest/EquityCurve";
import { RegimeZoneBreakdown } from "@/components/backtest/RegimeZoneBreakdown";
import { TradeTable } from "@/components/backtest/TradeTable";
import { api, ApiError } from "@/lib/api/client";
import type { BacktestDetail } from "@/lib/api/types";

export default function BacktestRunPage({ params }: { params: { runId: string } }) {
  const [detail, setDetail] = useState<BacktestDetail | null>(null);
  const [error, setError] = useState<{ message: string; requestId: string; code: string } | null>(null);

  useEffect(() => {
    api.getBacktest(params.runId)
      .then(({ data }) => setDetail(data))
      .catch((e) => {
        if (e instanceof ApiError) setError({ message: `${e.code}: ${e.message}`, requestId: e.requestId, code: e.code });
        else setError({ message: String(e), requestId: "", code: "unknown" });
      });
  }, [params.runId]);

  if (error) {
    const title = error.code === "not_found" ? "Run not found" : error.code === "forbidden" ? "Forbidden" : error.code === "unauthenticated" ? "Sign in required" : "Could not load run";
    return (
      <>
        <PageHeader title={title} breadcrumbs={[{ label: "Backtests", href: "/backtests" }, { label: params.runId.slice(0, 8) }]} description="Research run detail — backend is source of truth." />
        <ContentContainer><ErrorState message={error.message} requestId={error.requestId} /></ContentContainer>
      </>
    );
  }

  if (!detail) {
    return (
      <>
        <PageHeader title={`Backtest ${params.runId.slice(0, 8)}`} breadcrumbs={[{ label: "Backtests", href: "/backtests" }, { label: params.runId.slice(0, 8) }]} description="Loading deterministic run…" />
        <ContentContainer><LoadingState label="Loading backtest result" /></ContentContainer>
      </>
    );
  }

  const stats = detail.statistics;
  const cfg = detail.config as Record<string, unknown>;

  return (
    <>
      <PageHeader
        title={`Backtest ${detail.run_id.slice(0, 8)}`}
        description={`${detail.symbol} · ${detail.timeframe} · ${new Date(detail.period_start_ms).toLocaleDateString()} → ${new Date(detail.period_end_ms).toLocaleDateString()} · config ${detail.config_hash.slice(0, 8)} · engine ${detail.engine_version}`}
        breadcrumbs={[{ label: "Backtests", href: "/backtests" }, { label: detail.run_id.slice(0, 8) }]}
        actions={
          <div className="flex gap-2">
            <Badge variant="neutral">{detail.timeframe}</Badge>
            <Badge variant="success">{detail.symbol}</Badge>
            <Link href={`/strategies`}><Button variant="ghost" size="sm">Strategies</Button></Link>
          </div>
        }
      />
      <ContentContainer>
        <div className="space-y-4">
          {/* Market / Config */}
          <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
            <h2 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Market / Config</h2>
            <div className="mt-2 grid gap-3 mono text-[11px] text-[var(--color-text-secondary)] md:grid-cols-3">
              <div>
                <div className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Window</div>
                <div>{new Date(detail.period_start_ms).toISOString().slice(0, 10)} → {new Date(detail.period_end_ms).toISOString().slice(0, 10)}</div>
                <div>Capital {detail.initial_capital.toLocaleString()} → {detail.final_equity.toLocaleString()} (peak {detail.peak_equity.toLocaleString()})</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Config</div>
                <div>Range {(cfg.range_config as any)?.mode ?? "—"} · Signal {(cfg.signal_config as any)?.confirmation_policy ?? "—"}</div>
                <div className="text-[var(--color-text-tertiary)]">fee {(cfg.fee_rate as number)?.toString() ?? "0.0005"} · slip {(cfg.slippage_rate as number)?.toString() ?? "0.0002"}</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Reproducibility</div>
                <div>run_id {detail.run_id.slice(0, 12)} · hash {detail.config_hash.slice(0, 12)}</div>
                <div>engine {detail.engine_version} · created {new Date(detail.created_at_ms).toLocaleString()}</div>
              </div>
            </div>
            <details className="mt-2">
              <summary className="cursor-pointer text-[11px] font-medium text-[var(--color-purple-accent)]">Canonical config JSON (backend)</summary>
              <pre className="mono mt-1 max-h-40 overflow-auto rounded-sm bg-[var(--color-bg-surface-2)] p-2 text-[11px] text-[var(--color-text-tertiary)]">{JSON.stringify(cfg, null, 2)}</pre>
            </details>
            <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">Backend-authoritative identifiers. Do not approximate hash in frontend.</div>
          </div>

          {/* Performance */}
          <PerformanceSummary stats={stats as any} initialCapital={detail.initial_capital} finalEquity={detail.final_equity} />

          {/* Equity */}
          <div>
            <h2 className="mb-2 text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Equity — research instrument</h2>
            <EquityCurve points={detail.equity_curve} initialCapital={detail.initial_capital} />
          </div>

          {/* Regime / Zone */}
          <RegimeZoneBreakdown regimeCounts={detail.regime_counts} zoneCounts={detail.zone_counts} />

          {/* Trades */}
          <div>
            <h2 className="mb-2 text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Trade-by-trade — StoredTrade facts</h2>
            <TradeTable trades={detail.trades} />
          </div>

          {/* Data quality note */}
          <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
            <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-warning)]">Research safety</h3>
            <div className="mono mt-1 text-[11px] text-[var(--color-text-secondary)]">
              Quality, gaps, forming candles and source/provider are reported via backend `DataQualityReport` and persistence coverage where available. No React inference. Missing coverage shows “—”, not 0. This run’s trades and equity are deterministic replay results; not live.
            </div>
          </div>
        </div>
      </ContentContainer>
    </>
  );
}
