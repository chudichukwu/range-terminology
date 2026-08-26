"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

type RangeMode = "manual" | "structural" | "volatility" | "oscillator_confirmed";

export type StrategyPayloadDraft = {
  range_config: Record<string, unknown>;
  signal_config: Record<string, unknown>;
  risk_config: Record<string, unknown>;
};

// helpers
function toNum(v: string, fallback: number | undefined): number | undefined {
  if (v.trim() === "") return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

// ---- Range section ----
function RangeSection({ payload, onChange }: { payload: Record<string, unknown>; onChange: (p: Record<string, unknown>) => void }) {
  const mode = (payload.mode as RangeMode) ?? "structural";

  const setMode = (m: RangeMode) => {
    // preserve only relevant keys per mode; reset to defaults
    if (m === "manual") onChange({ mode: m, range_high: payload.range_high ?? 100, range_low: payload.range_low ?? 90 });
    else if (m === "structural") onChange({ mode: m, lookback: 100, pivot_window: 2, max_drift_ratio: 0.5 });
    else if (m === "volatility") onChange({ mode: m, method: "bollinger", period: 20, multiplier: 2 });
    else if (m === "oscillator_confirmed")
      onChange({
        mode: m,
        base: { mode: "structural", lookback: 100, pivot_window: 2 },
        oscillator: "rsi",
        osc_period: 14,
        oversold: 30,
        overbought: 70,
        edge_proximity: 0.25
      });
  };

  const params = (payload.params as Record<string, unknown>) ?? payload; // support both flat and nested legacy
  // For manual/structural/volatility, payload is flat; for oscillator, base is nested
  const isOsc = mode === "oscillator_confirmed";

  // We normalize: for non-osc, payload itself holds params. For osc, base holds nested.
  // To keep UI simple, we edit payload directly (flat) and for osc we edit both.
  const update = (k: string, v: unknown) => onChange({ ...payload, [k]: v });
  const updateBase = (k: string, v: unknown) => {
    const base = (payload.base as Record<string, unknown>) ?? { mode: "structural" };
    onChange({ ...payload, base: { ...base, [k]: v } });
  };

  return (
    <div className="space-y-3 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-4">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-[var(--color-slate)]" aria-hidden />
        <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-slate)]">Range</h3>
        <Badge variant="neutral">slate</Badge>
        <span className="ml-auto mono text-[11px] text-[var(--color-text-tertiary)]">backend: range_config</span>
      </div>

      <label className="block">
        <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Mode</span>
        <select value={mode} onChange={(e) => setMode(e.target.value as RangeMode)} className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-slate)] focus:outline-none">
          <option value="structural">Structural</option>
          <option value="volatility">Volatility</option>
          <option value="manual">Manual</option>
          <option value="oscillator_confirmed">Oscillator-confirmed</option>
        </select>
      </label>

      {mode === "manual" && (
        <div className="grid gap-3 md:grid-cols-3">
          <label className="block">
            <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">range_high (price)</span>
            <input type="number" value={String((payload.range_high as number) ?? "")} onChange={(e) => update("range_high", toNum(e.target.value, undefined))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-slate)] focus:outline-none" />
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">range_low (price)</span>
            <input type="number" value={String((payload.range_low as number) ?? "")} onChange={(e) => update("range_low", toNum(e.target.value, undefined))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-slate)] focus:outline-none" />
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">confidence (0–1)</span>
            <input type="number" step="0.01" placeholder="1.0" value={String((payload.confidence as number) ?? "")} onChange={(e) => update("confidence", toNum(e.target.value, undefined))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-slate)] focus:outline-none" />
          </label>
        </div>
      )}

      {mode === "structural" && (
        <div className="grid gap-3 md:grid-cols-3">
          <label className="block">
            <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">lookback (bars)</span>
            <input type="number" value={String((payload.lookback as number) ?? 100)} onChange={(e) => update("lookback", toNum(e.target.value, 100))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-slate)] focus:outline-none" />
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">pivot_window</span>
            <input type="number" value={String((payload.pivot_window as number) ?? 2)} onChange={(e) => update("pivot_window", toNum(e.target.value, 2))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-slate)] focus:outline-none" />
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">max_drift_ratio (0–)</span>
            <input type="number" step="0.05" value={String((payload.max_drift_ratio as number) ?? 0.5)} onChange={(e) => update("max_drift_ratio", toNum(e.target.value, 0.5))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-slate)] focus:outline-none" />
          </label>
        </div>
      )}

      {mode === "volatility" && (
        <div className="grid gap-3 md:grid-cols-3">
          <label className="block">
            <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">method</span>
            <select value={String((payload.method as string) ?? "bollinger")} onChange={(e) => update("method", e.target.value)} className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-slate)] focus:outline-none">
              <option value="bollinger">bollinger</option>
              <option value="atr">atr</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">period (≥2)</span>
            <input type="number" value={String((payload.period as number) ?? 20)} onChange={(e) => update("period", toNum(e.target.value, 20))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-slate)] focus:outline-none" />
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">multiplier</span>
            <input type="number" step="0.1" value={String((payload.multiplier as number) ?? 2)} onChange={(e) => update("multiplier", toNum(e.target.value, 2))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-slate)] focus:outline-none" />
          </label>
        </div>
      )}

      {isOsc && (
        <>
          <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] p-3">
            <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Base detector</div>
            <div className="mt-2 grid gap-3 md:grid-cols-3">
              <label className="block">
                <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">base mode</span>
                <select value={String(((payload.base as Record<string, unknown>)?.mode as string) ?? "structural")} onChange={(e) => updateBase("mode", e.target.value)} className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-slate)] focus:outline-none">
                  <option value="structural">structural</option>
                  <option value="volatility">volatility</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">lookback / period</span>
                <input type="number" value={String(((payload.base as Record<string, unknown>)?.lookback as number) ?? ((payload.base as Record<string, unknown>)?.period as number) ?? 100)} onChange={(e) => { const v = toNum(e.target.value, undefined); const b = payload.base as Record<string, unknown>; const mode = (b?.mode as string) ?? "structural"; if (mode === "volatility") updateBase("period", v); else updateBase("lookback", v); }} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-slate)] focus:outline-none" />
              </label>
              <label className="block">
                <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">pivot_window / multiplier</span>
                <input type="number" step="0.1" value={String(((payload.base as Record<string, unknown>)?.pivot_window as number) ?? ((payload.base as Record<string, unknown>)?.multiplier as number) ?? 2)} onChange={(e) => { const v = toNum(e.target.value, undefined); const b = payload.base as Record<string, unknown>; const mode = (b?.mode as string) ?? "structural"; if (mode === "volatility") updateBase("multiplier", v); else updateBase("pivot_window", v); }} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-slate)] focus:outline-none" />
              </label>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-5">
            <label className="block">
              <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">oscillator</span>
              <select value={String((payload.oscillator as string) ?? "rsi")} onChange={(e) => update("oscillator", e.target.value)} className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-purple-accent)] focus:outline-none">
                <option value="rsi">rsi</option>
                <option value="stoch">stoch</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">osc_period ≥2</span>
              <input type="number" value={String((payload.osc_period as number) ?? 14)} onChange={(e) => update("osc_period", toNum(e.target.value, 14))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-osc)] focus:outline-none" />
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">oversold</span>
              <input type="number" value={String((payload.oversold as number) ?? 30)} onChange={(e) => update("oversold", toNum(e.target.value, 30))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-osc)] focus:outline-none" />
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">overbought</span>
              <input type="number" value={String((payload.overbought as number) ?? 70)} onChange={(e) => update("overbought", toNum(e.target.value, 70))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-osc)] focus:outline-none" />
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">edge_proximity (0–1)</span>
              <input type="number" step="0.05" value={String((payload.edge_proximity as number) ?? 0.25)} onChange={(e) => update("edge_proximity", toNum(e.target.value, 0.25))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-osc)] focus:outline-none" />
            </label>
          </div>
        </>
      )}
    </div>
  );
}

