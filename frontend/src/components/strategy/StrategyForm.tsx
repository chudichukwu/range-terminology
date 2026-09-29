"use client";
import { BalancedForm } from "./BalancedForm";
import { Field, human } from "@/components/workspace/shared";
export type StrategyPayloadDraft = { range_config: Record<string, unknown>; signal_config: Record<string, unknown>; risk_config: Record<string, unknown> };
export const RANGE_TOUCH_PRESET: StrategyPayloadDraft = {
  "range_config": {
    "mode": "balanced",
    "lookback": 100,
    "pivot_window": 2,
    "min_touches": 2,
    "touch_tolerance": 0.05,
    "min_height_atr": 2.5,
    "adx_max": 22.0,
    "adx_trend": 25.0,
    "ema_slope_atr": 0.15
  },
  "signal_config": {
    "entry_mode": "confirmed",
    "edge_zone": 0.15,
    "reclaim_bars": 3,
    "confirmation": "sfp_or_rejection",
    "volume_multiple": 0.0
  },
  "risk_config": {
    "stop_buffer_atr": 0.375,
    "breakout_buffer_atr": 0.375,
    "hold_closes": 2,
    "tp1_fraction": 0.5,
    "target_inset": 0.02,
    "min_reward_risk": 2.0,
    "risk_per_trade": 0.01,
    "max_leverage": 3.0,
    "runner_fraction": 0.0
  }
};

