import {
  Library,
  FileText,
  Layers,
  Link2,
  BarChart3,
  Clock,
} from "lucide-react";
import { SelectedPaperCard } from "@/components/selected-paper-card";
import type { ContextPack } from "@/lib/chat-api";

interface ContextPackViewerProps {
  pack: ContextPack;
}

export function ContextPackViewer({ pack }: ContextPackViewerProps) {
  return (
    <div className="flex flex-col gap-5">
      {/* Summary bar */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Stat
          icon={Library}
          label="Papers"
          value={pack.papers.length}
          detail={`${pack.totalPaperCount} total`}
        />
        <Stat
          icon={FileText}
          label="Summaries"
          value={pack.summaries.length}
          detail="fetched"
        />
        <Stat
          icon={Layers}
          label="Evidence Chunks"
          value={pack.evidenceChunks.length}
          detail={`${pack.totalChunkCount} total`}
        />
        <Stat
          icon={Link2}
          label="Citation Anchors"
          value={pack.citationAnchors.length}
          detail="extracted"
        />
        <Stat
          icon={BarChart3}
          label="Token Estimate"
          value={pack.tokenEstimate.toLocaleString()}
          detail={
            <span className="text-[11px] text-muted-foreground">
              <Clock className="inline size-3 mr-0.5" />
              {(pack.elapsedMs / 1000).toFixed(1)}s
            </span>
          }
        />
      </div>

      {/* Selected Papers */}
      <Section title={`Selected Papers (${pack.papers.length})`}>
        <div className="grid gap-2 sm:grid-cols-2">
          {pack.papers.map((paper) => (
            <SelectedPaperCard key={paper.paper_id} paper={paper} />
          ))}
        </div>
      </Section>

      {/* Summaries */}
      {pack.summaries.length > 0 && (
        <Section
          title={`Retrieved Summaries (${pack.summaries.length})`}
        >
          <div className="grid gap-3">
            {pack.summaries.map((s) => (
              <div
                key={s.paper_id}
                className="rounded-lg border border-border bg-card p-4 shadow-sm"
              >
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="size-3.5 text-muted-foreground" />
                  <span className="text-xs font-semibold text-foreground">
                    {s.title ?? s.paper_id}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    ({estimateTokens(s.text).toLocaleString()} tokens)
                  </span>
                </div>
                <p className="text-xs text-muted-foreground line-clamp-6 leading-relaxed whitespace-pre-line">
                  {s.text.slice(0, 800)}
                  {s.text.length > 800 ? "…" : ""}
                </p>
                {s.citationAnchors.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {s.citationAnchors.slice(0, 10).map((a) => (
                      <span
                        key={a}
                        className="inline-flex rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
                      >
                        {a}
                      </span>
                    ))}
                    {s.citationAnchors.length > 10 && (
                      <span className="text-[10px] text-muted-foreground">
                        +{s.citationAnchors.length - 10}
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Evidence Chunks */}
      {pack.evidenceChunks.length > 0 && (
        <Section
          title={`Evidence Chunks (${pack.evidenceChunks.length})`}
        >
          <div className="grid gap-2">
            {pack.evidenceChunks.slice(0, 10).map((chunk, i) => (
              <div
                key={`${chunk.record_id}-${i}`}
                className="rounded-lg border border-border bg-card p-3 shadow-sm"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {chunk.paper_id}
                  </span>
                  {chunk.citation_anchor && (
                    <span className="font-mono text-[10px] font-medium text-accent-foreground">
                      {chunk.citation_anchor}
                    </span>
                  )}
                  <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                    score: {chunk.score?.toFixed(3) ?? "N/A"}
                  </span>
                </div>
                <p className="text-xs text-foreground/80 line-clamp-3 leading-relaxed">
                  {chunk.text_preview}
                </p>
              </div>
            ))}
            {pack.evidenceChunks.length > 10 && (
              <p className="text-xs text-muted-foreground text-center">
                +{pack.evidenceChunks.length - 10} more chunks
              </p>
            )}
          </div>
        </Section>
      )}
    </div>
  );
}

/* ── Helpers ── */

function Stat({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  detail?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3 shadow-sm">
      <div className="flex size-9 items-center justify-center rounded-lg bg-muted">
        <Icon className="size-4 text-muted-foreground" />
      </div>
      <div className="flex flex-col">
        <span className="text-lg font-bold text-foreground">{value}</span>
        <span className="text-[11px] text-muted-foreground">{label}</span>
        {detail && (
          <span className="text-[10px] text-muted-foreground/70">
            {detail}
          </span>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {children}
    </div>
  );
}

function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}
