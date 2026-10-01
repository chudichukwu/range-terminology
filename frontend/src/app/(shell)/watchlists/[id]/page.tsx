import { Scanner } from "@/components/workspace/Scanner";
export default async function WatchlistPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <Scanner initialId={id} />; }
