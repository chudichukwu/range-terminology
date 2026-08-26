"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import type { PairAnalysis } from "@/lib/api/types";

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: PairAnalysis }
  | { status: "error"; code: string; message: string; requestId: string; statusCode: number };

export function usePairAnalysis(symbol: string | null, timeframe: string, strategyId?: string, limit = 200) {
  const [state, setState] = useState<State>({ status: "idle" });

  useEffect(() => {
    if (!symbol) {
      setState({ status: "idle" });
      return;
    }
    const ac = new AbortController();
    setState({ status: "loading" });
    api
      .pairAnalysis({ symbol, timeframe, strategy_id: strategyId, limit }, ac.signal)
      .then(({ data }) => setState({ status: "success", data }))
      .catch((e) => {
        if ((e as Error).name === "AbortError") return;
        if (e instanceof ApiError) {
          setState({ status: "error", code: e.code, message: e.message, requestId: e.requestId, statusCode: e.status });
        } else {
          setState({ status: "error", code: "unknown", message: String(e), requestId: "", statusCode: 0 });
        }
      });
    return () => ac.abort();
  }, [symbol, timeframe, strategyId, limit]);

  return state;
}
