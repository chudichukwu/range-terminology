import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { PlaceholderPageShell } from "@/components/state/StatePrimitives";

export default function StrategiesPage() {
  return (
    <>
      <PageHeader title="Strategies" description="Named, reproducible configurations (range_config · signal_config · risk_config) — backend-validated." breadcrumbs={[{ label: "Strategies" }]} />
      <ContentContainer>
        <PlaceholderPageShell title="Strategies — foundation" description="Placeholder shell. Strategy list, editor (three sections mirroring backend payload), validation and config_hash display arrive later." />
      </ContentContainer>
    </>
  );
}
