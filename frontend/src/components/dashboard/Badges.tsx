import { Badge, StatusDot } from "@/components/ui/Badge";
import type { RangeStatus, MarketRegime } from "@/lib/api/types";

export function RangeStatusBadge({ status, isTradable }: { status: RangeStatus; isTradable?: boolean }) {
  if (status === "valid")
    return (
      <Badge variant="success" icon={<StatusDot variant="success" />}>
        Range — Valid{isTradable === false ? " · not tradable" : ""}
      </Badge>
    );
  if (status === "degenerate")
    return (
      <Badge variant="danger" icon={<StatusDot variant="danger" />}>
        Range — Degenerate
      </Badge>
    );
  return (
    <Badge variant="neutral" icon={<StatusDot variant="neutral" />}>
      Range — Insufficient Data
    </Badge>
  );
}

export function MarketRegimeBadge({ regime }: { regime: MarketRegime }) {
  const map: Record<MarketRegime, { label: string; variant: "neutral" | "info" | "bull" | "bear" | "warning" }> = {
    ranging: { label: "Regime — Ranging", variant: "info" },
    trending_up: { label: "Regime — Trending Up", variant: "bull" },
    trending_down: { label: "Regime — Trending Down", variant: "bear" },
    transitional: { label: "Regime — Transitional", variant: "warning" },
    insufficient_data: { label: "Regime — Insufficient Data", variant: "neutral" }
  };
  const c = map[regime];
  return (
    <Badge variant={c.variant} icon="◆">
      {c.label}
    </Badge>
  );
}

export function ConfidenceHeuristic({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value));
  const segs = 4;
  const filled = Math.round(pct * segs);
  return (
    <span className="inline-flex items-center gap-1.5" aria-label={`Confidence heuristic ${pct.toFixed(2)}`}>
      <span className="flex gap-0.5" aria-hidden>
        {Array.from({ length: segs }).map((_, i) => (
          <span key={i} className={`h-1.5 w-3 rounded-xs ${i < filled ? "bg-[var(--color-success)]" : "bg-[var(--color-bg-surface-3)]"}`} />
        ))}
      </span>
      <span className="mono text-[11px] font-medium text-[var(--color-text-secondary)]">{pct.toFixed(2)}</span>
      <span className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">heuristic</span>
    </span>
  );
}
