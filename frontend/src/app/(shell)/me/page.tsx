"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader, ContentContainer, Card } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState } from "@/components/state/StatePrimitives";
import { api, ApiError } from "@/lib/api/client";
import type { UserOut } from "@/lib/api/types";

export default function MePage() {
  const router = useRouter();
  const [user, setUser] = useState<UserOut | null>(null);
  const [error, setError] = useState<{ message: string; requestId: string; code: string } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .me()
      .then(({ data }) => setUser(data))
      .catch((e) => {
        if (e instanceof ApiError) setError({ message: e.message, requestId: e.requestId, code: e.code });
        else setError({ message: String(e), requestId: "", code: "unknown" });
      })
      .finally(() => setLoading(false));
  }, []);

  const onLogout = async () => {
    try {
      await api.logout();
    } catch {
      // ignore backend logout failure, still clear local
    }
    localStorage.removeItem("rt.accessToken");
    router.push("/login");
  };

  if (loading) {
    return (
      <>
        <PageHeader title="Account" breadcrumbs={[{ label: "Account" }]} description="Session via Authorization: Bearer — backend validates." />
        <ContentContainer>
          <LoadingState label="Loading account" />
        </ContentContainer>
      </>
    );
  }

  if (error) {
    return (
      <>
        <PageHeader title="Account" breadcrumbs={[{ label: "Account" }]} description="Session via Authorization: Bearer — backend validates." />
        <ContentContainer>
          <ErrorState message={error.message} requestId={error.requestId} onRetry={() => window.location.reload()} />
          <div className="mt-3 mono text-[11px] text-[var(--color-text-tertiary)]">Code: {error.code} · unauthenticated → sign in again.</div>
          <div className="mt-3">
            <Button variant="primary" onClick={() => router.push("/login")}>Sign in</Button>
          </div>
        </ContentContainer>
      </>
    );
  }

  if (!user) return null;

  return (
    <>
      <PageHeader
        title="Account"
        description="Your workspace profile and sign-in session."
        breadcrumbs={[{ label: "Account" }]}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant={user.role === "owner" ? "success" : "neutral"}>{user.role}</Badge>
            <Badge variant={user.active ? "success" : "neutral"}>{user.active ? "active" : "inactive"}</Badge>
          </div>
        }
      />
      <ContentContainer>
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <Card className="p-4">
            <h2 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Your profile</h2>
            <div className="mt-3 grid gap-3 md:grid-cols-2">

              <Fact label="Email" value={user.email} />
              <Fact label="Role" value={user.role} mono />
              <Fact label="Active" value={String(user.active)} mono />
              <Fact label="Created" value={new Date(user.created_at_ms).toLocaleString()} mono />
              <Fact label="Updated" value={new Date(user.updated_at_ms).toLocaleString()} mono />
              <Fact label="Last login" value={user.last_login_at_ms ? new Date(user.last_login_at_ms).toLocaleString() : "—"} mono />
            </div>

          </Card>
          <div className="space-y-3">
            <Card className="p-3">
              <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Session</h3>
              <div className="mono mt-1 text-[11px] text-[var(--color-text-secondary)]">
                Sign out of this browser. Your watchlists, playbooks and research will stay saved.
              </div>
              <Button variant="danger" className="mt-3 w-full" onClick={onLogout}>
                Log out
              </Button>

            </Card>
            <Card className="p-3">
              <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Authorization</h3>
              <div className="mono mt-1 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">Your account determines which workspace resources you can access.</div>
            </Card>
          </div>
        </div>
      </ContentContainer>
    </>
  );
}

function Fact({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">{label}</div>
      <div className={`${mono ? "mono" : ""} mt-0.5 text-[12px] font-medium text-[var(--color-text-primary)] break-all`}>{value}</div>
    </div>
  );
}
