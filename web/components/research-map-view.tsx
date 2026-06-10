import type { ResearchMapResponse } from "@/lib/types";
import { ResearchLandscapeCard } from "@/components/research-landscape-card";
import { EmergingTopicCard } from "@/components/emerging-topic-card";
import { GapCard } from "@/components/gap-card";

interface ResearchMapViewProps {
  data: ResearchMapResponse;
}

export function ResearchMapView({ data }: ResearchMapViewProps) {
  return (
    <div className="flex flex-col gap-6">
      {/* Overview stats */}
      <div className="grid gap-3 sm:grid-cols-4">
        <StatBox label="Mature Topics" value={data.mature_topics.length} color="secondary" />
        <StatBox label="Growing Topics" value={data.growing_topics.length} color="accent" />
        <StatBox label="Research Gaps" value={data.gap_topics.length} color="amber" />
        <StatBox label="Relationships" value={data.topic_relationships.length} color="slate" />
      </div>

      {/* Mature Topics */}
      {data.mature_topics.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
            Mature Topics
            <span className="text-[11px] font-normal text-muted-foreground">
              Established research areas with long publication history and diverse methods
            </span>
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.mature_topics.map((t) => (
              <ResearchLandscapeCard key={t.cluster_id} topic={t} />
            ))}
          </div>
        </section>
      )}

      {/* Growing Topics */}
      {data.growing_topics.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
            Growing Topics
            <span className="text-[11px] font-normal text-muted-foreground">
              Topics with accelerating research activity since 2020
            </span>
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.growing_topics.map((t) => (
              <EmergingTopicCard key={t.cluster_id} topic={t} />
            ))}
          </div>
        </section>
      )}

      {/* Research Gaps */}
      {data.gap_topics.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
            Research Gaps
            <span className="text-[11px] font-normal text-muted-foreground">
              Underexplored areas and promising combinations
            </span>
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.gap_topics.map((t) => (
              <GapCard key={t.cluster_id} topic={t} />
            ))}
          </div>
        </section>
      )}

      {/* Topic Relationships */}
      {data.topic_relationships.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-foreground mb-3">
            Topic Connections
          </h2>
          <div className="grid gap-2 sm:grid-cols-2">
            {data.topic_relationships.map((r, i) => (
              <div key={i} className="flex items-center gap-3 rounded-lg border border-border bg-card p-3 text-xs">
                <span className="font-medium text-foreground">{r.source}</span>
                <span className="text-muted-foreground">↔</span>
                <span className="font-medium text-foreground">{r.target}</span>
                <span className="ml-auto text-[10px] text-muted-foreground">
                  {r.strength} shared tags
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: number; color: string }) {
  const colors: Record<string, string> = {
    secondary: "bg-secondary/10 text-secondary",
    accent: "bg-accent/15 text-accent-foreground",
    amber: "bg-amber-100 text-amber-700",
    slate: "bg-muted text-muted-foreground",
  };
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className={`flex size-9 items-center justify-center rounded-lg ${colors[color] || colors.slate}`}>
        <span className="text-lg font-bold">{value}</span>
      </div>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
    </div>
  );
}
