"use client";
import { Field } from "@/components/workspace/shared";
type Config = Record<string, unknown>;
type Props = { name: string; setName:(v:string)=>void; active:boolean; setActive:(v:boolean)=>void; rangeConfig:Config; setRangeConfig:(v:Config)=>void; signalConfig:Config; setSignalConfig:(v:Config)=>void; riskConfig:Config; setRiskConfig:(v:Config)=>void };
export function BalancedForm(p:Props) {
 const number=(config:Config,set:(v:Config)=>void,key:string,label:string,value:number,min:number,max:number,step=.1,percent=false)=><Field key={key} label={label}><input type="number" min={min} max={max} step={step} value={Number(config[key]??value)*(percent?100:1)} onChange={e=>set({...config,[key]:e.target.value===""?"":Number(e.target.value)/(percent?100:1)})}/></Field>;
 const r=p.rangeConfig,s=p.signalConfig,k=p.riskConfig;
 return <div className="space-y-5">
 <section className="panel settings-panel"><p className="eyebrow">CONFIRMED RANGE / V2</p><h2>Balance first. Confirmation next.</h2><div className="settings-fields"><Field label="Playbook name"><input value={p.name} maxLength={80} placeholder="Confirmed range" onChange={e=>p.setName(e.target.value)}/></Field><Field label="Status"><select value={p.active?"active":"paused"} onChange={e=>p.setActive(e.target.value==="active")}><option value="active">Active</option><option value="paused">Paused</option></select></Field></div><p className="muted" style={{marginTop:18}}>Weekly / daily: context. Highest clean 4H / 1H range: boundaries. 15m / 5m / 1m: entry confirmation. Opposing higher-timeframe trends block entries. 30m remains available for inspection.</p></section>
 <section className="panel settings-panel"><p className="eyebrow">01 / VALID RANGE</p><h2>Repeated rejection, without a trend.</h2><div className="settings-fields">
 {number(r,p.setRangeConfig,"lookback","Structure lookback · candles",100,20,500,1)}
 {number(r,p.setRangeConfig,"pivot_window","Confirmed swing · bars each side",2,1,10,1)}
 {number(r,p.setRangeConfig,"min_touches","Minimum touches on each side",2,2,10,1)}
 {number(r,p.setRangeConfig,"touch_tolerance","Touch tolerance · % of range",.05,.1,15,.1,true)}
 {number(r,p.setRangeConfig,"min_height_atr","Minimum height · ATR",2.5,.1,20)}
 {number(r,p.setRangeConfig,"adx_max","Range ADX below",22,1,99)}
 {number(r,p.setRangeConfig,"adx_trend","Strong trend ADX at least",25,1,100)}
 {number(r,p.setRangeConfig,"ema_slope_atr","EMA flatness · ATR per bar",.15,0,2,.01)}
 </div><p className="muted" style={{marginTop:18}}>ATR / ADX use 14 periods. EMA20 and EMA50 slopes use five closed bars. Three successive higher highs + higher lows, or lower highs + lower lows, reject balance. Accepted boundaries stay fixed until a held breakout.</p></section>
 <section className="panel settings-panel"><p className="eyebrow">02 / CONFIRMED ENTRY</p><h2>Wait for price to reclaim the edge.</h2><div className="settings-fields">
 <Field label="Accepted confirmation"><select value={String(s.confirmation??"sfp_or_rejection")} onChange={e=>p.setSignalConfig({...s,confirmation:e.target.value})}><option value="sfp">SFP only</option><option value="sfp_or_rejection">SFP or rejection wick</option><option value="any">SFP, rejection, engulfing or structure shift</option></select></Field>
 {number(s,p.setSignalConfig,"edge_zone","Extreme zone · % of range",.15,1,25,1,true)}
 {number(s,p.setSignalConfig,"reclaim_bars","SFP reclaim within · candles",3,1,3,1)}
 {number(s,p.setSignalConfig,"volume_multiple","Sweep volume / prior 20 average · 0 = off",0,0,10,.1)}
 </div><p className="muted" style={{marginTop:18}}>A+ marks a range-boundary sweep and close back inside, not a probability of winning. Long confirmations must remain below midpoint; shorts above. Rejection: wick at least twice the body and half the candle. Structure shift: close beyond the previous three-bar high / low.</p></section>
 <section className="panel settings-panel"><p className="eyebrow">03 / EXIT PLAN</p><h2>Midpoint, then the opposite edge.</h2><div className="settings-fields">
 {number(k,p.setRiskConfig,"stop_buffer_atr","Beyond sweep wick / range · ATR buffer",.375,.01,3,.025)}
 {number(k,p.setRiskConfig,"breakout_buffer_atr","Breakout close beyond boundary · ATR",.375,0,3,.025)}
 {number(k,p.setRiskConfig,"hold_closes","Consecutive closes to confirm breakout",2,1,5,1)}
 {number(k,p.setRiskConfig,"tp1_fraction","Close at midpoint · % of position",.5,1,99,1,true)}
 {number(k,p.setRiskConfig,"target_inset","TP2 inside opposite edge · % of range",.02,0,24,1,true)}
 {number(k,p.setRiskConfig,"min_reward_risk","Minimum weighted reward / risk after costs",2,2,20,.1)}
 {number(k,p.setRiskConfig,"risk_per_trade","Simulated equity risk · %",.01,.1,10,.1,true)}
 {number(k,p.setRiskConfig,"max_leverage","Maximum simulated leverage",3,1,100,1)}
 </div><p className="muted" style={{marginTop:18}}>TP1 moves the remaining stop to entry; fees may still produce a small loss. TP2 closes the rest. No breakout runner. A break-and-retest is a separate setup, not a range entry. Live risk previews assume 10,000 quote-currency equity.</p></section></div>;
}
