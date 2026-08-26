"use client";

import { Badge } from "@/components/ui/Badge";

export type ScanFilter = {
  rangeStatus: string; // all | valid | degenerate | insufficient_data
  regime: string; // all | ranging | trending_up | trending_down | transitional | insufficient_data
  signal: string; // all | has_signal | long | short | none
  confirmation: string; // all | confirmed | not_confirmed | awaiting | ignored
  edge: string; // all | lower | middle | upper | outside
  analysisSafe: string; // all | safe | unsafe
  freshness: string; // all | live | stale | unavailable
};

export const DEFAULT_FILTER: ScanFilter = {
  rangeStatus: "all",
  regime: "all",
  signal: "all",
  confirmation: "all",
  edge: "all",
  analysisSafe: "all",
  freshness: "all"
};

export function ScanFilters({
  value,
  onChange,
  resultCount,
  totalCount
}: {
  value: ScanFilter;
  onChange: (v: ScanFilter) => void;
  resultCount: number;
  totalCount: number;
}) {
  const set = <K extends keyof ScanFilter>(k: K, v: ScanFilter[K]) => onChange({ ...value, [k]: v });

  const Select = ({ label, val, onVal, options }: { label: string; val: string; onVal: (v: string) => void; options: { value: string; label: string }[] }) => (
    <label className="flex items-center gap-1.5 text-[11px]">
      <span className="font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">{label}</span>
      <select value={val} onChange={(e) => onVal(e.target.value)} className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-1.5 py-1 text-[11px] text-[var(--color-text-secondary)] focus:border-[var(--color-purple-accent)] focus:outline-none">
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <div className="space-y-2 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="purple" icon="◎">
          Scan filters
        </Badge>
        <span className="mono text-[11px] text-[var(--color-text-tertiary)]">
          {resultCount} of {totalCount} markets match
        </span>
        <button onClick={() => onChange(DEFAULT_FILTER)} className="ml-auto text-[11px] font-medium text-[var(--color-purple-accent)] hover:underline">
          Reset
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        <Select
          label="Range"
          val={value.rangeStatus}
          onVal={(v) => set("rangeStatus", v)}
          options={[
            { value: "all", label: "All" },
            { value: "valid", label: "Valid" },
            { value: "degenerate", label: "Degenerate" },
            { value: "insufficient_data", label: "Insufficient" }
          ]}
        />
        <Select
          label="Regime"
          val={value.regime}
          onVal={(v) => set("regime", v)}
          options={[
            { value: "all", label: "All" },
            { value: "ranging", label: "Ranging" },
            { value: "trending_up", label: "Trending Up" },
            { value: "trending_down", label: "Trending Down" },
            { value: "transitional", label: "Transitional" },
            { value: "insufficient_data", label: "Insufficient" }
          ]}
        />
        <Select
          label="Signal"
          val={value.signal}
          onVal={(v) => set("signal", v)}
          options={[
            { value: "all", label: "All" },
            { value: "has_signal", label: "Has signal" },
            { value: "long", label: "Long" },
            { value: "short", label: "Short" },
            { value: "none", label: "None" }
          ]}
        />
        <Select
          label="Confirmation"
          val={value.confirmation}
          onVal={(v) => set("confirmation", v)}
          options={[
            { value: "all", label: "All" },
            { value: "confirmed", label: "Confirmed" },
            { value: "not_confirmed", label: "Not confirmed" },
            { value: "awaiting", label: "Awaiting" },
            { value: "ignored", label: "Ignored" }
          ]}
        />
        <Select
          label="Edge"
          val={value.edge}
          onVal={(v) => set("edge", v)}
          options={[
            { value: "all", label: "All" },
            { value: "lower", label: "Lower" },
            { value: "middle", label: "Middle (no-trade)" },
            { value: "upper", label: "Upper" },
            { value: "outside", label: "Outside" }
          ]}
        />
        <Select
          label="Safe"
          val={value.analysisSafe}
          onVal={(v) => set("analysisSafe", v)}
          options={[
            { value: "all", label: "All" },
            { value: "safe", label: "Safe" },
            { value: "unsafe", label: "Unsafe" }
          ]}
        />
        <Select
          label="Fresh"
          val={value.freshness}
          onVal={(v) => set("freshness", v)}
          options={[
            { value: "all", label: "All" },
            { value: "live", label: "Live" },
            { value: "stale", label: "Stale" },
            { value: "error", label: "Error/unavailable" }
          ]}
        />
      </div>
      <div className="mono text-[11px] text-[var(--color-text-tertiary)]">Filters are presentation over backend-provided analysis. “Ranging” filters on MarketRegime ≠ RangeStatus.</div>
    </div>
  );
}

export function matchesFilter(entry: { analysis?: import("@/lib/api/types").PairAnalysis | null; stateKind: string }, f: ScanFilter): boolean {
  const a = entry.analysis;
  if (!a && f.freshness !== "all" && f.freshness !== "error") {
    // no analysis yet — only show when filter allows errors
    if (entry.stateKind === "loading") return f.freshness === "all";
    if (entry.stateKind === "error") return f.freshness === "error" || f.freshness === "all";
    return false;
  }
  if (!a) return f.freshness === "all" || f.freshness === "error";

  if (f.rangeStatus !== "all" && a.range.status !== f.rangeStatus) return false;
  if (f.regime !== "all" && a.regime.value !== f.regime) return false;

  if (f.signal !== "all") {
    if (f.signal === "has_signal" && a.signal.direction === "none") return false;
    if (f.signal === "long" && a.signal.direction !== "long") return false;
    if (f.signal === "short" && a.signal.direction !== "short") return false;
    if (f.signal === "none" && a.signal.direction !== "none") return false;
  }
  if (f.confirmation !== "all") {
    const c = a.signal.confirmation;
    const p = a.signal.confirmation_policy;
    if (f.confirmation === "confirmed" && c !== true) return false;
    if (f.confirmation === "not_confirmed" && c !== false) return false;
    if (f.confirmation === "awaiting" && !(c === null && p === "required")) return false;
    if (f.confirmation === "ignored" && p !== "ignored") return false;
  }
  if (f.edge !== "all") {
    const pos = a.signal.position_in_range;
    if (pos === null || pos === undefined) return false;
    if (f.edge === "lower" && !(pos >= 0 && pos < 0.25)) return false;
    if (f.edge === "middle" && !(pos >= 0.25 && pos <= 0.75)) return false;
    if (f.edge === "upper" && !(pos > 0.75 && pos <= 1)) return false;
    if (f.edge === "outside" && !(pos < 0 || pos > 1)) return false;
  }
  if (f.analysisSafe !== "all") {
    if (f.analysisSafe === "safe" && !a.is_analysis_safe) return false;
    if (f.analysisSafe === "unsafe" && a.is_analysis_safe) return false;
  }
  if (f.freshness !== "all") {
    const kind = entry.stateKind;
    if (f.freshness === "live" && (kind === "error" || (a && a.freshness.is_stale))) return false;
    if (f.freshness === "stale" && !(kind === "stale" || (a && a.freshness.is_stale))) return false;
    if (f.freshness === "error" && kind !== "error") return false;
  }
  return true;
}
