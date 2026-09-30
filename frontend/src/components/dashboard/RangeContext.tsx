"use client";
import type {PairAnalysis} from "@/lib/api/types";
import {human, money} from "@/components/workspace/shared";
export function RangeContext({analysis:d}:{analysis:PairAnalysis}) {
 const m=d.range.metadata;
 const levels=(Array.isArray(m.nearby_levels)?m.nearby_levels:[]) as {kind:string;price:number;distance_atr:number}[];
 const events=d.range_events??[];
 return <section className="panel settings-panel" style={{marginBottom:20}}>
  <p className="eyebrow">RANGE & CONTEXT</p>
  <div className="stat-grid" style={{marginBottom:16}}>
   <div><span className="muted">Local structure</span><h3>{m.reclaimed?"Reclaimed range":m.structure_confirmed?human(d.range.status):"Developing · unconfirmed"}</h3><small className="muted">{m.structure_confirmed?`${Math.round(d.range.confidence*100)}% touch score · not win probability`:String(m.reason??"Awaiting repeated reactions")}</small></div>
   <div><span className="muted">Preceding move</span><h3>{m.preceding_trend?`After ${m.preceding_trend === "up"?"an advance":"a decline"}`:"No clear prior impulse"}</h3><small className="muted">Measured before the range began</small></div>
   <div><span className="muted">Current trend context</span><h3>{m.trend_context?human(String(m.trend_context)):"Mixed / balanced"}</h3><small className="muted">Separate from the local boundaries</small></div>
   <div><span className="muted">Nearby prior levels</span>{levels.length?levels.map(p=><p key={p.kind}>{human(p.kind)} · {money(p.price)}</p>):<h3>No nearby confirmed level</h3>}<small className="muted">Prior chart-timeframe pivots within 1 ATR</small></div>
  </div>
  <details><summary style={{cursor:"pointer"}}>Midpoint observations · {events.length} in loaded history</summary>
   <p className="muted" style={{margin:"12px 0"}}>Rejections, support and crosses of the 50% level. Context only; these do not trigger entries or predict a breakout.</p>
   {events.length?[...events].reverse().slice(0,20).map(e=><div className="level-row" key={`${e.timestamp}:${e.kind}`}><span>{e.repeated?"Repeated ":""}{human(e.kind)} · {money(e.level)}</span><time>{new Date(e.timestamp).toLocaleString()}</time></div>):<p className="muted">No confirmed midpoint events in loaded history.</p>}
   {events.length>20&&<small className="muted">Showing the latest 20 observations.</small>}
  </details>
 </section>;
}
