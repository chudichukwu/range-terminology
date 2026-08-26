"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/state/StatePrimitives";
import { StrategyForm, StrategySummary } from "@/components/strategy/StrategyForm";
import { api, ApiError } from "@/lib/api/client";

export default function NewStrategyPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [active, setActive] = useState(true);
  const [rangeConfig, setRangeConfig] = useState<Record<string, unknown>>({ mode: "structural", lookback: 100, pivot_window: 2, max_drift_ratio: 0.5 });
  const [signalConfig, setSignalConfig] = useState<Record<string, unknown>>({ lower_edge_zone: 0.25, upper_edge_zone: 0.25, confirmation_policy: "optional" });
  const [riskConfig, setRiskConfig] = useState<Record<string, unknown>>({
    risk_per_trade: 0.01,
    stop_method: "range",
    range_stop_buffer: 0.05,
    atr_multiplier: 2,
    fixed_stop_percent: 0.02,
    target_method: "opposite_range_edge",
    range_target_fraction: 0.9,
    fixed_rr_ratio: 3,
    min_reward_risk: 2,
    max_drawdown: 0.2,
    max_daily_drawdown: 0.05,
    max_consecutive_losses: 3,
    max_open_positions: 5,
    max_leverage: 1,
    fee_rate: 0.001,
    slippage_rate: 0.0005
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ message: string; requestId: string } | null>(null);

  const payloadJson = JSON.stringify({ range_config: rangeConfig, signal_config: signalConfig, risk_config: riskConfig }, null, 2);

  const onSave = async () => {
    setError(null);
    if (!name.trim()) {
      setError({ message: "Strategy name is required (1–80).", requestId: "" });
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await api.createStrategy({ name: name.trim(), payload: { range_config: rangeConfig, signal_config: signalConfig, risk_config: riskConfig }, active });
      router.push(`/strategies/${data.id}`);
    } catch (e) {
      if (e instanceof ApiError) setError({ message: `${e.code}: ${e.message}`, requestId: e.requestId });
      else setError({ message: String(e), requestId: "" });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <PageHeader
        title="New Strategy"
        description="Configure a reproducible strategy — backend validates. No engine logic runs in React."
        breadcrumbs={[{ label: "Strategies", href: "/strategies" }, { label: "New" }]}
        actions={
          <div className="flex gap-2">
            <Link href="/strategies"><Button variant="ghost">Cancel</Button></Link>
            <Button variant="primary" onClick={onSave} disabled={submitting || !name.trim()}>{submitting ? "Creating…" : "Create strategy"}</Button>
          </div>
        }
      />
      <ContentContainer>
        {error && <div className="mb-3"><ErrorState message={error.message} requestId={error.requestId} /></div>}
        <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
          <StrategyForm name={name} setName={setName} active={active} setActive={setActive} rangeConfig={rangeConfig} setRangeConfig={setRangeConfig} signalConfig={signalConfig} setSignalConfig={setSignalConfig} riskConfig={riskConfig} setRiskConfig={setRiskConfig} />
          <div>
            <StrategySummary name={name} active={active} rangeConfig={rangeConfig} signalConfig={signalConfig} riskConfig={riskConfig} payloadJson={payloadJson} />
            <div className="mt-3 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-3">
              <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Next steps</div>
              <div className="mt-2 flex flex-col gap-1.5 text-[11px] text-[var(--color-text-secondary)]">
                <span>After creation → Pair Analysis with <span className="mono text-[var(--color-text-primary)]">?strategy_id=…&symbol=BTC/USDT</span> (existing analysis endpoint, no duplication).</span>
                <span>Backtest handoff via <span className="mono">/backtests</span> route when Phase 14 lands (deep-link only now).</span>
              </div>
            </div>
          </div>
        </div>
      </ContentContainer>
    </>
  );
}
