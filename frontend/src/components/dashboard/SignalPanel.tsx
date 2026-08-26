import { Badge } from "@/components/ui/Badge";
import { ConfidenceHeuristic } from "./Badges";
import type { PairAnalysis } from "@/lib/api/types";

export function SignalPanel({ analysis }: { analysis: PairAnalysis | null }) {
  if (!analysis) {
    return (
      <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-4">
        <div className="h-4 w-28 animate-pulse rounded-sm bg-[var(--color-bg-surface-2)]" />
        <div className="mt-3 h-12 animate-pulse rounded-sm bg-[var(--color-bg-surface-2)]" />
      </div>
    );
  }
  const s = analysis.signal;
  const isLong = s.direction === "long";
  const isShort = s.direction === "short";
  const isNone = s.direction === "none";

  const reasonLabel: Record<string, string> = {
    support_edge_setup: "Support edge setup",
    resistance_edge_setup: "Resistance edge setup",
    price_mid_range: "Price in middle (no-trade)",
    price_outside_range: "Price outside range",
    non_tradable_range: "Non-tradable range",
    confirmation_not_met: "Confirmation not met"
  };

  return (
    <div className="space-y-3 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Signal</h2>
        <Badge variant={isLong ? "bull" : isShort ? "bear" : "neutral"} icon={isLong ? "▲" : isShort ? "▼" : "—"}>
          {isLong ? "LONG" : isShort ? "SHORT" : "NONE"}
        </Badge>
      </div>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2 text-[13px]">
          <span className="font-medium text-[var(--color-text-primary)]">{reasonLabel[s.reason] ?? s.reason}</span>
          {s.position_in_range !== null && (
            <span className="mono text-[11px] text-[var(--color-text-tertiary)]">pos {(s.position_in_range * 100).toFixed(1)}%</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <ConfidenceHeuristic value={s.confidence} />
          <span className="text-[11px] text-[var(--color-text-tertiary)]">heuristic — not probability</span>
        </div>
        {s.metadata && Object.keys(s.metadata).length > 0 && (
          <details className="group rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5">
            <summary className="cursor-pointer list-none text-[11px] font-medium text-[var(--color-text-secondary)]">Signal metadata</summary>
            <pre className="mono mt-2 max-h-24 overflow-auto text-[11px] text-[var(--color-text-tertiary)]">{JSON.stringify(s.metadata, null, 2)}</pre>
          </details>
        )}
      </div>

      <div className="border-t border-[var(--color-border-subtle)] pt-3">
        <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Confirmation</h3>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <Badge variant="neutral">{s.confirmation_policy ?? "policy —"}</Badge>
          {s.confirmation === true && <Badge variant="osc" icon="●">Confirmed</Badge>}
          {s.confirmation === false && <Badge variant="neutral" icon="○">Not confirmed</Badge>}
          {s.confirmation === null && <Badge variant="neutral">—</Badge>}
          {analysis.oscillator.value !== null && analysis.oscillator.value !== undefined && (
            <span className="mono text-[11px] text-[var(--color-text-secondary)]">
              {analysis.oscillator.type ?? "osc"} {analysis.oscillator.value.toFixed(1)}
              {analysis.oscillator.oversold !== null ? ` · OS ${analysis.oscillator.oversold}` : ""}
              {analysis.oscillator.overbought !== null ? ` · OB ${analysis.oscillator.overbought}` : ""}
            </span>
          )}
        </div>
        <div className="mt-1 text-[11px] text-[var(--color-text-tertiary)]">Oscillator is backend-provided; confirmation rendered as received.</div>
      </div>

      <div className="rounded-sm border border-dashed border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]/60 p-2.5">
        <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Divergence</div>
        <div className="mt-1 text-[11px] leading-relaxed text-[var(--color-text-tertiary)]">
          <span className="rounded-pill bg-[var(--color-bg-surface-1)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--color-text-secondary)]">Planned / Future</span>{" "}
          No backend divergence contract in Phase 9. Detection, fields and API are future work; this placeholder marks the intended product direction.
        </div>
      </div>

      {!isNone && isNone && null}
    </div>
  );
}
