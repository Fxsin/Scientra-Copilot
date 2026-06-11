"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Layers, ExternalLink, Loader2 } from "lucide-react";
import { getResearchMap } from "@/lib/api";

export default function TopicExplorerPage() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getResearchMap().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="max-w-4xl mx-auto py-16 text-center"><Loader2 className="size-6 animate-spin mx-auto text-slate-300" /></div>;

  const fgs = data?.facet_groups || [];

  if (fgs.length === 0) return (
    <div className="max-w-4xl mx-auto py-16 text-center">
      <Layers className="size-8 text-slate-300 mx-auto mb-2" />
      <h1 className="text-xl font-bold text-slate-700">Topic Explorer</h1>
      <p className="text-sm text-slate-400 mt-2 max-w-md mx-auto">Research Map cache is not available. Rebuild the Research Map first.</p>
      <button onClick={() => router.push("/research-map")} className="mt-4 text-sm text-blue-600 hover:underline">Open Research Map</button>
      <p className="text-[10px] text-slate-300 mt-4">This module is not yet connected to your literature database.</p>
    </div>
  );

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-16">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-800 flex items-center gap-2"><Layers className="size-5 text-slate-400" />Topic Explorer</h1>
        <p className="text-sm text-slate-400 mt-1">Browse topics across research facets from your literature library.</p>
      </div>

      {fgs.map((fg: any) => (
        <div key={fg.facet} className="rounded-xl border border-slate-200/50 bg-white overflow-hidden">
          <div className="bg-slate-50 px-4 py-2.5 border-b border-slate-100 flex items-center justify-between">
            <span className="text-[13px] font-bold text-slate-700">{fg.label}</span>
            <span className="text-[10px] text-slate-400">{fg.paper_count} papers · {fg.subtopics?.length || 0} subtopics</span>
          </div>
          <div className="p-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {(fg.subtopics || []).map((st: any) => (
                <button key={st.cluster_id} onClick={() => router.push(`/research-map/topic/${st.cluster_id}`)}
                  className="text-left rounded-lg border border-slate-200 bg-white p-3 hover:shadow-sm hover:border-blue-200 transition-all group">
                  <p className="text-[12px] font-semibold text-slate-700 group-hover:text-blue-600 leading-snug">{st.name}</p>
                  <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400">
                    <span>{st.paper_count} papers</span>
                    {st.evidence_coverage > 0 && <><span className="text-slate-300">·</span><span className="text-emerald-500">Ev {st.evidence_coverage}/{st.paper_count}</span></>}
                  </div>
                  <div className="flex items-center gap-1 mt-1.5 text-[9px] text-blue-500">
                    <ExternalLink className="size-2.5" /> View details
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
