"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useWatchlistScan } from "@/hooks/useWatchlistScan";
import type { WatchlistItem, Timeframe } from "@/lib/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { RangeStatusBadge, MarketRegimeBadge } from "@/components/dashboard/Badges";
import { FreshnessIndicator } from "@/components/dashboard/FreshnessIndicator";
import { PositionMeter, ConfidenceCells, SignalBadge, ConfirmationBadge } from "./ScanPrimitives";
import { ScanFilters, DEFAULT_FILTER, matchesFilter, type ScanFilter } from "./ScanFilters";
import { TimeframeSelector } from "@/components/dashboard/TimeframeSelector";

type SortKey = "symbol" | "position" | "confidence" | "width" | "regime" | "signal" | "freshness";

export function WatchlistScanner({
  items,
  timeframe,
  setTimeframe,
  strategyId,
  availableTimeframes
}: {
  items: WatchlistItem[];
  timeframe: Timeframe;
  setTimeframe: (tf: Timeframe) => void;
  strategyId?: string;
  availableTimeframes?: string[];
}) {
  const { scan, isScanning, refresh } = useWatchlistScan(items, { timeframe, strategyId });
  const [filter, setFilter] = useState<ScanFilter>(DEFAULT_FILTER);
  const [sortKey, setSortKey] = useState<SortKey>("symbol");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [showDetails, setShowDetails] = useState(false);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const toggleSort = (k: SortKey) => {
    if (k === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(k);
      setSortDir("asc");
    }
  };

  const rows = useMemo(() => {
    const list = items.map((it) => {
      const st = scan[it.id] ?? { kind: "loading" as const };
      return { item: it, state: st, analysis: (st as any).analysis ?? null, stateKind: (st as any).kind ?? "loading" };
    });

    const filtered = list.filter((r) => matchesFilter(r as any, filter));

    const sorted = [...filtered].sort((a, b) => {
      const dir = sortDir === "asc" ? 1 : -1;
      const av = a.analysis, bv = b.analysis;
      switch (sortKey) {
        case "symbol":
          return dir * a.item.symbol.localeCompare(b.item.symbol);
        case "position":
          return dir * ((av?.signal.position_in_range ?? -999) - (bv?.signal.position_in_range ?? -999));
        case "confidence":
          return dir * ((av?.signal.confidence ?? av?.range.confidence ?? -1) - (bv?.signal.confidence ?? bv?.range.confidence ?? -1));
        case "width":
          return dir * ((av?.range.width ?? -1) - (bv?.range.width ?? -1));
        case "regime":
          return dir * String(av?.regime.value ?? "").localeCompare(String(bv?.regime.value ?? ""));
        case "signal":
          return dir * String(av?.signal.direction ?? "").localeCompare(String(bv?.signal.direction ?? ""));
        case "freshness":
          return dir * ((av?.freshness.age_ms ?? 999999) - (bv?.freshness.age_ms ?? 999999));
        default:
          return 0;
      }
    });
    return sorted;
  }, [items, scan, filter, sortKey, sortDir]);

  const SortBtn = ({ k, label }: { k: SortKey; label: string }) => (
    <button
      onClick={() => toggleSort(k)}
      aria-label={`Sort by ${label}${sortKey === k ? `, ${sortDir}` : ""}`}
      className={`inline-flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide ${sortKey === k ? "text-[var(--color-purple-accent)]" : "text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]"}`}
    >
      {label} {sortKey === k ? (sortDir === "asc" ? "▲" : "▼") : ""}
    </button>
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-2">
        <span className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Scan timeframe</span>
        <TimeframeSelector value={timeframe} onChange={setTimeframe} available={availableTimeframes} />
        <Button variant="secondary" size="sm" onClick={() => refresh()} disabled={isScanning}>
          {isScanning ? "Scanning…" : "Refresh"}
        </Button>
        <label className="ml-auto inline-flex items-center gap-1.5 text-[11px] text-[var(--color-text-tertiary)]">
          <input type="checkbox" checked={showDetails} onChange={(e) => setShowDetails(e.target.checked)} className="rounded-sm" />
          Show details
        </label>
        <span className="mono text-[11px] text-[var(--color-text-tertiary)]">{items.length} markets · {isScanning ? "scanning" : "idle"} · single analysis endpoint per pair</span>
      </div>

      <ScanFilters value={filter} onChange={setFilter} resultCount={rows.length} totalCount={items.length} />

      {/* Desktop table */}
      <div className="hidden overflow-hidden rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] md:block">
        <div className="overflow-x-auto">
          <table className="w-full text-left" role="table">
            <thead className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]">
              <tr className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                <th className="px-3 py-2 font-medium">
                  <SortBtn k="symbol" label="Symbol" />
                </th>
                <th className="px-3 py-2 font-medium">Range Status</th>
                <th className="px-3 py-2 font-medium">
                  <SortBtn k="regime" label="Regime" />
                </th>
                <th className="px-3 py-2 font-medium">
                  <SortBtn k="position" label="Position / Edge" />
                </th>
                <th className="px-3 py-2 font-medium">
                  <SortBtn k="signal" label="Signal" />
                </th>
                <th className="px-3 py-2 font-medium">Confirmation</th>
                <th className="px-3 py-2 font-medium">
                  <SortBtn k="confidence" label="Confidence" />
                </th>
                <th className="px-3 py-2 font-medium">
                  <SortBtn k="freshness" label="Freshness" />
                </th>
                <th className="px-3 py-2 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-[13px] text-[var(--color-text-tertiary)]">
                    {items.length === 0 ? "No markets in this watchlist yet." : "No markets match these filters."}
                  </td>
                </tr>
              ) : (
                rows.map(({ item, state, analysis, stateKind }) => {
                  const key = item.id;
                  const isLoading = stateKind === "loading";
                  const isError = stateKind === "error";
                  const unsafe = analysis ? !analysis.is_analysis_safe : false;
                  const stale = (analysis?.freshness.is_stale ?? false) || stateKind === "stale";

                  return (
                    <>
                      <tr
                        key={key}
                        className={`border-b border-[var(--color-border-subtle)] last:border-0 hover:bg-[var(--color-bg-surface-2)] ${unsafe || stale ? "bg-[rgba(245,158,11,0.04)]" : ""}`}
                      >
                        <td className="px-3 py-2">
                          <div className="mono text-[12px] font-medium text-[var(--color-text-primary)]">{item.symbol}</div>
                          <div className="mono text-[11px] text-[var(--color-text-tertiary)]">{item.venue_id} · {item.enabled ? "enabled" : "disabled"}</div>
                        </td>
                        <td className="px-3 py-2">
                          {isLoading ? (
                            <span className="h-5 w-16 animate-pulse rounded-pill bg-[var(--color-bg-surface-3)]" />
                          ) : isError ? (
                            <Badge variant="neutral">{(state as any).code}</Badge>
                          ) : analysis ? (
                            <RangeStatusBadge status={analysis.range.status} isTradable={analysis.range.is_tradable} />
                          ) : (
                            <Badge variant="neutral">—</Badge>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {isLoading ? (
                            <span className="h-5 w-16 animate-pulse rounded-pill bg-[var(--color-bg-surface-3)]" />
                          ) : isError ? (
                            <Badge variant="neutral">—</Badge>
                          ) : analysis ? (
                            <MarketRegimeBadge regime={analysis.regime.value as any} />
                          ) : (
                            <Badge variant="neutral">—</Badge>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {isLoading ? (
                            <span className="h-4 w-28 animate-pulse rounded-sm bg-[var(--color-bg-surface-3)]" />
                          ) : isError ? (
                            <span className="mono text-[11px] text-[var(--color-text-tertiary)]">unavailable</span>
                          ) : analysis ? (
                            <PositionMeter value={analysis.signal.position_in_range} />
                          ) : (
                            <span className="mono text-[11px] text-[var(--color-text-tertiary)]">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {isLoading ? (
                            <span className="h-5 w-14 animate-pulse rounded-pill bg-[var(--color-bg-surface-3)]" />
                          ) : isError ? (
                            <Badge variant="neutral">Error</Badge>
                          ) : analysis ? (
                            <SignalBadge direction={analysis.signal.direction} reason={analysis.signal.reason} />
                          ) : (
                            <Badge variant="neutral">—</Badge>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {isLoading ? (
                            <span className="h-5 w-16 animate-pulse rounded-pill bg-[var(--color-bg-surface-3)]" />
                          ) : isError || !analysis ? (
                            <span className="mono text-[11px] text-[var(--color-text-tertiary)]">—</span>
                          ) : (
                            <ConfirmationBadge confirmation={analysis.signal.confirmation} policy={analysis.signal.confirmation_policy} />
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {isLoading ? (
                            <span className="h-3 w-16 animate-pulse rounded-sm bg-[var(--color-bg-surface-3)]" />
                          ) : analysis ? (
                            <ConfidenceCells value={analysis.signal.confidence ?? analysis.range.confidence} />
                          ) : (
                            <span className="mono text-[11px] text-[var(--color-text-tertiary)]">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {isLoading ? (
                            <span className="h-5 w-16 animate-pulse rounded-pill bg-[var(--color-bg-surface-3)]" />
                          ) : isError ? (
                            <div className="text-[11px] text-[var(--color-text-secondary)]">
                              <div>{(state as any).message?.slice(0, 48)}</div>
                              <div className="mono text-[10px] text-[var(--color-text-tertiary)]">id {(state as any).requestId?.slice(0, 8)}</div>
                            </div>
                          ) : analysis ? (
                            <FreshnessIndicator freshness={analysis.freshness} isAnalysisSafe={analysis.is_analysis_safe} qualityIssues={analysis.quality_issues} />
                          ) : (
                            <Badge variant="neutral">Unavailable</Badge>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex gap-1">
                            <Link href={`/?symbol=${encodeURIComponent(item.symbol)}&timeframe=${timeframe}`} className="rounded-sm bg-[var(--color-purple-accent)] px-2 py-1 text-[11px] font-medium text-white hover:bg-[#6d4af0]">
                              Analyze
                            </Link>
                            <button onClick={() => setExpandedRow(expandedRow === key ? null : key)} className="rounded-sm border border-[var(--color-border-subtle)] px-2 py-1 text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-2)]">
                              {expandedRow === key ? "Hide" : "Detail"}
                            </button>
                          </div>
                        </td>
                      </tr>
                      {expandedRow === key && analysis && (
                        <tr key={`${key}-detail`} className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]/50">
                          <td colSpan={9} className="px-3 py-2">
                            <div className="grid gap-3 md:grid-cols-4">
                              <div className="mono text-[11px] text-[var(--color-text-secondary)]">
                                <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Price · Range</div>
                                <div className="mt-1">Price {analysis.signal.price !== null ? analysis.signal.price.toLocaleString() : "—"}</div>
                                <div>High {analysis.range.high !== null ? (analysis.range.high as number).toLocaleString() : "—"} · Low {analysis.range.low !== null ? (analysis.range.low as number).toLocaleString() : "—"}</div>
                                <div>Width {analysis.range.width !== null ? (analysis.range.width as number).toFixed(2) : "—"} · Mode {analysis.range.mode}</div>
                              </div>
                              <div className="mono text-[11px] text-[var(--color-text-secondary)]">
                                <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Signal metadata</div>
                                <pre className="mt-1 max-h-20 overflow-auto text-[11px] text-[var(--color-text-tertiary)]">{JSON.stringify(analysis.signal.metadata, null, 2)}</pre>
                              </div>
                              <div className="mono text-[11px] text-[var(--color-text-secondary)]">
                                <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Oscillator</div>
                                <div className="mt-1">{analysis.oscillator.type ?? "—"} {analysis.oscillator.value !== null ? analysis.oscillator.value.toFixed(1) : "—"} · conf {String(analysis.signal.confirmation)}</div>
                                <div>OB {analysis.oscillator.overbought ?? "—"} · OS {analysis.oscillator.oversold ?? "—"}</div>
                              </div>
                              <div className="mono text-[11px] text-[var(--color-text-secondary)]">
                                <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Quality · Risk</div>
                                <div className="mt-1">{analysis.quality_issues.join(", ") || "clean"} · {analysis.is_analysis_safe ? "safe" : "unsafe"}</div>
                                <div>{analysis.risk ? `${analysis.risk.approved ? "Approved" : "Rejected · " + analysis.risk.rejection_reason}` : "No risk preview"}</div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile cards */}
      <div className="grid gap-2 md:hidden">
        {rows.length === 0 ? (
          <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-6 text-center text-[13px] text-[var(--color-text-tertiary)]">
            {items.length === 0 ? "No markets in this watchlist yet." : "No markets match these filters."}
          </div>
        ) : (
          rows.map(({ item, state, analysis, stateKind }) => {
            const isLoading = stateKind === "loading";
            const isError = stateKind === "error";
            return (
              <div key={item.id} className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="mono text-[13px] font-semibold text-[var(--color-text-primary)]">{item.symbol}</div>
                    <div className="mono text-[11px] text-[var(--color-text-tertiary)]">{item.venue_id}</div>
                  </div>
                  <Link href={`/?symbol=${encodeURIComponent(item.symbol)}&timeframe=${timeframe}`} className="rounded-sm bg-[var(--color-purple-accent)] px-2.5 py-1 text-[11px] font-medium text-white">
                    Analyze
                  </Link>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {isLoading ? (
                    <span className="h-5 w-16 animate-pulse rounded-pill bg-[var(--color-bg-surface-3)]" />
                  ) : isError ? (
                    <Badge variant="neutral">{(state as any).code}</Badge>
                  ) : analysis ? (
                    <>
                      <RangeStatusBadge status={analysis.range.status} />
                      <MarketRegimeBadge regime={analysis.regime.value as any} />
                      <SignalBadge direction={analysis.signal.direction} reason={analysis.signal.reason} />
                    </>
                  ) : null}
                </div>
                <div className="mt-2">
                  {isLoading ? <span className="h-4 w-28 animate-pulse rounded-sm bg-[var(--color-bg-surface-3)]" /> : analysis ? <PositionMeter value={analysis.signal.position_in_range} /> : <span className="mono text-[11px] text-[var(--color-text-tertiary)]">unavailable</span>}
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {isLoading ? null : analysis ? (
                    <>
                      <ConfirmationBadge confirmation={analysis.signal.confirmation} policy={analysis.signal.confirmation_policy} />
                      <ConfidenceCells value={analysis.signal.confidence ?? analysis.range.confidence} />
                    </>
                  ) : null}
                </div>
                <div className="mt-2">
                  {isLoading ? null : isError ? (
                    <div className="text-[11px] text-[var(--color-text-secondary)]">{(state as any).message?.slice(0, 80)}</div>
                  ) : analysis ? (
                    <FreshnessIndicator freshness={analysis.freshness} isAnalysisSafe={analysis.is_analysis_safe} qualityIssues={analysis.quality_issues} />
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
