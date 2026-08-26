"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useState } from "react";

type NavItem = { href: string; label: string; icon: string; group: string; ownerOnly?: boolean };

const NAV: NavItem[] = [
  { href: "/", label: "Dashboard", icon: "◈", group: "Trading" },
  { href: "/watchlists", label: "Watchlists", icon: "◎", group: "Trading" },
  { href: "/positions", label: "Positions", icon: "⬢", group: "Trading" },
  { href: "/journal", label: "Journal", icon: "▤", group: "Trading" },
  { href: "/backtests", label: "Backtests", icon: "⟡", group: "Research" },
  { href: "/strategies", label: "Strategies", icon: "⬔", group: "Configure" },
  { href: "/risk", label: "Risk", icon: "⬣", group: "Configure" },
  { href: "/exchanges", label: "Exchanges", icon: "⬢", group: "Configure" },
  { href: "/alerts", label: "Alerts", icon: "◐", group: "Account" },
];

const ADMIN: NavItem[] = [
  { href: "/admin", label: "Admin", icon: "⬢", group: "System", ownerOnly: true },
  { href: "/admin/users", label: "Users", icon: "◯", group: "System", ownerOnly: true },
  { href: "/admin/health", label: "Health", icon: "⬡", group: "System", ownerOnly: true },
  { href: "/admin/audit", label: "Audit", icon: "▭", group: "System", ownerOnly: true }
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(href + "/");
}

export function Sidebar({
  collapsed,
  onToggle,
  mobileOpen,
  onMobileClose
}: {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
}) {
  const pathname = usePathname();
  const [showOwner] = useState(true); // future: gate by role

  const groups: Record<string, NavItem[]> = {};
  for (const item of [...NAV, ...(showOwner ? ADMIN : [])]) {
    if (!groups[item.group]) groups[item.group] = [];
    groups[item.group]!.push(item);
  }

  const sidebarContent = (
    <div className="flex h-full flex-col">
      {/* Brand */}
      <div className="flex h-[52px] shrink-0 items-center gap-3 border-b border-[var(--color-border-subtle)] px-4">
        <div
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-sm text-[11px] font-bold tracking-tight"
          style={{
            background: "linear-gradient(135deg, #7c5cff 0%, #5b3bd6 100%)",
            color: "white"
          }}
        >
          R
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="text-[13px] font-semibold leading-none tracking-tight text-[var(--color-text-primary)]">
              Range Terminal
            </div>
            <div className="mono text-[10px] tracking-wide text-[var(--color-text-tertiary)]">
              PAPER · READ-ONLY
            </div>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav
        aria-label="Primary"
        className="flex-1 overflow-y-auto px-2 py-4"
        style={{ scrollbarWidth: "thin" }}
      >
        {Object.entries(groups).map(([group, items]) => (
          <div key={group} className="mb-5 last:mb-0">
            {!collapsed && (
              <div className="mb-2 px-2 text-[10px] font-medium uppercase tracking-[0.08em] text-[var(--color-text-tertiary)]">
                {group}
              </div>
            )}
            <ul className="space-y-0.5" role="list">
              {items.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      onClick={onMobileClose}
                      className={cn(
                        "group flex items-center gap-3 rounded-sm px-2.5 py-[7px] text-[13px] leading-none transition-colors",
                        active
                          ? "bg-[var(--color-bg-surface-2)] text-[var(--color-text-primary)] shadow-[inset_2px_0_0_var(--color-purple-accent)]"
                          : "text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-2)] hover:text-[var(--color-text-primary)]",
                        collapsed && "justify-center px-2"
                      )}
                      title={collapsed ? item.label : undefined}
                    >
                      <span
                        className={cn(
                          "flex h-5 w-5 shrink-0 items-center justify-center rounded-xs text-[11px]",
                          active
                            ? "bg-[var(--color-purple-subtle)] text-[var(--color-purple-accent)]"
                            : "text-[var(--color-text-tertiary)] group-hover:text-[var(--color-text-secondary)]"
                        )}
                        aria-hidden
                      >
                        {item.icon}
                      </span>
                      {!collapsed && <span className="truncate">{item.label}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Footer actions */}
      <div className="shrink-0 border-t border-[var(--color-border-subtle)] p-2">
        {!collapsed ? (
          <div className="space-y-1">
            <Link
              href="/me"
              className={cn(
                "flex items-center gap-2 rounded-sm px-2.5 py-2 text-[12px] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-2)] hover:text-[var(--color-text-primary)]",
                isActive(pathname, "/me") && "bg-[var(--color-bg-surface-2)] text-[var(--color-text-primary)]"
              )}
            >
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--color-bg-surface-3)] text-[11px]">◯</span>
              <span>Account</span>
            </Link>
            <div className="flex gap-1 px-1">
              <Link href="/login" className="flex-1 rounded-sm bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-center text-[11px] font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]">
                Login
              </Link>
              <Link
                href="/register"
                className="flex-1 rounded-sm bg-[var(--color-purple-accent)] px-2 py-1.5 text-center text-[11px] font-medium text-white hover:bg-[#6d4af0]"
              >
                Register
              </Link>
            </div>
          </div>
        ) : (
          <Link
            href="/me"
            aria-label="Account"
            className="flex h-9 w-9 items-center justify-center rounded-sm bg-[var(--color-bg-surface-2)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          >
            ◯
          </Link>
        )}
        <button
          onClick={onToggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="mt-2 hidden w-full items-center justify-center rounded-sm border border-[var(--color-border-subtle)] py-1.5 text-[11px] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)] lg:flex"
        >
          {collapsed ? "→" : "← Collapse"}
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop */}
      <aside
        aria-label="Sidebar"
        className={cn(
          "hidden shrink-0 flex-col border-r border-[var(--color-border-subtle)] bg-[var(--color-bg-subtle)] lg:flex",
          collapsed ? "w-[var(--sidebar-collapsed)]" : "w-[var(--sidebar-width)]"
        )}
        style={{ transition: "width var(--duration-normal) var(--ease-out)" }}
      >
        {sidebarContent}
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <button aria-label="Close navigation" className="flex-1 bg-[var(--color-bg-overlay)] backdrop-blur-sm" onClick={onMobileClose} />
          <div className="w-[280px] shrink-0 border-l border-[var(--color-border-subtle)] bg-[var(--color-bg-subtle)] shadow-lg">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
}
