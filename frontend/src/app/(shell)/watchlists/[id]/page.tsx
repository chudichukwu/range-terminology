"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorState, LoadingState, EmptyState } from "@/components/state/StatePrimitives";
import { WatchlistScanner } from "@/components/watchlist/WatchlistScanner";
import { api, ApiError } from "@/lib/api/client";
import type { Watchlist, WatchlistItem, Timeframe } from "@/lib/api/types";

export default function WatchlistDetailPage({ params }: { params: { id: string } }) {
  const [watchlist, setWatchlist] = useState<Watchlist | null>(null);
  const [items, setItems] = useState<WatchlistItem[] | null>(null);
  const [error, setError] = useState<{ message: string; requestId: string; code: string } | null>(null);
  const [timeframe, setTimeframe] = useState<Timeframe>("1h");
  const [strategyId, setStrategyId] = useState<string | undefined>(undefined);
  const [strategies, setStrategies] = useState<{ id: string; name: string }[]>([]);
  const [availableTfs, setAvailableTfs] = useState<string[] | undefined>(undefined);

  // dialogs
  const [addOpen, setAddOpen] = useState(false);
  const [addSymbol, setAddSymbol] = useState("BTC/USDT");
  const [addVenue, setAddVenue] = useState("binance");
  const [addNotes, setAddNotes] = useState("");
  const [addErr, setAddErr] = useState<string | null>(null);
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameName, setRenameName] = useState("");
  const [renameErr, setRenameErr] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    api
      .getWatchlist(params.id)
      .then(({ data }) => {
        setWatchlist({ id: data.id, name: data.name, owner_user_id: (data as any).owner_user_id, created_at_ms: data.created_at_ms, updated_at_ms: data.updated_at_ms });
        setItems((data as any).items ?? []);
      })
      .catch((e) => {
        if (e instanceof ApiError) setError({ message: e.message, requestId: e.requestId, code: e.code });
        else setError({ message: String(e), requestId: "", code: "unknown" });
      });
  }, [params.id]);

  useEffect(() => {
    load();
    api.listTimeframes().then(({ data }) => setAvailableTfs(data.timeframes)).catch(() => {});
    api.listStrategies().then(({ data }) => setStrategies(data.map((s) => ({ id: s.id, name: s.name })))).catch(() => {});
  }, [load]);

  useEffect(() => {
    if (watchlist) setRenameName(watchlist.name);
  }, [watchlist]);

  const doRename = async () => {
    setRenameErr(null);
    try {
      const { data } = await api.renameWatchlist(params.id, renameName.trim());
      setWatchlist((prev) => (prev ? { ...prev, name: data.name, updated_at_ms: data.updated_at_ms } : prev));
      setRenameOpen(false);
    } catch (e) {
      if (e instanceof ApiError) setRenameErr(`${e.code}: ${e.message}`);
      else setRenameErr(String(e));
    }
  };

  const doAdd = async () => {
    setAddErr(null);
    try {
      const { data } = await api.addWatchlistItem(params.id, { symbol: addSymbol.trim(), venue_id: addVenue.trim(), notes: addNotes });
      setItems((prev) => (prev ? [...prev, data] : [data]));
      setAddOpen(false);
      setAddSymbol("BTC/USDT");
      setAddNotes("");
    } catch (e) {
      if (e instanceof ApiError) setAddErr(`${e.code}: ${e.message}`);
      else setAddErr(String(e));
    }
  };

  const doRemove = async (itemId: string) => {
    try {
      await api.removeWatchlistItem(params.id, itemId);
      setItems((prev) => prev?.filter((it) => it.id !== itemId) ?? null);
    } catch (e) {
      if (e instanceof ApiError) setError({ message: e.message, requestId: e.requestId, code: e.code });
    }
  };

  if (error) {
    return (
      <>
        <PageHeader title="Watchlist" breadcrumbs={[{ label: "Watchlists", href: "/watchlists" }, { label: params.id }]} description="Could not load watchlist." />
        <ContentContainer>
          <ErrorState message={error.message} requestId={error.requestId} onRetry={load} />
        </ContentContainer>
      </>
    );
  }

  if (!watchlist || !items) {
    return (
      <>
        <PageHeader title="Watchlist" breadcrumbs={[{ label: "Watchlists", href: "/watchlists" }, { label: params.id }]} description="Loading scan set…" />
        <ContentContainer>
          <LoadingState label="Loading watchlist and items" />
        </ContentContainer>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={watchlist.name}
        description={`${items.length} market${items.length !== 1 ? "s" : ""} · scan hierarchy: Symbol → Range Status → Regime → Position/Edge → Signal → Confirmation → Confidence → Freshness. Secondary: Price, Range High/Low, Width, Venue.`}
        breadcrumbs={[{ label: "Watchlists", href: "/watchlists" }, { label: watchlist.name }]}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => setRenameOpen(true)}>
              Rename
            </Button>
            <Button variant="primary" size="sm" onClick={() => setAddOpen(true)}>
              Add market
            </Button>
          </div>
        }
      />
      <ContentContainer>
        <div className="mb-3 flex flex-wrap items-center gap-3 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
          <div className="flex items-center gap-2">
            <Badge variant="purple" icon="◎">
              {watchlist.name}
            </Badge>
            <span className="mono text-[11px] text-[var(--color-text-tertiary)]">{watchlist.id.slice(0, 8)} · updated {new Date(watchlist.updated_at_ms).toLocaleDateString()}</span>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <label htmlFor="strat-scan" className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
              Strategy
            </label>
            <select
              id="strat-scan"
              value={strategyId ?? ""}
              onChange={(e) => setStrategyId(e.target.value || undefined)}
              className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1 text-[12px] text-[var(--color-text-secondary)]"
            >
              <option value="">Default (structural)</option>
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <Link href={`/watchlists`} className="text-[11px] text-[var(--color-purple-accent)] hover:underline">
              All watchlists →
            </Link>
          </div>
        </div>

        {items.length === 0 ? (
          <EmptyState
            title="This watchlist is empty"
            description="Add markets like BTC/USDT, ETH/USDT or SOL/USDT to start scanning. Each market will be analyzed independently via backend truth; no fake data is shown."
            actionLabel="Add market"
            onAction={() => setAddOpen(true)}
          />
        ) : (
          <WatchlistScanner items={items} timeframe={timeframe} setTimeframe={setTimeframe} strategyId={strategyId} availableTimeframes={availableTfs} />
        )}

        {items.length > 0 && (
          <div className="mt-3 rounded-md border border-dashed border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)]/40 px-3 py-2">
            <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Manage markets</div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {items.map((it) => (
                <span key={it.id} className="inline-flex items-center gap-1 rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1 mono text-[11px] text-[var(--color-text-secondary)]">
                  {it.symbol}
                  <button
                    aria-label={`Remove ${it.symbol}`}
                    onClick={() => doRemove(it.id)}
                    className="ml-1 rounded-xs px-1 text-[var(--color-text-tertiary)] hover:bg-[var(--color-bg-surface-1)] hover:text-[var(--color-bear)]"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
            <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">Reorder via sort_order is persisted on creation; drag reorder arrives when backend add_order exposure supports it — no client-side fabrication.</div>
          </div>
        )}

        <Dialog open={addOpen} onClose={() => setAddOpen(false)} title="Add market" description="Symbol must be BASE/QUOTE (e.g. BTC/USDT). Venue is a non-empty identifier per backend.">
          <div className="space-y-3">
            <div>
              <label htmlFor="add-symbol" className="mb-1 block text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                Symbol
              </label>
              <input
                id="add-symbol"
                value={addSymbol}
                onChange={(e) => setAddSymbol(e.target.value)}
                placeholder="BTC/USDT"
                className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2.5 py-1.5 mono text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:border-[var(--color-purple-accent)] focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="add-venue" className="mb-1 block text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                Venue ID
              </label>
              <input
                id="add-venue"
                value={addVenue}
                onChange={(e) => setAddVenue(e.target.value)}
                placeholder="binance"
                className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2.5 py-1.5 mono text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-purple-accent)] focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="add-notes" className="mb-1 block text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                Notes (optional, ≤500)
              </label>
              <input id="add-notes" value={addNotes} onChange={(e) => setAddNotes(e.target.value)} placeholder="quarterly range study" className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2.5 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-purple-accent)] focus:outline-none" />
            </div>
            {addErr && <div className="rounded-sm border border-[rgba(245,158,11,0.18)] bg-[var(--color-danger-bg)] px-2 py-1.5 text-[12px] text-[var(--color-text-secondary)]">{addErr}</div>}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setAddOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={doAdd} disabled={!addSymbol.trim() || !addVenue.trim()}>
                Add
              </Button>
            </div>
          </div>
        </Dialog>

        <Dialog open={renameOpen} onClose={() => setRenameOpen(false)} title="Rename watchlist" description="1–80 characters, per backend.">
          <div className="space-y-3">
            <input
              autoFocus
              value={renameName}
              onChange={(e) => setRenameName(e.target.value)}
              className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2.5 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-purple-accent)] focus:outline-none"
            />
            {renameErr && <div className="rounded-sm border border-[rgba(245,158,11,0.18)] bg-[var(--color-danger-bg)] px-2 py-1.5 text-[12px] text-[var(--color-text-secondary)]">{renameErr}</div>}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setRenameOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={doRename} disabled={!renameName.trim()}>
                Rename
              </Button>
            </div>
          </div>
        </Dialog>
      </ContentContainer>
    </>
  );
}
