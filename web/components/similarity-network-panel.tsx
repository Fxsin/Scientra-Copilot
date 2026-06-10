// @ts-nocheck
"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */

import { useState, useMemo, useCallback, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { Info } from "lucide-react";
import { getSimilarityNetwork } from "@/lib/api";
import type { SimilarityNode, SimilarityLink } from "@/lib/types";
import { NetworkNodeDetail } from "@/components/network-node-detail";
import { SimilarityEdgeLegend } from "@/components/similarity-edge-legend";

const ForceGraph2D = dynamic(
  () => import("react-force-graph-2d"),
  { ssr: false },
);

const NODE_COLORS: Record<string, string> = { paper: "#0d1f39" };

export function SimilarityNetworkPanel() {
  const [minScore, setMinScore] = useState(0.65);
  const [selectedNode, setSelectedNode] = useState<SimilarityNode | null>(null);
  const [hoverNode, setHoverNode] = useState<SimilarityNode | null>(null);
  const fgRef = useRef<any>(null);

  const { data } = useQuery({
    queryKey: ["similarity-network", minScore],
    queryFn: () => getSimilarityNetwork(minScore),
    staleTime: 120_000,
  });

  const nodes = data?.nodes ?? [];
  const links = data?.links ?? [];
  const stats = data?.stats;

  // Stable graphData reference
  const graphData = useMemo(() => ({ nodes, links }), [nodes, links]);

  // Memoized neighbor set
  const highlightNodes = useMemo(() => {
    const set = new Set<string>();
    if (hoverNode) {
      set.add(hoverNode.id);
      for (const l of links) {
        const src = typeof l.source === "string" ? l.source : (l.source as any)?.id;
        const tgt = typeof l.target === "string" ? l.target : (l.target as any)?.id;
        if (src === hoverNode.id) set.add(tgt);
        if (tgt === hoverNode.id) set.add(src);
      }
    }
    return set;
  }, [hoverNode, links]);

  const handleNodeClick = useCallback((node: any) => {
    console.log("[similarity] node clicked:", node?.id, node?.title?.slice(0, 40));
    setSelectedNode(node as SimilarityNode);
  }, []);

  const handleNodeHover = useCallback((node: any | null) => {
    if (node) {
      console.log("[similarity] hover:", node.id, (node as SimilarityNode).title?.slice(0, 40));
    }
    setHoverNode(node as SimilarityNode | null);
  }, []);

  const paintNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D) => {
      const n = node as SimilarityNode;
      const hl = highlightNodes.size === 0 || highlightNodes.has(n.id);
      const r = 5;
      ctx.globalAlpha = hl ? 1 : 0.18;
      ctx.beginPath();
      ctx.arc(n.x ?? 0, n.y ?? 0, r, 0, 2 * Math.PI);
      ctx.fillStyle = NODE_COLORS.paper || "#0d1f39";
      ctx.fill();
      if (hl && hoverNode) {
        ctx.strokeStyle = "#ebc146";
        ctx.lineWidth = 2;
        ctx.stroke();
      }
      // Always show label on hovered node
      if (hl && highlightNodes.size > 0 && n.id === hoverNode?.id) {
        ctx.font = "bold 11px system-ui";
        ctx.fillStyle = "#0d1f39";
        const lbl = (n.title ?? n.id).slice(0, 40);
        ctx.fillText(lbl, n.x! + 8, n.y! - 6);
        // year subtitle
        if (n.year) {
          ctx.font = "9px system-ui";
          ctx.fillStyle = "#5c6b72";
          ctx.fillText(String(n.year), n.x! + 8, n.y! + 8);
        }
      }
      ctx.globalAlpha = 1;
    },
    [highlightNodes, hoverNode],
  );

  // Paint links - use "replace" mode to fully control rendering
  const paintLink = useCallback(
    (link: any, ctx: CanvasRenderingContext2D) => {
      const l = link as SimilarityLink;
      const src = typeof l.source === "string" ? l.source : (l.source as any)?.id;
      const tgt = typeof l.target === "string" ? l.target : (l.target as any)?.id;
      const hl = highlightNodes.size === 0 || highlightNodes.has(src) || highlightNodes.has(tgt);
      ctx.globalAlpha = hl ? 0.45 : 0.06;
      ctx.strokeStyle = "#5c6b72";
      ctx.lineWidth = hl ? 1.2 : 0.4;
      ctx.setLineDash(hl ? [] : [3, 5]);
      // Draw the line manually
      const s = link.source as any;
      const t = link.target as any;
      if (s?.x != null && t?.x != null) {
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(t.x, t.y);
        ctx.stroke();
      }
    },
    [highlightNodes],
  );

  return (
    <div className="flex flex-col gap-3">
      {/* Info banner */}
      <div className="flex items-center gap-2 rounded-lg border border-accent/30 bg-accent/5 px-3 py-2 text-xs text-muted-foreground">
        <Info className="size-3.5 text-accent-foreground shrink-0" />
        This is a similarity-based network, not a formal citation network.
        Edges represent high summary embedding similarity between papers.
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
        <span className="text-xs font-medium text-muted-foreground">
          Min Score: {minScore.toFixed(2)}
        </span>
        <input
          type="range"
          min={0.50}
          max={0.95}
          step={0.01}
          value={minScore}
          onChange={(e) => setMinScore(parseFloat(e.target.value))}
          className="flex-1 h-1.5 accent-primary"
        />
        <SimilarityEdgeLegend />
        {stats && (
          <span className="text-[10px] text-muted-foreground tabular-nums ml-auto">
            {stats.node_count} nodes · {stats.link_count} links · avg {stats.avg_score.toFixed(3)}
          </span>
        )}
      </div>

      {/* Graph + Detail */}
      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <div className="relative rounded-xl border border-border bg-card overflow-hidden" style={{ minHeight: 600 }}>
          {nodes.length > 0 ? (
            <>
              <ForceGraph2D
                ref={fgRef}
                graphData={graphData}
                width={800}
                height={600}
                nodeCanvasObject={paintNode}
                nodePointerAreaPaint={(node: any, _c: string, ctx: CanvasRenderingContext2D) => {
                  ctx.beginPath();
                  ctx.arc((node as any).x!, (node as any).y!, 9, 0, 2 * Math.PI);
                  ctx.fillStyle = "transparent";
                  ctx.fill();
                }}
                linkCanvasObjectMode={() => "replace"}
                linkCanvasObject={paintLink}
                linkDirectionalParticles={0}
                linkWidth={0}
                onNodeClick={handleNodeClick}
                onNodeHover={handleNodeHover}
                enableNodeDrag
                enableZoomInteraction
                minZoom={0.3}
                maxZoom={8}
                cooldownTicks={100}
              />
              {/* Tooltip overlay */}
              {hoverNode && (
                <div
                  className="absolute z-50 pointer-events-none rounded-lg border border-border bg-card px-3 py-2 shadow-lg text-xs"
                  style={{
                    left: (hoverNode.x ?? 0) + 14,
                    top: (hoverNode.y ?? 0) - 10,
                  }}
                >
                  <div className="font-semibold text-foreground max-w-[200px] truncate">
                    {hoverNode.title ?? hoverNode.id}
                  </div>
                  {hoverNode.year && (
                    <div className="text-muted-foreground">
                      {hoverNode.year}{hoverNode.journal ? ` · ${hoverNode.journal}` : ""}
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
              No similarity edges found at min_score={minScore}
            </div>
          )}
        </div>
        <aside>
          {selectedNode ? (
            <NetworkNodeDetail
              node={{ ...selectedNode, type: "paper", label: selectedNode.title ?? selectedNode.id, color: NODE_COLORS.paper }}
              onClose={() => setSelectedNode(null)}
            />
          ) : (
            <div className="rounded-xl border border-dashed border-border bg-card/50 p-6 text-center text-xs text-muted-foreground">
              Click a paper node to see details
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
