import { WatchlistManager } from "@/components/workspace/WatchlistManager";
export default async function WatchlistPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <WatchlistManager initialId={id} />; }
