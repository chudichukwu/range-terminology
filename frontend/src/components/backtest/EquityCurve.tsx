"use client";

import { useEffect, useRef } from "react";
import type { IChartApi, UTCTimestamp } from "lightweight-charts";
import type { EquityPoint } from "@/lib/api/types";

export function EquityCurve({ points, initialCapital }: { points: EquityPoint[]; initialCapital?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!ref.current || points.length === 0) return;
    let destroyed = false;
    let observer: ResizeObserver | undefined;
    (async () => {
      const lwc = await import("lightweight-charts");
      if (destroyed || !ref.current) return;
      const chart = lwc.createChart(ref.current, {
        layout: { background: { type: lwc.ColorType.Solid, color: "#121a21" }, textColor: "#8ea1ad" },
        grid: { vertLines: { color: "#26323c" }, horzLines: { color: "#26323c" } },
        rightPriceScale: { borderColor: "#34414c" },
        timeScale: { borderColor: "#34414c", timeVisible: true },
        crosshair: { vertLine: { color: "#526673", width: 1, style: 1 }, horzLine: { color: "#526673", width: 1, style: 1 } }
      });
      const area = chart.addAreaSeries({ lineColor: "#65aaff", topColor: "rgba(101,170,255,0.22)", bottomColor: "rgba(101,170,255,0.02)", lineWidth: 2 });
      const line = chart.addLineSeries({ color: "rgba(142,161,190,0.5)", lineWidth: 1, lineStyle: 2 });
      const data = points.map((p) => ({ time: Math.floor(p.timestamp_ms / 1000) as UTCTimestamp, value: p.equity }));
      const peakData = points.map((p) => ({ time: Math.floor(p.timestamp_ms / 1000) as UTCTimestamp, value: p.peak_equity }));
      area.setData(data);
      line.setData(peakData);
      chart.timeScale().fitContent();
      chartRef.current = chart;
      observer = new ResizeObserver(() => {
        if (ref.current && chart) chart.applyOptions({ width: ref.current.clientWidth, height: ref.current.clientHeight });
      });
      observer.observe(ref.current);
      chart.applyOptions({ width: ref.current.clientWidth, height: ref.current.clientHeight });
    })();
    return () => {
      destroyed = true;
      observer?.disconnect();
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [points]);

  if (points.length === 0) {
    return <div className="flex h-[220px] items-center justify-center rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] text-[13px] text-[var(--color-text-tertiary)]">No equity points — run produced no closed trades. This is expected for some windows.</div>;
  }

  return (
    <div className="space-y-2">
      <div ref={ref} role="img" aria-label={`Equity curve ${points.length} points, final ${points[points.length - 1]?.equity.toFixed(2)}`} className="h-[240px] w-full overflow-hidden rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)]" />
      <div className="mono text-[11px] text-[var(--color-text-tertiary)]">
        Closed-trade equity · dashed line shows the previous peak{initialCapital ? ` · starting equity ${initialCapital.toLocaleString()}` : ""}
      </div>
      {/* fallback table for screen readers */}
      <table className="sr-only">
        <caption>Equity curve</caption>
        <thead><tr><th>Time</th><th>Equity</th><th>Peak</th><th>Drawdown</th></tr></thead>
        <tbody>
          {points.slice(-5).map((p) => (
            <tr key={p.timestamp_ms}><td>{new Date(p.timestamp_ms).toISOString()}</td><td>{p.equity}</td><td>{p.peak_equity}</td><td>{p.drawdown}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
