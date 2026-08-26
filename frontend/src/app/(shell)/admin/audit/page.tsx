import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { PlaceholderPageShell } from "@/components/state/StatePrimitives";

export default function AdminAuditPage() {
  return (
    <>
      <PageHeader title="Audit Log" description="Append-only security log — actor, action, resource, outcome." breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Audit" }]} />
      <ContentContainer>
        <PlaceholderPageShell title="Admin · Audit — foundation" description="Audit table, filters and virtualized rows arrive in the Admin phase. No delete affordance (append-only)." />
      </ContentContainer>
    </>
  );
}
