"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import type { Watchlist, WatchlistItem } from "@/lib/api/types";
import { ErrorNotice, Field, SOURCES, WorkspaceHeader } from "./shared";

export function WatchlistManager({ initialId }: { initialId?: string }) {
  const [lists, setLists] = useState<Watchlist[]>([]), [id, setId] = useState(initialId ?? "");
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [name, setName] = useState(""), [rename, setRename] = useState("");
  const [symbol, setSymbol] = useState(""), [venue, setVenue] = useState("hyperliquid"), [notes, setNotes] = useState("");
  const [symbols, setSymbols] = useState<string[]>([]), [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true), [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null), [lookupError, setLookupError] = useState(false);
  const [status, setStatus] = useState("");
  useEffect(() => {
    const ac = new AbortController();
    api.listWatchlists(ac.signal).then(({ data }) => {
      if (ac.signal.aborted) return;
      setLists(data); setId(initialId && data.some(w => w.id === initialId) ? initialId : data[0]?.id ?? "");
      if (!data.length) setLoading(false);
    }).catch(e => { if (!ac.signal.aborted) { setError(e); setLoading(false); } });
    return () => ac.abort();
  }, [initialId]);
  useEffect(() => {
    const ac = new AbortController(); setItems([]); setStatus("");
    if (id) {
      setLoading(true); setError(null);
      api.getWatchlist(id, ac.signal).then(({ data }) => { if (!ac.signal.aborted) { setItems(data.items); setRename(data.name); } })
        .catch(e => { if (!ac.signal.aborted) setError(e); }).finally(() => { if (!ac.signal.aborted) setLoading(false); });
    }
    return () => ac.abort();
  }, [id]);
  useEffect(() => {
    const ac = new AbortController(); setSymbols([]); setLookupError(false);
    if (!symbol.trim()) return () => ac.abort();
    const timer = setTimeout(() => api.get<string[]>(`/markets/symbols?venue=${venue}&q=${encodeURIComponent(symbol)}`, ac.signal)
      .then(({ data }) => { if (!ac.signal.aborted) setSymbols(data); }).catch(() => { if (!ac.signal.aborted) setLookupError(true); }), 350);
    return () => { clearTimeout(timer); ac.abort(); };
  }, [venue, symbol]);
  const create = async () => {
    if (!name.trim() || saving) return;
    setSaving(true); setError(null);
    try { const { data } = await api.createWatchlist(name.trim()); setLists(p => [...p, data]); setId(data.id); setName(""); }
    catch (e) { setError(e); } finally { setSaving(false); }
  };
  const add = async () => {
    if (!id || !symbol.trim() || saving) return;
    setSaving(true); setError(null); setStatus("");
    try { const { data } = await api.addWatchlistItem(id, { symbol: symbol.trim(), venue_id: venue, notes: notes.trim() }); setItems(p => [...p, data]); setSymbol(""); setNotes(""); setStatus(`${data.symbol} added to your watchlist.`); }
    catch (e) { setError(e); } finally { setSaving(false); }
  };
  const remove = async (item: WatchlistItem) => {
    setSaving(true); setError(null);
    try { await api.removeWatchlistItem(id, item.id); setItems(p => p.filter(i => i.id !== item.id)); setStatus(`${item.symbol} removed from this list.`); }
    catch (e) { setError(e); } finally { setSaving(false); }
  };
  const saveName = async () => {
    if (!rename.trim() || saving) return;
    setSaving(true); setError(null);
    try { const { data } = await api.renameWatchlist(id, rename.trim()); setLists(p => p.map(w => w.id === id ? data : w)); setStatus("Watchlist renamed."); }
    catch (e) { setError(e); } finally { setSaving(false); }
  };
  const shown = items.filter(i => `${i.symbol} ${i.venue_id} ${i.notes}`.toLowerCase().includes(search.toLowerCase()));
  return <div className="workspace collection-workspace">
    <WorkspaceHeader eyebrow="YOUR MARKET UNIVERSE" title="Watchlists" description="Curate the markets you follow. Let the scanner find the setups.">
      <Link className="secondary-button" href="/alerts">Alert settings ↗</Link>{id && <Link className="primary-button" href={`/?watchlist=${encodeURIComponent(id)}`}>Scan this list ↗</Link>}
    </WorkspaceHeader><ErrorNotice error={error} /><p className="muted" role="status">{status}</p>
    <div className="collection-layout"><aside className="panel collection-sidebar"><p className="eyebrow">COLLECTIONS · {lists.length}</p><nav aria-label="Your watchlists">{lists.map(w => <button disabled={saving} aria-pressed={w.id === id} key={w.id} className={`collection-choice ${w.id === id ? "selected" : ""}`} onClick={() => setId(w.id)}><span>▤</span>{w.name}<span>↗</span></button>)}</nav><form onSubmit={e => { e.preventDefault(); void create(); }}><Field label="New watchlist"><input required maxLength={80} value={name} onChange={e => setName(e.target.value)} placeholder="Majors, swing ideas…" /></Field><button className="secondary-button" disabled={saving || !name.trim()}>+ Create list</button></form><p className="muted">Group markets by the way you trade. No scans run on this page.</p></aside>
      <section className="panel collection-main"><div className="panel-toolbar"><div><p className="eyebrow">{items.length} MARKETS</p><h2>{lists.find(w => w.id === id)?.name ?? "Your first watchlist"}</h2></div>{id && <details className="rename-list"><summary>Rename</summary><form onSubmit={e => { e.preventDefault(); void saveName(); }}><Field label="List name"><input value={rename} maxLength={80} required onChange={e => setRename(e.target.value)} /></Field><button className="secondary-button" disabled={saving || !rename.trim()}>Save name</button></form></details>}</div>
      {id && <><form className="collection-add" onSubmit={e => { e.preventDefault(); void add(); }}><Field label="Data source"><select value={venue} onChange={e => { setVenue(e.target.value); setSymbol(""); }}>{SOURCES.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field><Field label="Exact market"><input required list="watchlist-symbols" value={symbol} onChange={e => setSymbol(e.target.value)} placeholder="Search BTC, NEAR, SUI…" /><datalist id="watchlist-symbols">{symbols.map(s => <option key={s} value={s} />)}</datalist></Field><Field label="Why follow it? (optional)"><input value={notes} onChange={e => setNotes(e.target.value)} placeholder="Watching the daily range low" maxLength={1000} /></Field><button className="primary-button" disabled={saving || loading || !symbol.trim()}>Add market</button></form><p className="collection-hint muted">{lookupError ? "Symbol search is unavailable. Enter an exact market symbol or try again shortly." : "Choose the exact market for your source. Perpetuals may include :USDC or :USDT."}</p><div className="collection-search"><Field label="Filter this list"><input type="search" placeholder="Find a market or note" value={search} onChange={e => setSearch(e.target.value)} /></Field></div></>}
      {loading ? <div className="empty-workspace" role="status">Loading your markets…</div> : !shown.length ? <div className="empty-workspace"><div className="range-glyph">▤</div><h2>{search ? "No matching markets" : "Make room for your next idea."}</h2><p>{id ? "Add an exact market above to start following it." : "Create a named watchlist to get started."}</p></div> : <div className="collection-rows">{shown.map(item => <article className="collection-row" key={item.id}><div className="token-identity"><span className="token-avatar">{item.symbol.split("/")[0].slice(0, 2)}</span><div><strong>{item.symbol}</strong><small>{item.venue_id} · {item.enabled ? "Included in scans" : "Paused"}</small></div></div><p>{item.notes || "No note yet"}</p><div className="heading-actions"><Link className="secondary-button" href={`/?${new URLSearchParams({ symbol: item.symbol, venue: item.venue_id, timeframe: "4h", watchlist: id })}`}>Chart ↗</Link><button className="remove-market" disabled={saving} onClick={() => void remove(item)} aria-label={`Remove ${item.symbol} from watchlist`}>Remove</button></div></article>)}</div>}
      </section></div>
  </div>;
}
