"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorState, EmptyState, LoadingState } from "@/components/state/StatePrimitives";
import { api, ApiError } from "@/lib/api/client";
import type { Watchlist } from "@/lib/api/types";

export default function WatchlistsPage() {
  const [watchlists, setWatchlists] = useState<Watchlist[] | null>(null);
  const [error, setError] = useState<{ message: string; requestId: string; code: string } | null>(null);
  const [filter, setFilter] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [createErr, setCreateErr] = useState<string | null>(null);
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameName, setRenameName] = useState("");
  const [renameErr, setRenameErr] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const load = () => {
    setError(null);
    api
      .listWatchlists()
      .then(({ data }) => setWatchlists(data))
      .catch((e) => {
        if (e instanceof ApiError) setError({ message: e.message, requestId: e.requestId, code: e.code });
        else setError({ message: String(e), requestId: "", code: "unknown" });
      });
  };

  useEffect(() => {
    load();
  }, []);

  const filtered = watchlists ? watchlists.filter((w) => w.name.toLowerCase().includes(filter.toLowerCase())) : null;

  const doCreate = async () => {
    setCreateErr(null);
    try {
      const { data } = await api.createWatchlist(newName.trim());
      setWatchlists((prev) => (prev ? [...prev, data] : [data]));
      setCreateOpen(false);
      setNewName("");
    } catch (e: unknown) {
      if (e instanceof ApiError) setCreateErr(`${e.code}: ${e.message}`);
      else setCreateErr(String(e));
    }
  };

  const doRename = async () => {
    if (!renameId) return;
    setRenameErr(null);
    try {
      const { data } = await api.renameWatchlist(renameId, renameName.trim());
      setWatchlists((prev) => prev?.map((w) => (w.id === renameId ? data : w)) ?? null);
      setRenameId(null);
    } catch (e: unknown) {
      if (e instanceof ApiError) setRenameErr(`${e.code}: ${e.message}`);
      else setRenameErr(String(e));
    }
  };

  const doDelete = async () => {
    if (!deleteId) return;
    try {
      await api.deleteWatchlist(deleteId);
      setWatchlists((prev) => prev?.filter((w) => w.id !== deleteId) ?? null);
      setDeleteId(null);
    } catch (e: unknown) {
      if (e instanceof ApiError) setError({ message: e.message, requestId: e.requestId, code: e.code });
    }
  };

  return (
    <>
      <PageHeader
        title="Watchlists"
        description="Create, rename and open watchlists. Each watchlist is a research set for scanning range-trading markets."
        breadcrumbs={[{ label: "Watchlists" }]}
        actions={
          <Button variant="primary" onClick={() => setCreateOpen(true)}>
            New watchlist
          </Button>
        }
      />
      <ContentContainer>
        <div className="mb-3 flex items-center gap-2">
          <input
            placeholder="Search watchlists…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full max-w-[320px] rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-2.5 py-1.5 text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:border-[var(--color-purple-accent)] focus:outline-none"
            aria-label="Search watchlists"
          />
          <span className="mono hidden text-[11px] text-[var(--color-text-tertiary)] md:inline">{watchlists ? `${filtered?.length} of ${watchlists.length}` : ""}</span>
        </div>

        {!watchlists ? error ? <ErrorState message={error.message} requestId={error.requestId} onRetry={load} /> : <LoadingState label="Loading watchlists" /> : watchlists.length === 0 ? (
          <EmptyState title="No watchlists yet" description="Create your first watchlist to start scanning markets. Each watchlist holds symbols you want to observe for range structure and regime." actionLabel="New watchlist" onAction={() => setCreateOpen(true)} />
        ) : filtered && filtered.length === 0 ? (
          <EmptyState title="No matches" description={`No watchlists match “${filter}”.`} />
        ) : (
          <div className="overflow-hidden rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)]">
            <table className="w-full text-left" role="table">
              <thead className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]">
                <tr className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                  <th className="px-3 py-2 font-medium">Name</th>
                  <th className="px-3 py-2 font-medium">Updated</th>
                  <th className="px-3 py-2 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered!.map((w) => (
                  <tr key={w.id} className="border-b border-[var(--color-border-subtle)] last:border-0 hover:bg-[var(--color-bg-surface-2)]">
                    <td className="px-3 py-2.5">
                      <Link href={`/watchlists/${w.id}`} className="text-[13px] font-medium text-[var(--color-text-primary)] hover:text-[var(--color-purple-accent)] hover:underline">
                        {w.name}
                      </Link>
                      <div className="mono text-[11px] text-[var(--color-text-tertiary)]">{w.id.slice(0, 8)}</div>
                    </td>
                    <td className="mono px-3 py-2.5 text-[12px] text-[var(--color-text-secondary)]">{new Date(w.updated_at_ms).toLocaleDateString()}</td>
                    <td className="px-3 py-2.5">
                      <div className="flex gap-1">
                        <Link href={`/watchlists/${w.id}`}>
                          <Button variant="secondary" size="sm">
                            Open
                          </Button>
                        </Link>
                        <Button variant="ghost" size="sm" onClick={() => { setRenameId(w.id); setRenameName(w.name); setRenameErr(null); }}>
                          Rename
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setDeleteId(w.id)}>
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-3 mono text-[11px] text-[var(--color-text-tertiary)]">Owner isolation via backend authorization — you only see your watchlists (OWNER sees scope per backend).</div>

        {/* Create dialog */}
        <Dialog open={createOpen} onClose={() => setCreateOpen(false)} title="New watchlist" description="Name must be 1–80 characters per backend.">
          <div className="space-y-3">
            <input
              autoFocus
              placeholder="Majors"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2.5 py-1.5 text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:border-[var(--color-purple-accent)] focus:outline-none"
              aria-label="Watchlist name"
            />
            {createErr && <div className="rounded-sm border border-[rgba(245,158,11,0.18)] bg-[var(--color-danger-bg)] px-2 py-1.5 text-[12px] text-[var(--color-text-secondary)]">{createErr}</div>}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
              <Button variant="primary" onClick={doCreate} disabled={!newName.trim()}>
                Create
              </Button>
            </div>
          </div>
        </Dialog>

        {/* Rename dialog */}
        <Dialog open={!!renameId} onClose={() => setRenameId(null)} title="Rename watchlist" description="New name 1–80 characters.">
          <div className="space-y-3">
            <input
              value={renameName}
              onChange={(e) => setRenameName(e.target.value)}
              className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2.5 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-purple-accent)] focus:outline-none"
              aria-label="New watchlist name"
            />
            {renameErr && <div className="rounded-sm border border-[rgba(245,158,11,0.18)] bg-[var(--color-danger-bg)] px-2 py-1.5 text-[12px] text-[var(--color-text-secondary)]">{renameErr}</div>}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setRenameId(null)}>Cancel</Button>
              <Button variant="primary" onClick={doRename} disabled={!renameName.trim()}>
                Rename
              </Button>
            </div>
          </div>
        </Dialog>

        {/* Delete confirm */}
        <Dialog open={!!deleteId} onClose={() => setDeleteId(null)} title="Delete watchlist?" description="This removes the watchlist and its items. This cannot be undone.">
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setDeleteId(null)}>Cancel</Button>
            <Button variant="danger" onClick={doDelete}>
              Delete
            </Button>
          </div>
        </Dialog>
      </ContentContainer>
    </>
  );
}
