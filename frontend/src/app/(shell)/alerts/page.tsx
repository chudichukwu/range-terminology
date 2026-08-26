import { PageHeader, ContentContainer, Card } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { UnavailableState, PaperReadOnlyBanner } from "@/components/state/StatePrimitives";

export default function AlertsPage() {
  return (
    <>
      <PageHeader
        title="Alerts"
        description="Monitoring for analytical conditions — alerts notify about research state, never submit orders. Backend remains the source of truth."
        breadcrumbs={[{ label: "Alerts" }]}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant="danger">PAPER · READ-ONLY</Badge>
            <Badge variant="neutral">0 alerts · backend</Badge>
          </div>
        }
      />
      <ContentContainer>
        <div className="space-y-4">
          {/* Operational boundary assessment — honest state */}
          <Card className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Operational boundary — audited 2026</h2>
                <p className="mono mt-1 max-w-[68ch] text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                  Inspected <span className="text-[var(--color-text-primary)]">backend/src/api/routers/*</span>, <span className="text-[var(--color-text-primary)]">schemas/*</span>, <span className="text-[var(--color-text-primary)]">services/*</span>, <span className="text-[var(--color-text-primary)]">persistence/models</span>, and existing tests. No alert router, schema, service, domain model, notification service, or persistence table exists. No <span className="mono">/alerts</span> endpoint is exposed.
                </p>
              </div>
              <Badge variant="neutral" icon="◌">Unavailable</Badge>
            </div>

            <div className="mt-3 grid gap-2 md:grid-cols-3">
              <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2.5">
                <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Routers found</div>
                <div className="mono mt-1 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                  analysis, watchlists, strategies, backtests, trades, exchanges, markets, admin, auth
                </div>
                <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">No <span className="text-[var(--color-text-secondary)]">alerts</span> router</div>
              </div>
              <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2.5">
                <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Schemas / Services</div>
                <div className="mono mt-1 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">No alert schema, no alert service, no notification service</div>
                <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">Closest: <span className="text-[var(--color-text-secondary)]">audit events</span> (admin) — not alerts</div>
              </div>
              <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2.5">
                <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Frontend contract</div>
                <div className="mono mt-1 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">No <span className="mono">api.*Alerts</span> helper added — none to add</div>
                <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">Count not fabricated; “0 alerts · backend” is literal (no endpoint to count)</div>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2 rounded-sm border border-[rgba(245,158,11,0.16)] bg-[var(--color-danger-bg)] px-2.5 py-2">
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-[var(--color-danger)]" />
              <span className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-danger)]">Assessment</span>
              <span className="mono text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                Alert/notification capability is <span className="font-medium text-[var(--color-text-primary)]">not currently implemented/exposed</span>. This workspace therefore presents the planned boundary honestly rather than inventing an alert engine.
              </span>
            </div>
          </Card>

          {/* Honest unavailable state — not empty */}
          <UnavailableState
            title="Alerts — not currently available"
            description="No alert backend exists to list, create, or deliver alerts. This is distinct from “no alerts exist.” The planned alert surface is described below for orientation; no records, toggles, or channels are operational and no fake alert rows are shown."
          />

          {/* Planned surface — visually subordinate, clearly future */}
          <Card className="p-4 opacity-95">
            <div className="flex items-center gap-2">
              <h2 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Planned alert surface — reference only</h2>
              <Badge variant="neutral">FUTURE / PLANNED</Badge>
              <span className="ml-auto mono hidden text-[11px] text-[var(--color-text-tertiary)] md:inline">Stitch reference — Obsidian Violet, workstation hierarchy preserved</span>
            </div>
            <p className="mono mt-1 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
              When implemented, alerts will be presentation/orchestration over backend-provided condition, symbol, timeframe, strategy, range state, signal, and freshness — without inventing probability or win-rate predictions.
            </p>

            <div className="mt-3 overflow-hidden rounded-sm border border-dashed border-[var(--color-border-subtle)]">
              {/* Desktop table sketch */}
              <div className="hidden md:block">
                <table className="w-full text-left opacity-60" role="table" aria-label="Planned alert table — not operational">
                  <thead className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]">
                    <tr className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                      <th scope="col" className="px-3 py-2 font-medium">Condition</th>
                      <th scope="col" className="px-3 py-2 font-medium">Symbol / TF</th>
                      <th scope="col" className="px-3 py-2 font-medium">Strategy</th>
                      <th scope="col" className="px-3 py-2 font-medium">Status</th>
                      <th scope="col" className="px-3 py-2 font-medium">Last triggered</th>
                      <th scope="col" className="px-3 py-2 font-medium">Notifications</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-[var(--color-border-subtle)] last:border-0">
                      <td className="px-3 py-2 mono text-[11px] text-[var(--color-text-tertiary)]">e.g. VALID range · support edge</td>
                      <td className="px-3 py-2 mono text-[11px] text-[var(--color-text-tertiary)]">BTC/USDT · 1h</td>
                      <td className="px-3 py-2 mono text-[11px] text-[var(--color-text-tertiary)]">My Range · a1b2c3</td>
                      <td className="px-3 py-2"><Badge variant="neutral">planned</Badge></td>
                      <td className="px-3 py-2 mono text-[11px] text-[var(--color-text-tertiary)]">—</td>
                      <td className="px-3 py-2 mono text-[11px] text-[var(--color-text-tertiary)]">—</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2 mono text-[11px] text-[var(--color-text-tertiary)]">e.g. RANGING regime enter</td>
                      <td className="px-3 py-2 mono text-[11px] text-[var(--color-text-tertiary)]">ETH/USDT · 4h</td>
                      <td className="px-3 py-2 mono text-[11px] text-[var(--color-text-tertiary)]">—</td>
                      <td className="px-3 py-2"><Badge variant="neutral">future</Badge></td>
                      <td className="px-3 py-2 mono text-[11px] text-[var(--color-text-tertiary)]">—</td>
                      <td className="px-3 py-2 mono text-[11px] text-[var(--color-text-tertiary)]">—</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              {/* Mobile cards sketch */}
              <div className="grid gap-2 p-2 md:hidden">
                <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2 opacity-70">
                  <div className="flex items-center justify-between gap-2">
                    <span className="mono text-[11px] font-medium text-[var(--color-text-tertiary)]">VALID range · support edge</span>
                    <Badge variant="neutral">planned</Badge>
                  </div>
                  <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">BTC/USDT · 1h · My Range</div>
                </div>
                <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2 opacity-70">
                  <div className="flex items-center justify-between gap-2">
                    <span className="mono text-[11px] font-medium text-[var(--color-text-tertiary)]">RANGING enter</span>
                    <Badge variant="neutral">future</Badge>
                  </div>
                  <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">ETH/USDT · 4h</div>
                </div>
              </div>
            </div>

            <div className="mt-3 grid gap-2 text-[11px] md:grid-cols-3">
              <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2">
                <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">RANGING boundary</div>
                <div className="mono mt-1 leading-relaxed text-[var(--color-text-secondary)]">
                  <span className="font-medium text-[var(--color-text-primary)]">RANGING-triggered alerts</span> are <span className="font-medium text-[var(--color-text-primary)]">planned and not currently available</span>. Do not create “Alert when market enters RANGING” rule builder now.
                </div>
              </div>
              <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2">
                <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Notifications</div>
                <div className="mono mt-1 leading-relaxed text-[var(--color-text-secondary)]">No email/browser/webhook/Telegram/Discord/push channel is exposed by the backend. No channel configuration is shown as operational.</div>
              </div>
              <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2">
                <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Execution</div>
                <div className="mono mt-1 leading-relaxed text-[var(--color-text-secondary)]">Alerts will <span className="font-medium text-[var(--color-danger)]">never</span> submit/cancel orders or modify positions. PAPER / READ-ONLY is preserved.</div>
              </div>
            </div>

            <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">
              Semantic colors remain locked: <span className="text-[var(--color-success)]">green success</span> · <span className="text-[var(--color-bear)]">red bearish</span> · <span className="text-[var(--color-danger)]">amber PAPER/warning</span> · <span className="text-[var(--color-slate)]">slate range</span> · <span className="text-[var(--color-osc)]">lavender osc</span> · <span className="text-[var(--color-purple-accent)]">purple chrome only</span>.
            </div>
          </Card>

          <PaperReadOnlyBanner />

          <div className="mono rounded-sm border border-dashed border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)]/40 px-3 py-2 text-[11px] leading-relaxed text-[var(--color-text-tertiary)]">
            This phase intentionally creates <span className="font-medium text-[var(--color-text-secondary)]">no backend alert engine</span>, no <span className="mono">/alerts</span> endpoint, and no fake records. When a real alert contract is introduced, it will reuse existing <span className="mono">apiFetch</span> + <span className="mono">X-Request-Id</span> + <span className="mono">ApiError</span> + <span className="mono">Badge/Badge+icon+text</span> patterns and preserve Obsidian Violet workstation density.
          </div>
        </div>
      </ContentContainer>
    </>
  );
}
