import { Layers } from "lucide-react";
import { TagBadge } from "@/components/tag-badge";
import type { KnowledgeCluster } from "@/lib/types";

interface ClusterCardProps {
  cluster: KnowledgeCluster;
  onClick: () => void;
  active: boolean;
}

export function ClusterCard({ cluster, onClick, active }: ClusterCardProps) {
  return (
    <button
      onClick={onClick}
      className={`text-left rounded-xl border p-4 shadow-sm transition-all hover:shadow-md w-full ${
        active
          ? "border-accent/40 bg-accent/5 ring-1 ring-accent/20"
          : "border-border bg-card hover:border-muted-foreground/20"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-md bg-accent/15 text-accent-foreground">
            <Layers className="size-3.5" strokeWidth={1.5} />
          </div>
          <span className="text-sm font-semibold text-foreground">{cluster.name}</span>
        </div>
        <span className="font-mono text-xs text-muted-foreground tabular-nums">
          {cluster.paper_count}p
        </span>
      </div>

      <p className="mt-2 text-xs text-muted-foreground line-clamp-2">
        {cluster.summary}
      </p>

      {(cluster.top_toxins.length > 0 || cluster.top_mechanisms.length > 0) && (
        <div className="mt-2 flex flex-wrap gap-1">
          {cluster.top_toxins.map((t) => (
            <TagBadge key={t} label={`TOXIN:${t}`} />
          ))}
          {cluster.top_mechanisms.map((m) => (
            <TagBadge key={m} label={`MECH:${m}`} />
          ))}
        </div>
      )}
    </button>
  );
}
