"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { RangeContext } from "./RangeContext";
import { ManualRange } from "./ManualRange";
import { TradingChart } from "./TradingChart";
import { usePairAnalysis } from "@/hooks/usePairAnalysis";
import { Scanner } from "@/components/workspace/Scanner";
import { Field, human, money, SOURCES, WorkspaceHeader } from "@/components/workspace/shared";
import { api } from "@/lib/api/client";
import type { PairAnalysis, Strategy } from "@/lib/api/types";

export function DashboardClient() {
  const query = useSearchParams(), router = useRouter();
  const symbol = query.get("symbol"), tf = query.get("timeframe") ?? "1h", venue = query.get("venue") ?? "hyperliquid";
  const strategy = query.get("strategy_id") ?? query.get("strategy") ?? "", watchlist = query.get("watchlist");
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [inspector, setInspector] = useState("setup");
  useEffect(() => { if (symbol) api.listStrategies().then(({ data }) => setStrategies(data)).catch(() => {}); }, [symbol]);
  const history = [200, 500, 1000].includes(Number(query.get("history"))) ? Number(query.get("history")) : 200;
  const state = usePairAnalysis(symbol, tf, strategy || undefined, history, venue);
  const change = (key: string, value: string) => {
    const p = new URLSearchParams(query.toString()); p.set(key, value);
    if (["symbol", "venue", "timeframe"].includes(key)) { p.delete("range_low"); p.delete("range_high"); }
    if (key === "strategy_id") p.delete("strategy");
    router.replace(`/?${p}`);
  };
  if (!symbol) return <Scanner initialId={watchlist ?? undefined} />;
  const low = Number(query.get("range_low")), high = Number(query.get("range_high"));
  const manual = Number.isFinite(low) && Number.isFinite(high) && low > 0 && high > low;
  const setRange = (lo?: number, hi?: number) => {
    const p = new URLSearchParams(query.toString()); p.delete("range_low"); p.delete("range_high");
    if (lo !== undefined && hi !== undefined) { p.set("range_low", String(lo)); p.set("range_high", String(hi)); }
    router.replace(`/?${p}`);
  };
  const raw = state.status === "success" ? state.data : null;
  const d: PairAnalysis | null = raw && manual ? { ...raw, range: { ...raw.range, low, high, width: high - low, is_tradable: false, status: "manual", metadata: { ...raw.range.metadata, midpoint: (low + high) / 2, reclaimed: false, structure_confirmed: true, reason: "Manual chart levels; automated entry plan hidden", low_touches: "—", high_touches: "—" } }, risk: null, signal: { ...raw.signal, direction: "none" as const, metadata: { ...raw.signal.metadata } }, swing_failures: raw.swing_failures.filter(e => e.grade !== "A+") } : raw;
  const back = watchlist ? `/?watchlist=${encodeURIComponent(watchlist)}` : "/";
  return <div className="workspace analysis-workspace">
    <WorkspaceHeader eyebrow="MARKET ANALYSIS" title={symbol} description={`${venue} · ${tf} · ${manual ? "Your observed range" : "Range structure & entry context"}`}>
      <Link className="secondary-button" href={back}>← Scanner</Link><Link className="secondary-button" href="/journal">Write a note ↗</Link><Link className="primary-button" href="/alerts">Set up alerts ↗</Link>
    </WorkspaceHeader>
    <section className="panel analysis-tools"><div className="panel-toolbar"><div className="toolbar-controls">
      <Field label="Price source"><select value={venue} onChange={e => change("venue", e.target.value)}>{SOURCES.map(s => <option value={s.id} key={s.id}>{s.name}</option>)}</select></Field>
      <Field label="Exact market"><input key={symbol} defaultValue={symbol} onBlur={e => { if (e.target.value.trim() && e.target.value !== symbol) change("symbol", e.target.value.trim()); }} onKeyDown={e => { if (e.key === "Enter") e.currentTarget.blur(); }} /></Field>
      <Field label="Playbook"><select value={strategy} onChange={e => change("strategy_id", e.target.value)}><option value="">Confirmed range</option>{strategies.map(s => <option value={s.id} key={s.id}>{s.name}</option>)}</select></Field>
    </div></div><div className="timeframe-groups" role="group" aria-label="Chart timeframe">{[{ label: "Context", frames: ["1w", "1d"] }, { label: "Range", frames: ["4h", "1h"] }, { label: "Entry timing", frames: ["30m", "15m", "5m", "1m"] }].map(group => <div key={group.label}><span className="eyebrow">{group.label}</span><div className="chips">{group.frames.map(t => <button aria-pressed={tf === t} className={`chip ${tf === t ? "selected" : ""}`} onClick={() => change("timeframe", t)} key={t}>{t}</button>)}</div></div>)}<Field label="History"><select value={history} onChange={e => change("history", e.target.value)}><option value={200}>200 candles</option><option value={500}>500 candles</option><option value={1000}>1,000 candles</option></select></Field></div></section>
    {state.status === "error" && <div className="notice error" role="alert">{state.message}{state.statusCode === 401 && <Link href="/login">Sign in →</Link>}<p>Check the market and data source. Retrying every 30 seconds.</p></div>}
    {state.status === "loading" && <div className="empty-workspace" role="status"><h2>Reading market structure…</h2><p>Fetching candles and checking your playbook.</p></div>}
    {d && <><div className="chart-layout"><div><TradingChart analysis={d} /><div className="workspace-footnote"><span>{d.candles.length} candles · {d.candles.length ? new Date(d.candles[0].timestamp).toLocaleDateString() : "—"} to {d.candles.length ? new Date(d.candles[d.candles.length - 1].timestamp).toLocaleDateString() : "—"}</span><span>{d.freshness.is_stale ? "Stale data · signals blocked" : d.is_analysis_safe ? "Closed history checked · refreshes every 30s" : "Data gaps · signals blocked"}</span></div></div>
      <aside className="analysis-inspector"><div className="filter-tabs" role="group" aria-label="Analysis inspector">{[["setup", "Setup"], ["range", "My range"]].map(([key, label]) => <button key={key} aria-pressed={inspector === key} className={inspector === key ? "active" : ""} onClick={() => setInspector(key)}>{label}</button>)}</div>
        <div hidden={inspector !== "range"}><ManualRange analysis={raw!} key={`${symbol}:${tf}:${venue}`} low={manual ? low : undefined} high={manual ? high : undefined} onApply={setRange} onClear={() => setRange()} /></div>
        {inspector === "setup" && <section className="panel detail-panel"><p className="eyebrow">{manual ? "MANUAL LEVELS" : "ENTRY CHECK"} · {String(d.signal.metadata.range_timeframe ?? tf)}</p><h2>{manual ? "Your range" : d.signal.direction === "none" ? d.range.is_tradable ? "Waiting for confirmation" : "No valid range entry" : `${human(d.signal.direction)} ${d.signal.confirmation ? "confirmed" : "edge touched"}`}</h2><span className="status-pill">{d.range.metadata.reclaimed ? "Reclaimed · " : ""}{human(d.regime.value)}</span>
          {[["Last price", money(d.ticker_last ?? d.signal.price)], [`${tf} range high`, money(d.range.high)], [`${tf} range low`, money(d.range.low)], ["Midpoint · 50%", money(d.range.metadata.midpoint as number | undefined)], ["Touches · low / high", `${d.range.metadata.low_touches ?? "—"} / ${d.range.metadata.high_touches ?? "—"}`], ["Entry", d.signal.direction !== "none" ? money(d.signal.price) : "—"], ["Invalidation", money(d.risk?.stop_price ?? d.risk?.metadata?.stop_price as number | undefined)], ["TP1 · midpoint", money(d.risk?.target_price ?? d.risk?.metadata?.target_price as number | undefined)], ["TP2 · opposite edge", money(d.risk?.metadata.tp2 as number | undefined)]].map(([label, value]) => <div className="level-row" key={label}><span>{label}</span><b>{value}</b></div>)}
          {d.risk && <div className="level-row"><span>Runner</span><b>{Number(d.risk.metadata.runner_fraction ?? 0) * 100}% · {Number(d.risk.metadata.runner_trail_percent ?? .02) * 100}% trail</b></div>}
          <p className="muted" style={{ marginTop: 18 }}>{manual ? "Your levels are for chart observation. Automatic entry confirmation is hidden." : d.signal.reason}</p>{d.risk && !d.risk.approved && <p className="muted">Risk filter: {human(d.risk.rejection_reason ?? "not approved")}</p>}
        </section>}
      </aside></div>
      {!manual && <details className="panel analysis-context"><summary>Range context & midpoint observations</summary><RangeContext analysis={d} /></details>}
      <details className="panel analysis-history"><summary>Swing failure history · {d.swing_failures.length} in loaded candles</summary>{d.swing_failures.length ? [...d.swing_failures].reverse().map((s, i) => <div className="event-row" key={`${s.timestamp}:${i}`}><span className="event-icon">{s.direction === "bullish" ? "↗" : "↘"}</span><div><strong>{s.direction} {s.grade === "A+" ? "A+ range SFP" : "swing SFP"}</strong><p>Swept {money(s.level)} and reclaimed</p></div><time className="event-time muted">{new Date(s.timestamp).toLocaleString()}</time></div>) : <p className="muted" style={{ padding: 20 }}>No confirmed sweeps in the loaded history. The forming candle is excluded.</p>}</details>
      {d.timeframe_context && <details className="panel analysis-context"><summary>Higher-timeframe context</summary><div className="stat-grid" style={{ padding: 18, margin: 0 }}>{Object.entries(d.timeframe_context).map(([frame, c]) => <div className="stat-card" key={frame}><span>{frame} · {c.role}</span><h3>{human(c.state)}{c.trend ? ` · ${c.trend}` : ""}</h3><small>ADX {c.adx?.toFixed(1) ?? "—"} · ATR {money(c.atr)}</small><p className="muted">{c.reason}</p></div>)}</div></details>}
    </>}
  </div>;
}
