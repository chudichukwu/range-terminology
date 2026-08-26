"use client";

import { useEffect, useRef } from "react";
import type { PairAnalysis } from "@/lib/api/types";

type Props = {
  analysis: PairAnalysis | null;
};

export function TradingChart({ analysis }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const candleSeriesRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    let destroyed = false;

    (async () => {
      const lwc = await import("lightweight-charts");
      if (destroyed || !containerRef.current) return;

      const chart = lwc.createChart(containerRef.current, {
        layout: {
          background: { type: lwc.ColorType.Solid, color: "#151226" },
          textColor: "#9e98b8"
        },
        grid: {
          vertLines: { color: "#242041" },
          horzLines: { color: "#242041" }
        },
        rightPriceScale: {
          borderColor: "#302A55"
        },
        timeScale: {
          borderColor: "#302A55",
          timeVisible: true,
          secondsVisible: false
        },
        crosshair: {
          vertLine: { color: "#3D3660", width: 1, style: 1 },
          horzLine: { color: "#3D3660", width: 1, style: 1 }
        },
        handleScroll: true,
        handleScale: true
      });

      const series = chart.addCandlestickSeries({
        upColor: "#1db954",
        downColor: "#ef4444",
        wickUpColor: "#706a8e",
        wickDownColor: "#706a8e",
        borderVisible: false
      });

      chartRef.current = chart;
      candleSeriesRef.current = series;

      const ro = new ResizeObserver(() => {
        if (containerRef.current && chart) {
          chart.applyOptions({ width: containerRef.current.clientWidth, height: containerRef.current.clientHeight });
        }
      });
      ro.observe(containerRef.current);
      // initial size
      chart.applyOptions({ width: containerRef.current.clientWidth, height: containerRef.current.clientHeight });

      return () => {
        ro.disconnect();
      };
    })();

    return () => {
      destroyed = true;
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, []);

  // Update data when analysis changes
  useEffect(() => {
    if (!candleSeriesRef.current || !analysis) return;
    const data = analysis.candles
      .filter((c) => c.is_closed)
      .map((c) => ({
        time: Math.floor(c.timestamp / 1000) as any,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close
      }))
      .sort((a, b) => (a.time as number) - (b.time as number));
    candleSeriesRef.current.setData(data);

    // Fit
    chartRef.current?.timeScale().fitContent();

    // Range overlays via price lines
    const priceLines: any[] = [];
    const addLine = (price: number | null | undefined, opts: any) => {
      if (price === null || price === undefined || !Number.isFinite(price)) return;
      const line = candleSeriesRef.current.createPriceLine(opts);
      priceLines.push(line);
    };

    // Range high/low — slate, solid when tradable else dashed
    const isSolid = analysis.range.is_tradable && analysis.range.status === "valid";
    addLine(analysis.range.high, {
      price: analysis.range.high!,
      color: "#8ea1be",
      lineWidth: 1.5,
      lineStyle: isSolid ? 0 : 2,
      axisLabelVisible: true,
      title: "R HIGH"
    });
    addLine(analysis.range.low, {
      price: analysis.range.low!,
      color: "#8ea1be",
      lineWidth: 1.5,
      lineStyle: isSolid ? 0 : 2,
      axisLabelVisible: true,
      title: "R LOW"
    });

    // Risk levels — from backend RiskDecision preview
    if (analysis.risk) {
      if (analysis.risk.entry_price !== null) {
        addLine(analysis.risk.entry_price, { price: analysis.risk.entry_price, color: "#38bdf8", lineWidth: 1, lineStyle: 0, axisLabelVisible: true, title: "ENTRY" });
      }
      if (analysis.risk.stop_price !== null) {
        addLine(analysis.risk.stop_price, { price: analysis.risk.stop_price, color: "#f59e0b", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "STOP" });
      }
      if (analysis.risk.target_price !== null) {
        addLine(analysis.risk.target_price, { price: analysis.risk.target_price, color: "#22c55e", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "TARGET" });
      }
    }

    // Signal markers — backend-provided direction
    const markers: any[] = [];
    const last = analysis.candles.filter((c) => c.is_closed).at(-1);
    if (last && analysis.signal.direction !== "none") {
      const isLong = analysis.signal.direction === "long";
      markers.push({
        time: Math.floor(last.timestamp / 1000) as any,
        position: isLong ? "belowBar" : "aboveBar",
        color: isLong ? "#1db954" : "#ef4444",
        shape: isLong ? "arrowUp" : "arrowDown",
        text: isLong ? "LONG" : "SHORT"
      });
    }
    candleSeriesRef.current.setMarkers(markers);

    return () => {
      // cleanup price lines on next update (re-created above)
    };
  }, [analysis]);

  // a11y fallback table summary
  if (!analysis) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-6 text-[13px] text-[var(--color-text-tertiary)]">
        Loading chart…
      </div>
    );
  }

  const isStale = analysis.freshness.is_stale;
  const tradable = analysis.range.is_tradable;

  return (
    <div className="space-y-2">
      <div
        ref={containerRef}
        role="img"
        aria-label={`Chart for ${analysis.symbol} ${analysis.timeframe} — Range ${analysis.range.status}, Regime ${analysis.regime.value}, signal ${analysis.signal.direction}`}
        className="h-[420px] w-full overflow-hidden rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] md:h-[52vh] md:min-h-[420px]"
      />
      {/* Range zone legend — restrained hatch via CSS, not dominant */}
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="mono uppercase tracking-wide text-[var(--color-text-tertiary)]">Zones:</span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-6 rounded-xs border border-[rgba(142,161,190,0.3)] bg-[rgba(142,161,190,0.08)]" aria-hidden />
          <span className="text-[var(--color-text-secondary)]">Lower → LONG</span>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            className="h-2 w-6 rounded-xs border border-[rgba(107,122,144,0.2)] bg-[rgba(107,122,144,0.06)]"
            style={{ backgroundImage: "repeating-linear-gradient(45deg, transparent 0 4px, rgba(107,122,144,0.12) 4px 5px)" }}
            aria-hidden
          />
          <span className="text-[var(--color-text-secondary)]">Middle — NO-TRADE</span>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-6 rounded-xs border border-[rgba(142,161,190,0.3)] bg-[rgba(142,161,190,0.08)]" aria-hidden />
          <span className="text-[var(--color-text-secondary)]">Upper → SHORT</span>
        </span>
        <span className="ml-auto mono text-[11px] text-[var(--color-text-tertiary)]">
          {!tradable ? "Bounds not tradable — dashed" : "Solid bounds — tradable"} · {isStale ? "Stale data — faded" : "Live"} · Paper
        </span>
      </div>
      {/* Hidden table fallback for screen readers */}
      <table className="sr-only">
        <caption>
          Candles for {analysis.symbol} {analysis.timeframe}
        </caption>
        <thead>
          <tr>
            <th>Time</th>
            <th>Open</th>
            <th>High</th>
            <th>Low</th>
            <th>Close</th>
          </tr>
        </thead>
        <tbody>
          {analysis.candles.slice(-5).map((c) => (
            <tr key={c.timestamp}>
              <td>{new Date(c.timestamp).toISOString()}</td>
              <td>{c.open}</td>
              <td>{c.high}</td>
              <td>{c.low}</td>
              <td>{c.close}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
