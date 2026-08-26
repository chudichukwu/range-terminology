"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorState, LoadingState, EmptyState } from "@/components/state/StatePrimitives";
import { api, ApiError } from "@/lib/api/client";
import type { Strategy } from "@/lib/api/types";

function modeFromPayload(p: Record<string, unknown>): string {
  const rc = p.range_config as Record<string, unknown> | undefined;
  return String(rc?.mode ?? "structural");
}

function signalSummary(p: Record<string, unknown>): string {
  const sc = p.signal_config as Record<string, unknown> | undefined;
  const lz = sc?.lower_edge_zone ?? 0.25;
  const uz = sc?.upper_edge_zone ?? 0.25;
  const pol = String(sc?.confirmation_policy ?? "optional");
  return `edge ${lz}/${uz} · ${pol}`;
}

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<Strategy[] | null>(null);
  const [error, setError] = useState<{ message: string; requestId: string } | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const router = useRouter();

  const load = () => {
    setError(null);
    api
      .listStrategies()
      .then(({ data }) => setStrategies(data))
      .catch((e) => {
        if (e instanceof ApiError) setError({ message: `${e.code}: ${e.message}`, requestId: e.requestId });
        else setError({ message: String(e), requestId: "" });
      });
  };

  useEffect(() => {
    load();
  }, []);

  const doDelete = async () => {
    if (!deleteId) return;
    try {
      await api.deleteStrategy(deleteId);
      setStrategies((prev) => prev?.filter((s) => s.id !== deleteId) ?? null);
      setDeleteId(null);
    } catch (e) {
      if (e instanceof ApiError) setError({ message: `${e.code}: ${e.message}`, requestId: e.requestId });
    }
  };

  const doToggle = async (s: Strategy) => {
    try {
      const { data } = await api.updateStrategy(s.id, { active: !s.active });
      setStrategies((prev) => prev?.map((x) => (x.id === s.id ? data : x)) ?? null);
    } catch (e) {
      if (e instanceof ApiError) setError({ message: `${e.code}: ${e.message}`, requestId: e.requestId });
    }
  };

  const doDuplicate = async (s: Strategy) => {
    try {
      const payload = s.payload as { range_config: Record<string, unknown>; signal_config: Record<string, unknown>; risk_config: Record<string, unknown> };
      const { data } = await api.createStrategy({ name: `${s.name} (copy)`, payload, active: s.active });
      setStrategies((prev) => (prev ? [...prev, data] : [data]));
    } catch (e) {
      if (e instanceof ApiError) setError({ message: `${e.code}: ${e.message}`, requestId: e.requestId });
    }
  };

  return (
    <>
      <PageHeader
        title="Strategies"
        description="Reproducible research configurations — RANGE + SIGNAL/CONFIRMATION + RISK. Backend validates; frontend configures."
        breadcrumbs={[{ label: "Strategies" }]}
        actions={
          <Button variant="primary" onClick={() => router.push("/strategies/new")}>
            New strategy
          </Button>
        }
      />
      <ContentContainer>
        {error && <div className="mb-3"><ErrorState message={error.message} requestId={error.requestId} onRetry={load} /></div>}

        {!strategies ? (
          <LoadingState label="Loading strategies" />
        ) : strategies.length === 0 ? (
          <EmptyState title="No strategies yet" description="Create your first strategy to define range detection, signal/confirmation and risk for paper/research workflows. Strategies are configuration, not live trading." actionLabel="New strategy" onAction={() => router.push("/strategies/new")} />
        ) : (
          <div className="overflow-hidden rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)]">
            <div className="hidden md:block">
              <table className="w-full text-left" role="table">
                <thead className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]">
                  <tr className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                    <th className="px-3 py-2 font-medium">Name</th>
                    <th className="px-3 py-2 font-medium">Range mode</th>
                    <th className="px-3 py-2 font-medium">Signal</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 font-medium">Updated</th>
                    <th className="px-3 py-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {strategies.map((s) => {
                    const payload = s.payload as Record<string, unknown>;
                    return (
                      <tr key={s.id} className="border-b border-[var(--color-border-subtle)] last:border-0 hover:bg-[var(--color-bg-surface-2)]">
                        <td className="px-3 py-2.5">
                          <Link href={`/strategies/${s.id}`} className="text-[13px] font-medium text-[var(--color-text-primary)] hover:text-[var(--color-purple-accent)] hover:underline">
                            {s.name}
                          </Link>
                          <div className="mono text-[11px] text-[var(--color-text-tertiary)]">{s.id.slice(0, 8)} · v{s.schema_version}</div>
                        </td>
                        <td className="px-3 py-2.5">
                          <Badge variant="neutral">{modeFromPayload(payload)}</Badge>
                        </td>
                        <td className="mono px-3 py-2.5 text-[11px] text-[var(--color-text-secondary)]">{signalSummary(payload)}</td>
                        <td className="px-3 py-2.5">
                          <Badge variant={s.active ? "success" : "neutral"}>{s.active ? "ACTIVE" : "DISABLED"}</Badge>
                        </td>
                        <td className="mono px-3 py-2.5 text-[11px] text-[var(--color-text-tertiary)]">{new Date(s.updated_at_ms).toLocaleString()}</td>
                        <td className="px-3 py-2.5">
                          <div className="flex flex-wrap gap-1">
                            <Link href={`/strategies/${s.id}`}>
                              <Button variant="secondary" size="sm">Open</Button>
                            </Link>
                            <Button variant="ghost" size="sm" onClick={() => doDuplicate(s)}>Duplicate</Button>
                            <Button variant="ghost" size="sm" onClick={() => doToggle(s)}>{s.active ? "Disable" : "Enable"}</Button>
                            <Button variant="ghost" size="sm" onClick={() => setDeleteId(s.id)}>Delete</Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {/* Mobile cards */}
            <div className="grid gap-2 p-2 md:hidden">
              {strategies.map((s) => {
                const payload = s.payload as Record<string, unknown>;
                return (
                  <div key={s.id} className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-3">
                    <div className="flex items-start justify-between gap-2">
                      <Link href={`/strategies/${s.id}`} className="text-[13px] font-semibold text-[var(--color-text-primary)]">{s.name}</Link>
                      <Badge variant={s.active ? "success" : "neutral"}>{s.active ? "ACTIVE" : "DISABLED"}</Badge>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <Badge variant="neutral">{modeFromPayload(payload)}</Badge>
                      <span className="mono text-[11px] text-[var(--color-text-tertiary)]">{signalSummary(payload)}</span>
                    </div>
                    <div className="mt-2 flex gap-1">
                      <Link href={`/strategies/${s.id}`} className="flex-1"><Button variant="secondary" size="sm" className="w-full">Open</Button></Link>
                      <Button variant="ghost" size="sm" onClick={() => doDuplicate(s)}>Copy</Button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-[var(--color-text-tertiary)]">
          <Badge variant="danger">PAPER · READ-ONLY</Badge>
          <span>Enabling a strategy makes it available for research/paper workflows — not live execution.</span>
        </div>

        <Dialog open={!!deleteId} onClose={() => setDeleteId(null)} title="Disable strategy?" description="This will set the strategy to DISABLED (backend soft-delete). Historical backtests referencing it are preserved.">
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setDeleteId(null)}>Cancel</Button>
            <Button variant="danger" onClick={doDelete}>Disable</Button>
          </div>
        </Dialog>
      </ContentContainer>
    </>
  );
}