type Config = Record<string, unknown>;
type Props = { name: string; setName: (v: string) => void; active: boolean; setActive: (v: boolean) => void; rangeConfig: Config; setRangeConfig: (v: Config) => void; signalConfig: Config; setSignalConfig: (v: Config) => void; riskConfig: Config; setRiskConfig: (v: Config) => void };
function NumberField({ label, config, set, name, fallback, percent = false, min, max, step }: { label: string; config: Config; set: (v: Config) => void; name: string; fallback: number; percent?: boolean; min?: number; max?: number; step?: number }) {
 const factor = percent ? 100 : 1;
 return <Field label={label}><input type="number" min={min} max={max} step={step ?? (percent ? 0.1 : 1)} value={Math.round(Number(config[name] ?? fallback) * factor * 10000) / 10000} onChange={e => set({ ...config, [name]: e.target.value === "" ? "" : Number(e.target.value) / factor })} /></Field>;
}
export function StrategyForm(p: Props) {
 if (p.rangeConfig.mode === "balanced") return <BalancedForm {...p} />;
 const r = p.rangeConfig, s = p.signalConfig, k = p.riskConfig;
 const number = (config: Config, set: (v: Config) => void, name: string, label: string, fallback: number, percent = false, min = 0, max?: number) => <NumberField key={name} {...{ config, set, name, label, fallback, percent, min, max }} />;
 return <div className="space-y-5">
 <section className="panel settings-panel"><h2>Your playbook</h2><p className="muted">Name the rules you want the scanner and backtest to follow.</p><div className="settings-fields"><Field label="Name"><input value={p.name} onChange={e => p.setName(e.target.value)} maxLength={80} placeholder="Range extremes" /></Field><Field label="Status"><select value={p.active ? "active" : "paused"} onChange={e => p.setActive(e.target.value === "active")}><option value="active">Active</option><option value="paused">Paused</option></select></Field></div><button className="secondary-button" style={{ marginTop: 18 }} onClick={() => { p.setRangeConfig({ ...RANGE_TOUCH_PRESET.range_config }); p.setSignalConfig({ ...RANGE_TOUCH_PRESET.signal_config }); p.setRiskConfig({ ...RANGE_TOUCH_PRESET.risk_config }); }}>Use range-touch starting settings</button></section>
 <section className="panel settings-panel"><p className="eyebrow">01 / MARKET STRUCTURE</p><h2>What makes a range?</h2><p className="muted">Look for sideways movement with repeated swing highs and lows. Two or three touches describe double or triple boundary tests; no reversal is assumed.</p><div className="settings-fields"><Field label="Range detection"><select value={String(r.mode ?? "structural")} onChange={e => p.setRangeConfig({ ...r, mode: e.target.value })}><option value="structural">Repeated swing structure</option><option value="manual">Manual boundaries</option>{!["structural", "manual"].includes(String(r.mode)) && <option value={String(r.mode)}>{human(String(r.mode))} (existing)</option>}</select></Field>{r.mode === "manual" ? <>{number(r, p.setRangeConfig, "range_low", "Range low", 90)}{number(r, p.setRangeConfig, "range_high", "Range high", 100)}</> : <>{number(r, p.setRangeConfig, "lookback", "Lookback · candles", 100, false, 10, 500)}{number(r, p.setRangeConfig, "pivot_window", "Swing confirmation · bars per side", 2, false, 1, 10)}{number(r, p.setRangeConfig, "min_touches", "Minimum touches per boundary", 2, false, 1, 10)}{number(r, p.setRangeConfig, "touch_tolerance", "Touch tolerance · % of range width", .05, true, 0, 25)}{number(r, p.setRangeConfig, "max_drift_ratio", "Maximum directional drift · %", .3, true, 1, 100)}</>}</div></section>
 <section className="panel settings-panel"><p className="eyebrow">02 / ENTRY</p><h2>Meet price at the edge.</h2><div className="settings-fields"><Field label="Entry trigger"><select value={String(s.entry_mode ?? "close")} onChange={e => p.setSignalConfig({ ...s, entry_mode: e.target.value })}><option value="touch">Touch the exact range boundary</option><option value="close">Close inside an edge zone</option></select></Field><Field label="Oscillator confirmation"><select value={String(s.confirmation_policy ?? "ignored")} onChange={e => p.setSignalConfig({ ...s, confirmation_policy: e.target.value })}><option value="ignored">Not required</option><option value="optional">Optional</option><option value="required">Required (oscillator range only)</option></select></Field>{s.entry_mode !== "touch" && <>{number(s, p.setSignalConfig, "lower_edge_zone", "Lower entry zone · % of range", .02, true, .1, 50)}{number(s, p.setSignalConfig, "upper_edge_zone", "Upper entry zone · % of range", .02, true, .1, 50)}</>}</div><p className="muted" style={{ marginTop: 18 }}>Swing failures are marked separately after a candle sweeps a confirmed swing and closes back inside.</p></section>
 <section className="panel settings-panel"><p className="eyebrow">03 / INVALIDATION & EXITS</p><h2>Define the exit before the entry.</h2><div className="settings-fields"><Field label="Stop calculation"><select value={String(k.stop_method ?? "range_percent")} onChange={e => p.setRiskConfig({ ...k, stop_method: e.target.value })}><option value="range_percent">Percent outside the range boundary</option><option value="range">Fraction of range width</option><option value="fixed_percent">Percent from entry</option><option value="atr">ATR from entry</option></select></Field>{k.stop_method === "range" ? number(k, p.setRiskConfig, "range_stop_buffer", "Buffer · % of range width", .05, true, 0, 99) : k.stop_method === "atr" ? number(k, p.setRiskConfig, "atr_multiplier", "ATR multiplier", 2, false, .1, 20) : number(k, p.setRiskConfig, "fixed_stop_percent", "Invalidation distance · %", .02, true, .1, 99)}<Field label="First target"><select value={String(k.target_method ?? "opposite_range_edge")} onChange={e => p.setRiskConfig({ ...k, target_method: e.target.value })}><option value="opposite_range_edge">Opposite range boundary</option><option value="range_fraction">Fraction of range</option><option value="fixed_rr">Fixed reward / risk</option></select></Field>{k.target_method === "range_fraction" && number(k, p.setRiskConfig, "range_target_fraction", "Target · % of range", .9, true, 1, 100)}{k.target_method === "fixed_rr" && number(k, p.setRiskConfig, "fixed_rr_ratio", "Target reward / risk", 3, false, .1, 100)}{number(k, p.setRiskConfig, "runner_fraction", "Leave for breakout · % of position", .25, true, 0, 99)}{number(k, p.setRiskConfig, "runner_trail_percent", "Runner trailing distance · %", .02, true, .1, 99)}{number(k, p.setRiskConfig, "risk_per_trade", "Simulated equity risk per trade · %", .01, true, .1, 100)}{number(k, p.setRiskConfig, "min_reward_risk", "Minimum reward / risk after costs", 1, false, .1, 100)}{number(k, p.setRiskConfig, "max_leverage", "Maximum simulated leverage", 3, false, 1, 100)}</div><p className="muted" style={{ marginTop: 18 }}>Starting assumptions: leave 25% for a breakout; after the first target, protect the runner at entry or better and trail by 2% of candle closes. These are adjustable research settings.</p></section>
 </div>;
}
export function StrategySummary({ name, rangeConfig: r, signalConfig: s, riskConfig: k, active, updatedAt }: { name: string; active: boolean; rangeConfig: Config; signalConfig: Config; riskConfig: Config; payloadJson?: string; updatedAt?: number }) {
 if (r.mode === "balanced") return <aside className="panel detail-panel"><p className="eyebrow">CONFIRMED RANGE</p><h2>{name || "Your balanced-range playbook"}</h2><p className="muted">Weekly/daily context → 4H/1H range → lower-timeframe confirmation.</p>{[["Range",`2+ touches · ADX < ${r.adx_max ?? 22}`],["Minimum height",`${r.min_height_atr ?? 2.5}× ATR`],["Entry",human(String(s.confirmation ?? "sfp_or_rejection"))],["Stop",`Sweep + ${k.stop_buffer_atr ?? .375}× ATR`],["TP1",`${Number(k.tp1_fraction ?? .5)*100}% at midpoint`],["TP2","Opposite edge · full exit"],["Reward/risk",`≥ ${k.min_reward_risk ?? 2} weighted after costs`]].map(([label,value])=><div className="level-row" key={label}><span>{label}</span><b>{value}</b></div>)}</aside>;
 return <aside className="panel detail-panel"><p className="eyebrow">AT A GLANCE</p><h2>{name || "Your range playbook"}</h2><span className="status-pill range">{active ? "Active" : "Paused"}</span>{[["Structure", human(String(r.mode ?? "structural"))], ["Entry", s.entry_mode === "touch" ? "Boundary touch" : "Close in edge zone"], ["Stop", `${Number(k.fixed_stop_percent ?? .02) * 100}% · ${human(String(k.stop_method ?? "range_percent"))}`], ["First target", human(String(k.target_method ?? "opposite_range_edge"))], ["Breakout runner", `${Math.round(Number(k.runner_fraction ?? 0) * 100)}%`]].map(([label, value]) => <div className="level-row" key={label}><span>{label}</span><b style={{ textAlign: "right", fontSize: 11 }}>{value}</b></div>)}<p className="muted" style={{ marginTop: 18 }}>{updatedAt ? `Saved ${new Date(updatedAt).toLocaleString()}` : "Save to use these rules in your scans and backtests."}</p></aside>;
}
