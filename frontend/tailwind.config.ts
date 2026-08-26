import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "var(--color-bg-base)",
          subtle: "var(--color-bg-subtle)",
          surface1: "var(--color-bg-surface-1)",
          surface2: "var(--color-bg-surface-2)",
          surface3: "var(--color-bg-surface-3)"
        },
        border: {
          subtle: "var(--color-border-subtle)",
          strong: "var(--color-border-strong)"
        },
        text: {
          primary: "var(--color-text-primary)",
          secondary: "var(--color-text-secondary)",
          tertiary: "var(--color-text-tertiary)",
          disabled: "var(--color-text-disabled)"
        },
        bull: "var(--color-bull)",
        bear: "var(--color-bear)",
        danger: "var(--color-danger)",
        range: "var(--color-range)",
        osc: "var(--color-osc)",
        lavender: "var(--color-osc)",
        slate: "var(--color-slate)",
        purple: "var(--color-purple-accent)"
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
        display: ["var(--font-display)"]
      },
      borderRadius: {
        xs: "var(--radius-xs)",
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        pill: "var(--radius-pill)"
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)"
      },
      screens: {
        workstation: "1280px"
      }
    }
  },
  plugins: []
};
export default config;
