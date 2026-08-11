"use client";
import Link from "next/link";
import { Activity, ArrowRight, Compass, Film, FolderPlus, Radio, Send, Sparkles, Users } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { DiscoveredVideo, ProcessingJob, PublishingJob, RenderedClip } from "@/lib/types";
import { Empty, ErrorState, Loading, PageHeader, Panel, SetupNotice, Status, formatDate, formatNumber, relativeDate } from "@/components/ui";

type Overview = { stats: Record<string, number>; recent_discoveries: DiscoveredVideo[]; recent_clips: RenderedClip[]; publishing_status: PublishingJob[]; activity: ProcessingJob[] };
type Health = { status: string; checks: Record<string, {status: string}> };
type Settings = { checklist: Array<{label: string; ok: boolean; optional: boolean}> };
const statMeta = [
  ["discoveries", "Total discoveries", Compass], ["candidates", "Candidates", Sparkles], ["clips_ready", "Clips ready", Film], ["queued_posts", "Queued posts", Send], ["published_posts", "Published", Radio], ["creators", "Creators", Users],
] as const;

export default function OverviewPage() {
  const [data, setData] = useState<Overview>(); const [health, setHealth] = useState<Health>(); const [checklist, setChecklist] = useState<Settings["checklist"]>([]); const [error, setError] = useState("");
  const load = useCallback(() => Promise.all([api<Overview>("/overview"), api<Health>("/health"), api<Settings>("/settings")]).then(([overview, system, config]) => { setData(overview); setHealth(system); setChecklist(config.checklist); setError(""); }).catch(e => setError(e.message)), []);
  useEffect(() => { void load(); }, [load]);
  if (error) return <ErrorState message={error} retry={load}/>;
  if (!data) return <Loading/>;
  return <>
    <PageHeader eyebrow="Command centre" title="The work after hours." description="Discover opportunities, shape the strongest moments, and move every clip from source to publish." actions={<><Link className="button ghost" href="/sources"><FolderPlus size={16}/> Add source</Link><Link className="button lime" href="/discover"><Compass size={16}/> Start discovering</Link></>}/>
    <SetupNotice items={checklist}/>
    <div className="stat-grid">{statMeta.map(([key, label, Icon], index) => <div className={`stat-card ${index === 1 ? "featured" : ""}`} key={key}><div className="stat-top"><span>{label}</span><Icon size={17}/></div><strong>{formatNumber(data.stats[key])}</strong><small>{key === "discoveries" ? "All-time database total" : key === "candidates" ? "Ready for editorial review" : "Live from your workspace"}</small></div>)}</div>
    <div className="overview-grid">
      <Panel title="Opportunity radar" hint="Newest discoveries ranked by current signal" action={<Link href="/discover" className="text-link">View discover <ArrowRight size={14}/></Link>}>
        {data.recent_discoveries.length ? <div className="compact-list">{data.recent_discoveries.map(video => <div className="compact-row" key={video.id}>{video.thumbnail_url ? <img src={video.thumbnail_url} alt=""/> : <div className="thumb-fallback"><Film/></div>}<div className="compact-copy"><strong>{video.title}</strong><span>{video.creator_name} · {relativeDate(video.published_at)}</span></div><div className="score"><span>{Math.round(video.opportunity_score)}</span><small>score</small></div></div>)}</div> : <Empty title="No discoveries yet" detail="Connect YouTube Discovery, then run your first topic search." action={<Link href="/discover" className="button lime small">Open Discover</Link>}/>} 
      </Panel>
      <Panel title="System pulse" hint="API, storage and processing readiness">
        <div className="health-list">{health && Object.entries(health.checks).map(([name, check]) => <div key={name}><span><i className={check.status === "healthy" ? "ok" : "off"}/>{name === "postgresql" ? "PostgreSQL" : name.charAt(0).toUpperCase()+name.slice(1)}</span><Status value={check.status}/></div>)}</div>
        <Link href="/settings" className="panel-link">Open system settings <ArrowRight size={15}/></Link>
      </Panel>
      <Panel title="Processing activity" hint="Latest jobs across the production pipeline" className="wide">
        {data.activity.length ? <div className="job-table">{data.activity.map(job => <div key={job.id}><div className="job-icon"><Activity size={16}/></div><div><strong>{job.job_type.replaceAll("_", " ")}</strong><span>{job.message || job.entity_type || "Waiting for worker"}</span></div><div className="progress"><i style={{width: `${job.progress}%`}}/></div><Status value={job.status}/><time>{formatDate(job.created_at)}</time></div>)}</div> : <Empty title="The worker queue is clear" detail="Ingest, transcription, analysis and render jobs will appear here."/>}
      </Panel>
    </div>
  </>;
}
