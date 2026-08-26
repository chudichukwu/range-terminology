import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { PlaceholderPageShell } from "@/components/state/StatePrimitives";

export default function BacktestRunPage({ params }: { params: { runId: string } }) {
  return (
    <>
      <PageHeader title={`Backtest ${params.runId.slice(0, 8)}`} description="Run detail placeholder — stats, equity curve and trades will be rendered from backend BacktestResult." breadcrumbs={[{ label: "Backtests", href: "/backtests" }, { label: params.runId.slice(0, 8) }]} />
      <ContentContainer>
        <PlaceholderPageShell title="Backtest run — foundation" description="Dynamic run route established. Data and comparison views arrive later." />
      </ContentContainer>
    </>
  );
}
