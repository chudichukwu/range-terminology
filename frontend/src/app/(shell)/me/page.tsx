import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { PlaceholderPageShell } from "@/components/state/StatePrimitives";

export default function MePage() {
  return (
    <>
      <PageHeader title="Account" description="Profile and session — read-only card for id, email, role, active status." breadcrumbs={[{ label: "Account" }]} />
      <ContentContainer>
        <PlaceholderPageShell title="Account — foundation" description="Auth state, session display and logout arrive with the authentication phase. Token handling remains via Authorization: Bearer." />
      </ContentContainer>
    </>
  );
}
