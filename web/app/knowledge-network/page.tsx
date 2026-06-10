"use client";

import { useState, useCallback } from "react";
import { Share2, AlertCircle } from "lucide-react";
import {
  NetworkGraph,
  type EdgeDensity,
  type LabelMode,
} from "@/components/network-graph";
import { NetworkToolbar } from "@/components/network-toolbar";
import { NetworkLegend } from "@/components/network-legend";
import { NetworkNodeDetail } from "@/components/network-node-detail";
import { DemoBanner } from "@/components/demo-banner";
import { useApiWithFallback } from "@/lib/use-api";
import { getKnowledgeNetwork } from "@/lib/api";
import {
  getNetworkData,
  getResearchGapsByNode,
  type NetworkMode,
} from "@/lib/data/researchIntelligenceMock";
import type { NetworkNode, NetworkLink, KnowledgeNetworkResponse } from "@/lib/types";

function buildMockData() {
  return getNetworkData("concept");
}

export default function KnowledgeNetworkPage() {
  const [mode, setMode] = useState<NetworkMode>("concept");
  const [search, setSearch] = useState("");
  const [activeTypes, setActiveTypes] = useState<string[]>([
    "paper",
    "toxin",
    "host",
    "mechanism",
    "method",
  ]);
  const [selectedNode, setSelectedNode] = useState<NetworkNode | null>(null);
  const [edgeDensity, setEdgeDensity] = useState<EdgeDensity>("medium");
  const [labelMode, setLabelMode] = useState<LabelMode>("important");

  // API-first for concept network
  const { data: apiNetworkData, dataSource } = useApiWithFallback(
    getKnowledgeNetwork,
    { nodes: [], links: [], stats: { node_count: 0, link_count: 0, paper_count: 0, toxin_count: 0, host_count: 0, mechanism_count: 0, method_count: 0 } },
  );

  // Use mock for non-concept modes or when API returns empty data
  const mockData = getNetworkData(mode);
  const useApi = dataSource === "REAL_API" && apiNetworkData.nodes.length > 0;
  const rawData = !useApi ? mockData : {
    nodes: apiNetworkData.nodes.map((n) => ({
      id: n.id,
      label: n.label,
      type: n.type as "Concept" | "Method" | "Finding" | "Paper",
      color: n.color,
      size: n.count ?? 8,
      entityId: n.id,
      entityType: "concept" as const,
    })),
    links: apiNetworkData.links.map((l) => ({
      source: typeof l.source === "string" ? l.source : (l.source as NetworkNode).id,
      target: typeof l.target === "string" ? l.target : (l.target as NetworkNode).id,
      type: l.type,
      weight: l.weight,
      label: l.label,
    })),
  };

  const nodes: NetworkNode[] = rawData.nodes.map((n) => ({
    id: n.id,
    label: n.label,
    type: n.type === "Finding"
      ? "mechanism"
      : (n.type.toLowerCase() as NetworkNode["type"]),
    color: n.color,
    count: "size" in n ? n.size : 8,
    tags: [],
  }));

  const links: NetworkLink[] = rawData.links.map((l) => ({
    source: l.source,
    target: l.target,
    type: l.type,
    weight: l.weight,
    label: l.label,
  }));

  const selectedRINode = selectedNode
    ? mockData.nodes.find((n) => n.id === selectedNode.id) ?? null
    : null;
  const linkedGaps = selectedRINode
    ? getResearchGapsByNode(selectedRINode)
    : [];

  const handleNodeClick = useCallback((node: NetworkNode) => {
    setSelectedNode(node);
  }, []);

  const handleTypeToggle = useCallback((type: string) => {
    setActiveTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  }, []);

  const handleReset = useCallback(() => {
    setSearch("");
    setActiveTypes(["paper", "toxin", "host", "mechanism", "method"]);
    setSelectedNode(null);
    setEdgeDensity("medium");
    setLabelMode("important");
  }, []);

  const nodeTypes = ["paper", "toxin", "host", "mechanism", "method"];

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Share2 className="size-5 text-indigo-500" />
          <h1 className="text-2xl font-bold tracking-tight">
            Knowledge Network
          </h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Explore the interconnected knowledge graph of concepts, methods,
          evidence, and contradictions.
        </p>
      </div>

      <DemoBanner dataSource={dataSource} />

      <NetworkToolbar
        search={search}
        onSearchChange={setSearch}
        nodeTypes={nodeTypes}
        activeTypes={activeTypes}
        onTypeToggle={handleTypeToggle}
        onReset={handleReset}
        stats={{
          node_count: rawData.nodes.length,
          link_count: rawData.links.length,
        }}
        edgeDensity={edgeDensity}
        onEdgeDensityChange={setEdgeDensity}
        labelMode={labelMode}
        onLabelModeChange={setLabelMode}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="rounded-xl border bg-card overflow-hidden">
            <NetworkGraph
              nodes={nodes}
              links={links}
              search={search}
              activeTypes={activeTypes}
              selectedNode={selectedNode}
              edgeDensity={edgeDensity}
              labelMode={labelMode}
              onNodeClick={handleNodeClick}
              width={700}
              height={520}
            />
          </div>
          <div className="mt-3">
            <NetworkLegend activeTypes={activeTypes} />
          </div>
        </div>

        <div className="space-y-4">
          <NetworkNodeDetail
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
          />

          {linkedGaps.length > 0 && (
            <div className="rounded-xl border bg-card p-4 space-y-2">
              <h4 className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                <AlertCircle className="size-3 text-amber-500" />
                Connected Research Gaps
              </h4>
              {linkedGaps.map((gap) => (
                <div
                  key={gap.id}
                  className="text-xs text-muted-foreground p-2 rounded-md bg-red-50 border border-red-100"
                >
                  <p className="font-medium text-red-800">{gap.title}</p>
                  <p className="mt-0.5 text-red-700">{gap.missingSummary}</p>
                </div>
              ))}
            </div>
          )}

          <div className="rounded-xl border bg-card p-4">
            <h4 className="text-xs font-semibold text-muted-foreground mb-2">
              Network Stats
            </h4>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-md bg-muted p-2 text-center">
                <span className="block text-lg font-bold">
                  {rawData.nodes.length}
                </span>
                <span className="text-muted-foreground">Nodes</span>
              </div>
              <div className="rounded-md bg-muted p-2 text-center">
                <span className="block text-lg font-bold">
                  {rawData.links.length}
                </span>
                <span className="text-muted-foreground">Links</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
