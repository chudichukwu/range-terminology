import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { PlaceholderPageShell } from "@/components/state/StatePrimitives";

export default function AdminUsersPage() {
  return (
    <>
      <PageHeader title="Users" description="OWNER-only user management — activate/deactivate, role change, revoke sessions." breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Users" }]} />
      <ContentContainer>
        <PlaceholderPageShell title="Admin · Users — foundation" description="User table, creation dialog and action confirmations arrive in the Admin phase. All checks are server-side." />
      </ContentContainer>
    </>
  );
}
