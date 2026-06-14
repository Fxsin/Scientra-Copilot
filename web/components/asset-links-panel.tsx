"use client";

import { useState, useEffect } from "react";
import { Link2, AlertTriangle, Loader2, ExternalLink, FileText, Table2, Image, Database, HelpCircle } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_SCIENTRA_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8710";

interface CitationMention {
  mention_id: string;
  paper_id: string;
  source_type: string;
  source_id: string;
  section: string;
  sentence: string;
  citation_text: string;
  asset_type: string;
  normalized_label: string;
  subpanel: string;
  is_supplementary: boolean;
}

interface AssetLink {
  link_id: string;
  paper_id: string;
  citation_mention_id: string;
  asset_id: string;
  asset_type: string;
  normalized_label: string;
  match_method: string;
  confidence: number;
  status: string;
  linked_evidence_ids: string[];
}

interface EvidenceAssetLink {
  evidence_id: string;
  asset_id: string;
  relation: string;
  confidence: number;
  citation_text: string;
}

interface AssetLinksData {
  available: boolean;
  message?: string;
  citation_mentions: CitationMention[];
  asset_links: AssetLink[];
  evidence_asset_links: EvidenceAssetLink[];
  unmatched_assets: any[];
  low_confidence_links: AssetLink[];
  summary: {
    citation_count: number;
    link_count: number;
    evidence_link_count: number;
    unmatched_asset_count: number;
    low_confidence_count: number;
  };
}

const TYPE_ICONS: Record<string, React.ReactNode> = {
  figure: <Image className="size-3 text-purple-500" />,
  table: <Table2 className="size-3 text-emerald-500" />,
  dataset: <Database className="size-3 text-cyan-500" />,
  supplementary: <FileText className="size-3 text-indigo-500" />,
  unknown: <HelpCircle className="size-3 text-gray-400" />,
};

const TYPE_LABELS: Record<string, string> = {
  figure: "Figure",
  table: "Table",
  dataset: "Dataset",
  supplementary: "Supplementary",
  unknown: "Unknown",
};

const METHOD_LABELS: Record<string, string> = {
  notes: "Notes",
  filename: "Filename",
  caption: "Caption",
  fuzzy: "Fuzzy",
  none: "None",
};

const RELATION_LABELS: Record<string, string> = {
  supports: "Supports",
  illustrates: "Illustrates",
  reports_data: "Reports Data",
  method_detail: "Method Detail",
  unknown: "Related",
};

