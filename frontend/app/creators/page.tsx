"use client";
import Link from "next/link";
import { ArrowRight, Radio, Search, UserRound, Users } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Creator } from "@/lib/types";
import { Empty, ErrorState, Loading, PageHeader, Status, Toggle, formatNumber } from "@/components/ui";
import { useToast } from "@/components/Toast";

export default function CreatorsPage() {
  const toast = useToast(); const [creators, setCreators] = useState<Creator[]>(); const [q, setQ] = useState(""); const [error, setError] = useState("");
  const load = useCallback(() => api<Creator[]>(`/creators${q ? `?q=${encodeURIComponent(q)}` : ""}`).then(setCreators).catch(e => setError(e.message)), [q]);
  useEffect(() => { const timeout = setTimeout(load, 250); return () => clearTimeout(timeout); }, [load]);
  async function toggle(creator: Creator) { try { await api(`/creators/${creator.id}`, { method: "PATCH", body: JSON.stringify({ monitored: !creator.monitored }) }); toast(creator.monitored ? "Monitoring paused" : "Creator monitoring enabled"); load(); } catch(e) { toast((e as Error).message, "error"); } }
  return <><PageHeader eyebrow="Source intelligence" title="Creators" description="Follow the people and channels that consistently generate material worth watching." actions={<div className="search-mini"><Search size={16}/><input value={q} onChange={e => setQ(e.target.value)} placeholder="Find creator…"/></div>}/>
    {error && !creators ? <ErrorState message={error} retry={load}/> : !creators ? <Loading/> : creators.length ? <div className="creator-grid">{creators.map(creator => <article className="creator-card" key={creator.id}><div className="creator-top"><div className="avatar">{creator.avatar_url ? <img src={creator.avatar_url} alt=""/> : <UserRound size={24}/>}</div><div><h2>{creator.name}</h2><p><span>{creator.platform}</span> · {formatNumber(creator.follower_count)} followers</p></div><Toggle checked={creator.monitored} onChange={() => toggle(creator)} label={`Monitor ${creator.name}`}/></div><div className="creator-stats"><div><span>Discoveries</span><strong>{formatNumber(creator.discovery_count)}</strong></div><div><span>Frequency</span><strong>{creator.discovery_frequency}</strong></div><div><span>Sources</span><Status value={creator.source_permission}/></div></div><div className="tag-row">{creator.tags?.length ? creator.tags.map(tag => <span key={tag}>{tag}</span>) : <span className="quiet">No tags</span>}</div><Link className="card-link" href={`/creators/${creator.id}`}>Open creator workspace <ArrowRight size={15}/></Link></article>)}</div> : <Empty title="No monitored creators" detail="Follow a creator from a Discover result to build this watchlist." action={<Link href="/discover" className="button lime small"><Radio size={15}/> Discover creators</Link>}/>} 
  </>;
}

