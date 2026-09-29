"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/state/StatePrimitives";
import { StrategyForm, StrategySummary, RANGE_TOUCH_PRESET } from "@/components/strategy/StrategyForm";
import { api, ApiError } from "@/lib/api/client";

export default function NewStrategyPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [active, setActive] = useState(true);
  const [rangeConfig, setRangeConfig] = useState<Record<string, unknown>>({ ...RANGE_TOUCH_PRESET.range_config });
  const [signalConfig, setSignalConfig] = useState<Record<string, unknown>>({ ...RANGE_TOUCH_PRESET.signal_config });
  const [riskConfig, setRiskConfig] = useState<Record<string, unknown>>({ ...RANGE_TOUCH_PRESET.risk_config });
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
        title="New playbook"
        description="Start with your confirmed-range rules, then adjust the settings you want to test."
        breadcrumbs={[{ label: "Strategies", href: "/strategies" }, { label: "New" }]}
        actions={
          <div className="flex gap-2">
            <Link href="/strategies"><Button variant="ghost">Cancel</Button></Link>
            <Button variant="primary" onClick={onSave} disabled={submitting || !name.trim()}>{submitting ? "Creating…" : "Create playbook"}</Button>
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
                <span>Select this playbook in your scanner or alerts to use these rules.</span>
                <span>Run a backtest to review historical trades, costs, and the two-stage exits.</span>
              </div>
            </div>
          </div>
        </div>
      </ContentContainer>
    </>
  );
}
