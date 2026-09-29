import { PageHeader, ContentContainer, Card } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { UnavailableState, PaperReadOnlyBanner } from "@/components/state/StatePrimitives";
import Link from "next/link";
import { Button } from "@/components/ui/Button";

export default function RiskPage() {
  return (
    <>
      <PageHeader
        title="Risk"
        description="Account gates and sizing — backend-provided, read-only. No frontend gate math."
        breadcrumbs={[{ label: "Risk" }]}
        actions={<Badge variant="danger">PAPER · READ-ONLY</Badge>}
      />
      <ContentContainer>
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <div className="space-y-4">
            <Card className="p-3">
              <h2 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Account gates — backend facts</h2>
              <div className="mt-2 grid gap-2 md:grid-cols-4">
                {["Equity","Available","Exposure","Drawdown"].map((k) => (
                  <div key={k} className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2 opacity-60">
                    <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">{k}</div>
                    <div className="mono mt-0.5 text-[11px] text-[var(--color-text-tertiary)]">—</div>
                    <div className="mt-1 h-1 rounded-pill bg-[var(--color-bg-surface-3)]"><div className="h-full w-0 bg-[var(--color-danger)]" /></div>
                  </div>
                ))}
              </div>
              <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">
                Gates <span className="text-[var(--color-text-secondary)]">max_drawdown / max_daily_drawdown / max_consecutive_losses / max_open_positions / notional caps / leverage</span> would render here from an account/risk endpoint. Currently no dedicated account endpoint is exposed — shows as <span className="text-[var(--color-text-secondary)]">—</span>, not 0.
              </div>
            </Card>

            <UnavailableState
              title="Risk overview — not currently exposed"
              description="No dedicated account/risk endpoint is currently available to populate gates. Risk preview remains available inside Pair Analysis (per-signal backend RiskDecision) and is not duplicated here as a fake summary."
            />
          </div>

          <div className="space-y-3">
            <Card className="p-3">
              <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Where risk is visible now</h3>
              <ul className="mono mt-2 list-disc space-y-1 pl-4 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                <li>Dashboard → <span className="text-[var(--color-text-primary)]">Risk strip</span> (backend RiskDecision per signal)</li>
                <li>Pair Analysis → <span className="text-[var(--color-text-primary)]">RiskSummary</span> (approved/rejected, amber, not red)</li>
                <li>Backtest → per-trade <span className="mono">risk_amount</span> and stats</li>
              </ul>
              <div className="mt-3 flex gap-2">
                <Link href="/"><Button variant="secondary" size="sm">Pair Analysis →</Button></Link>
                <Link href="/backtests"><Button variant="ghost" size="sm">Backtests</Button></Link>
              </div>
            </Card>
            <PaperReadOnlyBanner />
          </div>
        </div>
      </ContentContainer>
    </>
  );
}
