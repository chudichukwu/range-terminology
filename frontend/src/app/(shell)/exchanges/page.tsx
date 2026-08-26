"use client";

import { useEffect, useState } from "react";
import { PageHeader, ContentContainer, Card } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorState, LoadingState, EmptyState, PermissionDeniedState } from "@/components/state/StatePrimitives";
import { api, ApiError } from "@/lib/api/client";
import type { ExchangeConnection } from "@/lib/api/types";

type Health = { market_data_provider: string } | null;

export default function ExchangesPage() {
  const [connections, setConnections] = useState<ExchangeConnection[] | null>(null);
  const [health, setHealth] = useState<Health>(null);
  const [error, setError] = useState<{ message: string; requestId: string; code: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  // form state
  const [venueId, setVenueId] = useState("binance");
  const [displayName, setDisplayName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [secret, setSecret] = useState("");
  const [password, setPassword] = useState("");
  const [sandbox, setSandbox] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<{ message: string; requestId: string } | null>(null);

  const [deleteId, setDeleteId] = useState<string | null>(null);

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [connRes] = await Promise.all([
        api.listExchangeConnections(),
      ]);
      setConnections(connRes.data);
    } catch (e) {
      if (e instanceof ApiError) setError({ message: e.message, requestId: e.requestId, code: e.code });
      else setError({ message: String(e), requestId: "", code: "unknown" });
    } finally {
      setLoading(false);
    }
    // health is best-effort (owner-only)
    try {
      const { data } = await api.getSystemHealth();
      setHealth({ market_data_provider: data.market_data_provider });
    } catch {
      // try timeframes as fallback for non-owners
      try {
        const { data } = await api.listTimeframes();
        setHealth({ market_data_provider: data.timeframes.length > 0 ? "configured" : "unconfigured" });
      } catch {
        setHealth(null);
      }
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const onCreate = async () => {
    setFormError(null);
    if (!venueId.trim() || !displayName.trim() || !apiKey.trim() || !secret.trim()) {
      setFormError({ message: "validation_error: venue, display name, api key and secret are required", requestId: "" });
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await api.createExchangeConnection({
        venue_id: venueId.trim().toLowerCase(),
        display_name: displayName.trim(),
        api_key: apiKey,
        secret: secret,
        password: password.trim() || undefined,
        sandbox,
      });
      setConnections((prev) => (prev ? [...prev, data] : [data]));
      setCreateOpen(false);
      setVenueId("binance");
      setDisplayName("");
      setApiKey("");
      setSecret("");
      setPassword("");
      setSandbox(false);
    } catch (e) {
      if (e instanceof ApiError) setFormError({ message: `${e.code}: ${e.message}`, requestId: e.requestId });
      else setFormError({ message: String(e), requestId: "" });
    } finally {
      setSubmitting(false);
    }
  };

  const onDelete = async () => {
    if (!deleteId) return;
    try {
      await api.deleteExchangeConnection(deleteId);
      setConnections((prev) => prev?.filter((c) => c.id !== deleteId) ?? null);
      setDeleteId(null);
      if (detailId === deleteId) setDetailId(null);
    } catch (e) {
      if (e instanceof ApiError) setError({ message: `${e.code}: ${e.message}`, requestId: e.requestId, code: e.code });
    }
  };

  const isForbidden = error?.code === "forbidden";
  const isUnauth = error?.code === "unauthenticated";

  return (
    <>
      <PageHeader
        title="Exchanges"
        description="Exchange connectivity is observable but execution remains PAPER / READ-ONLY. Connection, market-data, account and execution are distinct capabilities."
        breadcrumbs={[{ label: "Exchanges" }]}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant="danger">PAPER · READ-ONLY</Badge>
            <Button variant="primary" onClick={() => setCreateOpen(true)}>
              Add connection
            </Button>
          </div>
        }
      />
      <ContentContainer>
        {/* Capability matrix + health summary */}
        <div className="grid gap-3 lg:grid-cols-[1fr_360px]">
          <Card className="p-3">
            <h2 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Capability matrix</h2>
            <div className="mt-2 grid gap-2 text-[12px] md:grid-cols-4">
              <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2">
                <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-primary)]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-purple-accent)]" aria-hidden /> Connection
                </div>
                <div className="mt-1 mono text-[11px] leading-relaxed text-[var(--color-text-secondary)]">Can the terminal establish the exchange connection? From <span className="mono text-[var(--color-text-primary)]">/exchanges/connections</span>.</div>
              </div>
              <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2">
                <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-primary)]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-success)]" aria-hidden /> Market Data
                </div>
                <div className="mt-1 mono text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                  Can market data be obtained? From <span className="mono text-[var(--color-text-primary)]">/markets/timeframes</span> / health: <span className={health?.market_data_provider === "configured" ? "text-[var(--color-success)]" : "text-[var(--color-text-tertiary)]"}>{health?.market_data_provider ?? "—"}</span>
                </div>
              </div>
              <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2">
                <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-primary)]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-warning)]" aria-hidden /> Account
                </div>
                <div className="mt-1 mono text-[11px] leading-relaxed text-[var(--color-text-secondary)]">Can account information be observed? No dedicated account endpoint is exposed in the current backend — shows as unavailable.</div>
              </div>
              <div className="rounded-sm border border-amber-500/20 bg-[var(--color-danger-bg)] p-2">
                <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-[var(--color-danger)]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-danger)]" aria-hidden /> Execution
                </div>
                <div className="mt-1 mono text-[11px] leading-relaxed text-[var(--color-text-secondary)]">Can orders be submitted? <span className="font-medium text-[var(--color-danger)]">PAPER / READ-ONLY</span> — live submission not enabled. No order CTA.</div>
              </div>
            </div>
            <div className="mt-2 mono text-[11px] text-[var(--color-text-tertiary)]">
              A successful connection does <span className="font-medium text-[var(--color-text-secondary)]">not</span> imply market-data, account or execution are available. Capabilities are independent.
            </div>
          </Card>

          <Card className="p-3">
            <h2 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Health summary</h2>
            {loading ? (
              <div className="mt-2 h-4 w-32 animate-pulse rounded-sm bg-[var(--color-bg-surface-2)]" />
            ) : connections ? (
              <div className="mt-2 space-y-1.5 mono text-[12px] text-[var(--color-text-secondary)]">
                <div>
                  Configured connections: <span className="font-medium text-[var(--color-text-primary)]">{connections.length}</span>
                </div>
                <div>
                  Market-data provider: <span className={health?.market_data_provider === "configured" ? "text-[var(--color-success)] font-medium" : "text-[var(--color-text-tertiary)]"}>{health?.market_data_provider ?? "—"}</span>
                </div>
                <div>
                  Execution: <span className="font-medium text-[var(--color-danger)]">PAPER / READ-ONLY</span>
                </div>
                <div className="text-[11px] text-[var(--color-text-tertiary)]">Counts are from actual backend state; not fabricated.</div>
              </div>
            ) : (
              <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">Health unavailable — see error below.</div>
            )}
            <div className="mt-3 rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 mono text-[11px] text-[var(--color-text-tertiary)]">
              Credential presence is shown as <span className="text-[var(--color-text-secondary)]">configured</span>; secrets are write-only and never displayed.
            </div>
          </Card>
        </div>

        {/* Main list */}
        <div className="mt-4">
          {loading ? (
            <LoadingState label="Loading exchange connections" />
          ) : error && (isForbidden || isUnauth) ? (
            <PermissionDeniedState />
          ) : error ? (
            <ErrorState message={error.message} requestId={error.requestId} onRetry={fetchAll} />
          ) : !connections || connections.length === 0 ? (
            <EmptyState
              title="No exchange connections configured"
              description="No exchange connection has been configured for this workspace. Add a CEX connection (API key / secret) to make connectivity observable. No venues are fabricated — Binance, Coinbase, etc. only appear after you add them."
              actionLabel="Add connection"
              onAction={() => setCreateOpen(true)}
            />
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden overflow-hidden rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] md:block">
                <div className="overflow-x-auto">
                  <table className="w-full text-left" role="table">
                    <thead className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]">
                      <tr className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                        <th scope="col" className="px-3 py-2 font-medium">
                          Exchange / Venue
                        </th>
                        <th scope="col" className="px-3 py-2 font-medium">
                          Connection
                        </th>
                        <th scope="col" className="px-3 py-2 font-medium">
                          Market Data
                        </th>
                        <th scope="col" className="px-3 py-2 font-medium">
                          Account
                        </th>
                        <th scope="col" className="px-3 py-2 font-medium">
                          Execution
                        </th>
                        <th scope="col" className="px-3 py-2 font-medium">
                          Environment
                        </th>
                        <th scope="col" className="px-3 py-2 font-medium">
                          Updated
                        </th>
                        <th scope="col" className="px-3 py-2 font-medium">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {connections.map((c) => {
                        const isDetail = detailId === c.id;
                        return (
                          <>
                            <tr key={c.id} className={`border-b border-[var(--color-border-subtle)] last:border-0 hover:bg-[var(--color-bg-surface-2)] ${isDetail ? "bg-[var(--color-bg-surface-2)]" : ""}`}>
                              <td className="px-3 py-2">
                                <div className="text-[13px] font-medium text-[var(--color-text-primary)]">{c.display_name}</div>
                                <div className="mono text-[11px] text-[var(--color-text-tertiary)]">{c.venue_id} · <span className="mono">{c.id.slice(0, 8)}</span></div>
                              </td>
                              <td className="px-3 py-2">
                                <Badge variant={c.status === "registered" ? "success" : "neutral"} icon={c.status === "registered" ? "●" : "○"}>
                                  {c.status}
                                </Badge>
                                <div className="mono mt-0.5 text-[10px] text-[var(--color-text-tertiary)]">configured</div>
                              </td>
                              <td className="px-3 py-2">
                                <Badge variant={health?.market_data_provider === "configured" ? "success" : "neutral"} icon={health?.market_data_provider === "configured" ? "●" : "○"}>
                                  {health?.market_data_provider === "configured" ? "available" : health?.market_data_provider === "unconfigured" ? "unconfigured" : "—"}
                                </Badge>
                                <div className="mono mt-0.5 text-[10px] text-[var(--color-text-tertiary)]">from provider</div>
                              </td>
                              <td className="px-3 py-2">
                                <Badge variant="neutral" icon="○">
                                  unavailable
                                </Badge>
                                <div className="mono mt-0.5 text-[10px] text-[var(--color-text-tertiary)]">no account endpoint</div>
                              </td>
                              <td className="px-3 py-2">
                                <Badge variant="danger" icon="◐">
                                  PAPER
                                </Badge>
                                <div className="mono mt-0.5 text-[10px] text-[var(--color-text-tertiary)]">read-only</div>
                              </td>
                              <td className="px-3 py-2">
                                <Badge variant={c.sandbox ? "info" : "neutral"}>{c.sandbox ? "sandbox" : "live"}</Badge>
                              </td>
                              <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-secondary)]">{new Date(c.updated_at_ms).toLocaleDateString()}</td>
                              <td className="px-3 py-2">
                                <div className="flex gap-1">
                                  <Button variant="secondary" size="sm" onClick={() => setDetailId(isDetail ? null : c.id)}>
                                    {isDetail ? "Hide" : "Detail"}
                                  </Button>
                                  <Button variant="ghost" size="sm" onClick={() => setDeleteId(c.id)}>
                                    Remove
                                  </Button>
                                </div>
                              </td>
                            </tr>
                            {isDetail && (
                              <tr key={`${c.id}-detail`} className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]/50">
                                <td colSpan={8} className="px-3 py-3">
                                  <div className="grid gap-3 text-[12px] md:grid-cols-3">
                                    <div className="space-y-1">
                                      <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Identity</div>
                                      <div className="mono text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                                        <div>id: {c.id}</div>
                                        <div>venue: {c.venue_id}</div>
                                        <div>display: {c.display_name}</div>
                                        <div>status: {c.status}</div>
                                      </div>
                                    </div>
                                    <div className="space-y-1">
                                      <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Configuration</div>
                                      <div className="mono text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                                        <div>credentials: <span className="text-[var(--color-success)]">configured</span> (write-only)</div>
                                        <div>environment: {c.sandbox ? "sandbox" : "live"}</div>
                                        <div>created: {new Date(c.created_at_ms).toLocaleString()}</div>
                                        <div>updated: {new Date(c.updated_at_ms).toLocaleString()}</div>
                                      </div>
                                    </div>
                                    <div className="space-y-1">
                                      <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Diagnostics</div>
                                      <div className="mono text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                                        <div>verification: <span className="text-[var(--color-text-tertiary)]">unavailable — no backend verification endpoint</span></div>
                                        <div>last checked: <span className="text-[var(--color-text-tertiary)]">—</span></div>
                                        <div>account: <span className="text-[var(--color-text-tertiary)]">unavailable — no account endpoint</span></div>
                                      </div>
                                    </div>
                                  </div>
                                  <div className="mt-2 mono text-[11px] text-[var(--color-text-tertiary)]">
                                    Secrets are never displayed, logged, or placed in URLs. Credential presence is shown as <span className="text-[var(--color-text-secondary)]">configured</span>; values remain in the backend <span className="mono">CredentialStore</span>.
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
              </div>

              {/* Mobile cards */}
              <div className="grid gap-2 md:hidden">
                {connections.map((c) => (
                  <div key={c.id} className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-[13px] font-semibold text-[var(--color-text-primary)]">{c.display_name}</div>
                        <div className="mono text-[11px] text-[var(--color-text-tertiary)]">{c.venue_id} · {c.id.slice(0, 8)}</div>
                      </div>
                      <Badge variant="danger">PAPER</Badge>
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-2">
                      <div>
                        <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Connection</div>
                        <Badge variant={c.status === "registered" ? "success" : "neutral"} icon={c.status === "registered" ? "●" : "○"}>
                          {c.status}
                        </Badge>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Market Data</div>
                        <Badge variant={health?.market_data_provider === "configured" ? "success" : "neutral"}>{health?.market_data_provider ?? "—"}</Badge>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Account</div>
                        <Badge variant="neutral">unavailable</Badge>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Env</div>
                        <Badge variant={c.sandbox ? "info" : "neutral"}>{c.sandbox ? "sandbox" : "live"}</Badge>
                      </div>
                    </div>
                    <div className="mt-3 flex gap-2">
                      <Button variant="secondary" size="sm" className="flex-1" onClick={() => setDetailId(detailId === c.id ? null : c.id)}>
                        {detailId === c.id ? "Hide" : "Detail"}
                      </Button>
                      <Button variant="ghost" size="sm" className="flex-1" onClick={() => setDeleteId(c.id)}>
                        Remove
                      </Button>
                    </div>
                    {detailId === c.id && (
                      <div className="mt-3 rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-2 mono text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                        <div>id: {c.id}</div>
                        <div>credentials: <span className="text-[var(--color-success)]">configured</span> (never displayed)</div>
                        <div>verification: unavailable (no backend endpoint)</div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Read-only boundary */}
        <div className="mt-4 rounded-md border border-amber-500/20 bg-[var(--color-danger-bg)] p-3">
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-danger)]" aria-hidden />
            <span className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-danger)]">Execution — PAPER / READ-ONLY</span>
          </div>
          <div className="mono mt-1 text-[12px] leading-relaxed text-[var(--color-text-secondary)]">
            Execution is currently <span className="font-medium text-[var(--color-danger)]">PAPER / READ-ONLY</span>. Live order submission, cancellation, position closing, withdrawals, deposits, wallet signing and DEX connectivity are not enabled. Connecting an exchange does not enable trading; it makes connectivity observable. No order forms are shown because no live execution capability exists.
          </div>
        </div>

        {/* Add dialog */}
        <Dialog
          open={createOpen}
          onClose={() => {
            if (!submitting) setCreateOpen(false);
          }}
          title="Add exchange connection"
          description="CEX API-key flow (write-only). Secrets are stored via backend CredentialStore and never returned. PAPER remains enforced."
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              onCreate();
            }}
            className="space-y-3"
          >
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Venue ID *</span>
                <input
                  value={venueId}
                  onChange={(e) => setVenueId(e.target.value)}
                  placeholder="binance"
                  autoComplete="off"
                  className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2.5 py-1.5 text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:border-[var(--color-purple-accent)] focus:outline-none"
                  required
                />
                <span className="mono mt-0.5 block text-[10px] text-[var(--color-text-tertiary)]">2–30, e.g. binance, kraken</span>
              </label>
              <label className="block">
                <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Display name *</span>
                <input
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Binance Main"
                  className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2.5 py-1.5 text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:border-[var(--color-purple-accent)] focus:outline-none"
                  required
                />
                <span className="mono mt-0.5 block text-[10px] text-[var(--color-text-tertiary)]">1–60 characters</span>
              </label>
            </div>
            <label className="block">
              <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">API key *</span>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                autoComplete="new-password"
                className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2.5 py-1.5 text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:border-[var(--color-purple-accent)] focus:outline-none"
                required
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Secret *</span>
              <input
                type="password"
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                autoComplete="new-password"
                className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2.5 py-1.5 text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:border-[var(--color-purple-accent)] focus:outline-none"
                required
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Password / passphrase (optional)</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2.5 py-1.5 text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:border-[var(--color-purple-accent)] focus:outline-none"
              />
            </label>
            <label className="flex items-center gap-2 text-[12px] text-[var(--color-text-secondary)]">
              <input type="checkbox" checked={sandbox} onChange={(e) => setSandbox(e.target.checked)} className="rounded-sm" />
              Sandbox / testnet
            </label>
            {formError && <div className="rounded-sm border border-amber-500/20 bg-[var(--color-danger-bg)] px-2.5 py-2 text-[12px] text-[var(--color-danger)]">{formError.message} {formError.requestId && <span className="mono text-[11px] text-[var(--color-text-tertiary)]">id {formError.requestId.slice(0, 8)}</span>}</div>}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setCreateOpen(false)} disabled={submitting}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" disabled={submitting}>
                {submitting ? "Adding…" : "Add connection"}
              </Button>
            </div>
            <div className="mono text-[11px] text-[var(--color-text-tertiary)]">Credentials are sent directly to <span className="text-[var(--color-text-secondary)]">POST /exchanges/connections</span> (SecretStr) and stored server-side; they are never in URLs, localStorage, or error messages.</div>
          </form>
        </Dialog>

        <Dialog
          open={!!deleteId}
          onClose={() => setDeleteId(null)}
          title="Remove connection?"
          description="This will delete the exchange connection and its stored credential reference. This cannot be undone."
        >
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setDeleteId(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={onDelete}>
              Remove
            </Button>
          </div>
        </Dialog>
      </ContentContainer>
    </>
  );
}
