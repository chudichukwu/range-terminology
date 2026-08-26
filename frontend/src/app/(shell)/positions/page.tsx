import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { PlaceholderPageShell } from "@/components/state/StatePrimitives";

export default function PositionsPage() {
  return (
    <>
      <PageHeader title="Positions" description="Operational/current trading state — separate from Journal historical trades. Paper/read-only in Phase 9." breadcrumbs={[{ label: "Positions" }]} />
      <ContentContainer>
        <PlaceholderPageShell title="Positions — foundation" description="Positions table and execution preview arrive in the Positions/Execution phase. System remains PAPER · READ-ONLY." />
      </ContentContainer>
    </>
  );
}
