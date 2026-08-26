import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { PlaceholderPageShell } from "@/components/state/StatePrimitives";

export default function AlertsPage() {
  return (
    <>
      <PageHeader title="Alerts" description="Activity feed — range/signal/quality events. RANGING-triggered alerts are planned/future." breadcrumbs={[{ label: "Alerts" }]} />
      <ContentContainer>
        <PlaceholderPageShell title="Alerts — foundation" description="Feed, filters and empty states arrive later. Planned alert types remain labeled as such." />
      </ContentContainer>
    </>
  );
}
