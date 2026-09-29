"use client";

import { useEffect, useMemo, useState } from "react";
import { PageHeader, ContentContainer, Card } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { LoadingState, ErrorState, PermissionDeniedState, EmptyState } from "@/components/state/StatePrimitives";
import { api, ApiError } from "@/lib/api/client";
import type { AdminUser } from "@/lib/api/types";

type SortKey = "email" | "role" | "active" | "created_at_ms";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [error, setError] = useState<{ message: string; requestId: string; code: string } | null>(null);
  const [filter, setFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("email");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  useEffect(() => {
    api
      .listAdminUsers()
      .then(({ data }) => setUsers(data))
      .catch((e) => {
        if (e instanceof ApiError) setError({ message: e.message, requestId: e.requestId, code: e.code });
        else setError({ message: String(e), requestId: "", code: "unknown" });
      });
  }, []);

  const filtered = useMemo(() => {
    if (!users) return null;
    let list = users;
    if (filter.trim()) {
      const q = filter.toLowerCase();
      list = list.filter((u) => u.email.toLowerCase().includes(q) || u.role.toLowerCase().includes(q) || u.id.toLowerCase().includes(q));
    }
    const dir = sortDir === "asc" ? 1 : -1;
    return [...list].sort((a, b) => {
      if (sortKey === "email") return dir * a.email.localeCompare(b.email);
      if (sortKey === "role") return dir * a.role.localeCompare(b.role);
      if (sortKey === "active") return dir * (Number(a.active) - Number(b.active));
      return dir * (a.created_at_ms - b.created_at_ms);
    });
  }, [users, filter, sortKey, sortDir]);

  const toggle = (k: SortKey) => {
    if (k === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(k);
      setSortDir("asc");
    }
  };

  if (error && (error.code === "forbidden" || error.code === "unauthenticated")) {
    return (
      <>
        <PageHeader title="Users" breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Users" }]} description="User directory — OWNER only." />
        <ContentContainer>
          <PermissionDeniedState />
          <div className="mt-3 mono text-[11px] text-[var(--color-text-tertiary)]">Request ID: {error.requestId || "—"} · Code: {error.code}</div>
        </ContentContainer>
      </>
    );
  }

  if (error) {
    return (
      <>
        <PageHeader title="Users" breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Users" }]} description="User directory — OWNER only." />
        <ContentContainer>
          <ErrorState message={error.message} requestId={error.requestId} />
        </ContentContainer>
      </>
    );
  }

  if (!users) {
    return (
      <>
        <PageHeader title="Users" breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Users" }]} description="User directory — OWNER only." />
        <ContentContainer>
          <LoadingState label="Loading users" />
        </ContentContainer>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Users"
        description="Read-only directory of backend-provided users. Only fields actually returned are shown; no password, permission mutation, or impersonation."
        breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Users" }]}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant="neutral">{users.length} users</Badge>
            <Badge variant={users.some((u) => u.role === "owner") ? "success" : "neutral"}>OWNER present</Badge>
          </div>
        }
      />
      <ContentContainer>
        <Card className="p-3">
          <div className="flex flex-wrap items-center gap-2">
            <input
              placeholder="Filter by email, role, id…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="w-full max-w-[320px] rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2.5 py-1.5 text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:border-[var(--color-purple-accent)] focus:outline-none"
              aria-label="Filter users"
            />
            <span className="mono ml-auto text-[11px] text-[var(--color-text-tertiary)]">
              {filtered ? `${filtered.length} of ${users.length}` : ""} · sorting: {sortKey} {sortDir}
            </span>
          </div>
        </Card>

        {filtered && filtered.length === 0 ? (
          <div className="mt-3">
            <EmptyState title="No users match filter" description={`No users match “${filter}”.`} />
          </div>
        ) : (
          <>
            <div className="mt-3 hidden overflow-hidden rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] md:block">
              <table className="w-full text-left" role="table">
                <thead className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]">
                  <tr className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">
                    <th scope="col" className="px-3 py-2 font-medium">
                      <button onClick={() => toggle("email")} className={sortKey === "email" ? "text-[var(--color-purple-accent)]" : ""} aria-label={`Sort by email ${sortKey === "email" ? sortDir : ""}`}>
                        Email {sortKey === "email" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                      </button>
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      <button onClick={() => toggle("role")} className={sortKey === "role" ? "text-[var(--color-purple-accent)]" : ""}>Role {sortKey === "role" ? (sortDir === "asc" ? "▲" : "▼") : ""}</button>
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      <button onClick={() => toggle("active")} className={sortKey === "active" ? "text-[var(--color-purple-accent)]" : ""}>Active {sortKey === "active" ? (sortDir === "asc" ? "▲" : "▼") : ""}</button>
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">ID</th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      <button onClick={() => toggle("created_at_ms")} className={sortKey === "created_at_ms" ? "text-[var(--color-purple-accent)]" : ""}>Created {sortKey === "created_at_ms" ? (sortDir === "asc" ? "▲" : "▼") : ""}</button>
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">Last login</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered!.map((u) => (
                    <tr key={u.id} className="border-b border-[var(--color-border-subtle)] last:border-0 hover:bg-[var(--color-bg-surface-2)]">
                      <td className="px-3 py-2 text-[13px] font-medium text-[var(--color-text-primary)]">{u.email}</td>
                      <td className="px-3 py-2">
                        <Badge variant={u.role === "owner" ? "success" : "neutral"} icon={u.role === "owner" ? "●" : "○"}>
                          {u.role}
                        </Badge>
                      </td>
                      <td className="px-3 py-2">
                        <Badge variant={u.active ? "success" : "neutral"} icon={u.active ? "●" : "○"}>
                          {u.active ? "active" : "inactive"}
                        </Badge>
                      </td>
                      <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-tertiary)]">{u.id.slice(0, 8)}</td>
                      <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-secondary)]">{new Date(u.created_at_ms).toLocaleString()}</td>
                      <td className="mono px-3 py-2 text-[11px] text-[var(--color-text-tertiary)]">{u.last_login_at_ms ? new Date(u.last_login_at_ms).toLocaleString() : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="grid gap-2 md:hidden">
              {filtered!.map((u) => (
                <div key={u.id} className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="text-[13px] font-medium text-[var(--color-text-primary)]">{u.email}</div>
                    <Badge variant={u.role === "owner" ? "success" : "neutral"}>{u.role}</Badge>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <Badge variant={u.active ? "success" : "neutral"}>{u.active ? "active" : "inactive"}</Badge>
                    <span className="mono text-[11px] text-[var(--color-text-tertiary)]">{u.id.slice(0, 8)}</span>
                  </div>
                  <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">created {new Date(u.created_at_ms).toLocaleDateString()}</div>
                </div>
              ))}
            </div>
          </>
        )}

        <div className="mono mt-3 text-[11px] text-[var(--color-text-tertiary)]">Only <span className="text-[var(--color-text-secondary)]">id/email/role/active/created_at/updated_at/last_login_at</span> are shown — exactly what <span className="mono text-[var(--color-text-secondary)]">GET /admin/users</span> returns. No password or mutation UI.</div>
      </ContentContainer>
    </>
  );
}
