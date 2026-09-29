import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

export function Button({
  variant = "secondary",
  size = "md",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  const base = "inline-flex items-center justify-center rounded-sm font-medium transition-colors focus-visible:outline-none disabled:opacity-50 disabled:pointer-events-none";
  const sizes = {
    sm: "h-7 px-2.5 text-[12px]",
    md: "h-8 px-3.5 text-[12px]"
  } as const;
  const variants: Record<Variant, string> = {
    primary: "bg-[var(--color-purple-accent)] text-[#172314] hover:bg-[#d0f6a9] shadow-sm",
    secondary:
      "border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-2)] hover:text-[var(--color-text-primary)]",
    ghost: "text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-2)] hover:text-[var(--color-text-primary)]",
    danger: "bg-[var(--color-danger)] text-[var(--color-text-inverse)] hover:bg-[var(--color-danger-strong)]"
  };
  return <button className={cn(base, sizes[size], variants[variant], className)} {...props} />;
}
