"use client";

import { useEffect, useState } from "react";

interface AssetSummary {
  papers_count: number;
  figure_assets_count: number;
  table_assets_count: number;
  supplementary_assets_count: number;
  gene_evidence_count: number;
  entity_comparison_count: number;
  vector_tables: Record<string, number>;
  vector_rows: number;
  lancedb_status: string;
}

interface SearchResult {
  chunk_id?: string;
  asset_type: string;
  paper_id?: string;
  text?: string;
  score?: number;
  entity_text?: string;
  entity_type?: string;
  value_columns?: Record<string, string>;
}

export default function AssetsPage() {
  const [summary, setSummary] = useState<AssetSummary | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [query, setQuery] = useState("");
  const [aType, setAType] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/assets/summary").then(r => r.json()).then(d => {
      setSummary(d);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const search = () => {
    fetch(`/api/assets/search?query=${encodeURIComponent(query)}&type=${aType}&limit=20`)
      .then(r => r.json())
      .then(d => setResults(d.results || []));
  };

  const assetTypes = ["figure", "table", "supplementary", "gene_evidence", "entity_comparison", "method", "result", "claim"];

  if (loading) return <div className="p-8 text-muted-foreground">Loading...</div>;

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-8">
      <h1 className="text-2xl font-bold">Assets Viewer</h1>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <SCard label="Papers" value={summary.papers_count} />
          <SCard label="Figures" value={summary.figure_assets_count} />
          <SCard label="Tables" value={summary.table_assets_count} />
          <SCard label="Supplementary" value={summary.supplementary_assets_count} />
          <SCard label="Gene Evidence" value={summary.gene_evidence_count} />
          <SCard label="Comparisons" value={summary.entity_comparison_count} />
          <SCard label="Vector Rows" value={summary.vector_rows} />
          <SCard label="LanceDB" value={summary.lancedb_status === "ok" ? "OK" : "Offline"}
                 color={summary.lancedb_status === "ok" ? "text-emerald-600" : "text-red-500"} />
        </div>
      )}

      {/* Vector tables detail */}
      {summary?.vector_tables && (
        <div className="border rounded-lg p-3 bg-muted/20 text-sm">
          <span className="font-medium">LanceDB Tables (06_Index/vector/lancedb):</span>
          <div className="grid grid-cols-3 gap-2 mt-2">
            {Object.entries(summary.vector_tables).map(([name, rows]) => (
              <div key={name} className="text-xs">
                <span className="text-muted-foreground">{name}:</span>{" "}
                <span className="font-mono">{rows}</span> rows
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Search */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Search Assets</h2>
        <div className="flex gap-2 flex-wrap">
          <input
            type="text" value={query} onChange={e => setQuery(e.target.value)}
            placeholder="Search query..."
            className="border rounded px-3 py-1.5 text-sm flex-1 min-w-[200px]"
            onKeyDown={e => e.key === "Enter" && search()}
          />
          <select value={aType} onChange={e => setAType(e.target.value)}
                  className="border rounded px-3 py-1.5 text-sm bg-background">
            <option value="">All types</option>
            {assetTypes.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <button onClick={search}
                  className="px-4 py-1.5 bg-primary text-primary-foreground rounded text-sm">
            Search
          </button>
        </div>

        {/* Results */}
        {results.length > 0 && (
          <div className="mt-4 space-y-2">
            <p className="text-xs text-muted-foreground">{results.length} results</p>
            {results.map((r, i) => (
              <div key={i} className="border rounded-lg p-3 text-sm hover:bg-muted/20">
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-2 py-0.5 rounded text-xs bg-blue-100 text-blue-700">{r.asset_type}</span>
                  {r.score != null && <span className="text-xs text-muted-foreground">score: {r.score.toFixed(3)}</span>}
                </div>
                {r.entity_text && (
                  <div className="font-medium">{r.entity_text} <span className="text-xs text-muted-foreground">({r.entity_type})</span></div>
                )}
                {r.text && <div className="text-xs text-muted-foreground mt-1 line-clamp-3">{r.text}</div>}
                {r.value_columns && (
                  <div className="text-xs mt-1 text-muted-foreground">
                    {Object.entries(r.value_columns).slice(0, 5).map(([k, v]) => (
                      <span key={k} className="mr-3">{k}: <b>{v}</b></span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        {results.length === 0 && query && (
          <p className="text-sm text-muted-foreground mt-3">No results.</p>
        )}
      </section>
    </div>
  );
}

function SCard({ label, value, color }: { label: string; value: number | string; color?: string }) {
  return (
    <div className="border rounded-lg p-4 bg-background">
      <div className={`text-2xl font-bold ${color || ""}`}>{value}</div>
      <div className="text-xs text-muted-foreground mt-1">{label}</div>
    </div>
  );
}
