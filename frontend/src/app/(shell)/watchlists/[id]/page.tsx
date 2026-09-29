import { Scanner } from "@/components/workspace/Scanner";
export default function WatchlistPage({ params }: { params: { id: string } }) { return <Scanner initialId={params.id} />; }
