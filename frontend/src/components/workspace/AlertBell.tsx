"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
export type AlertEvent = { strategy_id?: string | null; id: string; symbol: string; timeframe: string; venue: string; message: string; kind: string; price: number | null; seen: boolean; created_at_ms: number; telegram_status: string };
export function AlertBell() {
 const [count, setCount] = useState(0);
 useEffect(() => { let active = true; const load = async () => { try { const { data } = await api.get<AlertEvent[]>("/alerts"); if (!active) return; setCount(data.filter(e => !e.seen).length); const prior = new Set<string>(JSON.parse(sessionStorage.getItem("rt.notified") ?? "[]")); const initialized = sessionStorage.getItem("rt.notified") !== null;
 for (const e of data) { if (initialized && !prior.has(e.id) && !e.seen && localStorage.getItem("rt.browserAlerts") === "1" && "Notification" in window && Notification.permission === "granted") { new Notification(`${e.symbol} · ${e.timeframe}`, { body: e.message, tag: e.id }); } prior.add(e.id); } sessionStorage.setItem("rt.notified", JSON.stringify([...prior].slice(-1000))); } catch { /* Alerts page exposes actionable errors. */ } }; void load(); const t = setInterval(load, 15000); return () => { active = false; clearInterval(t); }; }, []);
 return <Link href="/alerts" className="alert-bell" aria-label={`${count} unread alerts`}>◉ <span>Alerts</span>{count > 0 && <b>{count}</b>}</Link>;
}
