import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/PageHeader";

function Shell({ icon, title, description, action, tone = "neutral" }: { icon?: string; title: string; description: string; action?: React.ReactNode; tone?: "neutral" | "amber" | "purple" }) {
  const border = tone === "amber" ? "border-[rgba(245,158,11,0.18)]" : tone === "purple" ? "border-[rgba(124,92,255,0.14)]" : "border-[var(--color-border-subtle)]";
  return (
    <Card className={`${border} p-6`}>
      <div className="mx-auto max-w-[560px] text-center">
        {icon && (
          <div aria-hidden className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-md bg-[var(--color-bg-surface-2)] text-[var(--color-text-tertiary)]">
            {icon}
          </div>
        )}
        <h3 className="text-[14px] font-semibold tracking-tight text-[var(--color-text-primary)]">{title}</h3>
        <p className="mx-auto mt-1.5 max-w-[48ch] text-[13px] leading-relaxed text-[var(--color-text-secondary)]">{description}</p>
        {action && <div className="mt-4 flex justify-center gap-2">{action}</div>}
      </div>
    </Card>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" aria-label={label} className="space-y-3">
      <div className="h-4 w-32 animate-pulse rounded-sm bg-[var(--color-bg-surface-2)]" />
      <div className="grid gap-2">
        <div className="h-12 animate-pulse rounded-md bg-[var(--color-bg-surface-2)]" />
        <div className="h-12 animate-pulse rounded-md bg-[var(--color-bg-surface-2)] opacity-80" />
        <div className="h-12 animate-pulse rounded-md bg-[var(--color-bg-surface-2)] opacity-60" />
      </div>
      <span className="sr-only">{label}</span>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  actionLabel,
  onAction
}: {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <Shell
      icon="◯"
      title={title}
      description={description}
      action={actionLabel && <Button variant="primary" onClick={onAction}>{actionLabel}</Button>}
    />
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  requestId,
  onRetry
}: {
  title?: string;
  message: string;
  requestId?: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="rounded-md border border-[rgba(245,158,11,0.18)] bg-[var(--color-danger-bg)] p-4">
      <div className="flex items-start gap-3">
        <span aria-hidden className="mt-0.5 text-[var(--color-danger)]">
          ⚠
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-medium text-[var(--color-text-primary)]">{title}</div>
          <div className="mt-1 text-[13px] leading-relaxed text-[var(--color-text-secondary)]">{message}</div>
          {requestId && <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">Request ID: {requestId}</div>}
          {onRetry && (
            <div className="mt-3">
              <Button variant="secondary" size="sm" onClick={onRetry}>
                Retry
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function UnavailableState({ title = "Unavailable", description }: { title?: string; description: string }) {
  return <Shell icon="◌" tone="neutral" title={title} description={description} />;
}

export function StaleState({ title = "Data may be stale", description, age }: { title?: string; description: string; age?: string }) {
  return (
    <div className="rounded-md border border-[rgba(245,158,11,0.16)] bg-[rgba(245,158,11,0.06)] px-3 py-2.5">
      <div className="flex items-center gap-2">
        <Badge variant="danger" icon="◐">
          Stale
        </Badge>
        {age && <span className="mono text-[11px] text-[var(--color-text-tertiary)]">{age}</span>}
      </div>
      <div className="mt-1.5 text-[13px] leading-relaxed text-[var(--color-text-secondary)]">{description}</div>
      <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">{title} — shown with last known data; no fabrication.</div>
    </div>
  );
}

export function PermissionDeniedState() {
  return (
    <Shell
      icon="⬢"
      tone="amber"
      title="Permission required"
      description="You don't have access to this area. System pages require OWNER role. If you believe this is an error, contact an owner."
    />
  );
}

export function PaperReadOnlyBanner({ compact = false }: { compact?: boolean }) {
  return (
    <div
      role="note"
      aria-label="Paper trading mode"
      className={
        compact
          ? "inline-flex items-center gap-1.5 rounded-pill bg-[var(--color-danger-bg)] px-2 py-1 text-[11px] font-medium text-[var(--color-danger)]"
          : "flex items-center gap-2 rounded-md border border-[rgba(245,158,11,0.16)] bg-[var(--color-danger-bg)] px-3 py-2"
      }
    >
      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-[var(--color-danger)] shadow-[0_0_6px_rgba(245,158,11,0.5)]" />
      <span className={compact ? "" : "text-[13px] font-medium text-[var(--color-danger)]"}>PAPER · READ-ONLY</span>
      {!compact && <span className="text-[12px] text-[var(--color-text-secondary)]">— Live order execution is not enabled. All trading views are simulation/research only.</span>}
    </div>
  );
}

export function PlaceholderPageShell({
  title,
  description
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="space-y-4">
      <PaperReadOnlyBanner />
      <Shell icon="⬔" tone="purple" title={title} description={description} />
      <div className="rounded-md border border-dashed border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)]/50 p-4">
        <div className="mono text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Foundation placeholder</div>
        <div className="mt-1 text-[13px] text-[var(--color-text-secondary)]">
          This route shell exists to establish navigation and layout. Dashboard/chart/watchlist/signal/risk/backtest/journal/exchange/admin functionality lands in later frontend phases. Backend truth is not reimplemented here.
        </div>
      </div>
    </div>
  );
}
