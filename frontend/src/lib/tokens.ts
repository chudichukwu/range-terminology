/**
 * Design tokens — typed mirror of CSS variables for JS usage.
 * Single source for colors/spacing/etc when JS needs them (e.g., charts).
 * Values must stay in sync with globals.css.
 */

export const tokens = {
  color: {
    bgBase: "var(--color-bg-base)",
    bgSubtle: "var(--color-bg-subtle)",
    bgSurface1: "var(--color-bg-surface-1)",
    bgSurface2: "var(--color-bg-surface-2)",
    bgSurface3: "var(--color-bg-surface-3)",
    borderSubtle: "var(--color-border-subtle)",
    borderStrong: "var(--color-border-strong)",
    textPrimary: "var(--color-text-primary)",
    textSecondary: "var(--color-text-secondary)",
    textTertiary: "var(--color-text-tertiary)",
    bull: "var(--color-bull)",
    bear: "var(--color-bear)",
    danger: "var(--color-danger)",
    range: "var(--color-range)",
    osc: "var(--color-osc)",
    purple: "var(--color-purple-accent)",
    success: "var(--color-success)",
    warning: "var(--color-warning)",
    info: "var(--color-info)",
    neutral: "var(--color-neutral)"
  },
  font: {
    sans: "var(--font-sans)",
    mono: "var(--font-mono)"
  },
  radius: {
    xs: "var(--radius-xs)",
    sm: "var(--radius-sm)",
    md: "var(--radius-md)",
    lg: "var(--radius-lg)",
    pill: "var(--radius-pill)"
  },
  spacing: {
    1: "var(--space-1)",
    2: "var(--space-2)",
    3: "var(--space-3)",
    4: "var(--space-4)",
    6: "var(--space-6)",
    8: "var(--space-8)"
  },
  breakpoints: {
    sm: 640,
    md: 768,
    lg: 1024,
    xl: 1280,
    xxl: 1536
  }
} as const;

export type Tokens = typeof tokens;
