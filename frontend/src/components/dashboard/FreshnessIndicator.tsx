import { Badge } from "@/components/ui/Badge";
import type { FreshnessInfo } from "@/lib/api/types";

function formatAge(ageMs: number | null | undefined): string | null {
  if (ageMs === null || ageMs === undefined) return null;
  const s = Math.floor(ageMs / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m ago`;
}

export function FreshnessIndicator({ freshness, isAnalysisSafe, qualityIssues }: { freshness: FreshnessInfo; isAnalysisSafe?: boolean; qualityIssues?: string[] }) {
  const age = formatAge(freshness.age_ms);
  const stale = freshness.is_stale;
  const forming = freshness.has_forming_candle;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {stale ? (
        <Badge variant="danger" icon="◐">
          Stale{age ? ` · ${age}` : ""}
        </Badge>
      ) : (
        <Badge variant="success" icon="●">
          {age ? `Live · ${age}` : "Live"}
        </Badge>
      )}
      {forming && <Badge variant="info">Forming</Badge>}
      {!forming && freshness.last_closed_timestamp_ms && (
        <span className="mono text-[11px] text-[var(--color-text-tertiary)]">
          last closed {new Date(freshness.last_closed_timestamp_ms).toLocaleTimeString()}
        </span>
      )}
      {isAnalysisSafe === false && <Badge variant="warning">Not analysis-safe</Badge>}
      {qualityIssues && qualityIssues.length > 0 && (
        <span className="mono text-[11px] text-[var(--color-text-tertiary)]" title={qualityIssues.join(", ")}>
          quality: {qualityIssues.join(", ")}
        </span>
      )}
    </div>
  );
}
