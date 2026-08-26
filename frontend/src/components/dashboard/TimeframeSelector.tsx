"use client";

import { cn } from "@/lib/utils";
import type { Timeframe } from "@/lib/api/types";

const CANONICAL: Timeframe[] = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];

export function TimeframeSelector({
  value,
  onChange,
  available
}: {
  value: Timeframe;
  onChange: (tf: Timeframe) => void;
  available?: string[];
}) {
  return (
    <div role="group" aria-label="Timeframe" className="inline-flex rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-0.5">
      {CANONICAL.map((tf) => {
        const active = tf === value;
        const disabled = available ? !available.includes(tf) : false;
        return (
          <button
            key={tf}
            role="radio"
            aria-checked={active}
            aria-label={`Timeframe ${tf}`}
            disabled={disabled}
            onClick={() => onChange(tf)}
            title={disabled ? "Not available from provider" : undefined}
            className={cn(
              "mono min-w-[36px] rounded-xs px-2 py-1 text-[12px] font-medium leading-none",
              active
                ? "bg-[var(--color-bg-surface-2)] text-[var(--color-text-primary)] shadow-sm ring-1 ring-[var(--color-border-subtle)]"
                : "text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]",
              disabled && "opacity-40 cursor-not-allowed"
            )}
          >
            {tf}
          </button>
        );
      })}
    </div>
  );
}
