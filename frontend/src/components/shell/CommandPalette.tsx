"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

type Entry = { label: string; href: string; hint: string };

const ENTRIES: Entry[] = [
  { label: "Dashboard", href: "/", hint: "Main workstation" },
  { label: "Watchlists", href: "/watchlists", hint: "Scan pairs" },
  { label: "Strategies", href: "/strategies", hint: "Configure engines" },
  { label: "Backtests", href: "/backtests", hint: "Research runs" },
  { label: "Journal", href: "/journal", hint: "History & stats" },
  { label: "Exchanges", href: "/exchanges", hint: "Connections" },
  { label: "Admin", href: "/admin", hint: "System (OWNER)" },
  { label: "Admin · Users", href: "/admin/users", hint: "User management" },
  { label: "Admin · Health", href: "/admin/health", hint: "System health" },
  { label: "Admin · Audit", href: "/admin/audit", hint: "Audit log" },
  { label: "Account", href: "/me", hint: "Profile & session" },
  { label: "Login", href: "/login", hint: "Sign in" },
  { label: "Register", href: "/register", hint: "First user → OWNER" }
];

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [query, setQuery] = useState("");
  const router = useRouter();

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return ENTRIES;
    return ENTRIES.filter((e) => e.label.toLowerCase().includes(q) || e.hint.toLowerCase().includes(q));
  }, [query]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[20vh]">
      <button aria-label="Close command palette" className="absolute inset-0 bg-[var(--color-bg-overlay)] backdrop-blur-sm" onClick={() => onOpenChange(false)} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="relative w-[min(560px,calc(100vw-24px))] overflow-hidden rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-bg-surface-1)] shadow-lg"
      >
        <div className="flex items-center gap-2 border-b border-[var(--color-border-subtle)] px-3 py-2">
          <span aria-hidden className="text-[var(--color-text-tertiary)]">
            ⌕
          </span>
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Jump to pair, timeframe, strategy, run, trade…"
            className="flex-1 bg-transparent text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:outline-none"
            aria-label="Search"
          />
          <kbd className="rounded-xs border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-1.5 py-0.5 text-[10px] text-[var(--color-text-tertiary)]">ESC</kbd>
        </div>
        <div className="max-h-[42vh] overflow-auto p-1.5">
          {filtered.length === 0 ? (
            <div className="px-3 py-6 text-center text-[13px] text-[var(--color-text-tertiary)]">No results — foundation palette has routes only.</div>
          ) : (
            <ul role="listbox" aria-label="Commands">
              {filtered.map((entry) => (
                <li key={entry.href}>
                  <button
                    role="option"
                    aria-selected={false}
                    onClick={() => {
                      onOpenChange(false);
                      router.push(entry.href);
                    }}
                    className="flex w-full items-center justify-between rounded-sm px-3 py-2 text-left hover:bg-[var(--color-bg-surface-2)] focus-visible:bg-[var(--color-bg-surface-2)] focus-visible:outline-none"
                  >
                    <span className="text-[13px] font-medium text-[var(--color-text-primary)]">{entry.label}</span>
                    <span className="mono text-[11px] text-[var(--color-text-tertiary)]">{entry.hint}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-1 border-t border-[var(--color-border-subtle)] px-3 py-2 text-[11px] text-[var(--color-text-tertiary)]">
            Foundation — routes resolve to page shells. Full search (pairs/timeframes/strategies) arrives with later phases.{" "}
            <span className="text-[var(--color-purple-accent)]">⌘K</span> to toggle.
          </div>
        </div>
      </div>
    </div>
  );
}
