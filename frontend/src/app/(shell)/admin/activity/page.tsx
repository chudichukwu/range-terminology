"use client";

import { useEffect, useState } from "react";
import { PageHeader, ContentContainer, Card } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { LoadingState, ErrorState, PermissionDeniedState } from "@/components/state/StatePrimitives";
import { api, ApiError } from "@/lib/api/client";
import type { TradingActivity } from "@/lib/api/types";

export default function AdminActivityPage() {
  const [activity, setActivity] = useState<TradingActivity | null>(null);
  const [error, setError] = useState<{ message: string; requestId: string; code: string } | null>(null);

  useEffect(() => {
    api
      .getTradingActivity(50)
      .then(({ data }) => setActivity(data))
      .catch((e) => {
        if (e instanceof ApiError) setError({ message: e.message, requestId: e.requestId, code: e.code });
        else setError({ message: String(e), requestId: "", code: "unknown" });
      });
  }, []);

  if (error && (error.code === "forbidden" || error.code === "unauthenticated")) {
    return (
      <>
        <PageHeader title="Trading Activity" breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Activity" }]} description="Aggregated trading oversight — OWNER only." />
        <ContentContainer>
          <PermissionDeniedState />
          <div className="mt-3 mono text-[11px] text-[var(--color-text-tertiary)]">Request ID: {error.requestId || "—"} · Code: {error.code}</div>
        </ContentContainer>
      </>
    );
  }

  if (error) {
    return (
      <>
        <PageHeader title="Trading Activity" breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Activity" }]} description="Aggregated trading oversight — OWNER only." />
        <ContentContainer>
          <ErrorState message={error.message} requestId={error.requestId} />
        </ContentContainer>
      </>
    );
  }

  if (!activity) {
    return (
      <>
        <PageHeader title="Trading Activity" breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Activity" }]} description="Aggregated trading oversight — OWNER only." />
        <ContentContainer>
          <LoadingState label="Loading trading activity" />
        </ContentContainer>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Trading Activity"
        description="Backend-provided aggregation from GET /admin/trading-activity — totals + recent backtests. Read-only, not trading authority."
        breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Activity" }]}
        actions={<Badge variant="neutral">{activity.totals.trades} trades · {activity.totals.backtest_runs} runs</Badge>}
      />
      <ContentContainer>
        <div className="grid gap-3 md:grid-cols-5">
          <Card className="p-3">
            <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Trades</div>
            <div className="mono mt-1 text-[13px] font-medium text-[var(--color-text-primary)]">{activity.totals.trades}</div>
          </Card>
          <Card className="p-3">
            <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Wins</div>
            <div className="mono mt-1 text-[13px] font-medium text-[var(--color-success)]">{activity.totals.wins}</div>
          </Card>
          <Card className="p-3">
            <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Losses</div>
            <div className="mono mt-1 text-[13px] font-medium text-[var(--color-bear)]">{activity.totals.losses}</div>
          </Card>
          <Card className="p-3">
            <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Open</div>
            <div className="mono mt-1 text-[13px] font-medium text-[var(--color-text-primary)]">{activity.totals.open}</div>
          </Card>
          <Card className="p-3">
            <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Backtest runs</div>
            <div className="mono mt-1 text-[13px] font-medium text-[var(--color-text-primary)]">{activity.totals.backtest_runs}</div>
          </Card>
        </div>

        <Card className="mt-4 p-3">
          <h2 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Recent backtests — from GET /admin/trading-activity.recent_backtests</h2>
          {activity.recent_backtests.length === 0 ? (
            <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">No recent backtests.</div>
          ) : (
            <div className="mt-2 overflow-hidden rounded-sm border border-[var(--color-border-subtle)]">
              <table className="w-full text-left" role="table">
                <thead className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]">
                  <tr className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                    <th scope="col" className="px-3 py-2 font-medium">Run</th>
                    <th scope="col" className="px-3 py-2 font-medium">Symbol/TF</th>
                    <th scope="col" className="px-3 py-2 font-medium">Trades</th>
                    <th scope="col" className="px-3 py-2 font-medium">Final equity</th>
                    <th scope="col" className="px-3 py-2 font-medium">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {activity.recent_backtests.map((r) => (
                    <tr key={r.run_id} className="border-b border-[var(--color-border-subtle)] last:border-0 hover:bg-[var(--color-bg-surface-2)]">
                      <td className="mono px-3 py-1.5 text-[11px] text-[var(--color-purple-accent)]">{r.run_id.slice(0, 8)}</td>
                      <td className="mono px-3 py-1.5 text-[11px] text-[var(--color-text-secondary)]">
                        {r.symbol} · {r.timeframe}
                      </td>
                      <td className="mono px-3 py-1.5 text-[11px] text-[var(--color-text-secondary)]">{r.total_trades}</td>
                      <td className="mono px-3 py-1.5 text-[11px] text-[var(--color-text-primary)]">{r.final_equity.toFixed(0)}</td>
                      <td className="mono px-3 py-1.5 text-[11px] text-[var(--color-text-tertiary)]">{new Date(r.created_at_ms).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">
            Only fields actually returned are shown. This page <span className="font-medium text-[var(--color-text-secondary)]">does not</span> exist as <span className="mono text-[var(--color-text-secondary)]">GET /admin/activity</span> — the real contract is <span className="mono text-[var(--color-text-secondary)]">GET /admin/trading-activity</span> (frontend maps route <span className="mono">/admin/activity</span> → that endpoint). Missing → <span className="text-[var(--color-text-secondary)]">—</span>.
          </div>
        </Card>

        <div className="mt-3 rounded-md border border-amber-500/20 bg-[var(--color-danger-bg)] p-3">
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-danger)]" aria-hidden />
            <span className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-danger)]">PAPER / READ-ONLY</span>
          </div>
          <div className="mono mt-1 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">Activity is read-only aggregation. No order, position, or trading mutation is implied.</div>
        </div>
      </ContentContainer>
    </>
  );
}
