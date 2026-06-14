"use client";

import { useState, useEffect } from "react";
import { Network, Loader2, BarChart3 } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_SCIENTRA_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8710";

export function UnifiedGraphPanel() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/knowledge/unified-evidence-graph/stats`);
        const d = await r.json();
        setStats(d.available ? d : null);
      } catch { setStats(null); }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) return <div className="rounded-xl border bg-card p-4"><Loader2 className="size-4 animate-spin mx-auto" /></div>;
  if (!stats) return null;

  return (
    <div className="rounded-xl border bg-card p-4 space-y-2">
      <div className="flex items-center gap-2">
        <Network className="size-4 text-blue-500" />
        <h3 className="text-sm font-semibold">Unified Evidence Graph</h3>
      </div>
      <div className="grid grid-cols-2 gap-1 text-xs text-muted-foreground">
        <span>Papers: <b>{stats.paper_count || 0}</b></span>
        <span>Nodes: <b>{stats.total_nodes || 0}</b></span>
        <span>Edges: <b>{stats.total_edges || 0}</b></span>
      </div>
      {stats.node_types && (
        <div className="text-[10px] text-muted-foreground/70">
          {Object.entries(stats.node_types).slice(0, 6).map(([k, v]) => (
            <span key={k} className="mr-2">{k}: {v as number}</span>
          ))}
        </div>
      )}
    </div>
  );
}
