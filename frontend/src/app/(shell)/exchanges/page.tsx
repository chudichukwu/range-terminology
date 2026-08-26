import { PageHeader, ContentContainer } from "@/components/ui/PageHeader";
import { PlaceholderPageShell } from "@/components/state/StatePrimitives";

export default function ExchangesPage() {
  return (
    <>
      <PageHeader
        title="Exchanges"
        description="Four capabilities distinguished: connection/credentials · market-data · account/balance · execution. DEX is a separate future concern."
        breadcrumbs={[{ label: "Exchanges" }]}
      />
      <ContentContainer>
        <PlaceholderPageShell
          title="Exchanges — foundation"
          description="Connection cards, CEX API-key flow, capability indicators and paper-mode banner arrive in the Exchanges phase. No live execution, no DEX design here."
        />
      </ContentContainer>
    </>
  );
}
