"use client";

import { useEffect, useState } from "react";
import { PageHeader, ContentContainer, Card } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { LoadingState, ErrorState, PermissionDeniedState } from "@/components/state/StatePrimitives";
import { api, ApiError } from "@/lib/api/client";
import type { SystemHealth } from "@/lib/api/types";

export default function AdminHealthPage() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [error, setError] = useState<{ message: string; requestId: string; code: string } | null>(null);

  useEffect(() => {
    api
      .getSystemHealth()
      .then(({ data }) => setHealth(data))
      .catch((e) => {
        if (e instanceof ApiError) setError({ message: e.message, requestId: e.requestId, code: e.code });
        else setError({ message: String(e), requestId: "", code: "unknown" });
      });
  }, []);

  if (error && (error.code === "forbidden" || error.code === "unauthenticated")) {
    return (
      <>
        <PageHeader title="System Health" breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Health" }]} description="Backend health facts — OWNER only." />
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
        <PageHeader title="System Health" breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Health" }]} description="Backend health facts — OWNER only." />
        <ContentContainer>
          <ErrorState message={error.message} requestId={error.requestId} />
        </ContentContainer>
      </>
    );
  }

  if (!health) {
    return (
      <>
        <PageHeader title="System Health" breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Health" }]} description="Backend health facts — OWNER only." />
        <ContentContainer>
          <LoadingState label="Loading system health" />
        </ContentContainer>
      </>
    );
  }

  const providerConfigured = health.market_data_provider === "configured";

  return (
    <>
      <PageHeader
        title="System Health"
        description="Operational health as returned by GET /admin/system-health. Only backend fields are shown."
        breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Health" }]}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant={health.status === "ok" ? "success" : "neutral"} icon={health.status === "ok" ? "●" : "○"}>
              {health.status}
            </Badge>
            <Badge variant={providerConfigured ? "success" : "neutral"} icon={providerConfigured ? "●" : "○"}>
              Market data {health.market_data_provider}
            </Badge>
          </div>
        }
      />
      <ContentContainer>
        <div className="grid gap-3 md:grid-cols-3">
          <Card className="p-3">
            <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Status</div>
            <div className="mt-1 flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${health.status === "ok" ? "bg-[var(--color-success)]" : "bg-[var(--color-neutral)]"}`} aria-hidden />
              <span className="text-[13px] font-medium text-[var(--color-text-primary)]">{health.status}</span>
            </div>
            <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">Backend explicitly returns “ok”; do not infer degraded from frontend.</div>
          </Card>
          <Card className="p-3">
            <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Schema / Engines</div>
            <div className="mono mt-1 text-[12px] text-[var(--color-text-primary)]">schema v{health.schema_version}</div>
            <pre className="mono mt-1 max-h-24 overflow-auto rounded-sm bg-[var(--color-bg-surface-2)] p-2 text-[11px] text-[var(--color-text-secondary)]">{JSON.stringify(health.engine_versions, null, 2)}</pre>
          </Card>
          <Card className="p-3">
            <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Counts / Time</div>
            <div className="mono mt-1 text-[12px] text-[var(--color-text-primary)]">users {health.user_count} · datasets {health.dataset_count}</div>
            <div className="mono mt-1 text-[11px] text-[var(--color-text-secondary)]">{new Date(health.time).toLocaleString()}</div>
            <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">provider: {health.market_data_provider}</div>
          </Card>
        </div>

        <Card className="mt-4 p-3">
          <h2 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Field-level health</h2>
          <div className="mt-2 overflow-hidden rounded-sm border border-[var(--color-border-subtle)]">
            <table className="w-full text-left" role="table">
              <thead className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]">
                <tr className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                  <th scope="col" className="px-3 py-2 font-medium">Field</th>
                  <th scope="col" className="px-3 py-2 font-medium">Value</th>
                  <th scope="col" className="px-3 py-2 font-medium">Treatment</th>
                </tr>
              </thead>
              <tbody className="mono text-[12px]">
                <Row label="status" value={health.status} variant={health.status === "ok" ? "success" : "neutral"} />
                <Row label="schema_version" value={String(health.schema_version)} />
                <Row label="market_data_provider" value={health.market_data_provider} variant={providerConfigured ? "success" : "neutral"} />
                <Row label="user_count" value={String(health.user_count)} />
                <Row label="dataset_count" value={String(health.dataset_count)} />
                <Row label="time" value={new Date(health.time).toISOString()} />
              </tbody>
            </table>
          </div>
          <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">
            No uptime, latency, CPU, memory, DB health, websocket health, or exchange health is shown — backend does not expose those values. Missing → <span className="text-[var(--color-text-secondary)]">—</span> (never inferred).
          </div>
        </Card>
      </ContentContainer>
    </>
  );
}

function Row({ label, value, variant }: { label: string; value: string; variant?: "success" | "neutral" }) {
  return (
    <tr className="border-b border-[var(--color-border-subtle)] last:border-0">
      <td className="px-3 py-1.5 text-[var(--color-text-tertiary)]">{label}</td>
      <td className="px-3 py-1.5 text-[var(--color-text-primary)]">{value || "—"}</td>
      <td className="px-3 py-1.5">
        {variant ? <Badge variant={variant}>{variant === "success" ? "healthy" : "neutral"}</Badge> : <span className="text-[var(--color-text-tertiary)]">—</span>}
      </td>
    </tr>
  );
}
