import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { PlaceholderPageShell } from "@/components/state/StatePrimitives";

export default function RiskPage() {
  return (
    <>
      <PageHeader title="Risk" description="Account gates and sizing — backend-provided gates rendered read-only." breadcrumbs={[{ label: "Risk" }]} />
      <ContentContainer>
        <PlaceholderPageShell title="Risk — foundation" description="Gate progress, PAPER preview and amber blocked states arrive in the Risk phase. No frontend gate math." />
      </ContentContainer>
    </>
  );
}
