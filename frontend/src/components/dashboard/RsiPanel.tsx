import type { PairAnalysis } from "@/lib/api/types";

export function RsiPanel({ analysis }: { analysis: PairAnalysis | null }) {
  if (!analysis) {
    return <div className="h-[120px] animate-pulse rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]" />;
  }
  const osc = analysis.oscillator;
  const value = osc.value;
  const hasValue = value !== null && value !== undefined && Number.isFinite(value as number);

  // Simple horizontal bar 0–100 with marker + bands
  return (
    <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">RSI / Oscillator — backend</span>
        <span className="mono text-[11px] text-[var(--color-text-tertiary)]">
          {hasValue ? `${(value as number).toFixed(1)}` : "—"} · subordinate to range
        </span>
      </div>
      <div className="relative mt-3 h-8 rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]">
        {/* bands */}
        <div className="absolute inset-y-0 left-0 w-[30%] bg-[var(--color-osc-subtle)] opacity-40" title="Oversold" />
        <div className="absolute inset-y-0 right-0 w-[30%] bg-[var(--color-osc-subtle)] opacity-40" title="Overbought" />
        <div className="absolute inset-y-0 left-0 w-px bg-[var(--color-osc)] opacity-30" style={{ left: "30%" }} />
        <div className="absolute inset-y-0 left-0 w-px bg-[var(--color-osc)] opacity-30" style={{ left: "70%" }} />
        {hasValue && (
          <div
            className="absolute top-1/2 h-3 w-1 -translate-y-1/2 rounded-full bg-[var(--color-osc-strong)] shadow-sm"
            style={{ left: `calc(${(value as number)}% - 2px)` }}
            aria-hidden
          />
        )}
        <div className="absolute -bottom-4 left-0 mono text-[10px] text-[var(--color-text-tertiary)]">0</div>
        <div className="absolute -bottom-4 left-[30%] mono -translate-x-1/2 text-[10px] text-[var(--color-osc)]">OS {osc.oversold ?? 30}</div>
        <div className="absolute -bottom-4 left-1/2 mono -translate-x-1/2 text-[10px] text-[var(--color-text-tertiary)]">50</div>
        <div className="absolute -bottom-4 left-[70%] mono -translate-x-1/2 text-[10px] text-[var(--color-osc)]">OB {osc.overbought ?? 70}</div>
        <div className="absolute -bottom-4 right-0 mono text-[10px] text-[var(--color-text-tertiary)]">100</div>
      </div>
      <div className="mt-5 text-[11px] text-[var(--color-text-tertiary)]">
        {hasValue ? (
          <>
            Backend-provided RSI · {osc.type ?? "rsi"} · confirmation{" "}
            <span className={osc.is_confirmation ? "text-[var(--color-osc-strong)]" : "text-[var(--color-text-tertiary)]"}>{osc.is_confirmation ? "true" : String(osc.is_confirmation)}</span> · Do not compute RSI in React.
          </>
        ) : (
          <>No oscillator value for this configuration — backend reports null. Not an error.</>
        )}
      </div>
    </div>
  );
}
