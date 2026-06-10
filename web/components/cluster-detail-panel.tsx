import Link from "next/link";
import { ExternalLink, X } from "lucide-react";
import { TagBadge } from "@/components/tag-badge";
import type { KnowledgeCluster } from "@/lib/types";

interface ClusterDetailPanelProps {
  cluster: KnowledgeCluster;
  onClose: () => void;
}

export function ClusterDetailPanel({ cluster, onClose }: ClusterDetailPanelProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-sm font-bold text-foreground">{cluster.name}</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            {cluster.paper_count} papers · {cluster.node_count} nodes
          </p>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
          <X className="size-4" />
        </button>
      </div>

      {/* Summary */}
      <p className="text-xs text-foreground/80 leading-relaxed mb-4">{cluster.summary}</p>

      {/* Central Papers */}
      {(cluster.central_papers?.length ?? 0) > 0 && (
        <div className="mb-4">
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            Central Papers
          </h4>
          <div className="flex flex-col gap-1.5">
            {(cluster.central_papers ?? []).slice(0, 5).map((cp) => (
              <Link
                key={cp.paper_id}
                href={`/papers/${cp.paper_id}`}
                className="flex items-center justify-between rounded-md bg-muted/40 px-2.5 py-1.5 text-xs hover:bg-muted transition-colors group"
              >
                <span className="text-foreground/85 line-clamp-1 group-hover:text-primary">
                  {cp.title || cp.paper_id}
                </span>
                <ExternalLink className="size-3 shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100 ml-1" />
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Tag sections */}
      <TagSection title="Top Toxins" tags={cluster.top_toxins ?? []} prefix="TOXIN" />
      <TagSection title="Top Mechanisms" tags={cluster.top_mechanisms ?? []} prefix="MECH" />
      <TagSection title="Top Methods" tags={cluster.top_methods ?? []} prefix="METHOD" />
      <TagSection title="Top Hosts" tags={cluster.top_hosts ?? []} prefix="HOST" />
    </div>
  );
}

function TagSection({
  title,
  tags,
  prefix,
}: {
  title: string;
  tags: string[];
  prefix: string;
}) {
  if (tags.length === 0) return null;
  return (
    <div className="mb-3">
      <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
        {title}
      </h4>
      <div className="flex flex-wrap gap-1">
        {tags.map((t) => (
          <TagBadge key={t} label={`${prefix}:${t}`} />
        ))}
      </div>
    </div>
  );
}
