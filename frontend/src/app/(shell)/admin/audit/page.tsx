"use client";

import { useEffect, useMemo, useState } from "react";
import { PageHeader, ContentContainer, Card } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { LoadingState, ErrorState, PermissionDeniedState, EmptyState } from "@/components/state/StatePrimitives";
import { api, ApiError } from "@/lib/api/client";
import type { AuditEvent } from "@/lib/api/types";

type SortKey = "timestamp_ms" | "action" | "resource_type";

export default function AdminAuditPage() {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<{ message: string; requestId: string; code: string } | null>(null);
  const [filterAction, setFilterAction] = useState("");
  const [filterResource, setFilterResource] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("timestamp_ms");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [limit, setLimit] = useState(100);

  useEffect(() => {
    api
      .getAuditLog(limit)
      .then(({ data }) => setEvents(data))
      .catch((e) => {
        if (e instanceof ApiError) setError({ message: e.message, requestId: e.requestId, code: e.code });
        else setError({ message: String(e), requestId: "", code: "unknown" });
      });
  }, [limit]);

  const filtered = useMemo(() => {
    if (!events) return null;
    let list = events;
    if (filterAction.trim()) {
      const q = filterAction.toLowerCase();
      list = list.filter((ev) => ev.action.toLowerCase().includes(q));
    }
    if (filterResource.trim()) {
      const q = filterResource.toLowerCase();
      list = list.filter((ev) => ev.resource_type.toLowerCase().includes(q));
    }
    const dir = sortDir === "asc" ? 1 : -1;
    return [...list].sort((a, b) => {
      if (sortKey === "action") return dir * a.action.localeCompare(b.action);
      if (sortKey === "resource_type") return dir * a.resource_type.localeCompare(b.resource_type);
      return dir * (a.timestamp_ms - b.timestamp_ms);
    });
  }, [events, filterAction, filterResource, sortKey, sortDir]);

  const toggle = (k: SortKey) => {
    if (k === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(k);
      setSortDir(k === "timestamp_ms" ? "desc" : "asc");
    }
  };

  if (error && (error.code === "forbidden" || error.code === "unauthenticated")) {
    return (
      <>
        <PageHeader title="Audit Log" breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Audit" }]} description="Chronological audit — OWNER only." />
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
        <PageHeader title="Audit Log" breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Audit" }]} description="Chronological audit — OWNER only." />
        <ContentContainer>
          <ErrorState message={error.message} requestId={error.requestId} />
        </ContentContainer>
      </>
    );
  }

  if (!events) {
    return (
      <>
        <PageHeader title="Audit Log" breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Audit" }]} description="Chronological audit — OWNER only." />
        <ContentContainer>
          <LoadingState label="Loading audit log" />
        </ContentContainer>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Audit Log"
        description="Dense chronological audit from GET /admin/audit-log — timestamp, actor, action, resource, outcome, metadata. No secrets exposed."
        breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Audit" }]}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant="neutral">{events.length} events</Badge>
            <select value={String(limit)} onChange={(e) => setLimit(Number(e.target.value))} className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1 text-[11px] text-[var(--color-text-secondary)]">
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
              <option value={500}>500</option>
            </select>
          </div>
        }
      />
      <ContentContainer>
        <Card className="p-3">
          <div className="flex flex-wrap gap-2">
            <label className="flex items-center gap-1.5 text-[11px]">
              <span className="font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Action</span>
              <input value={filterAction} onChange={(e) => setFilterAction(e.target.value)} placeholder="exchange.connected" className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1 text-[11px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:border-[var(--color-purple-accent)] focus:outline-none" />
            </label>
            <label className="flex items-center gap-1.5 text-[11px]">
              <span className="font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Resource</span>
              <input value={filterResource} onChange={(e) => setFilterResource(e.target.value)} placeholder="exchange_connection" className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1 text-[11px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:border-[var(--color-purple-accent)] focus:outline-none" />
            </label>
            <span className="ml-auto mono text-[11px] text-[var(--color-text-tertiary)]">
              {filtered ? `${filtered.length} of ${events.length}` : ""} · sorted {sortKey} {sortDir}
            </span>
          </div>
        </Card>

        {!filtered || filtered.length === 0 ? (
          <div className="mt-3">
            <EmptyState title="No audit events match filter" description={`No events match “${filterAction || filterResource}”`} />
          </div>
        ) : events.length === 0 ? (
          <div className="mt-3">
            <EmptyState title="No audit events" description="Backend returned no audit events. This is an empty state, not unavailable." />
          </div>
        ) : (
          <>
            <div className="mt-3 hidden overflow-hidden rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] md:block">
              <table className="w-full text-left" role="table">
                <thead className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]">
                  <tr className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                    <th scope="col" className="px-3 py-2 font-medium">
                      <button onClick={() => toggle("timestamp_ms")} className={sortKey === "timestamp_ms" ? "text-[var(--color-purple-accent)]" : ""}>
                        Time {sortKey === "timestamp_ms" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                      </button>
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      <button onClick={() => toggle("action")} className={sortKey === "action" ? "text-[var(--color-purple-accent)]" : ""}>
                        Action {sortKey === "action" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                      </button>
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">Actor</th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      <button onClick={() => toggle("resource_type")} className={sortKey === "resource_type" ? "text-[var(--color-purple-accent)]" : ""}>
                        Resource {sortKey === "resource_type" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                      </button>
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">Outcome</th>
                    <th scope="col" className="px-3 py-2 font-medium">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered!.map((ev) => (
                    <>
                      <tr key={ev.id} className="border-b border-[var(--color-border-subtle)] last:border-0 hover:bg-[var(--color-bg-surface-2)]">
                        <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-secondary)]">{new Date(ev.timestamp_ms).toLocaleString()}</td>
                        <td className="mono px-3 py-2 text-[11px] font-medium text-[var(--color-text-primary)]">{ev.action}</td>
                        <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-tertiary)]">{ev.actor_user_id ? ev.actor_user_id.slice(0, 8) : "—"}</td>
                        <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-secondary)]">
                          {ev.resource_type}
                          {ev.resource_id ? ` · ${ev.resource_id.slice(0, 8)}` : ""}
                        </td>
                        <td className="px-3 py-2">
                          <Badge variant={ev.outcome === "success" ? "success" : ev.outcome === "failure" ? "bear" : "neutral"}>{ev.outcome}</Badge>
                        </td>
                        <td className="px-3 py-2">
                          <button onClick={() => setExpanded(expanded === ev.id ? null : ev.id)} className="rounded-sm border border-[var(--color-border-subtle)] px-2 py-1 text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-2)]">
                            {expanded === ev.id ? "Hide" : "View"}
                          </button>
                        </td>
                      </tr>
                      {expanded === ev.id && (
                        <tr key={`${ev.id}-meta`} className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]/50">
                          <td colSpan={6} className="px-3 py-2">
                            <div className="mono text-[11px] text-[var(--color-text-tertiary)]">id {ev.id} · metadata</div>
                            <pre className="mono mt-1 max-h-32 overflow-auto rounded-sm bg-[var(--color-bg-surface-1)] p-2 text-[11px] text-[var(--color-text-secondary)]">{JSON.stringify(ev.metadata, null, 2)}</pre>
                            <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">Metadata rendered progressively; secrets are never exposed — backend scrubs via `scrub_sensitive`.</div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="grid gap-2 md:hidden">
              {filtered!.map((ev) => (
                <div key={ev.id} className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="text-[13px] font-medium text-[var(--color-text-primary)]">{ev.action}</div>
                    <Badge variant={ev.outcome === "success" ? "success" : "neutral"}>{ev.outcome}</Badge>
                  </div>
                  <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">{new Date(ev.timestamp_ms).toLocaleString()} · {ev.resource_type}</div>
                  <button onClick={() => setExpanded(expanded === ev.id ? null : ev.id)} className="mt-2 rounded-sm border border-[var(--color-border-subtle)] px-2 py-1 text-[11px] text-[var(--color-text-secondary)]">
                    {expanded === ev.id ? "Hide metadata" : "View metadata"}
                  </button>
                  {expanded === ev.id && <pre className="mono mt-1 max-h-24 overflow-auto rounded-sm bg-[var(--color-bg-surface-2)] p-2 text-[11px] text-[var(--color-text-secondary)]">{JSON.stringify(ev.metadata, null, 2)}</pre>}
                </div>
              ))}
            </div>
          </>
        )}

        <div className="mono mt-3 text-[11px] text-[var(--color-text-tertiary)]">
          Only fields actually returned by <span className="text-[var(--color-text-secondary)]">GET /admin/audit-log</span> are shown. Missing actor/resource → <span className="text-[var(--color-text-secondary)]">—</span>; large metadata is progressively disclosed, not dumped into the main table.
        </div>
      </ContentContainer>
    </>
  );
}
