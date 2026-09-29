"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import type { PairAnalysis, Strategy, Watchlist, WatchlistItem } from "@/lib/api/types";
import { ErrorNotice, Field, human, money, SOURCES, TIMEFRAMES, WorkspaceHeader } from "./shared";

type Row = { item: WatchlistItem; tf: string; data?: PairAnalysis; error?: string };
export function Scanner({ initialId }: { initialId?: string }) {
  const [lists, setLists] = useState<Watchlist[]>([]);
  const [id, setId] = useState(initialId ?? "");
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [strategy, setStrategy] = useState("");
  const [tfs, setTfs] = useState<string[]>(["15m", "1h", "4h", "1d", "1w"]);
  const [rows, setRows] = useState<Record<string, Row>>({});
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [filter, setFilter] = useState("all");
  const [name, setName] = useState("");
  const [venue, setVenue] = useState("hyperliquid");
  const [symbol, setSymbol] = useState("");
  const [symbols, setSymbols] = useState<string[]>([]);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [updated, setUpdated] = useState<number | null>(null);
  const generation = useRef(0);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => {
    let alive = true;
    Promise.all([api.listWatchlists(), api.listStrategies()]).then(([w, s]) => {
      if (!alive) return;
      setLists(w.data); setStrategies(s.data.filter(x => x.active));
      if (!initialId) setId(w.data[0]?.id ?? "");
    }).catch(e => alive && setError(e)).finally(() => alive && setLoaded(true));
    return () => { alive = false; };
  }, [initialId]);
  useEffect(() => {
    const ac = new AbortController(); setItems([]); setRows({});
    if (id) api.getWatchlist(id, ac.signal).then(({ data }) => setItems(data.items)).catch(e => { if (!ac.signal.aborted) setError(e); });
    return () => ac.abort();
  }, [id]);
  useEffect(() => {
    if (!editing) return;
    const ac = new AbortController(); setSymbols([]);
    const timer = setTimeout(() => api.get<string[]>(`/markets/symbols?venue=${venue}&q=${encodeURIComponent(symbol)}`, ac.signal).then(({ data }) => setSymbols(data)).catch(e => { if (!ac.signal.aborted) setError(e); }), 300);
    return () => { clearTimeout(timer); ac.abort(); };
  }, [venue, editing, symbol]);
  const scan = useCallback(async () => {
    abort.current?.abort(); const ac = new AbortController(); abort.current = ac;
    const gen = ++generation.current;
    const jobs = items.filter(i => i.enabled).flatMap(item => tfs.map(tf => ({ item, tf })));
    if (!jobs.length) { setRows({}); setBusy(false); return; }
    setBusy(true); let index = 0;
    await Promise.all(Array.from({ length: Math.min(1, jobs.length) }, async () => {
      while (index < jobs.length && !ac.signal.aborted) {
        const job = jobs[index++]; const key = `${job.item.id}:${job.tf}`;
        try {
          const { data } = await api.pairAnalysis({ symbol: job.item.symbol, timeframe: job.tf, venue: job.item.venue_id, strategy_id: strategy || undefined }, ac.signal);
          if (generation.current === gen && !ac.signal.aborted) setRows(prev => ({ ...prev, [key]: { ...job, data } }));
        } catch (e) {
          if (generation.current === gen && !ac.signal.aborted) setRows(prev => ({ ...prev, [key]: { ...job, error: e instanceof Error ? e.message : String(e) } }));
        }
      }
    }));
    if (generation.current === gen && !ac.signal.aborted) { setBusy(false); setUpdated(Date.now()); }
  }, [items, tfs, strategy]);
  useEffect(() => {
    setRows({}); setUpdated(null);
    let disposed = false; let timer: ReturnType<typeof setTimeout>;
    const repeat = async () => { if (!document.hidden) await scan(); if (!disposed) timer = setTimeout(repeat, 60000); };
    void repeat();
    return () => { disposed = true; clearTimeout(timer); abort.current?.abort(); };
  }, [scan]);
  const create = async () => {
    if (!name.trim() || saving) return; setSaving(true); setError(null);
    try { const { data } = await api.createWatchlist(name.trim()); setLists(p => [...p, data]); setId(data.id); setName(""); setEditing(true); } catch (e) { setError(e); } finally { setSaving(false); }
  };
  const add = async () => {
    if (!id || !symbol.trim() || saving) return; setSaving(true); setError(null);
    try { const { data } = await api.addWatchlistItem(id, { symbol: symbol.trim(), venue_id: venue }); setItems(p => [...p, data]); setSymbol(""); } catch (e) { setError(e); } finally { setSaving(false); }
  };
  const remove = async (item: WatchlistItem) => {
    setError(null); try { await api.removeWatchlistItem(id, item.id); setItems(p => p.filter(i => i.id !== item.id)); } catch (e) { setError(e); }
  };
  const all = Object.values(rows);
  const sfp = (d: PairAnalysis) => d.swing_failures?.some(s => s.timestamp === d.freshness.last_closed_timestamp_ms);
  const edge = (d: PairAnalysis) => d.signal.direction !== "none" && d.is_analysis_safe && !d.freshness.is_stale;
  const shown = all.filter(r => filter === "all" || (r.data && (filter === "edge" ? edge(r.data) : filter === "sfp" ? sfp(r.data) : filter === "range" ? r.data.range.is_tradable : r.data.regime.value.startsWith("trending"))));
  shown.sort((a, b) => Number(!!b.data && edge(b.data)) - Number(!!a.data && edge(a.data)) || a.item.symbol.localeCompare(b.item.symbol) || TIMEFRAMES.indexOf(a.tf as any) - TIMEFRAMES.indexOf(b.tf as any));
  return <div className="workspace">
    <WorkspaceHeader eyebrow="GRANDBLUE TERMINAL" title="A clearer view of the market." description="Your markets. Every timeframe. One place to find the range.">
      <Link className="secondary-button" href="/strategies/new">+ New strategy</Link><Link className="secondary-button" href="/admin">Admin</Link><Link className="secondary-button" href="/alerts">Manage alerts ↗</Link><button className="primary-button" disabled={busy || !items.length} onClick={() => void scan()}>{busy ? "Scanning…" : "Refresh scan"}</button>
    </WorkspaceHeader>
    <ErrorNotice error={error} />
    <div className="stat-grid">
      {[['Markets', items.length, 'In your watchlist'], ['Ranges', all.filter(r => r.data?.range.is_tradable).length, 'Across selected timeframes'], ['Confirmed entries', all.filter(r => r.data && edge(r.data)).length, 'Closed-candle triggers'], ['Swing failures', all.filter(r => r.data && sfp(r.data)).length, 'Latest closed candle']].map(([label, value, note]) => <div className="stat-card" key={label}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>)}
    </div>
    <section className="panel">
      <div className="panel-toolbar"><div className="toolbar-controls"><Field label="Watchlist"><select aria-label="Watchlist" value={id} onChange={e => setId(e.target.value)}><option value="">Choose a watchlist</option>{lists.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}</select></Field><Field label="Strategy / playbook"><select value={strategy} onChange={e => setStrategy(e.target.value)}><option value="">Confirmed range · starting settings</option>{strategies.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field></div><button className="secondary-button" onClick={() => setEditing(!editing)}>{editing ? "Done editing" : "+ Manage watchlist"}</button></div>
      {(editing || (loaded && !lists.length)) && <div className="watchlist-editor"><form onSubmit={e => { e.preventDefault(); void create(); }}><Field label="New watchlist"><input value={name} onChange={e => setName(e.target.value)} placeholder="My perps watchlist" maxLength={80} /></Field><button className="secondary-button" disabled={saving || !name.trim()}>Create</button></form>{id && <><form onSubmit={e => { e.preventDefault(); void add(); }}><Field label="Price source"><select value={venue} onChange={e => { setVenue(e.target.value); setSymbol(""); }}>{SOURCES.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field><Field label="Market"><input list="market-symbols" value={symbol} onChange={e => setSymbol(e.target.value)} placeholder="BTC/USDC:USDC" /><datalist id="market-symbols">{symbols.map(s => <option key={s} value={s} />)}</datalist></Field><button className="primary-button" disabled={saving || !symbol.trim()}>Add market</button></form><p className="muted">Use the exact market symbol from the selected source. Your trading venue can be different.</p><div className="chips">{items.map(i => <button className="chip" key={i.id} onClick={() => void remove(i)} aria-label={`Remove ${i.symbol} from watchlist`}>{i.symbol} · {i.venue_id} ×</button>)}</div></>}</div>}
      <div className="timeframe-toolbar"><span className="muted">Timeframes</span>{TIMEFRAMES.map(tf => <button key={tf} className={`chip ${tfs.includes(tf) ? "selected" : ""}`} aria-pressed={tfs.includes(tf)} onClick={() => setTfs(p => p.includes(tf) ? p.length > 1 ? p.filter(x => x !== tf) : p : [...p, tf])}>{tf}</button>)}<span className="scan-status">{busy ? "Updating market data…" : updated ? `Updated ${new Date(updated).toLocaleTimeString()} · every 60s` : "Ready when you are"}</span></div>
      <div className="filter-tabs">{[["all", "All markets"], ["edge", "At the edge"], ["range", "Ranging"], ["trend", "Trending"], ["sfp", "Swing failures"]].map(([key, label]) => <button key={key} className={filter === key ? "active" : ""} onClick={() => setFilter(key)}>{label}</button>)}</div>
      {!items.length ? <div className="empty-workspace"><div className="range-glyph">↔</div><h2>Your edge starts with a watchlist.</h2><p>Add the markets you follow. We’ll check each selected timeframe for ranges, edge touches, and swing failures.</p><button className="primary-button" onClick={() => setEditing(true)}>Build my watchlist</button></div> : !shown.length ? <div className="empty-workspace"><h2>{busy ? "Reading market structure…" : "No matches in this view"}</h2><p>{busy ? "Results appear as each market is checked." : "Try another filter or timeframe. A quiet scan is a valid result."}</p></div> : <div className="token-groups">{items.filter(item=>shown.some(r=>r.item.id===item.id)).map(item=><section className="token-group" key={item.id}><div className="panel-toolbar"><div className="token-identity"><span className="token-avatar">{item.symbol.split("/")[0].slice(0,2)}</span><div><strong>{item.symbol.split("/")[0]}</strong><small>{item.symbol} · {item.venue_id}</small></div></div></div><div className="token-timeframes">{tfs.map(tf=>{const r=shown.find(r=>r.item.id===item.id&&r.tf===tf);if(!r)return null;const d=r.data;return <Link className="timeframe-card" key={tf} href={`/?symbol=${encodeURIComponent(item.symbol)}&timeframe=${tf}&venue=${item.venue_id}${strategy?`&strategy=${strategy}`:""}`}><strong>{tf} ↗</strong><span className={`status-pill ${d?.range.is_tradable?"range":""}`}>{r.error ? "Provider error" : d?human(d.regime.value):"Loading"}</span><small>{r.error??(d?`${money(d.range.low)} → ${money(d.range.high)}`:"Waiting")}</small>{d&&<small>{edge(d)?`${d.signal.direction} confirmed`:sfp(d)?"Swing failure":"No entry"}</small>}</Link>;})}</div></section>)}</div>}
    </section><div className="workspace-footnote"><span>Extremes are watch alerts. Entries require a closed-candle trigger. Scans refresh between polling cycles.</span><Link href="/strategies/new">Tune the confirmed-range playbook →</Link></div>
  </div>;
}
