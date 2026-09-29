"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { IChartApi, ISeriesApi, IPriceLine, UTCTimestamp } from "lightweight-charts";
import type { PairAnalysis } from "@/lib/api/types";
export function TradingChart({ analysis }: { analysis: PairAnalysis | null }) {
 const host = useRef<HTMLDivElement>(null), chart = useRef<IChartApi>(), series = useRef<ISeriesApi<"Candlestick">>();
 const [sfpMode, setSfpMode] = useState("recent");
 const allSfps = useMemo(() => analysis?.swing_failures ?? [], [analysis]);
 const visibleSfps = useMemo(() => sfpMode === "off" ? [] : sfpMode === "range" ? allSfps.filter(e => e.grade === "A+") : sfpMode === "recent" ? allSfps.slice(-3) : allSfps, [sfpMode, allSfps]);
 const lines = useRef<IPriceLine[]>([]), fitted = useRef(""); const [ready, setReady] = useState(false);
 useEffect(() => {
   let disposed = false; let resize: ResizeObserver | undefined;
   void import("lightweight-charts").then(lwc => {
     if (disposed || !host.current) return;
     chart.current = lwc.createChart(host.current, { layout: { background: { type: lwc.ColorType.Solid, color: "#121a21" }, textColor: "#8199a7" }, grid: { vertLines: { color: "#1b2832" }, horzLines: { color: "#1b2832" } }, rightPriceScale: { borderColor: "#2c3b46" }, timeScale: { borderColor: "#2c3b46", timeVisible: true }, crosshair: { mode: lwc.CrosshairMode.Normal } });
     series.current = chart.current.addCandlestickSeries({ upColor: "#92caa3", downColor: "#d88279", wickUpColor: "#92caa3", wickDownColor: "#d88279", borderVisible: false });
     resize = new ResizeObserver(() => { if (host.current) chart.current?.applyOptions({ width: host.current.clientWidth, height: host.current.clientHeight }); });
     resize.observe(host.current); chart.current.applyOptions({ width: host.current.clientWidth, height: host.current.clientHeight }); setReady(true);
   });
   return () => { disposed = true; resize?.disconnect(); chart.current?.remove(); chart.current = undefined; series.current = undefined; lines.current = []; };
 }, []);
 useEffect(() => {
   if (!ready || !analysis || !series.current) return;
   const s = series.current;
   s.setData(analysis.candles.map(c => ({ time: Math.floor(c.timestamp / 1000) as UTCTimestamp, open: c.open, high: c.high, low: c.low, close: c.close })).sort((a, b) => a.time - b.time));
   for (const line of lines.current) s.removePriceLine(line); lines.current = [];
   const add = (price: number | null | undefined, title: string, color: string) => { if (price != null && Number.isFinite(price)) lines.current.push(s.createPriceLine({ price, color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title })); };
   add(analysis.range.high, analysis.range.metadata.reclaimed ? "Reclaimed high" : analysis.range.metadata.structure_confirmed || analysis.range.is_tradable ? "Range high" : "Candidate high", "#b9d7a0"); add(analysis.range.low, analysis.range.metadata.reclaimed ? "Reclaimed low" : analysis.range.metadata.structure_confirmed || analysis.range.is_tradable ? "Range low" : "Candidate low", "#b9d7a0");
   add(analysis.range.metadata.midpoint as number | undefined, "Equilibrium · 50%", "#acb6d5");
   add(analysis.risk?.metadata.tp2 as number | undefined, "TP2 · opposite edge", "#93c7b9");
   add(analysis.risk?.stop_price, "Invalidation", "#d88279"); add(analysis.risk?.target_price, "TP1", "#93c7b9");
   s.setMarkers(visibleSfps.map(e => ({ time: Math.floor(e.timestamp / 1000) as UTCTimestamp, position: e.direction === "bullish" ? "belowBar" as const : "aboveBar" as const, color: e.direction === "bullish" ? "#b9ed83" : "#efae98", shape: e.direction === "bullish" ? "arrowUp" as const : "arrowDown" as const, text: e.grade === "A+" ? "A+" : "" })).sort((a,b) => a.time - b.time));
   const key = `${analysis.symbol}:${analysis.timeframe}:${analysis.candles[0]?.timestamp}`; if (fitted.current !== key) { chart.current?.timeScale().fitContent(); fitted.current = key; }
 }, [analysis, ready, visibleSfps]);
 const latest = visibleSfps.at(-1);
 const focusLatest = () => { if (latest && analysis) { const bars = analysis.candles; const index = bars.findIndex(b => b.timestamp === latest.timestamp); if (index >= 0) chart.current?.timeScale().setVisibleLogicalRange({ from: Math.max(0, index - 20), to: index + 8 }); } };
 return <div className="panel"><div className="panel-toolbar"><div><strong>{analysis?.timeframe} chart</strong><p className="muted">Chart range and confirmed swing sweeps</p></div><div className="chips"><select aria-label="SFP visibility" value={sfpMode} onChange={e => setSfpMode(e.target.value)} className="chip"><option value="recent">Latest 3 SFPs</option><option value="range">A+ range SFPs only</option><option value="all">All SFPs ({allSfps.length})</option><option value="off">Hide SFPs</option></select><button className="chip" disabled={!latest} onClick={() => {focusLatest();}}>Latest SFP ↗</button><button className="chip" onClick={() => chart.current?.timeScale().fitContent()}>Reset view</button></div></div><div className="chart-box" ref={host} role="img" aria-label="Candlestick chart with range boundaries, invalidation, and swing-failure markers" /><div className="workspace-footnote" style={{ margin: 0, padding: "12px 18px" }}><span>Swing SFP = pivot sweep · A+ = range-boundary sweep</span><span>Last candle may still be forming</span></div></div>;
}
