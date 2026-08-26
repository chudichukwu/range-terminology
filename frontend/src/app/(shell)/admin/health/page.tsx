import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { PlaceholderPageShell } from "@/components/state/StatePrimitives";

export default function AdminHealthPage() {
  return (
    <>
      <PageHeader title="System Health" description="Schema version, engine versions, dataset counts and provider status — as returned by GET /admin/system-health." breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Health" }]} />
      <ContentContainer>
        <PlaceholderPageShell title="Admin · Health — foundation" description="Health cards and degraded/down states (amber/infra-red, not market red) arrive in the Admin phase." />
      </ContentContainer>
    </>
  );
}
