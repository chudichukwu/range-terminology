import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { PlaceholderPageShell } from "@/components/state/StatePrimitives";

export default function BacktestsPage() {
  return (
    <>
      <PageHeader title="Backtests" description="Research runs — deterministic replay over historical candles, backend-provided results." breadcrumbs={[{ label: "Backtests" }]} />
      <ContentContainer>
        <PlaceholderPageShell title="Backtests — foundation" description="Config form, run history, result detail with regime/zone breakdowns and comparison are deferred to the Backtesting phase." />
      </ContentContainer>
    </>
  );
}
