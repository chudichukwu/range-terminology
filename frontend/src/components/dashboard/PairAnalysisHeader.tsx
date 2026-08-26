import { RangeStatusBadge, MarketRegimeBadge, ConfidenceHeuristic } from "./Badges";
import { FreshnessIndicator } from "./FreshnessIndicator";
import { TimeframeSelector } from "./TimeframeSelector";
import { PairSelector } from "./PairSelector";
import type { PairAnalysis, Timeframe } from "@/lib/api/types";
import { Badge } from "@/components/ui/Badge";

export function PairAnalysisHeader({
  analysis,
  symbol,
  timeframe,
  onSymbolChange,
  onTimeframeChange,
  availableTimeframes
}: {
  analysis?: PairAnalysis | null;
  symbol: string;
  timeframe: Timeframe;
  onSymbolChange: (s: string) => void;
  onTimeframeChange: (tf: Timeframe) => void;
  availableTimeframes?: string[];
}) {
  const range = analysis?.range;
  const regime = analysis?.regime;
  const price = analysis?.ticker_last ?? analysis?.signal.price ?? null;
  const quality = analysis?.quality_issues ?? [];

  return (
    <div className="space-y-3 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-base)] px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="mono text-[18px] font-semibold tracking-tight text-[var(--color-text-primary)]">{symbol}</h1>
            <span className="mono text-[12px] text-[var(--color-text-tertiary)]">·</span>
            <span className="mono text-[13px] font-medium text-[var(--color-text-secondary)]">{timeframe}</span>
            {price !== null && price !== undefined && (
              <span className="mono ml-2 text-[15px] font-semibold text-[var(--color-text-primary)]">
                {price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            )}
          </div>
          {analysis ? (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <RangeStatusBadge status={analysis.range.status} isTradable={analysis.range.is_tradable} />
              <MarketRegimeBadge regime={analysis.regime.value} />
              <ConfidenceHeuristic value={analysis.range.confidence} />
              {analysis.range.mode && (
                <Badge variant="neutral" icon="⬔">
                  {analysis.range.mode}
                </Badge>
              )}
            </div>
          ) : (
            <div className="mt-2 h-5 w-64 animate-pulse rounded-sm bg-[var(--color-bg-surface-2)]" aria-hidden />
          )}
          {analysis && (
            <div className="mt-2">
              <FreshnessIndicator freshness={analysis.freshness} isAnalysisSafe={analysis.is_analysis_safe} qualityIssues={quality} />
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PairSelector value={symbol} onChange={onSymbolChange} />
          <TimeframeSelector value={timeframe} onChange={onTimeframeChange} available={availableTimeframes} />
        </div>
      </div>

      {analysis && (
        <div className="grid gap-2 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3 md:grid-cols-4">
          <div>
            <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Range</div>
            <div className="mono mt-0.5 text-[12px] text-[var(--color-text-primary)]">
              {range && range.high !== null && range.low !== null ? (
                <>
                  <span className="text-[var(--color-range)]">H</span> {(range.high as number).toLocaleString()} · <span className="text-[var(--color-range)]">L</span> {(range.low as number).toLocaleString()}
                  {range.width !== null && <span className="ml-1 text-[11px] text-[var(--color-text-tertiary)]">w {(range.width as number).toFixed(2)}</span>}
                </>
              ) : (
                <span className="text-[var(--color-text-tertiary)]">—</span>
              )}
            </div>
            <div className="text-[11px] text-[var(--color-text-tertiary)]">
              {range?.is_tradable ? "Bounds actionable" : "Bounds not tradable"} · confidence heuristic
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Regime</div>
            <div className="mono mt-0.5 text-[12px] text-[var(--color-text-primary)]">
              {regime?.value} {regime?.efficiency_ratio !== null && regime?.efficiency_ratio !== undefined ? `· ER ${regime.efficiency_ratio.toFixed(2)}` : ""}
            </div>
            <div className="text-[11px] text-[var(--color-text-tertiary)]">lookback {regime?.lookback} · thr {regime?.threshold}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Position in range</div>
            <div className="mono mt-0.5 text-[12px] text-[var(--color-text-primary)]">
              {analysis.signal.position_in_range !== null && analysis.signal.position_in_range !== undefined
                ? `${(analysis.signal.position_in_range * 100).toFixed(1)}%`
                : "—"}
              {analysis.signal.position_in_range !== null && (
                <span className="ml-2 text-[11px] text-[var(--color-text-tertiary)]">
                  {analysis.signal.position_in_range < 0 || analysis.signal.position_in_range > 1 ? "outside" : analysis.signal.position_in_range < 0.25 ? "near lower edge" : analysis.signal.position_in_range > 0.75 ? "near upper edge" : "middle"}
                </span>
              )}
            </div>
            <div className="text-[11px] text-[var(--color-text-tertiary)]">lower → LONG · middle/outside → NO-TRADE · upper → SHORT</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Current price context</div>
            <div className="mono mt-0.5 text-[12px] text-[var(--color-text-primary)]">
              {analysis.signal.price !== null ? analysis.signal.price.toLocaleString() : "—"}
            </div>
            <div className="text-[11px] text-[var(--color-text-tertiary)]">from backend last close · not computed in React</div>
          </div>
        </div>
      )}
    </div>
  );
}
