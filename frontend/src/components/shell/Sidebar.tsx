"use client";
import {useEffect,useState} from "react";
import {api} from "@/lib/api/client";
import {NavIcon} from "./NavIcon";
import Link from "next/link";
import { usePathname } from "next/navigation";
const NAV = [{href:"/ranges",label:"My ranges",icon:""},{ href: "/journal", label: "Journal", icon: "" },{ href: "/", label: "Scanner", icon: "⌘" }, { href: "/watchlists", label: "Watchlists", icon: "☷" }, { href: "/alerts", label: "Alerts", icon: "◉" }, { href: "/backtests", label: "Backtests", icon: "↗" }, { href: "/strategies", label: "Strategies", icon: "◇" }];
export function Sidebar({ collapsed, onToggle, mobileOpen, onMobileClose }: { collapsed: boolean; onToggle: () => void; mobileOpen: boolean; onMobileClose: () => void }) {
 const path = usePathname();
 const [owner,setOwner]=useState(false);
 useEffect(()=>{api.me().then(({data})=>setOwner(data.role==="owner")).catch(()=>setOwner(false));},[path]);
 const compact = collapsed && !mobileOpen;
 const content = <><Link href="/" className="brand" onClick={onMobileClose}><span className="brand-mark" aria-hidden="true">G</span>{!compact && <span>Grand<span className="brand-dot">blue</span></span>}</Link><div className="sidebar-caption">{!compact && "WORKSPACE"}</div><nav aria-label="Primary navigation">{(owner ? [...NAV,{href:"/admin",label:"Admin",icon:"⚙"}] : NAV).map(n => <Link key={n.href} href={n.href} title={n.label} onClick={onMobileClose} className={`nav-link ${(n.href === "/" ? path === "/" : path.startsWith(n.href)) ? "active" : ""}`}><span className="nav-icon"><NavIcon name={n.href}/></span>{!compact && <span>{n.label}</span>}</Link>)}</nav><div className="sidebar-bottom">{!compact && <><div className="sidebar-note"><span className="live-dot" /> Research & alerts<p>Your market. Your rules.<br/>You place the trades.</p></div><Link href="/me" className="nav-link" onClick={onMobileClose}>◎ <span>Account</span></Link></>}<button className="collapse-button" onClick={onToggle} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>{collapsed ? "→" : "← Collapse"}</button></div></>;
 return <><aside className={`desktop-sidebar ${collapsed ? "collapsed" : ""}`}>{content}</aside>{mobileOpen && <div className="mobile-nav-overlay"><button className="nav-backdrop" onClick={onMobileClose} aria-label="Close navigation" /><aside className="mobile-sidebar"><button className="mobile-close" onClick={onMobileClose} aria-label="Close navigation">×</button>{content}</aside></div>}</>;
}
