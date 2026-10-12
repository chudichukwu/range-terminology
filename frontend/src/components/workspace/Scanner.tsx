"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import type { PairAnalysis, Strategy, Watchlist, WatchlistItem } from "@/lib/api/types";
import { ErrorNotice, Field, human, money, WorkspaceHeader } from "./shared";

type Row = { data?: PairAnalysis; error?: string };
const GROUPS = [{ label: "Context", frames: ["1w", "1d"] }, { label: "Range", frames: ["4h", "1h"] }, { label: "Entry", frames: ["30m", "15m", "5m", "1m"] }];
const DEFAULT_FRAMES = ["4h", "1h", "15m", "1d", "1w"];
const isFresh = (r: Row) => !!r.data && !r.error && !r.data.freshness.is_stale && r.data.is_analysis_safe;
const isConfirmed = (d: PairAnalysis) => d.signal.direction !== "none" && !!d.signal.confirmation;
const hasSfp = (d: PairAnalysis) => d.swing_failures.some(s => s.timestamp === d.freshness.last_closed_timestamp_ms);

export function Scanner({ initialId }: { initialId?: string }) {
  const [lists, setLists] = useState<Watchlist[]>([]), [id, setId] = useState(initialId ?? "");
  const [items, setItems] = useState<WatchlistItem[]>([]), [strategies, setStrategies] = useState<Strategy[]>([]);
  const [strategy, setStrategy] = useState("");
  const [frames, setFrames] = useState<string[]>(DEFAULT_FRAMES), [draft, setDraft] = useState<string[]>(DEFAULT_FRAMES);
  const [rows, setRows] = useState<Record<string, Row>>({});
  const [loading, setLoading] = useState(true), [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [filter, setFilter] = useState("all"), [search, setSearch] = useState("");
  const [cycle, setCycle] = useState(0), [progress, setProgress] = useState({ completed: 0, total: 0 });
  const [updated, setUpdated] = useState<number | null>(null);
  const generation = useRef(0);
  useEffect(() => {
    const ac = new AbortController();
    Promise.all([api.listWatchlists(ac.signal), api.listStrategies(ac.signal)]).then(([w, s]) => {
      if (ac.signal.aborted) return;
      setLists(w.data); setStrategies(s.data.filter(x => x.active));
      setId(initialId && w.data.some(x => x.id === initialId) ? initialId : w.data[0]?.id ?? "");
      if (!w.data.length) setLoading(false);
    }).catch(e => { if (!ac.signal.aborted) { setError(e); setLoading(false); } });
    return () => ac.abort();
  }, [initialId]);
  useEffect(() => {
    const ac = new AbortController(); setItems([]); setRows({}); setUpdated(null);
    if (id) {
      setLoading(true); setError(null);
      api.getWatchlist(id, ac.signal).then(({ data }) => { if (!ac.signal.aborted) setItems(data.items.filter(i => i.enabled)); })
        .catch(e => { if (!ac.signal.aborted) setError(e); }).finally(() => { if (!ac.signal.aborted) setLoading(false); });
    }
    return () => ac.abort();
  }, [id]);
  useEffect(() => { setRows({}); setUpdated(null); }, [strategy, frames]);
  useEffect(() => {
    const ac = new AbortController(); const gen = ++generation.current;
    let timer: ReturnType<typeof setTimeout>;
    const scan = async (requested = false) => {
      if (document.hidden && !requested) { timer = setTimeout(scan, 10000); return; }
      const jobs = frames.flatMap(tf => items.map(item => ({ item, tf })));
      setProgress({ completed: 0, total: jobs.length });
      if (!jobs.length) { setBusy(false); return; }
      setBusy(true); let index = 0;
      await Promise.all(Array.from({ length: Math.min(2, jobs.length) }, async () => {
        while (index < jobs.length && !ac.signal.aborted) {
          const { item, tf } = jobs[index++]; const key = `${item.id}:${tf}`;
          try {
            const { data } = await api.pairAnalysis({ symbol: item.symbol, timeframe: tf, venue: item.venue_id, strategy_id: strategy || undefined, summary: true }, ac.signal);
            if (generation.current === gen && !ac.signal.aborted) setRows(prev => ({ ...prev, [key]: { data } }));
          } catch (e) {
            if (generation.current === gen && !ac.signal.aborted) setRows(prev => ({ ...prev, [key]: { ...prev[key], error: e instanceof Error ? e.message : String(e) } }));
          } finally {
            if (generation.current === gen && !ac.signal.aborted) setProgress(prev => ({ ...prev, completed: prev.completed + 1 }));
          }
        }
      }));
      if (generation.current === gen && !ac.signal.aborted) { setBusy(false); setUpdated(Date.now()); timer = setTimeout(scan, 60000); }
    };
    void scan(true); return () => { ac.abort(); clearTimeout(timer); };
  }, [items, frames, strategy, cycle]);
  const matches = (r?: Row) => {
    if (filter === "all") return true;
    if (!r || !isFresh(r)) return false;
    const d = r.data!;
    return filter === "edge" ? !!d.signal.metadata.at_extreme : filter === "entry" ? isConfirmed(d) : filter === "sfp" ? hasSfp(d) : filter === "range" ? d.range.is_tradable : d.regime.value.startsWith("trending");
  };
  const shown = items.filter(i => i.symbol.toLowerCase().includes(search.toLowerCase()) && frames.some(tf => matches(rows[`${i.id}:${tf}`])));
  const fresh = Object.values(rows).filter(isFresh).map(r => r.data!);
  const pending = draft.length !== frames.length || draft.some(tf => !frames.includes(tf));
  const completed = progress.total ? progress.completed / progress.total * 100 : 0;
  return <div className="workspace discovery-workspace">
    <WorkspaceHeader eyebrow="MARKET DISCOVERY" title="Find your next range." description="Read the context. Find the extreme. Wait for your trigger.">
      <Link className="secondary-button" href="/watchlists">Manage watchlists ↗</Link><button className="primary-button" disabled={busy || !items.length} onClick={() => setCycle(c => c + 1)}>{busy ? "Scanning…" : "Refresh scan"}</button>
    </WorkspaceHeader><ErrorNotice error={error} />
    <div className="scan-overview"><div><span className="eyebrow">YOUR UNIVERSE</span><strong>{items.length}<small>markets</small></strong></div><div><span>Valid ranges</span><strong>{fresh.filter(d => d.range.is_tradable).length}<small>timeframes</small></strong></div><div><span>At an extreme</span><strong>{fresh.filter(d => d.signal.metadata.at_extreme).length}<small>watch conditions</small></strong></div><div><span>Confirmed entries</span><strong>{fresh.filter(isConfirmed).length}<small>closed candle</small></strong></div></div>
    <section className="panel scan-surface" aria-label="Market scanner">
      <div className="panel-toolbar"><div className="toolbar-controls"><Field label="Scan watchlist"><select value={id} onChange={e => setId(e.target.value)}><option value="">Choose a watchlist</option>{lists.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}</select></Field><Field label="Playbook"><select value={strategy} onChange={e => setStrategy(e.target.value)}><option value="">Confirmed range</option>{strategies.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field></div><Field label="Find a market"><input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="BTC, ETH, SOL…" /></Field></div>
      <details className="scan-timeframes"><summary>Timeframes <span>{frames.join(" · ")}</span><span className="muted">Customize</span></summary><div className="scan-timeframe-options">{GROUPS.map(g => <div key={g.label}><span className="eyebrow">{g.label}</span><div className="chips">{g.frames.map(tf => <button key={tf} className={`chip ${draft.includes(tf) ? "selected" : ""}`} aria-pressed={draft.includes(tf)} onClick={() => setDraft(p => p.includes(tf) ? p.filter(t => t !== tf) : [...p, tf])}>{tf}</button>)}</div></div>)}<button className="primary-button" disabled={!draft.length || !pending} onClick={() => setFrames([...draft])}>Apply timeframes</button></div></details>
      <div className="scan-filter-row"><div className="filter-tabs">{[["all", "All markets"], ["range", "Valid ranges"], ["edge", "At extremes"], ["entry", "Confirmed"], ["sfp", "SFP"], ["trend", "Trending"]].map(([key, label]) => <button key={key} aria-pressed={filter === key} className={filter === key ? "active" : ""} onClick={() => setFilter(key)}>{label}</button>)}</div></div>
      <div className="scan-live-status" role="status"><span className="live-dot" /><span>{loading ? "Loading your watchlist…" : busy ? `Checking ${progress.completed} / ${progress.total} timeframes` : updated ? `Scan completed ${new Date(updated).toLocaleTimeString()}` : "Ready to scan"}</span><small>{busy ? "Results appear as they arrive" : "Refreshes every 60s while visible"}</small></div><div className="scan-progress" role="progressbar" aria-label="Scan progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(completed)}><span style={{ width: `${completed}%` }} /></div>
      {!loading && !items.length ? <div className="empty-workspace"><div className="range-glyph">↔</div><h2>Choose the markets you follow.</h2><p>Your watchlists define where the scanner looks for setups.</p><Link className="primary-button" href="/watchlists">Build a watchlist</Link></div> : !shown.length && !loading ? <div className="empty-workspace"><h2>{busy ? "Looking for matches…" : "No matching setups"}</h2><p>{busy ? "Markets will appear as each timeframe is checked." : "Try another filter. A quiet scan is a valid result."}</p></div> : <div className="scan-matrix" style={{ "--scan-columns": frames.length } as React.CSSProperties}>
        <div className="scan-matrix-head"><span>Market / source</span>{frames.map(tf => <span key={tf}>{tf}<small>{["1w", "1d"].includes(tf) ? "Context" : ["4h", "1h"].includes(tf) ? "Range" : "Entry"}</small></span>)}</div>
        {shown.map(item => <div className="scan-market-row" key={item.id}><div className="token-identity"><span className="token-avatar">{item.symbol.split("/")[0].slice(0, 2)}</span><div><strong>{item.symbol.split("/")[0]}</strong><small>{item.venue_id}</small><small>{item.symbol}</small></div></div><div className="scan-market-cells">{frames.map(tf => {
          const r = rows[`${item.id}:${tf}`], d = r?.data, safe = !!r && isFresh(r);
          const href = `/?${new URLSearchParams({ symbol: item.symbol, timeframe: tf, venue: item.venue_id, watchlist: id, ...(strategy ? { strategy } : {}) })}`;
          return <Link key={tf} href={href} className={`scan-cell ${safe && d?.range.is_tradable ? "is-range" : ""} ${filter !== "all" && !matches(r) ? "is-muted" : ""}`} title={r?.error ?? d?.signal.reason ?? `Open ${tf} chart`}><span className="scan-cell-timeframe">{tf} <span>↗</span></span><strong>{r?.error ? "Refresh failed" : !d ? "Waiting…" : !safe ? "Data incomplete" : human(d.range.status)}</strong><span>{d ? `${money(d.range.low)} — ${money(d.range.high)}` : "Checking structure"}</span><small>{!safe ? (d ? "Previous result · not current" : "") : isConfirmed(d!) ? `${human(d!.signal.direction)} confirmed` : hasSfp(d!) ? "Swing failure" : d!.signal.metadata.at_extreme ? "At extreme · watch" : "No entry trigger"}</small>{d && <time>{new Date(d.freshness.retrieved_at_ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time>}</Link>;
        })}</div></div>)}
      </div>}
    </section><p className="workspace-footnote">A range or edge touch is a watch condition. Entry confirmation and higher-timeframe context are checked separately.</p>
  </div>;
}
