"use client";
import { useEffect, useState } from "react";
import { Sidebar } from "./Sidebar";
import { TopRibbon } from "./TopRibbon";
import { CommandPalette } from "./CommandPalette";
import { AlertBell } from "@/components/workspace/AlertBell";
export function AppShell({ children }: { children: React.ReactNode }) {
 const [collapsed, setCollapsed] = useState(false), [mobileOpen, setMobileOpen] = useState(false), [paletteOpen, setPaletteOpen] = useState(false);
 useEffect(() => { setCollapsed(localStorage.getItem("rt.sidebarCollapsed") === "1"); const key = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPaletteOpen(v => !v); } }; window.addEventListener("keydown", key); return () => window.removeEventListener("keydown", key); }, []);
 return <div className="app-shell"><Sidebar collapsed={collapsed} onToggle={() => setCollapsed(v => { localStorage.setItem("rt.sidebarCollapsed", !v ? "1" : "0"); return !v; })} mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} /><div className="app-body"><div className="app-topbar"><button className="mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Open navigation">☰</button><TopRibbon /><div className="topbar-actions"><button className="command-button" onClick={() => setPaletteOpen(true)}>Search <kbd>⌘ K</kbd></button><AlertBell /></div></div><main id="main-content">{children}</main><footer className="app-footer"><span>GRANDBLUE / MARKET RESEARCH</span><span>Scan with context. Trade with intention.</span></footer></div><CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} /></div>;
}
