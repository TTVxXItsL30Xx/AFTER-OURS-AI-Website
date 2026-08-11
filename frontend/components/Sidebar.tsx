"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart3, Compass, Film, FolderOpen, Gauge, Menu, Radio, Send, Settings, Sparkles, Users, X } from "lucide-react";
import { useState } from "react";

const nav = [
  ["Overview", "/", Gauge], ["Discover", "/discover", Compass], ["Creators", "/creators", Users], ["Sources", "/sources", FolderOpen],
  ["Studio", "/studio", Film], ["Queue", "/queue", Send], ["Published", "/published", Radio], ["Analytics", "/analytics", BarChart3], ["Settings", "/settings", Settings],
] as const;

export function Sidebar() {
  const pathname = usePathname(); const [open, setOpen] = useState(false);
  return <>
    <button className="mobile-menu" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu size={20}/></button>
    {open && <button className="nav-backdrop" onClick={() => setOpen(false)} aria-label="Close navigation"/>}
    <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
      <div className="brand-row"><Link href="/" className="brand" onClick={() => setOpen(false)}><span className="brand-mark"><Sparkles size={16}/></span><span>AFTER <b>OURS</b></span></Link><button className="mobile-close" onClick={() => setOpen(false)} aria-label="Close navigation"><X size={18}/></button></div>
      <div className="nav-label">Workspace</div>
      <nav>{nav.map(([label, href, Icon]) => { const active = href === "/" ? pathname === "/" : pathname.startsWith(href); return <Link key={href} href={href} className={`nav-item ${active ? "active" : ""}`} onClick={() => setOpen(false)}><Icon size={18}/><span>{label}</span>{active && <i/>}</Link>; })}</nav>
      <div className="sidebar-spacer"/>
      <div className="system-chip"><span className="live-dot"/><div><strong>Local workspace</strong><small>Self-hosted control plane</small></div><Activity size={16}/></div>
      <div className="sidebar-foot">AFTER OURS <span>V1</span></div>
    </aside>
  </>;
}

