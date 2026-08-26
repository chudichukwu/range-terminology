import { Badge } from "@/components/ui/Badge";
import type { PairAnalysis } from "@/lib/api/types";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">{label}</div>
      <div className="mono mt-0.5 text-[13px] font-medium text-[var(--color-text-primary)]">{value ?? <span className="text-[var(--color-text-tertiary)]">—</span>}</div>
    </div>
  );
}

export function RiskSummary({ analysis }: { analysis: PairAnalysis | null }) {
  if (!analysis) {
    return <div className="h-[88px] animate-pulse rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]" />;
  }
  const r = analysis.risk;

  if (!r) {
    return (
      <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
        <div className="flex items-center gap-2">
          <Badge variant="neutral">Risk — No preview</Badge>
          <span className="text-[11px] text-[var(--color-text-tertiary)]">No actionable signal — backend did not produce a RiskDecision. Not an error.</span>
        </div>
      </div>
    );
  }

  const approved = r.approved && r.status === "approved";
  return (
    <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={approved ? "success" : "danger"} icon={approved ? "✓" : "⚠"}>
          {approved ? "Risk — Approved" : `Risk — Rejected · ${r.rejection_reason ?? "unknown"}`}
        </Badge>
        {!approved && r.binding_constraint && <Badge variant="neutral">{r.binding_constraint}</Badge>}
        <span className="mono ml-auto text-[11px] text-[var(--color-text-tertiary)]">Paper · read-only · amber</span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
        <Field label="Entry" value={r.entry_price !== null ? r.entry_price.toLocaleString() : "—"} />
        <Field label="Stop" value={r.stop_price !== null ? r.stop_price.toLocaleString() : "—"} />
        <Field label="Target" value={r.target_price !== null ? r.target_price.toLocaleString() : "—"} />
        <Field label="Qty (req → final)" value={`${r.requested_quantity?.toFixed(4) ?? "—"} → ${r.position_quantity?.toFixed(4) ?? "—"}`} />
        <Field label="Notional / Risk" value={r.position_notional !== null ? `${r.position_notional.toFixed(2)} / ${r.risk_amount?.toFixed(2) ?? "—"}` : "—"} />
        <Field label="R:R" value={r.reward_risk_ratio !== null ? (r.reward_risk_ratio as number).toFixed(2) : "—"} />
        <Field label="Fees / Slippage" value={`${r.fees_estimate?.toFixed(2) ?? "—"} / ${r.slippage_estimate?.toFixed(2) ?? "—"}`} />
      </div>
      {r.metadata && Object.keys(r.metadata).length > 0 && (
        <details className="mt-3 rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5">
          <summary className="cursor-pointer text-[11px] font-medium text-[var(--color-text-secondary)]">Risk diagnostics</summary>
          <pre className="mono mt-2 max-h-28 overflow-auto text-[11px] text-[var(--color-text-tertiary)]">{JSON.stringify(r.metadata, null, 2)}</pre>
        </details>
      )}
      <div className="mt-2 text-[11px] text-[var(--color-text-tertiary)]">Backend-provided RiskDecision — never invented as 0. “—” means null per backend.</div>
    </div>
  );
}
