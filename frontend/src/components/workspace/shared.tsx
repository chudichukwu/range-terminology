"use client";
import Link from "next/link";
import { ApiError } from "@/lib/api/client";
export const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"] as const;
export const SOURCES = [{ id: "hyperliquid", name: "Hyperliquid · perps & spot" }, { id: "binanceusdm", name: "Binance · USDT perps" }, { id: "binance", name: "Binance · spot" }];
export const money = (v: number | null | undefined) => v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: Math.abs(v) < 1 ? 6 : 2 });
export const human = (v: string) => v.replaceAll("_", " ");
export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  const auth = error instanceof ApiError && error.status === 401;
  return <div className="notice error" role="alert">{auth ? <>Sign in to save your watchlist and start scanning. <Link href="/login">Sign in →</Link></> : error instanceof Error ? error.message : String(error)}</div>;
}
export function WorkspaceHeader({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: React.ReactNode }) {
  return <header className="workspace-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="muted">{description}</p></div><div className="heading-actions">{children}</div></header>;
}
export function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="field"><span>{label}</span>{children}</label>; }
