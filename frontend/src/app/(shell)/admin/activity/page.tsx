import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { PlaceholderPageShell } from "@/components/state/StatePrimitives";

export default function AdminActivityPage() {
  return (
    <>
      <PageHeader title="Trading Activity" description="Aggregate oversight — trades, wins/losses, backtest runs (OWNER)." breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Activity" }]} />
      <ContentContainer>
        <PlaceholderPageShell title="Admin · Activity — foundation" description="Trading activity overview arrives in the Admin phase. Aggregated via GET /admin/trading-activity as provided by backend." />
      </ContentContainer>
    </>
  );
}
