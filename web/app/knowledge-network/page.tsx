"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Share2, ExternalLink, Loader2, AlertCircle, Search, Hash, Filter } from "lucide-react";
import { getKnowledgeNetwork } from "@/lib/api";
import type { KnowledgeNetworkResponse, KnowledgeNode, KnowledgeEdge } from "@/lib/types";

const GROUP_COLORS: Record<string, string> = {
  Papers: "bg-slate-50 text-slate-600 border-slate-200",
  Facets: "bg-indigo-50 text-indigo-600 border-indigo-200",
  Subtopics: "bg-blue-50 text-blue-600 border-blue-200",
  Methods: "bg-purple-50 text-purple-600 border-purple-200",
  Findings: "bg-amber-50 text-amber-600 border-amber-200",
};

const EDGE_LABELS: Record<string, string> = {
  paper_belongs_to_subtopic: "Paper → Subtopic",
  paper_belongs_to_facet: "Paper → Facet",
  subtopic_belongs_to_facet: "Subtopic → Facet",
  paper_uses_method: "Uses method",
  paper_supports_finding: "Supports finding",
  method_associated_with_subtopic: "Method ↔ Subtopic",
  finding_associated_with_subtopic: "Finding ↔ Subtopic",
  subtopic_related_to_subtopic: "Subtopic ↔ Subtopic",
};

export default function KnowledgeNetworkPage() {
  const router = useRouter();
  const [data, setData] = useState<KnowledgeNetworkResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("All");
  const [search, setSearch] = useState("");

  useEffect(() => {
    getKnowledgeNetwork().then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="max-w-6xl mx-auto py-16 text-center"><Loader2 className="size-6 animate-spin mx-auto text-slate-300" /></div>;
  if (error) return <div className="max-w-6xl mx-auto py-16 text-center"><AlertCircle className="size-8 text-red-300 mx-auto mb-2" /><p className="text-sm text-red-500">{error}</p></div>;
  if (!data || data.status === "cache_missing") return (
    <div className="max-w-6xl mx-auto py-16 text-center"><Share2 className="size-8 text-slate-300 mx-auto mb-2" /><h1 className="text-xl font-bold text-slate-700">Knowledge Network</h1><p className="text-sm text-slate-400 mt-2">Research Map cache is not available.</p></div>
  );

  const groups = data.node_groups || ["Papers", "Facets", "Subtopics", "Methods", "Findings"];
  const filteredNodes = (data.nodes || []).filter((n: any) => {
    if (filter !== "All" && n.group !== filter) return false;
    if (search && !n.label.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });
  const filteredNodeIds = new Set(filteredNodes.map((n: any) => n.id));
  const filteredEdges = (data.edges || []).filter((e: any) => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target));

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-16">
      <div>
        <div className="flex items-center gap-2 mb-1"><Share2 className="size-5 text-blue-500" /><h1 className="text-2xl font-bold tracking-tight text-slate-800">Knowledge Network</h1></div>
        <p className="text-sm text-slate-400">Papers, research facets, methods, findings, and relationships from your literature library.</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-6 gap-2">
        {[{l:"Papers",v:data.paper_count},{l:"Nodes",v:data.node_count},{l:"Edges",v:data.edge_count},{l:"Facets",v:data.nodes.filter(n=>n.type==="facet").length},{l:"Methods",v:data.nodes.filter(n=>n.type==="method").length},{l:"Findings",v:data.nodes.filter(n=>n.type==="finding").length}].map(s=>(
          <div key={s.l} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-center"><p className="text-lg font-bold text-slate-700">{s.v}</p><p className="text-[9px] text-slate-400 uppercase">{s.l}</p></div>
        ))}
      </div>

      {/* Insights */}
      <div className="rounded-xl border border-slate-200/50 bg-white p-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Insights</p>
        {(data.insights || []).map((ins, i) => <p key={i} className="text-[11px] text-slate-600">· {ins}</p>)}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1"><Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3 text-slate-300" /><input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search nodes..." className="w-full rounded-lg border border-slate-200 pl-8 pr-3 py-1.5 text-[11px] outline-none focus:ring-1 focus:ring-blue-100" /></div>
        <div className="flex gap-1">{["All",...groups].map(g=><button key={g} onClick={()=>setFilter(g)} className={`text-[10px] px-2 py-1 rounded-md border ${filter===g?"bg-blue-50 text-blue-600 border-blue-200":"border-slate-200 text-slate-400 hover:text-slate-600"}`}>{g}</button>)}</div>
      </div>

      {/* Node list */}
      <div>
        <p className="text-xs font-semibold text-slate-500 mb-2">Nodes ({filteredNodes.length})</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-1.5">
          {filteredNodes.slice(0, 60).map((n) => (
            <button key={n.id} onClick={() => { if (n.type==="paper") router.push(`/paper/${n.id}`); else if (n.type==="subtopic") router.push(`/research-map/topic/${n.id}`); }}
              className={`text-left rounded-lg border px-2.5 py-2 hover:shadow-sm transition-all truncate ${GROUP_COLORS[n.group||"Papers"]||GROUP_COLORS.Papers} ${(n.type==="paper"||n.type==="subtopic")?"cursor-pointer":""}`}>
              <p className="text-[10px] font-medium truncate" title={n.label}>{n.label.slice(0,50)}</p>
              <p className="text-[8px] opacity-60">{n.group} {(n.size||1)>1?`· ${n.size||1}`:""}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Relationship table */}
      <div>
        <p className="text-xs font-semibold text-slate-500 mb-2">Relationships ({filteredEdges.length})</p>
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full text-[10px]">
            <thead><tr className="bg-slate-50 text-left text-slate-400"><th className="p-2">Source</th><th className="p-2">Type</th><th className="p-2">Target</th><th className="p-2 text-right">Weight</th></tr></thead>
            <tbody className="divide-y divide-slate-50">
              {filteredEdges.slice(0, 50).map((e) => {
                const src = data.nodes.find(n=>n.id===e.source);
                const tgt = data.nodes.find(n=>n.id===e.target);
                return (<tr key={e.id} className="hover:bg-slate-50"><td className="p-2 truncate max-w-[200px]">{src?.label?.slice(0,50)||e.source}</td><td className="p-2"><span className="text-[9px] px-1 py-0.5 rounded bg-slate-100">{EDGE_LABELS[e.type]||e.type}</span></td><td className="p-2 truncate max-w-[200px]">{tgt?.label?.slice(0,50)||e.target}</td><td className="p-2 text-right text-slate-400">{(e.weight*100).toFixed(0)}%</td></tr>);
              })}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-center text-[9px] text-slate-300">Generated from Research Map cache · {data.source}</p>
    </div>
  );
}
