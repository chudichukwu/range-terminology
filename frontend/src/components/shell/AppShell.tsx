"use client";

import { useEffect, useState } from "react";
import { Sidebar } from "./Sidebar";
import { TopRibbon } from "./TopRibbon";
import { CommandPalette } from "./CommandPalette";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("rt.sidebarCollapsed");
    if (saved !== null) setCollapsed(saved === "1");
  }, []);
  useEffect(() => {
    localStorage.setItem("rt.sidebarCollapsed", collapsed ? "1" : "0");
  }, [collapsed]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div className="flex min-h-screen bg-[var(--color-bg-base)]">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar */}
        <div className="flex h-12 items-center gap-2 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-subtle)] px-3 lg:hidden">
          <button
            aria-label="Open navigation"
            onClick={() => setMobileOpen(true)}
            className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-2.5 py-1.5 text-[12px] text-[var(--color-text-secondary)]"
          >
            ☰
          </button>
          <span className="text-[13px] font-semibold tracking-tight">Range Terminal</span>
          <span className="ml-auto rounded-pill bg-[var(--color-danger-bg)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--color-danger)]">
            Paper
          </span>
          <button
            aria-label="Open command palette"
            onClick={() => setPaletteOpen(true)}
            className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-2 py-1 text-[11px] text-[var(--color-text-tertiary)]"
          >
            ⌘K
          </button>
        </div>
        <TopRibbon />
        <div className="flex shrink-0 items-center justify-end border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-base)] px-3 py-1.5">
          <button
            onClick={() => setPaletteOpen(true)}
            className="hidden items-center gap-2 rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-2.5 py-1 text-[11px] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)] lg:flex"
            aria-label="Open command palette (Cmd+K)"
          >
            <span>⌘K</span>
            <span>Jump to…</span>
          </button>
        </div>
        <main id="main-content" className="flex-1">
          {children}
        </main>
        <footer className="border-t border-[var(--color-border-subtle)] bg-[var(--color-bg-subtle)] px-4 py-2 text-[11px] leading-none text-[var(--color-text-tertiary)]">
          <span className="mono">Range Trading Terminal</span> — Obsidian Violet · <span className="text-[var(--color-purple-accent)]">PAPER · READ-ONLY</span> · No live execution
        </footer>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  );
}
