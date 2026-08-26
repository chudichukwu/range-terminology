import { Badge } from "@/components/ui/Badge";

const REGIME_ORDER = ["ranging", "trending_up", "trending_down", "transitional", "insufficient_data"] as const;
const ZONE_ORDER = ["lower_edge", "middle", "upper_edge", "outside", "no_range"] as const;

function bar(count: number, total: number) {
  const pct = total > 0 ? count / total : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-pill bg-[var(--color-bg-surface-3)]">
        <div className="h-full bg-[var(--color-purple-accent)]" style={{ width: `${pct * 100}%` }} />
      </div>
      <span className="mono text-[11px] text-[var(--color-text-secondary)]">{count}</span>
      <span className="mono text-[11px] text-[var(--color-text-tertiary)]">{(pct * 100).toFixed(0)}%</span>
    </div>
  );
}

export function RegimeZoneBreakdown({ regimeCounts, zoneCounts }: { regimeCounts: Record<string, number>; zoneCounts: Record<string, number> }) {
  const hasRegime = Object.keys(regimeCounts).length > 0 && Object.values(regimeCounts).some((v) => (v as number) > 0);
  const hasZone = Object.keys(zoneCounts).length > 0 && Object.values(zoneCounts).some((v) => (v as number) > 0);
  const regimeTotal = Object.values(regimeCounts).reduce((a, b) => (a as number) + (b as number), 0) as number;
  const zoneTotal = Object.values(zoneCounts).reduce((a, b) => (a as number) + (b as number), 0) as number;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Market Regime — research</span>
          <Badge variant="neutral">backend counts</Badge>
        </div>
        {!hasRegime ? (
          <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">Regime counts unavailable for this persisted run (pre-Phase 14). Immediate POST runs show breakdown; historical runs show “—” until counts are persisted. This is intentional — not fabricated.</div>
        ) : (
          <div className="mt-2 space-y-1.5">
            {REGIME_ORDER.map((k) => (
              <div key={k} className="flex flex-col gap-0.5">
                <div className="flex items-center gap-1.5">
                  <span className="mono text-[11px] font-medium text-[var(--color-text-secondary)]">{k}</span>
                  {k === "ranging" && <Badge variant="info">ranging</Badge>}
                  {(k === "trending_up" || k === "trending_down") && <Badge variant={k === "trending_up" ? "bull" : "bear"}>{k}</Badge>}
                </div>
                {bar((regimeCounts[k] as number) ?? 0, regimeTotal)}
              </div>
            ))}
          </div>
        )}
        <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">Ranging ≠ Valid range. RangeStatus is detection quality; MarketRegime is broader behavior. A VALID range can coexist with TRENDING_UP.</div>
      </div>

      <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Zone — research</span>
          <Badge variant="neutral">backend counts</Badge>
        </div>
        {!hasZone ? (
          <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">Zone counts unavailable for this persisted run (see above). Middle zone is NO-TRADE by design.</div>
        ) : (
          <div className="mt-2 space-y-1.5">
            {ZONE_ORDER.map((k) => (
              <div key={k} className="flex flex-col gap-0.5">
                <span className="mono text-[11px] font-medium text-[var(--color-text-secondary)]">{k}</span>
                {bar((zoneCounts[k] as number) ?? 0, zoneTotal)}
              </div>
            ))}
          </div>
        )}
        <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">lower_edge → LONG intent, middle → NO-TRADE, upper_edge → SHORT, outside/no_range → NO-TRADE.</div>
      </div>
    </div>
  );
}
