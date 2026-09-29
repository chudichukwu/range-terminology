"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { PageHeader, ContentContainer, Card } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState, EmptyState, PermissionDeniedState, UnavailableState } from "@/components/state/StatePrimitives";
import { api, ApiError } from "@/lib/api/client";
import type { Dataset } from "@/lib/api/types";

function fmtMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  return new Date(ms).toLocaleDateString();
}
function fmtMsFull(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  return new Date(ms).toLocaleString();
}
function fmtNum(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString();
}
function formatGapDuration(start: number, end: number): string {
  const ms = end - start;
  if (!Number.isFinite(ms) || ms <= 0) return "—";
  const mins = Math.round(ms / 60000);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  if (hrs < 24) return rem ? `${hrs}h ${rem}m` : `${hrs}h`;
  const days = Math.floor(hrs / 24);
  const rh = hrs % 24;
  return rh ? `${days}d ${rh}h` : `${days}d`;
}

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[] | null>(null);
  const [error, setError] = useState<{ message: string; requestId: string; code: string } | null>(null);

  // presentation filters (client-side over backend-provided fields)
  const [filterSymbol, setFilterSymbol] = useState("all");
  const [filterTimeframe, setFilterTimeframe] = useState("all");
  const [filterSource, setFilterSource] = useState("all");
  const [filterQuality, setFilterQuality] = useState("all");
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    api
      .listDatasets()
      .then(({ data }) => setDatasets(data))
      .catch((e) => {
        if (e instanceof ApiError) setError({ message: e.message, requestId: e.requestId, code: e.code });
        else setError({ message: String(e), requestId: "", code: "unknown" });
      });
  }, []);

  const symbols = useMemo(() => Array.from(new Set((datasets ?? []).map((d) => d.symbol))).sort(), [datasets]);
  const timeframes = useMemo(() => Array.from(new Set((datasets ?? []).map((d) => d.timeframe))).sort(), [datasets]);
  const sources = useMemo(() => Array.from(new Set((datasets ?? []).map((d) => d.source))).sort(), [datasets]);

  const filtered = useMemo(() => {
    if (!datasets) return null;
    return datasets.filter((d) => {
      if (filterSymbol !== "all" && d.symbol !== filterSymbol) return false;
      if (filterTimeframe !== "all" && d.timeframe !== filterTimeframe) return false;
      if (filterSource !== "all" && d.source !== filterSource) return false;
      if (filterQuality !== "all" && d.quality_status !== filterQuality) return false;
      return true;
    });
  }, [datasets, filterSymbol, filterTimeframe, filterSource, filterQuality]);

  // coverage summary — presentation aggregation over authoritative facts, not fabrication
  const summary = useMemo(() => {
    if (!datasets || datasets.length === 0) return null;
    const totalCandles = datasets.reduce((a, d) => a + d.candle_count, 0);
    const earliest = datasets.reduce<number | null>((min, d) => (d.first_timestamp_ms !== null ? (min === null ? d.first_timestamp_ms! : Math.min(min!, d.first_timestamp_ms!)) : min), null as number | null);
    const latest = datasets.reduce<number | null>((max, d) => (d.last_timestamp_ms !== null ? (max === null ? d.last_timestamp_ms! : Math.max(max!, d.last_timestamp_ms!)) : max), null as number | null);
    return {
      datasets: datasets.length,
      symbols: new Set(datasets.map((d) => d.symbol)).size,
      timeframes: new Set(datasets.map((d) => d.timeframe)).size,
      totalCandles,
      earliest,
      latest
    };
  }, [datasets]);

  if (error && (error.code === "unauthenticated" || error.code === "forbidden")) {
    return (
      <>
        <PageHeader title="Datasets" breadcrumbs={[{ label: "Datasets" }]} description="Historical coverage — authoritative dataset inventory." />
        <ContentContainer>
          <PermissionDeniedState />
          <div className="mt-3 mono text-[11px] text-[var(--color-text-tertiary)]">Request ID: {error.requestId || "—"} · Code: {error.code}</div>
        </ContentContainer>
      </>
    );
  }

  if (error) {
    // Distinguish Unavailable (404 on /datasets means contract not exposed) vs Error
    if (error.code === "not_found") {
      return (
        <>
          <PageHeader title="Datasets" breadcrumbs={[{ label: "Datasets" }]} description="Historical coverage — authoritative dataset inventory." />
          <ContentContainer>
            <UnavailableState title="Dataset coverage not available" description="The backend does not currently expose a dataset coverage endpoint. This is the historical-coverage boundary documented in DESIGN.md. Missing information is shown as —, not fabricated." />
            <div className="mt-3 mono text-[11px] text-[var(--color-text-tertiary)]">Request ID: {error.requestId || "—"}</div>
          </ContentContainer>
        </>
      );
    }
    return (
      <>
        <PageHeader title="Datasets" breadcrumbs={[{ label: "Datasets" }]} description="Historical coverage — authoritative dataset inventory." />
        <ContentContainer>
          <ErrorState message={error.message} requestId={error.requestId} />
        </ContentContainer>
      </>
    );
  }

  if (!datasets) {
    return (
      <>
        <PageHeader title="Datasets" breadcrumbs={[{ label: "Datasets" }]} description="Historical coverage — authoritative dataset inventory." />
        <ContentContainer>
          <LoadingState label="Loading datasets" />
        </ContentContainer>
      </>
    );
  }

  // Empty — backend returned valid empty collection (distinct from unavailable)
  if (datasets.length === 0) {
    return (
      <>
        <PageHeader
          title="Datasets"
          description="Historical coverage — authoritative dataset inventory. No datasets exist yet."
          breadcrumbs={[{ label: "Datasets" }]}
          actions={<Badge variant="neutral">0 datasets</Badge>}
        />
        <ContentContainer>
          <EmptyState
            title="No datasets exist"
            description="The backend returned a valid empty dataset collection. Ingest market data to populate historical coverage. This is distinct from “coverage not available” — here the endpoint exists and confirms there is nothing stored yet."
          />
          <div className="mt-3 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
            <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">What would appear here</h3>
            <ul className="mono mt-1 list-disc space-y-0.5 pl-4 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
              <li>Dataset inventory — symbol, timeframe, provider/source, candles, from→to, quality_status</li>
              <li>Coverage summary — datasets, symbols, timeframes, total candles, earliest/latest</li>
              <li>Dataset handoffs — Dashboard analysis and Backtests (factual, no optimization)</li>
            </ul>
          </div>
        </ContentContainer>
      </>
    );
  }

  const displayCount = filtered?.length ?? 0;

  return (
    <>
      <PageHeader
        title="Datasets"
        description="Historical coverage & dataset intelligence — authoritative research facts from persistence DatasetSummary. Backend is source of truth; no frontend-derived coverage metrics."
        breadcrumbs={[{ label: "Datasets" }]}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant="neutral">{datasets.length} datasets</Badge>
            <Badge variant="success">backend</Badge>
            <Badge variant="danger">PAPER</Badge>
          </div>
        }
      />
      <ContentContainer>
        <div className="space-y-4">
          {/* Coverage summary */}
          <Card className="p-3">
            <h2 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Coverage summary — backend-known facts</h2>
            <div className="mt-2 grid gap-2 md:grid-cols-3 lg:grid-cols-6">
              <Stat label="Datasets" value={summary ? String(summary.datasets) : "—"} />
              <Stat label="Symbols covered" value={summary ? String(summary.symbols) : "—"} mono />
              <Stat label="Timeframes" value={summary ? String(summary.timeframes) : "—"} mono />
              <Stat label="Total candles" value={summary ? fmtNum(summary.totalCandles) : "—"} mono />
              <Stat label="Earliest data" value={fmtMs(summary?.earliest ?? null)} mono />
              <Stat label="Latest data" value={fmtMs(summary?.latest ?? null)} mono />
            </div>
            <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">
              Only backend-known fields are shown. Missing → <span className="text-[var(--color-text-secondary)]">—</span>. Total candles is sum of <span className="mono">candle_count</span> over returned summaries — presentation aggregation, not a new backend metric. No quality-score invented.
            </div>
          </Card>

          {/* Symbol/timeframe coverage strips */}
          <div className="grid gap-3 md:grid-cols-2">
            <Card className="p-3">
              <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Symbol coverage</h3>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {Array.from(new Set(datasets.map((d) => d.symbol))).map((s) => (
                  <Badge key={s} variant="neutral">{s}</Badge>
                ))}
              </div>
              <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">{symbols.length} distinct symbols from returned datasets.</div>
            </Card>
            <Card className="p-3">
              <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Timeframe coverage</h3>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {Array.from(new Set(datasets.map((d) => d.timeframe))).map((tf) => (
                  <Badge key={tf} variant="neutral">{tf}</Badge>
                ))}
              </div>
              <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">{timeframes.length} distinct timeframes.</div>
            </Card>
          </div>

          {/* Filters — presentation-only */}
          <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="purple">Filters</Badge>
              <span className="mono text-[11px] text-[var(--color-text-tertiary)]">{displayCount} of {datasets.length} datasets</span>
              <button onClick={() => { setFilterSymbol("all"); setFilterTimeframe("all"); setFilterSource("all"); setFilterQuality("all"); }} className="ml-auto text-[11px] font-medium text-[var(--color-purple-accent)] hover:underline">
                Reset
              </button>
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              <Sel label="Symbol" value={filterSymbol} onValue={setFilterSymbol} options={["all", ...symbols]} />
              <Sel label="Timeframe" value={filterTimeframe} onValue={setFilterTimeframe} options={["all", ...timeframes]} />
              <Sel label="Provider" value={filterSource} onValue={setFilterSource} options={["all", ...sources]} />
              <Sel label="Quality" value={filterQuality} onValue={setFilterQuality} options={["all", "clean", "warnings"]} />
            </div>
            <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">Presentation filters over backend-provided fields. No server-side filtering invented.</div>
          </div>

          {/* Dataset inventory */}
          <div>
            <h2 className="mb-2 text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Dataset inventory — authoritative</h2>
            {/* Desktop table */}
            <div className="hidden overflow-hidden rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] md:block">
              <table className="w-full text-left" role="table">
                <thead className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]">
                  <tr className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                    <th scope="col" className="px-3 py-2 font-medium">Dataset</th>
                    <th scope="col" className="px-3 py-2 font-medium">Symbol</th>
                    <th scope="col" className="px-3 py-2 font-medium">TF</th>
                    <th scope="col" className="px-3 py-2 font-medium">Provider</th>
                    <th scope="col" className="px-3 py-2 font-medium">Candles</th>
                    <th scope="col" className="px-3 py-2 font-medium">From</th>
                    <th scope="col" className="px-3 py-2 font-medium">To</th>
                    <th scope="col" className="px-3 py-2 font-medium">Quality</th>
                    <th scope="col" className="px-3 py-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered!.map((d) => {
                    const key = `${d.symbol}-${d.timeframe}-${d.source}`;
                    const isExpanded = expanded === key;
                    return (
                      <>
                        <tr key={key} className="border-b border-[var(--color-border-subtle)] last:border-0 hover:bg-[var(--color-bg-surface-2)]">
                          <td className="mono px-3 py-2 text-[11px] font-medium text-[var(--color-text-primary)]">{d.symbol} · {d.timeframe} · {d.source}</td>
                          <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-secondary)]">{d.symbol}</td>
                          <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-secondary)]">{d.timeframe}</td>
                          <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-secondary)]">{d.source}</td>
                          <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-primary)]">{fmtNum(d.candle_count)}</td>
                          <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-secondary)]">{fmtMs(d.first_timestamp_ms)}</td>
                          <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-secondary)]">{fmtMs(d.last_timestamp_ms)}</td>
                          <td className="px-3 py-2">
                            <div className="flex items-center gap-1.5">
                              <Badge variant={d.quality_status === "clean" ? "success" : "neutral"} icon={d.quality_status === "clean" ? "●" : "○"}>{d.quality_status}</Badge>
                              {d.issues.length > 0 && <span className="mono text-[10px] text-[var(--color-text-tertiary)]">{d.issues.length} {d.issues.length === 1 ? "issue" : "issues"}</span>}
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex gap-1">
                              <Link href={`/?symbol=${encodeURIComponent(d.symbol)}&timeframe=${d.timeframe}`} className="rounded-sm bg-[var(--color-purple-accent)] px-2 py-1 text-[11px] font-medium text-white hover:bg-[#6d4af0]">Analyze</Link>
                              <Link href="/backtests" className="rounded-sm border border-[var(--color-border-subtle)] px-2 py-1 text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-2)]">Backtest</Link>
                              <button onClick={() => setExpanded(isExpanded ? null : key)} className="rounded-sm border border-[var(--color-border-subtle)] px-2 py-1 text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-2)]">{isExpanded ? "Hide" : "Detail"}</button>
                            </div>
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr key={`${key}-detail`} className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]/50">
                            <td colSpan={9} className="px-3 py-2">
                              <div className="grid gap-3 md:grid-cols-3 mono text-[11px] text-[var(--color-text-secondary)]">
                                <div>
                                  <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Ingested</div>
                                  <div className="mt-1">{fmtMsFull(d.ingested_at_ms)}</div>
                                  <div>Updated: {fmtMsFull(d.updated_at_ms)}</div>
                                </div>
                                <div>
                                  <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Quality — stored diagnostics</div>
                                  <div className="mt-1 flex items-center gap-1.5">
                                    <span className={d.quality_status === "clean" ? "text-[var(--color-success)]" : "text-[var(--color-warning)]"}>{d.quality_status.toUpperCase()}</span>
                                    <span className="text-[var(--color-text-tertiary)]">· {d.issues.length} {d.issues.length === 1 ? "issue" : "issues"}</span>
                                  </div>
                                  {d.issues.length === 0 ? (
                                    <div className="mt-1 text-[var(--color-text-tertiary)]">{d.quality_status === "clean" ? "CLEAN — no stored quality diagnostics." : "—"}</div>
                                  ) : (
                                    <ul className="mt-1 max-h-32 space-y-1 overflow-auto pr-1">
                                      {d.issues.map((iss, idx) => (
                                        <li key={idx} className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-2 py-1">
                                          <div className="flex items-center gap-1.5">
                                            <span className="font-medium text-[var(--color-text-primary)]">{iss.kind}</span>
                                            {iss.gap_start_ms !== null && iss.gap_end_ms !== null && (
                                              <span className="rounded-pill bg-[var(--color-warning)]/15 px-1.5 py-0.5 text-[10px] text-[var(--color-warning)]">gap</span>
                                            )}
                                          </div>
                                          <div className="mt-0.5 leading-relaxed text-[var(--color-text-secondary)]">{iss.detail || "—"}</div>
                                          {(iss.gap_start_ms !== null || iss.gap_end_ms !== null) && (
                                            <div className="mt-0.5 text-[10px] text-[var(--color-text-tertiary)]">
                                              gap: {iss.gap_start_ms !== null ? fmtMsFull(iss.gap_start_ms) : "—"} → {iss.gap_end_ms !== null ? fmtMsFull(iss.gap_end_ms) : "—"}
                                              {iss.gap_start_ms !== null && iss.gap_end_ms !== null && (
                                                <span className="ml-1 text-[var(--color-text-secondary)]">· derived duration {formatGapDuration(iss.gap_start_ms, iss.gap_end_ms)}</span>
                                              )}
                                            </div>
                                          )}
                                          {iss.index !== null && <div className="text-[10px] text-[var(--color-text-tertiary)]">index: {iss.index}</div>}
                                        </li>
                                      ))}
                                    </ul>
                                  )}
                                  <div className="mt-1 text-[10px] text-[var(--color-text-tertiary)]">Stored quality diagnostic — not a fabricated health score.</div>
                                </div>
                                <div>
                                  <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Handoffs</div>
                                  <div className="mt-1 flex flex-col gap-1">
                                    <Link href={`/?symbol=${encodeURIComponent(d.symbol)}&timeframe=${d.timeframe}`} className="text-[var(--color-purple-accent)] hover:underline">Dashboard analysis →</Link>
                                    <Link href="/backtests" className="text-[var(--color-purple-accent)] hover:underline">Backtest workspace →</Link>
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="grid gap-2 md:hidden">
              {filtered!.map((d) => {
                const key = `${d.symbol}-${d.timeframe}-${d.source}`;
                const isExpanded = expanded === key;
                return (
                  <div key={key} className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="mono text-[12px] font-semibold text-[var(--color-text-primary)]">{d.symbol} · {d.timeframe}</div>
                      <div className="flex items-center gap-1.5">
                        <Badge variant={d.quality_status === "clean" ? "success" : "neutral"}>{d.quality_status}</Badge>
                        {d.issues.length > 0 && <span className="mono text-[10px] text-[var(--color-text-tertiary)]">{d.issues.length} {d.issues.length === 1 ? "issue" : "issues"}</span>}
                      </div>
                    </div>
                    <div className="mono mt-1 text-[11px] text-[var(--color-text-secondary)]">{d.source} · {fmtNum(d.candle_count)} candles</div>
                    <div className="mono text-[11px] text-[var(--color-text-tertiary)]">{fmtMs(d.first_timestamp_ms)} → {fmtMs(d.last_timestamp_ms)}</div>
                    <div className="mt-2 flex gap-1.5">
                      <Link href={`/?symbol=${encodeURIComponent(d.symbol)}&timeframe=${d.timeframe}`} className="flex-1 rounded-sm bg-[var(--color-purple-accent)] px-2 py-1 text-center text-[11px] font-medium text-white">Analyze</Link>
                      <button onClick={() => setExpanded(isExpanded ? null : key)} className="flex-1 rounded-sm border border-[var(--color-border-subtle)] px-2 py-1 text-[11px] text-[var(--color-text-secondary)]">{isExpanded ? "Hide" : "Detail"}</button>
                    </div>
                    {isExpanded && (
                      <div className="mt-2 space-y-2 rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2 mono text-[11px] text-[var(--color-text-secondary)]">
                        <div>Ingested: {fmtMsFull(d.ingested_at_ms)}</div>
                        <div>Updated: {fmtMsFull(d.updated_at_ms)}</div>
                        <div className="flex items-center gap-1.5">
                          <span>Quality: {d.quality_status}</span>
                          <span className="text-[var(--color-text-tertiary)]">· {d.issues.length} {d.issues.length === 1 ? "issue" : "issues"}</span>
                        </div>
                        {d.issues.length === 0 ? (
                          <div className="text-[var(--color-text-tertiary)]">{d.quality_status === "clean" ? "CLEAN — no stored diagnostics." : "—"}</div>
                        ) : (
                          <ul className="space-y-1">
                            {d.issues.slice(0, 3).map((iss, idx) => (
                              <li key={idx} className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-2 py-1">
                                <div className="font-medium text-[var(--color-text-primary)]">{iss.kind}</div>
                                <div className="leading-relaxed text-[var(--color-text-secondary)]">{iss.detail || "—"}</div>
                                {(iss.gap_start_ms !== null || iss.gap_end_ms !== null) && (
                                  <div className="text-[10px] text-[var(--color-text-tertiary)]">
                                    gap: {iss.gap_start_ms !== null ? fmtMsFull(iss.gap_start_ms) : "—"} → {iss.gap_end_ms !== null ? fmtMsFull(iss.gap_end_ms) : "—"}
                                    {iss.gap_start_ms !== null && iss.gap_end_ms !== null && ` · derived ${formatGapDuration(iss.gap_start_ms, iss.gap_end_ms)}`}
                                  </div>
                                )}
                              </li>
                            ))}
                            {d.issues.length > 3 && <li className="text-[10px] text-[var(--color-text-tertiary)]">+{d.issues.length - 3} more — expand on desktop.</li>}
                          </ul>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {filtered!.length === 0 && (
              <div className="mt-3 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-6 text-center mono text-[13px] text-[var(--color-text-tertiary)]">No datasets match these filters.</div>
            )}
          </div>

          <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
            <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Data quality — stored diagnostics</h3>
            <div className="mono mt-1 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
              Each dataset exposes <span className="text-[var(--color-text-primary)]">quality_status</span> (<span className="text-[var(--color-success)]">clean</span> / <span className="text-[var(--color-warning)]">warnings</span>) plus <span className="text-[var(--color-text-primary)]">issues</span> — stored quality diagnostics (kind, detail, gap timestamps). Displayed as <span className="text-[var(--color-text-primary)]">Stored quality diagnostic</span> (e.g., gap) with derived duration only where both timestamps are authoritative. No quality-score, completeness %, or reliability rating is invented.
            </div>
          </div>

          <div className="mono rounded-sm border border-dashed border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)]/40 px-3 py-2 text-[11px] leading-relaxed text-[var(--color-text-tertiary)]">
            Datasets are global historical facts (symbol/timeframe/source) ordered by <span className="mono text-[var(--color-text-secondary)]">symbol, timeframe, source</span>. Backend authorization: <span className="mono text-[var(--color-text-secondary)]">CurrentUser</span> (authenticated readable), not owner-scoped. Missing → <span className="text-[var(--color-text-secondary)]">—</span>.
          </div>
        </div>
      </ContentContainer>
    </>
  );
}

function Stat({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">{label}</div>
      <div className={`${mono ? "mono" : ""} mt-0.5 text-[12px] font-medium text-[var(--color-text-primary)]`}>{value}</div>
    </div>
  );
}

function Sel({ label, value, onValue, options }: { label: string; value: string; onValue: (v: string) => void; options: string[] }) {
  return (
    <label className="flex items-center gap-1.5 text-[11px]">
      <span className="font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">{label}</span>
      <select value={value} onChange={(e) => onValue(e.target.value)} className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-1.5 py-1 text-[11px] text-[var(--color-text-secondary)] focus:border-[var(--color-purple-accent)] focus:outline-none">
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}
