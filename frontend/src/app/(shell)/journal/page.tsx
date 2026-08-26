import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { PlaceholderPageShell } from "@/components/state/StatePrimitives";

export default function JournalPage() {
  return (
    <>
      <PageHeader title="Journal" description="Historical trades, performance and research — distinct from operational Positions." breadcrumbs={[{ label: "Journal" }]} />
      <ContentContainer>
        <PlaceholderPageShell title="Journal — foundation" description="Statistics cards, equity curve (trade-close granularity), trade table and regime segmentation are deferred to the Journal phase. Null stats render as — per backend." />
      </ContentContainer>
    </>
  );
}
