import { Badge } from "@/components/ui/Badge";

export function PositionMeter({ value }: { value: number | null | undefined }) {
  const has = value !== null && value !== undefined && Number.isFinite(value);
  const pct = has ? Math.max(-0.05, Math.min(1.05, value as number)) : null;
  const zone = (() => {
    if (pct === null) return { label: "—", sub: "no range" };
    if (pct < 0 || pct > 1) return { label: "OUTSIDE", sub: "no-trade" };
    if (pct < 0.25) return { label: "Lower edge", sub: "LONG zone" };
    if (pct > 0.75) return { label: "Upper edge", sub: "SHORT zone" };
    return { label: "Middle", sub: "NO-TRADE" };
  })();

  return (
    <div className="min-w-[140px]">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium tracking-wide text-[var(--color-text-secondary)]">{zone.label}</span>
        <span className="mono text-[11px] text-[var(--color-text-tertiary)]">{zone.sub}</span>
      </div>
      <div className="relative mt-1 h-[6px] overflow-hidden rounded-pill bg-[var(--color-bg-surface-2)]">
        {/* zones */}
        <div className="absolute inset-y-0 left-0 w-[25%] bg-[rgba(142,161,190,0.16)]" aria-hidden />
        <div className="absolute inset-y-0 right-0 w-[25%] bg-[rgba(142,161,190,0.16)]" aria-hidden />
        <div className="absolute inset-y-0 left-[25%] right-[25%] bg-[rgba(107,122,144,0.14)]" style={{ backgroundImage: "repeating-linear-gradient(45deg, transparent 0 4px, rgba(107,122,144,0.18) 4px 5px)" }} aria-hidden />
        {pct !== null && (
          <span
            aria-hidden
            className="absolute top-1/2 h-[10px] w-[2px] -translate-y-1/2 rounded-full bg-[var(--color-text-primary)] shadow-sm"
            style={{ left: `calc(${Math.max(0, Math.min(1, pct)) * 100}% - 1px)` }}
          />
        )}
      </div>
      <div className="mt-1 flex justify-between mono text-[10px] text-[var(--color-text-tertiary)]">
        <span>0%</span>
        <span>{has ? `${((value as number) * 100).toFixed(0)}%` : "—"}</span>
        <span>100%</span>
      </div>
    </div>
  );
}

export function ConfidenceCells({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined || !Number.isFinite(value as number)) {
    return <span className="mono text-[11px] text-[var(--color-text-tertiary)]">—</span>;
  }
  const pct = Math.max(0, Math.min(1, value as number));
  const segs = 4;
  const filled = Math.round(pct * segs);
  return (
    <span className="inline-flex items-center gap-1" aria-label={`Confidence heuristic ${(pct).toFixed(2)}`}>
      <span className="flex gap-0.5" aria-hidden>
        {Array.from({ length: segs }).map((_, i) => (
          <span key={i} className={`h-1.5 w-2.5 rounded-xs ${i < filled ? "bg-[var(--color-success)]" : "bg-[var(--color-bg-surface-3)]"}`} />
        ))}
      </span>
      <span className="mono text-[11px] text-[var(--color-text-secondary)]">{pct.toFixed(2)}</span>
    </span>
  );
}

export function SignalBadge({ direction, reason }: { direction: string; reason: string }) {
  if (direction === "long") return <Badge variant="bull" icon="▲">LONG</Badge>;
  if (direction === "short") return <Badge variant="bear" icon="▼">SHORT</Badge>;
  if (reason === "price_mid_range") return <Badge variant="neutral">— No setup (mid)</Badge>;
  if (reason === "price_outside_range") return <Badge variant="neutral">— Outside</Badge>;
  if (reason === "confirmation_not_met") return <Badge variant="osc">○ Awaiting conf.</Badge>;
  if (reason === "non_tradable_range") return <Badge variant="danger">— No range</Badge>;
  return <Badge variant="neutral">— None</Badge>;
}

export function ConfirmationBadge({ confirmation, policy }: { confirmation: boolean | null; policy: string | null }) {
  if (policy === "ignored") return <Badge variant="neutral">Ignored</Badge>;
  if (confirmation === true) return <Badge variant="osc" icon="●">Confirmed</Badge>;
  if (confirmation === false) return <Badge variant="neutral" icon="○">Not confirmed</Badge>;
  if (policy === "required") return <Badge variant="danger" icon="◐">Awaiting</Badge>;
  return <Badge variant="neutral">—</Badge>;
}