export function AssetLinksPanel({ paperId }: { paperId: string }) {
  const [data, setData] = useState<AssetLinksData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  const fetchLinks = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/paper/${paperId}/asset-links`);
      setData(await r.json());
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLinks();
  }, [paperId]);

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <Link2 className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Asset Links</h3>
        </div>
        <Loader2 className="size-4 animate-spin text-muted-foreground mx-auto" />
      </div>
    );
  }

  if (!data?.available) {
    return (
      <div className="rounded-xl border bg-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <Link2 className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Asset Links</h3>
        </div>
        <p className="text-xs text-muted-foreground text-center py-2">
          Asset links not yet built. Run the linking engine to connect citations to assets.
        </p>
        <p className="text-[10px] text-muted-foreground/50 text-center">
          python Scripts/build_asset_links.py --paper-id {paperId}
        </p>
      </div>
    );
  }

  const summary = data.summary || {};
  const hasWarnings = summary.unmatched_asset_count > 0 || summary.low_confidence_count > 0;

  return (
    <div className="rounded-xl border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link2 className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Asset Links</h3>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
        >
          {expanded ? "Collapse" : "Expand"}
        </button>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-1 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="text-muted-foreground">Citations:</span>
          <span className="font-medium">{summary.citation_count || 0}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-muted-foreground">Linked:</span>
          <span className="font-medium text-emerald-600">{summary.link_count || 0}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-muted-foreground">Evidence:</span>
          <span className="font-medium">{summary.evidence_link_count || 0}</span>
        </div>
        {(summary.unmatched_asset_count > 0 || summary.low_confidence_count > 0) && (
          <div className="flex items-center gap-1.5">
            <AlertTriangle className="size-3 text-amber-500" />
            <span className="font-medium text-amber-600">
              {summary.unmatched_asset_count || 0} unmatched, {summary.low_confidence_count || 0} low
            </span>
          </div>
        )}
      </div>

      {/* Warnings */}
      {hasWarnings && !expanded && (
        <div className="flex items-center gap-1.5 text-[11px] text-amber-600 bg-amber-50 dark:bg-amber-950/20 rounded px-2 py-1">
          <AlertTriangle className="size-3 shrink-0" />
          <span>Review needed — expand for details</span>
        </div>
      )}

      {/* Expanded detail */}
      {expanded && (
        <div className="space-y-3 border-t pt-3">
          {/* Linked assets */}
          {data.asset_links.length > 0 && (
            <div>
              <h4 className="text-[11px] font-semibold text-muted-foreground mb-1.5 uppercase tracking-wide">
                Linked Assets ({data.asset_links.length})
              </h4>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {data.asset_links.slice(0, 10).map(link => (
                  <div key={link.link_id} className="flex items-center gap-1.5 text-[11px] py-0.5">
                    {TYPE_ICONS[link.asset_type] || TYPE_ICONS.unknown}
                    <span className="font-medium">{link.normalized_label}</span>
                    <span className="text-muted-foreground">→</span>
                    <span className="truncate text-muted-foreground" title={link.asset_id}>
                      {link.asset_id.slice(-12)}
                    </span>
                    <span className="text-[10px] px-1 py-0.5 rounded bg-muted text-muted-foreground">
                      {METHOD_LABELS[link.match_method] || link.match_method}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {Math.round(link.confidence * 100)}%
                    </span>
                  </div>
                ))}
                {data.asset_links.length > 10 && (
                  <p className="text-[10px] text-muted-foreground text-center">
                    + {data.asset_links.length - 10} more
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Evidence-Asset relations */}
          {data.evidence_asset_links.length > 0 && (
            <div>
              <h4 className="text-[11px] font-semibold text-muted-foreground mb-1.5 uppercase tracking-wide">
                Evidence Relations ({data.evidence_asset_links.length})
              </h4>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {data.evidence_asset_links.slice(0, 8).map((el, i) => (
                  <div key={i} className="flex items-center gap-1.5 text-[11px] py-0.5">
                    <span className="truncate text-muted-foreground max-w-[100px]" title={el.evidence_id}>
                      {el.evidence_id.split(":").pop() || el.evidence_id.slice(-20)}
                    </span>
                    <span className="text-[10px] px-1 py-0.5 rounded bg-muted text-muted-foreground">
                      {RELATION_LABELS[el.relation] || el.relation}
                    </span>
                    <span className="text-muted-foreground">→</span>
                    <span className="font-medium">{el.citation_text}</span>
                  </div>
                ))}
                {data.evidence_asset_links.length > 8 && (
                  <p className="text-[10px] text-muted-foreground text-center">
                    + {data.evidence_asset_links.length - 8} more
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Unmatched assets warning */}
          {data.unmatched_assets.length > 0 && (
            <div className="rounded bg-amber-50 dark:bg-amber-950/20 p-2">
              <h4 className="text-[11px] font-semibold text-amber-700 dark:text-amber-400 mb-1 flex items-center gap-1">
                <AlertTriangle className="size-3" />
                Unmatched Assets ({data.unmatched_assets.length})
              </h4>
              <div className="space-y-0.5 max-h-24 overflow-y-auto">
                {data.unmatched_assets.slice(0, 5).map((a: any, i: number) => (
                  <p key={i} className="text-[10px] text-amber-600 dark:text-amber-400 truncate">
                    {a.filename || a.asset_id || "Unknown"}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* Low confidence warnings */}
          {data.low_confidence_links.length > 0 && (
            <div className="rounded bg-amber-50 dark:bg-amber-950/20 p-2">
              <h4 className="text-[11px] font-semibold text-amber-700 dark:text-amber-400 mb-1 flex items-center gap-1">
                <AlertTriangle className="size-3" />
                Low Confidence ({data.low_confidence_links.length})
              </h4>
              <div className="space-y-0.5 max-h-24 overflow-y-auto">
                {data.low_confidence_links.slice(0, 5).map((lc, i) => (
                  <p key={i} className="text-[10px] text-amber-600 dark:text-amber-400">
                    {lc.normalized_label} → {lc.asset_id.slice(-12)} ({Math.round(lc.confidence * 100)}%)
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