function SignalSection({ payload, onChange }: { payload: Record<string, unknown>; onChange: (p: Record<string, unknown>) => void }) {
  const update = (k: string, v: unknown) => onChange({ ...payload, [k]: v });
  return (
    <div className="space-y-3 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-4">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-[var(--color-purple-accent)]" aria-hidden />
        <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-primary)]">Signal / Confirmation</h3>
        <Badge variant="osc">lavender</Badge>
        <span className="ml-auto mono text-[11px] text-[var(--color-text-tertiary)]">backend: signal_config</span>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">lower_edge_zone (0–0.5]</span>
          <input type="number" step="0.05" min={0} max={0.5} value={String((payload.lower_edge_zone as number) ?? 0.25)} onChange={(e) => update("lower_edge_zone", toNum(e.target.value, 0.25))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-osc)] focus:outline-none" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">upper_edge_zone (0–0.5]</span>
          <input type="number" step="0.05" min={0} max={0.5} value={String((payload.upper_edge_zone as number) ?? 0.25)} onChange={(e) => update("upper_edge_zone", toNum(e.target.value, 0.25))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-osc)] focus:outline-none" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">confirmation_policy</span>
          <select value={String((payload.confirmation_policy as string) ?? "optional")} onChange={(e) => update("confirmation_policy", e.target.value)} className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-osc)] focus:outline-none">
            <option value="required">required — setup needs true confirmation</option>
            <option value="optional">optional — surfaced, never blocks</option>
            <option value="ignored">ignored — confirmation not read</option>
          </select>
        </label>
      </div>
      <div className="rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]/60 px-2.5 py-2 text-[11px] leading-relaxed text-[var(--color-text-tertiary)]">
        Oscillator confirmation is confirmation of range-based reasoning, not a replacement for range structure. <span className="text-[var(--color-osc)]">Lavender</span> semantics. Divergence is planned/future — not configured here.
      </div>
    </div>
  );
}

