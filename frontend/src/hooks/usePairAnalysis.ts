"use client";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import type { PairAnalysis } from "@/lib/api/types";
type State = { status: "idle" } | { status: "loading" } | { status: "success"; data: PairAnalysis } | { status: "error"; code: string; message: string; requestId: string; statusCode: number };
export function usePairAnalysis(symbol: string | null, timeframe: string, strategyId?: string, limit = 200, venue?: string) {
 const [state, setState] = useState<State>({ status: "idle" });
 useEffect(() => {
   if (!symbol) { setState({ status: "idle" }); return; }
   const ac = new AbortController(); let timer: ReturnType<typeof setTimeout>;
   setState({ status: "loading" });
   const load = async () => { try { const { data } = await api.pairAnalysis({ symbol, timeframe, strategy_id: strategyId, limit, venue }, ac.signal); if (!ac.signal.aborted) setState({ status: "success", data }); } catch (e) { if (ac.signal.aborted) return; setState({ status: "error", code: e instanceof ApiError ? e.code : "network_error", message: e instanceof Error ? e.message : String(e), requestId: e instanceof ApiError ? e.requestId : "", statusCode: e instanceof ApiError ? e.status : 0 }); } finally { if (!ac.signal.aborted) timer = setTimeout(load, 30000); } };
   void load(); return () => { ac.abort(); clearTimeout(timer); };
 }, [symbol, timeframe, strategyId, limit, venue]);
 return state;
}
