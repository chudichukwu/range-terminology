import { PageHeader, ContentContainer, Card } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { UnavailableState, PaperReadOnlyBanner } from "@/components/state/StatePrimitives";
import Link from "next/link";
import { Button } from "@/components/ui/Button";

export default function PositionsPage() {
  return (
    <>
      <PageHeader
        title="Positions"
        description="Operational/current trading state — backend is source of truth. Distinct from Journal (historical). PAPER / READ-ONLY."
        breadcrumbs={[{ label: "Positions" }]}
        actions={<Badge variant="danger">PAPER · READ-ONLY</Badge>}
      />
      <ContentContainer>
        <div className="grid gap-4">
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <h2 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Operational positions</h2>
              <Badge variant="neutral">unavailable</Badge>
            </div>
            <div className="mt-2 overflow-hidden rounded-sm border border-[var(--color-border-subtle)]">
              <table className="w-full text-left opacity-60" role="table" aria-label="Positions — unavailable">
                <thead className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]">
                  <tr className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                    <th scope="col" className="px-3 py-2 font-medium">Symbol</th>
                    <th scope="col" className="px-3 py-2 font-medium">Side</th>
                    <th scope="col" className="px-3 py-2 font-medium">Quantity</th>
                    <th scope="col" className="px-3 py-2 font-medium">Entry / Mark</th>
                    <th scope="col" className="px-3 py-2 font-medium">Unrealized P&L</th>
                    <th scope="col" className="px-3 py-2 font-medium">Liquidation</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td colSpan={6} className="px-3 py-6 text-center mono text-[11px] text-[var(--color-text-tertiary)]">No operational position endpoint is currently exposed — table is intentionally unavailable, not empty.</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">Open positions would appear here when a backend <span className="text-[var(--color-text-secondary)]">GET /positions</span> exists. Currently, use Journal for historical facts.</div>
          </Card>

          <UnavailableState
            title="Positions — not currently exposed"
            description="The backend does not currently expose an operational positions endpoint. This surface is therefore honestly unavailable — not merely empty — and shows no fabricated position rows. Historical trades are available via Journal."
          />
          <div className="flex gap-2">
            <Link href="/journal"><Button variant="secondary">Open Journal →</Button></Link>
            <Link href="/"><Button variant="ghost">Pair Analysis</Button></Link>
          </div>
          <PaperReadOnlyBanner />
        </div>
      </ContentContainer>
    </>
  );
}
