"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ErrorState, LoadingState, EmptyState } from "@/components/state/StatePrimitives";
import { RegimeZoneBreakdown } from "@/components/backtest/RegimeZoneBreakdown";
import { EquityCurve } from "@/components/backtest/EquityCurve";
import { PerformanceSummary } from "@/components/backtest/PerformanceSummary";
import { TradeTable } from "@/components/backtest/TradeTable";
import { api, ApiError } from "@/lib/api/client";
import type { BacktestDetail, BacktestRunSummary, Strategy } from "@/lib/api/types";

function toDateInput(ms: number): string {
  const d = new Date(ms);
  return d.toISOString().slice(0, 10);
}
function fromDateInput(s: string): number | null {
  if (!s) return null;
  const ms = new Date(s + "T00:00:00Z").getTime();
  return Number.isFinite(ms) ? ms : null;
}

export default function BacktestsPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [runs, setRuns] = useState<BacktestRunSummary[] | null>(null);
  const [listError, setListError] = useState<{ message: string; requestId: string } | null>(null);

  // config state
  const [strategyId, setStrategyId] = useState<string>("");
  const [startDate, setStartDate] = useState<string>(() => toDateInput(Date.now() - 90 * 86400000));
  const [endDate, setEndDate] = useState<string>(() => toDateInput(Date.now() - 1 * 86400000));
  const [initialCapital, setInitialCapital] = useState<string>("10000");
  const [feeRate, setFeeRate] = useState<string>("");
  const [slippageRate, setSlippageRate] = useState<string>("");

  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<{ message: string; requestId: string } | null>(null);
  const [lastResult, setLastResult] = useState<BacktestDetail | null>(null);

  // comparison selection
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [compareDetails, setCompareDetails] = useState<BacktestDetail[] | null>(null);

  const loadStrategies = () => {
    api.listStrategies().then(({ data }) => {
      setStrategies(data);
      if (data.length > 0 && !strategyId) setStrategyId(data[0]!.id);
    }).catch(() => {});
  };
  const loadRuns = () => {
    setListError(null);
    api.listBacktests().then(({ data }) => setRuns(data)).catch((e) => {
      if (e instanceof ApiError) setListError({ message: `${e.code}: ${e.message}`, requestId: e.requestId });
      else setListError({ message: String(e), requestId: "" });
    });
  };

  useEffect(() => {
    loadStrategies();
    loadRuns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedStrategy = strategies.find((s) => s.id === strategyId);
  const canRun = !!strategyId && !!fromDateInput(startDate) && !!fromDateInput(endDate) && !!initialCapital.trim() && Number.isFinite(Number(initialCapital)) && Number(initialCapital) > 0;

  const onRun = async () => {
    if (!canRun || running) return;
    setRunning(true);
    setRunError(null);
    setLastResult(null);
    const start_ms = fromDateInput(startDate)!;
    const end_ms = fromDateInput(endDate)!;
    if (start_ms >= end_ms) {
      setRunError({ message: "validation_error: start_ms must precede end_ms", requestId: "" });
      setRunning(false);
      return;
    }
    try {
      const body: Record<string, unknown> = { strategy_id: strategyId, start_ms, end_ms, initial_capital: Number(initialCapital) };
      if (feeRate.trim() !== "") body.fee_rate = Number(feeRate);
      if (slippageRate.trim() !== "") body.slippage_rate = Number(slippageRate);
      const { data } = await api.runBacktest(body as any);
      // POST returns full detail already
      setLastResult(data as unknown as BacktestDetail);
      // refresh history
      loadRuns();
    } catch (e) {
      if (e instanceof ApiError) setRunError({ message: `${e.code}: ${e.message}`, requestId: e.requestId });
      else setRunError({ message: String(e), requestId: "" });
    } finally {
      setRunning(false);
    }
  };

  const toggleCompare = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else {
        if (next.size >= 4) return prev;
        next.add(id);
      }
      return next;
    });
  };

  const loadCompare = async () => {
    const ids = Array.from(selected);
    if (ids.length < 2) return;
    setCompareDetails(null);
    try {
      const results = await Promise.all(ids.map((id) => api.getBacktest(id).then(({ data }) => data as unknown as BacktestDetail)));
      setCompareDetails(results);
    } catch (e) {
      // individual fetch error handled per detail; comparison will show error
      if (e instanceof ApiError) setRunError({ message: `${e.code}: ${e.message}`, requestId: e.requestId });
    }
  };

  return (
    <>
      <PageHeader
        title="Backtests & Research"
        description="Deterministic replay over historical candles via existing Phase-8 engine. Strategy is primary config source; backend owns all domain truth."
        breadcrumbs={[{ label: "Backtests" }]}
        actions={<Badge variant="danger">PAPER</Badge>}
      />
      <ContentContainer>
        <div className="grid gap-4 lg:grid-cols-[420px_1fr]">
          {/* Config */}
          <div className="space-y-3 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-4">
            <h2 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Configuration</h2>
            <label className="block">
              <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Strategy (required)</span>
              <select value={strategyId} onChange={(e) => setStrategyId(e.target.value)} className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-purple-accent)] focus:outline-none">
                <option value="">Select strategy…</option>
                {strategies.map((s) => (
                  <option key={s.id} value={s.id}>{s.name} {s.active ? "" : "(disabled)"} — {s.id.slice(0, 6)}</option>
                ))}
              </select>
              {selectedStrategy && (
                <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">
                  {String((selectedStrategy.payload as any).symbol ?? "symbol from strategy")} · {String((selectedStrategy.payload as any).timeframe ?? "1h")} · id {selectedStrategy.id.slice(0, 8)} · v{selectedStrategy.schema_version} · {selectedStrategy.active ? "active" : "disabled"}
                </div>
              )}
              <div className="mt-1 mono text-[11px] text-[var(--color-text-tertiary)]">Strategy payload holds range/signal/risk + symbol/timeframe. No manual reconstruction.</div>
            </label>

            <div className="grid gap-3 md:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">Start (UTC)</span>
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-purple-accent)] focus:outline-none" />
              </label>
              <label className="block">
                <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">End (UTC)</span>
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-purple-accent)] focus:outline-none" />
              </label>
            </div>
            <label className="block">
              <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">Initial capital (quote)</span>
              <input type="number" value={initialCapital} onChange={(e) => setInitialCapital(e.target.value)} placeholder="10000" className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-purple-accent)] focus:outline-none" />
            </label>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">Fee rate (0–0.1, optional)</span>
                <input type="number" step="0.0001" placeholder="0.0005" value={feeRate} onChange={(e) => setFeeRate(e.target.value)} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-purple-accent)] focus:outline-none" />
              </label>
              <label className="block">
                <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">Slippage (0–0.1, optional)</span>
                <input type="number" step="0.0001" placeholder="0.0002" value={slippageRate} onChange={(e) => setSlippageRate(e.target.value)} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-purple-accent)] focus:outline-none" />
              </label>
            </div>

            <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2">
              <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Review — configuration</div>
              <div className="mono mt-1 text-[11px] text-[var(--color-text-secondary)]">
                {selectedStrategy ? `${selectedStrategy.name} · ${strategyId.slice(0, 8)}` : "No strategy"} · {startDate} → {endDate} · capital {initialCapital || "—"}
              </div>
              <div className="mono text-[11px] text-[var(--color-text-tertiary)]">Results are deterministic per config_hash + window; backend validates symbol/timeframe from strategy.</div>
            </div>

            <Button variant="primary" className="w-full" onClick={onRun} disabled={!canRun || running}>
              {running ? "Running…" : "Run backtest"}
            </Button>
            {runError && <ErrorState message={runError.message} requestId={runError.requestId} />}
            <div className="mono text-[11px] text-[var(--color-text-tertiary)]">Data quality: backend reports quality_issues/gaps; no React inference. Missing coverage shows “—”, not 0. Forming candles excluded from replay per engine.</div>
          </div>

          {/* Research context / history */}
          <div className="space-y-3">
            {lastResult && (
              <div className="space-y-3 rounded-md border border-[var(--color-purple-accent)]/30 bg-[var(--color-bg-surface-1)] p-3">
                <div className="flex items-center gap-2">
                  <Badge variant="success">Latest run</Badge>
                  <span className="mono text-[11px] text-[var(--color-text-tertiary)]">{lastResult.run_id.slice(0, 8)} · {lastResult.config_hash.slice(0, 8)} · {lastResult.engine_version ?? "engine"}</span>
                  <Link href={`/backtests/${lastResult.run_id}`} className="ml-auto text-[11px] font-medium text-[var(--color-purple-accent)] hover:underline">Open detail →</Link>
                </div>
                <PerformanceSummary stats={lastResult.statistics as any} initialCapital={lastResult.initial_capital} finalEquity={lastResult.final_equity} />
                <EquityCurve points={lastResult.equity_curve} initialCapital={lastResult.initial_capital} />
              </div>
            )}

            <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
              <div className="flex items-center justify-between">
                <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Recent runs</h3>
                <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())} disabled={selected.size === 0}>Clear</Button>
                <Button variant="secondary" size="sm" onClick={loadCompare} disabled={selected.size < 2}>Compare ({selected.size})</Button>
              </div>
              {!runs ? listError ? <div className="mt-2"><ErrorState message={listError.message} requestId={listError.requestId} /></div> : <div className="mt-2"><LoadingState label="Loading runs" /></div> : runs.length === 0 ? (
                <EmptyState title="No runs yet" description="Configure a strategy and window above and Run. Runs are persisted per user (OWNER sees all)." />
              ) : (
                <div className="mt-2 overflow-hidden rounded-sm border border-[var(--color-border-subtle)]">
                  <div className="max-h-[320px] overflow-auto">
                    <table className="w-full text-left" role="table">
                      <thead className="sticky top-0 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                        <tr>
                          <th className="px-2 py-1.5 font-medium">Compare</th>
                          <th className="px-2 py-1.5 font-medium">Run</th>
                          <th className="px-2 py-1.5 font-medium">Symbol/TF</th>
                          <th className="px-2 py-1.5 font-medium">Trades</th>
                          <th className="px-2 py-1.5 font-medium">Final</th>
                          <th className="px-2 py-1.5 font-medium">Created</th>
                        </tr>
                      </thead>
                      <tbody>
                        {runs.map((r) => (
                          <tr key={r.run_id} className="border-b border-[var(--color-border-subtle)] last:border-0 hover:bg-[var(--color-bg-surface-2)]">
                            <td className="px-2 py-1.5"><input type="checkbox" checked={selected.has(r.run_id)} onChange={() => toggleCompare(r.run_id)} aria-label={`Select ${r.run_id.slice(0, 8)} for comparison`} /></td>
                            <td className="mono px-2 py-1.5 text-[11px]"><Link href={`/backtests/${r.run_id}`} className="font-medium text-[var(--color-purple-accent)] hover:underline">{r.run_id.slice(0, 8)}</Link> <span className="text-[var(--color-text-tertiary)]">{r.config_hash.slice(0, 6)}</span></td>
                            <td className="mono px-2 py-1.5 text-[11px] text-[var(--color-text-secondary)]">{r.symbol} · {r.timeframe}</td>
                            <td className="mono px-2 py-1.5 text-[11px] text-[var(--color-text-secondary)]">{r.total_trades}</td>
                            <td className="mono px-2 py-1.5 text-[11px] text-[var(--color-text-primary)]">{r.final_equity.toFixed(0)}</td>
                            <td className="mono px-2 py-1.5 text-[11px] text-[var(--color-text-tertiary)]">{new Date(r.created_at_ms).toLocaleDateString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {compareDetails && (
              <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
                <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Comparison — authoritative fields only</h3>
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full text-left" role="table">
                    <thead className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                      <tr><th className="px-2 py-1 font-medium">Metric</th>{compareDetails.map((d) => (<th key={d.run_id} className="mono px-2 py-1 font-medium text-[var(--color-purple-accent)]">{d.run_id.slice(0, 8)}</th>))}</tr>
                    </thead>
                    <tbody className="mono text-[11px] text-[var(--color-text-secondary)]">
                      <tr className="border-t border-[var(--color-border-subtle)]"><td className="px-2 py-1 text-[var(--color-text-tertiary)]">Total P&L</td>{compareDetails.map((d) => <td key={d.run_id} className="px-2 py-1">{d.statistics.total_realized_pnl?.toFixed(2) ?? "—"}</td>)}</tr>
                      <tr className="border-t border-[var(--color-border-subtle)]"><td className="px-2 py-1 text-[var(--color-text-tertiary)]">Win rate</td>{compareDetails.map((d) => <td key={d.run_id} className="px-2 py-1">{d.statistics.win_rate !== null ? `${(d.statistics.win_rate * 100).toFixed(1)}%` : "—"}</td>)}</tr>
                      <tr className="border-t border-[var(--color-border-subtle)]"><td className="px-2 py-1 text-[var(--color-text-tertiary)]">Trades</td>{compareDetails.map((d) => <td key={d.run_id} className="px-2 py-1">{d.statistics.total_trades}</td>)}</tr>
                      <tr className="border-t border-[var(--color-border-subtle)]"><td className="px-2 py-1 text-[var(--color-text-tertiary)]">Profit factor</td>{compareDetails.map((d) => <td key={d.run_id} className="px-2 py-1">{d.statistics.profit_factor !== null ? (d.statistics.profit_factor as number).toFixed(2) : "—"}</td>)}</tr>
                      <tr className="border-t border-[var(--color-border-subtle)]"><td className="px-2 py-1 text-[var(--color-text-tertiary)]">Max DD</td>{compareDetails.map((d) => <td key={d.run_id} className="px-2 py-1">{d.statistics.max_drawdown !== null ? (d.statistics.max_drawdown as number).toFixed(2) : "—"}</td>)}</tr>
                      <tr className="border-t border-[var(--color-border-subtle)]"><td className="px-2 py-1 text-[var(--color-text-tertiary)]">R avg</td>{compareDetails.map((d) => <td key={d.run_id} className="px-2 py-1">{d.statistics.average_r !== null ? (d.statistics.average_r as number).toFixed(3) : "—"}</td>)}</tr>
                    </tbody>
                  </table>
                </div>
                <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">No “best” ranking, no optimization, no AI. Research instrument only; “—” means backend null, not 0.</div>
              </div>
            )}
          </div>
        </div>
      </ContentContainer>
    </>
  );
}
