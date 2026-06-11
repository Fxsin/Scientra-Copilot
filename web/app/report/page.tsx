"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FileText, ExternalLink, Loader2, AlertCircle, TrendingUp, SearchCheck, Share2, BarChart3 } from "lucide-react";
import { getReport } from "@/lib/api";
import type { ReportResponse } from "@/lib/types";

export default function ReportPage() {
  const router = useRouter();
  const [data, setData] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getReport().then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="max-w-4xl mx-auto py-16 text-center"><Loader2 className="size-6 animate-spin mx-auto text-slate-300" /></div>;
  if (error) return <div className="max-w-4xl mx-auto py-16 text-center"><AlertCircle className="size-8 text-red-300 mx-auto mb-2" /><p className="text-sm text-red-500">{error}</p></div>;
  if (!data || data.status === "cache_missing") return (
    <div className="max-w-4xl mx-auto py-16 text-center"><FileText className="size-8 text-slate-300 mx-auto mb-2" /><h1 className="text-xl font-bold text-slate-700">Library Intelligence Report</h1><p className="text-sm text-slate-400 mt-2">Research Map cache is not available.</p></div>
  );

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-16">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1"><FileText className="size-5 text-blue-500" /><h1 className="text-2xl font-bold tracking-tight text-slate-800">{data.report_title}</h1></div>
        <p className="text-sm text-slate-400">A data-driven summary of your literature library, research map, hotspots, gaps, and evidence network.</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
        {[{l:"Papers",v:data.coverage_summary?.paper_count},{l:"Facets",v:data.coverage_summary?.facet_count},{l:"Subtopics",v:data.coverage_summary?.subtopic_count},{l:"Trending",v:data.hotspots_summary?.trending_topic_count},{l:"Gaps",v:data.research_gaps_summary?.gap_count},{l:"Evidence",v:data.evidence_summary?.total_chunks}].map(s=>(
          <div key={s.l} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-center"><p className="text-lg font-bold text-slate-700">{s.v||"—"}</p><p className="text-[9px] text-slate-400 uppercase">{s.l}</p></div>
        ))}
      </div>

      {/* Executive Summary */}
      <div className="rounded-xl border border-slate-200/50 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-700 mb-2">Executive Summary</h2>
        {(data.executive_summary||[]).map((s,i)=><p key={i} className="text-[11px] text-slate-600 leading-relaxed">· {s}</p>)}
      </div>

      {/* Sections */}
      {(data.sections||[]).map((sec) => (
        <div key={sec.id} className="rounded-xl border border-slate-200/50 bg-white p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-slate-700">{sec.title}</h2>
            <button onClick={() => router.push(`/${sec.id==="research_map"?"research-map":sec.id==="hotspots"?"hotspots":sec.id==="gaps"?"research-gaps":sec.id==="network"?"knowledge-network":"research-map"}`)} className="text-[10px] text-blue-600 hover:underline flex items-center gap-1"><ExternalLink className="size-2.5"/> View full</button>
          </div>
          <p className="text-[11px] text-slate-500 mb-2">{sec.summary}</p>
          {sec.id === "research_map" && sec.items?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {(sec.items as any[]).slice(0,5).map((f:any,i:number)=>(
                <span key={i} className="text-[10px] px-2 py-1 rounded bg-indigo-50 text-indigo-600 border border-indigo-100">{f.label}: {f.paper_count}p</span>
              ))}
            </div>
          )}
          {sec.id === "hotspots" && sec.items?.length > 0 && (
            <div className="space-y-1">
              {(sec.items as any[]).slice(0,3).map((t:any,i:number)=>(
                <div key={i} className="text-[10px] text-slate-600">{t.name} <span className="text-slate-400">({t.facet_label}, {Math.round((t.recent_ratio||0)*100)}% recent)</span></div>
              ))}
            </div>
          )}
          {sec.id === "gaps" && sec.items?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {(sec.items as any[]).slice(0,4).map((g:any,i:number)=>(
                <span key={i} className="text-[10px] px-2 py-1 rounded bg-red-50 text-red-600 border border-red-100">{g.title?.slice(0,60)}</span>
              ))}
            </div>
          )}
          {sec.id === "actions" && sec.items?.length > 0 && (
            <div className="space-y-1">
              {(sec.items as any[]).map((a:any,i:number)=>(
                <p key={i} className="text-[10px] text-slate-600">· {a.text||a}</p>
              ))}
            </div>
          )}
        </div>
      ))}

      <p className="text-center text-[9px] text-slate-300">Generated {data.generated_at?.slice(0,19).replace("T"," ")} · {data.source}</p>
    </div>
  );
}
