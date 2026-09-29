"use client";
import {useEffect, useState} from "react";
import {usePathname, useRouter} from "next/navigation";
import {api} from "@/lib/api/client";
export default function AdminLayout({children}: {children: React.ReactNode}) {
 const [allowed, setAllowed] = useState(false);
 const router = useRouter(), path = usePathname();
 useEffect(() => {
  let active = true;
  setAllowed(false);
  api.me().then(({data}) => {if (!active) return; if (data.role === "owner") setAllowed(true); else router.replace("/");}).catch(() => {if(active) router.replace("/login");});
  return () => {active = false;};
 }, [path, router]);
 return allowed ? children : <div className="workspace" role="status">Checking access…</div>;
}
