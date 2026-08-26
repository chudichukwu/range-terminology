import { cn } from "@/lib/utils";

type Variant = "neutral" | "success" | "warning" | "danger" | "info" | "bull" | "bear" | "purple" | "range" | "osc";

const variantStyles: Record<Variant, string> = {
  neutral: "bg-[var(--color-bg-surface-2)] text-[var(--color-text-secondary)] border-[var(--color-border-subtle)]",
  success: "bg-[var(--color-success-subtle)] text-[var(--color-success)] border-[rgba(34,197,94,0.18)]",
  warning: "bg-[rgba(250,204,21,0.08)] text-[var(--color-warning)] border-[rgba(250,204,21,0.18)]",
  danger: "bg-[var(--color-danger-bg)] text-[var(--color-danger)] border-[rgba(245,158,11,0.18)]",
  info: "bg-[rgba(56,189,248,0.08)] text-[var(--color-info)] border-[rgba(56,189,248,0.18)]",
  bull: "bg-[var(--color-bull-subtle)] text-[var(--color-bull)] border-[rgba(29,185,84,0.18)]",
  bear: "bg-[var(--color-bear-subtle)] text-[var(--color-bear)] border-[rgba(239,68,68,0.18)]",
  purple: "bg-[var(--color-purple-subtle)] text-[var(--color-purple-accent)] border-[rgba(124,92,255,0.18)]",
  range: "bg-[var(--color-range-subtle)] text-[var(--color-range)] border-[rgba(142,161,190,0.18)]",
  osc: "bg-[var(--color-osc-subtle)] text-[var(--color-osc)] border-[rgba(154,139,181,0.18)]"
};

export function Badge({
  variant = "neutral",
  children,
  icon,
  className
}: {
  variant?: Variant;
  children: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-pill border px-2 py-0.5 text-[11px] font-medium leading-none tracking-wide",
        variantStyles[variant],
        className
      )}
    >
      {icon && (
        <span aria-hidden className="text-[10px] leading-none">
          {icon}
        </span>
      )}
      {children}
    </span>
  );
}

export function StatusDot({ variant = "neutral" }: { variant?: Variant }) {
  const dot: Record<Variant, string> = {
    neutral: "bg-[var(--color-neutral)]",
    success: "bg-[var(--color-success)]",
    warning: "bg-[var(--color-warning)]",
    danger: "bg-[var(--color-danger)]",
    info: "bg-[var(--color-info)]",
    bull: "bg-[var(--color-bull)]",
    bear: "bg-[var(--color-bear)]",
    purple: "bg-[var(--color-purple-accent)]",
    range: "bg-[var(--color-range)]",
    osc: "bg-[var(--color-osc)]"
  };
  return <span aria-hidden className={cn("h-1.5 w-1.5 shrink-0 rounded-full", dot[variant])} />;
}
