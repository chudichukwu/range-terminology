"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
export function TopRibbon() {
 const [connected, setConnected] = useState<boolean | null>(null);
 useEffect(() => { let active = true; const check = () => api.health().then(() => active && setConnected(true)).catch(() => active && setConnected(false)); void check(); const t = setInterval(check, 30000); return () => { active = false; clearInterval(t); }; }, []);
 return <div className="connection-status"><span className="connection-main"><span className={`live-dot ${connected === false ? "offline" : ""}`} />{connected === null ? "Connecting" : connected ? "Server connected" : "Server offline"}</span><span className="connection-divider" /><span className="connection-detail">Public market data · No wallet connection</span></div>;
}
