"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorState, LoadingState } from "@/components/state/StatePrimitives";
import { StrategyForm, StrategySummary } from "@/components/strategy/StrategyForm";
import { api, ApiError } from "@/lib/api/client";
import type { Strategy } from "@/lib/api/types";

export default function StrategyDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; requestId: string } | null>(null);

  // editable draft
  const [name, setName] = useState("");
  const [active, setActive] = useState(true);
  const [rangeConfig, setRangeConfig] = useState<Record<string, unknown>>({});
  const [signalConfig, setSignalConfig] = useState<Record<string, unknown>>({});
  const [riskConfig, setRiskConfig] = useState<Record<string, unknown>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<{ message: string; requestId: string } | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [duplicateLoading, setDuplicateLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.getStrategy(params.id);
      setStrategy(data);
      setName(data.name);
      setActive(data.active);
      const p = data.payload as Record<string, Record<string, unknown>>;
      setRangeConfig((p.range_config as Record<string, unknown>) ?? {});
      setSignalConfig((p.signal_config as Record<string, unknown>) ?? {});
      setRiskConfig((p.risk_config as Record<string, unknown>) ?? {});
      setDirty(false);
    } catch (e) {
      if (e instanceof ApiError) setError({ message: `${e.code}: ${e.message}`, requestId: e.requestId });
      else setError({ message: String(e), requestId: "" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  // dirty tracking
  useEffect(() => {
    if (!strategy) return;
    const p = strategy.payload as Record<string, unknown>;
    const origRange = JSON.stringify(p.range_config);
    const origSignal = JSON.stringify(p.signal_config);
    const origRisk = JSON.stringify(p.risk_config);
    const isDirty = name !== strategy.name || active !== strategy.active || JSON.stringify(rangeConfig) !== origRange || JSON.stringify(signalConfig) !== origSignal || JSON.stringify(riskConfig) !== origRisk;
    setDirty(isDirty);
  }, [name, active, rangeConfig, signalConfig, riskConfig, strategy]);

  // beforeunload warning
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  const onSave = async () => {
    setSaveError(null);
    if (!name.trim()) {
      setSaveError({ message: "Name is required (1–80).", requestId: "" });
      return;
    }
    setSaving(true);
    try {
      const { data } = await api.updateStrategy(params.id, {
        name: name.trim(),
        payload: { range_config: rangeConfig, signal_config: signalConfig, risk_config: riskConfig },
        active
      });
      setStrategy(data);
      setDirty(false);
    } catch (e) {
      if (e instanceof ApiError) setSaveError({ message: `${e.code}: ${e.message}`, requestId: e.requestId });
      else setSaveError({ message: String(e), requestId: "" });
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async () => {
    try {
      await api.deleteStrategy(params.id);
      router.push("/strategies");
    } catch (e) {
      if (e instanceof ApiError) setSaveError({ message: `${e.code}: ${e.message}`, requestId: e.requestId });
    }
  };

  const onDuplicate = async () => {
    setDuplicateLoading(true);
    setSaveError(null);
    try {
      const { data } = await api.createStrategy({
        name: `${name} (copy)`,
        payload: { range_config: rangeConfig, signal_config: signalConfig, risk_config: riskConfig },
        active
      });
      router.push(`/strategies/${data.id}`);
    } catch (e) {
      if (e instanceof ApiError) setSaveError({ message: `${e.code}: ${e.message}`, requestId: e.requestId });
    } finally {
      setDuplicateLoading(false);
    }
  };

  if (loading) {
    return (
      <>
        <PageHeader title="Strategy" breadcrumbs={[{ label: "Strategies", href: "/strategies" }, { label: params.id.slice(0, 8) }]} description="Loading reproducible configuration…" />
        <ContentContainer><LoadingState label="Loading strategy" /></ContentContainer>
      </>
    );
  }

  if (error || !strategy) {
    return (
      <>
        <PageHeader title="Strategy" breadcrumbs={[{ label: "Strategies", href: "/strategies" }, { label: "Error" }]} description="Could not load strategy." />
        <ContentContainer><ErrorState message={error?.message ?? "Not found"} requestId={error?.requestId ?? ""} onRetry={load} /></ContentContainer>
      </>
    );
  }

  const payloadJson = JSON.stringify({ range_config: rangeConfig, signal_config: signalConfig, risk_config: riskConfig }, null, 2);
  const canonicalStored = JSON.stringify(strategy.payload, null, 2);

  return (
    <>
      <PageHeader
        title={strategy.name}
        description={`${strategy.id.slice(0, 8)} · v${strategy.schema_version} · updated ${new Date(strategy.updated_at_ms).toLocaleString()} · backend hash authoritative`}
        breadcrumbs={[{ label: "Strategies", href: "/strategies" }, { label: strategy.name }]}
        actions={
          <div className="flex flex-wrap gap-2">
            <Link href={`/?strategy_id=${strategy.id}&symbol=BTC/USDT`}>
              <Button variant="secondary" size="sm">Analyze</Button>
            </Link>
            <Link href="/backtests">
              <Button variant="ghost" size="sm">Backtest →</Button>
            </Link>
            <Button variant="ghost" size="sm" onClick={onDuplicate} disabled={duplicateLoading}>{duplicateLoading ? "Duplicating…" : "Duplicate"}</Button>
            <Button variant="ghost" size="sm" onClick={() => setDeleteOpen(true)}>Delete</Button>
            <Button variant="primary" size="sm" onClick={onSave} disabled={!dirty || saving || !name.trim()}>
              {saving ? "Saving…" : dirty ? "Save changes" : "Saved"}
            </Button>
          </div>
        }
      />
      <ContentContainer>
        {dirty && <div className="mb-3 rounded-sm border border-[rgba(124,92,255,0.18)] bg-[var(--color-purple-subtle)] px-3 py-1.5 text-[12px] text-[var(--color-purple-accent)]">Unsaved changes — you have not yet saved this configuration.</div>}
        {saveError && <div className="mb-3"><ErrorState message={saveError.message} requestId={saveError.requestId} /></div>}

        <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
          <StrategyForm name={name} setName={setName} active={active} setActive={setActive} rangeConfig={rangeConfig} setRangeConfig={setRangeConfig} signalConfig={signalConfig} setSignalConfig={setSignalConfig} riskConfig={riskConfig} setRiskConfig={setRiskConfig} />
          <div className="space-y-3">
            <StrategySummary name={name} active={active} rangeConfig={rangeConfig} signalConfig={signalConfig} riskConfig={riskConfig} payloadJson={canonicalStored} updatedAt={strategy.updated_at_ms} />
            <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
              <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Reproducibility</div>
              <div className="mono mt-1 text-[11px] text-[var(--color-text-secondary)]">Stored id {strategy.id} · owner {strategy.owner_user_id.slice(0, 8)} · schema {strategy.schema_version}</div>
              <details className="mt-2">
                <summary className="cursor-pointer text-[11px] font-medium text-[var(--color-text-secondary)]">Draft payload (unsaved preview)</summary>
                <pre className="mono mt-1 max-h-32 overflow-auto rounded-sm bg-[var(--color-bg-surface-2)] p-2 text-[11px] text-[var(--color-text-tertiary)]">{payloadJson}</pre>
              </details>
              <div className="mt-2 flex gap-1">
                <Badge variant={dirty ? "warning" : "success"}>{dirty ? "Unsaved" : "In sync with backend"}</Badge>
                <Badge variant="neutral">backend validates</Badge>
              </div>
            </div>

            <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
              <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Handoff</div>
              <div className="mt-2 flex flex-col gap-2">
                <Link href={`/?strategy_id=${strategy.id}&symbol=BTC/USDT`} className="rounded-sm bg-[var(--color-purple-accent)] px-3 py-1.5 text-center text-[12px] font-medium text-white hover:bg-[#6d4af0]">Analyze with this strategy →</Link>
                <Link href="/backtests" className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-3 py-1.5 text-center text-[12px] font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]">Open Backtests (strategy selectable there)</Link>
                <span className="mono text-[11px] text-[var(--color-text-tertiary)]">Full backtest UI arrives Phase 14 — deep-link only now.</span>
              </div>
            </div>
          </div>
        </div>

        <Dialog open={deleteOpen} onClose={() => setDeleteOpen(false)} title="Disable strategy?" description="Backend soft-deletes (active=false). Historical trades/backtests referencing it are preserved per backend.">
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setDeleteOpen(false)}>Cancel</Button>
            <Button variant="danger" onClick={onDelete}>Disable</Button>
          </div>
        </Dialog>
      </ContentContainer>
    </>
  );
}
