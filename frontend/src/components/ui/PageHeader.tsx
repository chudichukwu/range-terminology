import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  description,
  actions,
  breadcrumbs
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  breadcrumbs?: { label: string; href?: string }[];
}) {
  return (
    <div className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-base)] px-4 py-4 md:px-6">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="mb-2">
          <ol className="flex flex-wrap gap-1.5 text-[11px] text-[var(--color-text-tertiary)]">
            {breadcrumbs.map((b, i) => (
              <li key={i} className="flex items-center gap-1.5">
                {i > 0 && <span aria-hidden className="opacity-40">/</span>}
                {b.href ? (
                  <a href={b.href} className="hover:text-[var(--color-text-secondary)]">
                    {b.label}
                  </a>
                ) : (
                  <span aria-current="page" className="text-[var(--color-text-secondary)]">
                    {b.label}
                  </span>
                )}
              </li>
            ))}
          </ol>
        </nav>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-[18px] font-semibold tracking-tight text-[var(--color-text-primary)]">{title}</h1>
          {description && <p className="mt-1 max-w-[64ch] text-[13px] leading-relaxed text-[var(--color-text-secondary)]">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}

export function ContentContainer({
  children,
  className,
  narrow
}: {
  children: React.ReactNode;
  className?: string;
  narrow?: boolean;
}) {
  return <div className={cn("mx-auto w-full max-w-[1920px] p-4 md:p-6", narrow && "max-w-[960px]", className)}>{children}</div>;
}

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)]", className)}>{children}</div>
  );
}

export function CardHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-[var(--color-border-subtle)] px-4 py-3">
      <div>
        <div className="text-[13px] font-medium text-[var(--color-text-primary)]">{title}</div>
        {subtitle && <div className="mono text-[11px] text-[var(--color-text-tertiary)]">{subtitle}</div>}
      </div>
      {actions}
    </div>
  );
}
