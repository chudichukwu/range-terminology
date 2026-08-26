import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { PlaceholderPageShell } from "@/components/state/StatePrimitives";

export default function AdminPage() {
  return (
    <>
      <PageHeader title="Admin" description="System overview — OWNER only. Server enforces role; sidebar merely hides." breadcrumbs={[{ label: "Admin" }]} />
      <ContentContainer>
        <PlaceholderPageShell title="Admin — foundation" description="Overview KPIs (user/dataset counts, provider status) and links to Users/Health/Audit arrive in the Admin phase. Permission denied state is established." />
      </ContentContainer>
    </>
  );
}
