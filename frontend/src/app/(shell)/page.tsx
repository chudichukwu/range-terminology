import { Suspense } from "react";
import { DashboardClient } from "@/components/dashboard/DashboardClient";
import { LoadingState } from "@/components/state/StatePrimitives";

export const dynamic = "force-dynamic";

export default function DashboardPage() {
  return (
    <Suspense fallback={<div className="p-6"><LoadingState label="Loading dashboard" /></div>}>
      <DashboardClient />
    </Suspense>
  );
}