function RiskSection({ payload, onChange }: { payload: Record<string, unknown>; onChange: (p: Record<string, unknown>) => void }) {
  const update = (k: string, v: unknown) => {
    if (v === "" || v === null || v === undefined) {
      const next = { ...payload };
      delete (next as Record<string, unknown>)[k];
      onChange(next);
    } else onChange({ ...payload, [k]: v });
  };
  const num = (k: string, fallback?: number) => (payload[k] as number) ?? fallback;

  return (
    <div className="space-y-3 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-4">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-[var(--color-danger)]" aria-hidden />
        <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-danger)]">Risk</h3>
        <Badge variant="danger">amber</Badge>
        <span className="ml-auto mono text-[11px] text-[var(--color-text-tertiary)]">backend: risk_config — PAPER/READ-ONLY</span>
      </div>

      <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Sizing</div>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">risk_per_trade (0–1, fraction of equity)</span>
          <input type="number" step="0.001" value={String(num("risk_per_trade", 0.01))} onChange={(e) => update("risk_per_trade", toNum(e.target.value, 0.01))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">max_leverage</span>
          <input type="number" step="0.1" value={String(num("max_leverage", 1))} onChange={(e) => update("max_leverage", toNum(e.target.value, 1))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">min_reward_risk</span>
          <input type="number" step="0.1" value={String(num("min_reward_risk", 2))} onChange={(e) => update("min_reward_risk", toNum(e.target.value, 2))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
      </div>

      <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Stops & Targets (backend calculates; UI configures method)</div>
      <div className="grid gap-3 md:grid-cols-4">
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">stop_method</span>
          <select value={String(payload.stop_method ?? "range")} onChange={(e) => update("stop_method", e.target.value)} className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none">
            <option value="range">range</option>
            <option value="atr">atr</option>
            <option value="fixed_percent">fixed_percent</option>
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">range_stop_buffer (0–1)</span>
          <input type="number" step="0.01" value={String(num("range_stop_buffer", 0.05))} onChange={(e) => update("range_stop_buffer", toNum(e.target.value, 0.05))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">atr_multiplier</span>
          <input type="number" step="0.1" value={String(num("atr_multiplier", 2))} onChange={(e) => update("atr_multiplier", toNum(e.target.value, 2))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">fixed_stop_percent</span>
          <input type="number" step="0.001" value={String(num("fixed_stop_percent", 0.02))} onChange={(e) => update("fixed_stop_percent", toNum(e.target.value, 0.02))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">target_method</span>
          <select value={String(payload.target_method ?? "opposite_range_edge")} onChange={(e) => update("target_method", e.target.value)} className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none">
            <option value="opposite_range_edge">opposite_range_edge</option>
            <option value="range_fraction">range_fraction</option>
            <option value="fixed_rr">fixed_rr</option>
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">range_target_fraction (0–1]</span>
          <input type="number" step="0.05" value={String(num("range_target_fraction", 0.9))} onChange={(e) => update("range_target_fraction", toNum(e.target.value, 0.9))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">fixed_rr_ratio</span>
          <input type="number" step="0.1" value={String(num("fixed_rr_ratio", 3))} onChange={(e) => update("fixed_rr_ratio", toNum(e.target.value, 3))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
      </div>

      <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Portfolio gates & costs (display-only, backend-enforced)</div>
      <div className="grid gap-3 md:grid-cols-4">
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">max_drawdown (0–1)</span>
          <input type="number" step="0.01" value={String(num("max_drawdown", 0.2))} onChange={(e) => update("max_drawdown", toNum(e.target.value, 0.2))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">max_daily_drawdown</span>
          <input type="number" step="0.01" value={String(num("max_daily_drawdown", 0.05))} onChange={(e) => update("max_daily_drawdown", toNum(e.target.value, 0.05))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">max_consecutive_losses</span>
          <input type="number" value={String(num("max_consecutive_losses", 3))} onChange={(e) => update("max_consecutive_losses", toNum(e.target.value, 3))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">max_open_positions</span>
          <input type="number" value={String(num("max_open_positions", 5))} onChange={(e) => update("max_open_positions", toNum(e.target.value, 5))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
      </div>
      <div className="grid gap-3 md:grid-cols-5">
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">fee_rate</span>
          <input type="number" step="0.0001" value={String(num("fee_rate", 0.001))} onChange={(e) => update("fee_rate", toNum(e.target.value, 0.001))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">slippage_rate</span>
          <input type="number" step="0.0001" value={String(num("slippage_rate", 0.0005))} onChange={(e) => update("slippage_rate", toNum(e.target.value, 0.0005))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">max_position_notional (optional)</span>
          <input type="number" placeholder="—" value={payload.max_position_notional !== undefined ? String(payload.max_position_notional as number) : ""} onChange={(e) => update("max_position_notional", toNum(e.target.value, undefined))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">max_total_exposure (optional)</span>
          <input type="number" placeholder="—" value={payload.max_total_exposure !== undefined ? String(payload.max_total_exposure as number) : ""} onChange={(e) => update("max_total_exposure", toNum(e.target.value, undefined))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-[var(--color-text-tertiary)]">max_asset_exposure (optional)</span>
          <input type="number" placeholder="—" value={payload.max_asset_exposure !== undefined ? String(payload.max_asset_exposure as number) : ""} onChange={(e) => update("max_asset_exposure", toNum(e.target.value, undefined))} className="mono w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2 py-1.5 text-[13px] text-[var(--color-text-primary)] focus:border-[var(--color-danger)] focus:outline-none" />
        </label>
      </div>
      <div className="mono text-[11px] text-[var(--color-text-tertiary)]">Quantity/stop/target are backend calculations. “—” means the field is omitted, not 0.</div>
    </div>
  );
}

export function StrategyForm({
  name,
  setName,
  active,
  setActive,
  rangeConfig,
  setRangeConfig,
  signalConfig,
  setSignalConfig,
  riskConfig,
  setRiskConfig
}: {
  name: string;
  setName: (v: string) => void;
  active: boolean;
  setActive: (v: boolean) => void;
  rangeConfig: Record<string, unknown>;
  setRangeConfig: (v: Record<string, unknown>) => void;
  signalConfig: Record<string, unknown>;
  setSignalConfig: (v: Record<string, unknown>) => void;
  riskConfig: Record<string, unknown>;
  setRiskConfig: (v: Record<string, unknown>) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-4">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-[var(--color-purple-accent)]" aria-hidden />
          <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-primary)]">Strategy Identity</h3>
          <span className="ml-auto mono text-[11px] text-[var(--color-text-tertiary)]">name + active</span>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto]">
          <label className="block">
            <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Strategy name (1–80)</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="My Range Strategy" aria-describedby="name-help" className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-2.5 py-1.5 text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:border-[var(--color-purple-accent)] focus:outline-none" />
            <span id="name-help" className="mt-1 block mono text-[11px] text-[var(--color-text-tertiary)]">Distinct name; identity is backend id + payload hash.</span>
          </label>
          <label className="flex flex-col items-start gap-1">
            <span className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Status</span>
            <button type="button" role="switch" aria-checked={active} onClick={() => setActive(!active)} className={`inline-flex h-7 items-center rounded-pill border px-1 ${active ? "border-[var(--color-success)] bg-[var(--color-success-subtle)]" : "border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)]"}`}>
              <span className={`h-5 rounded-pill px-2 py-0.5 text-[11px] font-medium ${active ? "bg-[var(--color-success)] text-white" : "bg-[var(--color-bg-surface-1)] text-[var(--color-text-tertiary)]"}`}>{active ? "ACTIVE" : "DISABLED"}</span>
            </button>
            <span className="mono text-[11px] text-[var(--color-text-tertiary)]">PAPER only — active ≠ live trading.</span>
          </label>
        </div>
      </div>

      <RangeSection payload={rangeConfig} onChange={setRangeConfig} />
      <SignalSection payload={signalConfig} onChange={setSignalConfig} />
      <RiskSection payload={riskConfig} onChange={setRiskConfig} />
    </div>
  );
}

export function StrategySummary({
  name,
  active,
  rangeConfig,
  signalConfig,
  riskConfig,
  payloadJson,
  updatedAt
}: {
  name: string;
  active: boolean;
  rangeConfig: Record<string, unknown>;
  signalConfig: Record<string, unknown>;
  riskConfig: Record<string, unknown>;
  payloadJson?: string;
  updatedAt?: number;
}) {
  const hashShort = useMemo(() => {
    if (!payloadJson) return "—";
    // frontend hash is illustrative only; backend hash is authoritative. Show short.
    let s = 0;
    for (let i = 0; i < payloadJson.length; i++) s = (s * 31 + payloadJson.charCodeAt(i)) >>> 0;
    return s.toString(16).slice(0, 8);
  }, [payloadJson]);

  return (
    <div className="space-y-3 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-4 lg:sticky lg:top-4">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-[var(--color-purple-accent)]" aria-hidden />
        <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-primary)]">Review / Reproducibility</h3>
      </div>
      <div className="space-y-2">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Strategy</div>
          <div className="mono text-[13px] font-medium text-[var(--color-text-primary)]">{name || "—"}</div>
          <div className="mt-1 flex gap-1">
            <Badge variant={active ? "success" : "neutral"}>{active ? "ACTIVE" : "DISABLED"}</Badge>
            <Badge variant="neutral">{updatedAt ? new Date(updatedAt).toLocaleString() : "unsaved"}</Badge>
          </div>
        </div>
        <div className="border-t border-[var(--color-border-subtle)] pt-2">
          <div className="text-[11px] uppercase tracking-wide text-[var(--color-slate)]">Range — {String((rangeConfig.mode as string) ?? "structural")}</div>
          <pre className="mono mt-1 max-h-20 overflow-auto rounded-sm bg-[var(--color-bg-surface-2)] p-2 text-[11px] text-[var(--color-text-secondary)]">{JSON.stringify(rangeConfig, null, 2)}</pre>
        </div>
        <div className="border-t border-[var(--color-border-subtle)] pt-2">
          <div className="text-[11px] uppercase tracking-wide text-[var(--color-osc)]">Signal — {String((signalConfig.confirmation_policy as string) ?? "optional")}</div>
          <pre className="mono mt-1 max-h-20 overflow-auto rounded-sm bg-[var(--color-bg-surface-2)] p-2 text-[11px] text-[var(--color-text-secondary)]">{JSON.stringify(signalConfig, null, 2)}</pre>
        </div>
        <div className="border-t border-[var(--color-border-subtle)] pt-2">
          <div className="text-[11px] uppercase tracking-wide text-[var(--color-danger)]">Risk — PAPER</div>
          <pre className="mono mt-1 max-h-20 overflow-auto rounded-sm bg-[var(--color-bg-surface-2)] p-2 text-[11px] text-[var(--color-text-secondary)]">{JSON.stringify(riskConfig, null, 2)}</pre>
        </div>
        <div className="border-t border-[var(--color-border-subtle)] pt-2">
          <div className="text-[11px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Identity</div>
          <div className="mono mt-1 text-[11px] text-[var(--color-text-secondary)]">frontend preview hash {hashShort} · backend id/hash authoritative</div>
          {payloadJson && (
            <details className="mt-2">
              <summary className="cursor-pointer text-[11px] font-medium text-[var(--color-text-secondary)]">Canonical JSON (backend)</summary>
              <pre className="mono mt-1 max-h-32 overflow-auto rounded-sm bg-[var(--color-bg-surface-2)] p-2 text-[11px] text-[var(--color-text-tertiary)]">{payloadJson}</pre>
            </details>
          )}
          <div className="mt-2 mono text-[11px] text-[var(--color-text-tertiary)]">This backtest used this exact payload (range+signal+risk). No frontend hash is authoritative.</div>
        </div>
      </div>
    </div>
  );
}
