"use client";

/* eslint-disable @typescript-eslint/no-explicit-any */
import { useCallback, useRef, useEffect, useState, useMemo } from "react";
import dynamic from "next/dynamic";
import type { NetworkNode, NetworkLink } from "@/lib/types";

const ForceGraph2D = dynamic(
  () => import("react-force-graph-2d"),
  { ssr: false },
);

interface GraphNode extends NetworkNode {
  x?: number;
  y?: number;
  degree?: number;
}
interface GraphLink {
  source: GraphNode | string;
  target: GraphNode | string;
  type: string;
  weight: number;
  label: string;
}

export type EdgeDensity = "sparse" | "medium" | "dense";
export type LabelMode = "off" | "concepts" | "important" | "all";

interface NetworkGraphProps {
  nodes: NetworkNode[];
  links: NetworkLink[];
  search: string;
  activeTypes: string[];
  selectedNode: NetworkNode | null;
  edgeDensity: EdgeDensity;
  labelMode: LabelMode;
  onNodeClick: (node: NetworkNode) => void;
  width: number;
  height: number;
}

export function NetworkGraph({
  nodes,
  links,
  search,
  activeTypes,
  selectedNode,
  edgeDensity,
  labelMode,
  onNodeClick,
  width,
  height,
}: NetworkGraphProps) {
  const fgRef = useRef<any>(null);
  const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);

  // Filter by type
  const visibleNodes = useMemo(() => {
    const filtered = nodes.filter((n) => activeTypes.includes(n.type));
    // Compute degree for each node
    const degree = new Map<string, number>();
    for (const l of links) {
      const src = typeof l.source === "string" ? l.source : (l.source as GraphNode).id;
      const tgt = typeof l.target === "string" ? l.target : (l.target as GraphNode).id;
      degree.set(src, (degree.get(src) || 0) + 1);
      degree.set(tgt, (degree.get(tgt) || 0) + 1);
    }
    // Top 10% degree threshold for "important"
    const degrees = [...degree.values()].sort((a, b) => b - a);
    const threshold = degrees[Math.floor(degrees.length * 0.1)] || 0;
    return filtered.map((n) => ({ ...n, degree: degree.get(n.id) || 0, isImportant: (degree.get(n.id) || 0) >= threshold }));
  }, [nodes, activeTypes, links]);

  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map((n) => n.id)), [visibleNodes]);

  // Edge density filter + concept-concept hide
  const MAX_LINKS_PER_PAPER = edgeDensity === "sparse" ? 4 : edgeDensity === "medium" ? 8 : 0;

  const visibleLinks = useMemo(() => {
    let filtered = links.filter((l) => {
      const src = typeof l.source === "string" ? l.source : (l.source as GraphNode).id;
      const tgt = typeof l.target === "string" ? l.target : (l.target as GraphNode).id;
      if (!visibleNodeIds.has(src) || !visibleNodeIds.has(tgt)) return false;
      // Hide concept-concept links
      const srcType = visibleNodes.find((n) => n.id === src)?.type;
      const tgtType = visibleNodes.find((n) => n.id === tgt)?.type;
      if (srcType !== "paper" && tgtType !== "paper") return false;
      return true;
    });

    if (MAX_LINKS_PER_PAPER > 0) {
      // Per paper, keep only top N links by weight
      const paperLinks = new Map<string, typeof filtered>();
      for (const l of filtered) {
        const src = typeof l.source === "string" ? l.source : (l.source as GraphNode).id;
        const tgt = typeof l.target === "string" ? l.target : (l.target as GraphNode).id;
        const paperId = visibleNodes.find((n) => n.id === src)?.type === "paper" ? src : tgt;
        if (!paperLinks.has(paperId)) paperLinks.set(paperId, []);
        paperLinks.get(paperId)!.push(l);
      }
      filtered = [];
      for (const [, plinks] of paperLinks) {
        plinks.sort((a, b) => (b.weight || 0) - (a.weight || 0));
        filtered.push(...plinks.slice(0, MAX_LINKS_PER_PAPER));
      }
    }
    return filtered;
  }, [links, visibleNodeIds, visibleNodes, MAX_LINKS_PER_PAPER]);

  // Highlight set
  const highlightNodes = useMemo(() => {
    const set = new Set<string>();
    if (hoverNode) {
      set.add(hoverNode.id);
      for (const l of visibleLinks) {
        const src = typeof l.source === "string" ? l.source : (l.source as GraphNode).id;
        const tgt = typeof l.target === "string" ? l.target : (l.target as GraphNode).id;
        if (src === hoverNode.id) set.add(tgt);
        if (tgt === hoverNode.id) set.add(src);
      }
    }
    if (search && search.length >= 2) {
      const match = nodes.find(
        (n) => n.label.toLowerCase().includes(search.toLowerCase()) && activeTypes.includes(n.type),
      );
      if (match) {
        set.add(match.id);
        for (const l of visibleLinks) {
          const src = typeof l.source === "string" ? l.source : (l.source as GraphNode).id;
          const tgt = typeof l.target === "string" ? l.target : (l.target as GraphNode).id;
          if (src === match.id) set.add(tgt);
          if (tgt === match.id) set.add(src);
        }
      }
    }
    return set;
  }, [hoverNode, search, nodes, activeTypes, visibleLinks]);

  const isSelected = (id: string) => selectedNode?.id === id;
  const hasHighlight = highlightNodes.size > 0;

  const paintNode = useCallback(
    (node: unknown, ctx: CanvasRenderingContext2D) => {
      const n = node as GraphNode;
      const isPaper = n.type === "paper";
      const sel = isSelected(n.id);
      const hl = !hasHighlight || highlightNodes.has(n.id);
      const isHovered = n.id === hoverNode?.id;

      // Opacity: selected > hovered neighbor > normal neighbor > dim
      const alpha = sel ? 1 : hl ? (isHovered ? 1 : 0.9) : 0.08;
      const baseR = isPaper ? 5 : 6;
      const r = isHovered ? baseR * 1.25 : sel ? baseR * 1.15 : baseR;

      ctx.globalAlpha = alpha;
      ctx.beginPath();
      ctx.arc(n.x ?? 0, n.y ?? 0, r, 0, 2 * Math.PI);
      ctx.fillStyle = n.color || "#999";
      ctx.fill();

      // Stroke: gold for selected, white for hovered, transparent otherwise
      if (sel) {
        ctx.strokeStyle = "#ebc146";
        ctx.lineWidth = 2.5;
        ctx.stroke();
      } else if (isHovered || hl) {
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      // Labels
      const showLabel =
        labelMode === "all" ||
        (labelMode === "concepts" && !isPaper) ||
        (labelMode === "important" && (n as any).isImportant);
      const alwaysShow = isHovered || sel;

      if ((showLabel || alwaysShow) && alpha > 0.5) {
        ctx.globalAlpha = Math.max(alpha, 0.7);
        const lbl = (n.label || "").slice(0, isHovered ? 35 : 22);
        ctx.font = `${isHovered ? "bold 11" : "10"}px Inter, system-ui, sans-serif`;
        ctx.fillStyle = isPaper ? "#0d1f39" : "#5c6b72";
        ctx.fillText(lbl, (n.x ?? 0) + r + 3, (n.y ?? 0) + 4);
        if (isHovered && !isPaper) {
          ctx.font = "9px Inter, system-ui, sans-serif";
          ctx.fillStyle = "#8b8b8b";
          ctx.fillText(n.type, (n.x ?? 0) + r + 3, (n.y ?? 0) + 16);
        }
      }
      ctx.globalAlpha = 1;
    },
    [highlightNodes, hoverNode, selectedNode, labelMode, hasHighlight],
  );

  const onNodeHover = useCallback((node: unknown | null) => {
    setHoverNode(node as GraphNode | null);
  }, []);

  const onNodeClickWrapped = useCallback(
    (node: unknown) => onNodeClick(node as NetworkNode),
    [onNodeClick],
  );

  useEffect(() => {
    if (fgRef.current && visibleNodes.length > 0) {
      const t = setTimeout(() => fgRef.current?.zoomToFit?.(400, 60), 800);
      return () => clearTimeout(t);
    }
  }, [visibleNodes.length > 0]);

  useEffect(() => {
    if (search && search.length >= 2) {
      const match = nodes.find(
        (n) => n.label.toLowerCase().includes(search.toLowerCase()) && activeTypes.includes(n.type),
      );
      if (match && fgRef.current) {
        fgRef.current.centerAt?.(match.x ?? 0, match.y ?? 0, 1000);
        fgRef.current.zoom?.(3, 1000);
      }
    }
  }, [search, nodes, activeTypes]);

  const graphData = useMemo(
    () => ({ nodes: visibleNodes, links: visibleLinks }),
    [visibleNodes, visibleLinks],
  );

  const isDimmed = edgeDensity === "dense" || edgeDensity === "medium";

  return (
    <div style={{ width, height, position: "relative" }}>
      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        width={width}
        height={height}
        nodeCanvasObject={paintNode}
        nodePointerAreaPaint={(n: unknown, _c: string, ctx: CanvasRenderingContext2D) => {
          const node = n as GraphNode;
          const r = node.type === "paper" ? 10 : 11;
          ctx.beginPath();
          ctx.arc(node.x ?? 0, node.y ?? 0, r, 0, 2 * Math.PI);
          ctx.fillStyle = "transparent";
          ctx.fill();
        }}
        linkCanvasObjectMode={() => "replace"}
        linkCanvasObject={(link: unknown, ctx: CanvasRenderingContext2D) => {
          const s = (link as any).source as any;
          const t = (link as any).target as any;
          const srcId = (link as any).source?.id ?? (link as any).source;
          const tgtId = (link as any).target?.id ?? (link as any).target;
          if (s?.x == null || t?.x == null) return;
          const isHl = !hasHighlight || highlightNodes.has(srcId) || highlightNodes.has(tgtId);
          ctx.beginPath();
          ctx.moveTo(s.x, s.y);
          ctx.lineTo(t.x, t.y);
          ctx.strokeStyle = "#5c6b72";
          ctx.lineWidth = isHl ? 1.5 : (isDimmed ? 0.3 : 0.6);
          ctx.globalAlpha = isHl ? 0.7 : (isDimmed ? 0.08 : 0.18);
          ctx.stroke();
        }}
        onNodeClick={onNodeClickWrapped}
        onNodeHover={onNodeHover}
        linkDirectionalParticles={0}
        linkWidth={0}
        cooldownTicks={100}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
        enableNodeDrag
        enableZoomInteraction
        minZoom={0.3}
        maxZoom={8}
      />

      {/* Interaction hint */}
      <div className="absolute bottom-3 left-3 text-[10px] text-muted-foreground/60 bg-card/80 rounded-md px-2 py-1 pointer-events-none">
        Drag · Scroll to zoom · Hover for details · Click to inspect
      </div>

      {/* Tooltip card */}
      {hoverNode && !isSelected(hoverNode.id) && (
        <div
          className="absolute z-50 pointer-events-none rounded-lg border border-border bg-card px-3 py-2 shadow-lg text-xs max-w-[240px]"
          style={{ left: (hoverNode.x ?? 0) + 14, top: Math.min((hoverNode.y ?? 0) - 10, height - 100) }}
        >
          {hoverNode.type === "paper" ? (
            <>
              <div className="font-semibold text-foreground leading-snug line-clamp-2">
                {hoverNode.title || hoverNode.label}
              </div>
              {hoverNode.year && (
                <div className="text-muted-foreground mt-0.5">
                  {hoverNode.year}
                  {hoverNode.journal ? ` · ${hoverNode.journal}` : ""}
                </div>
              )}
              {hoverNode.tags && hoverNode.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {hoverNode.tags.slice(0, 4).map((t) => (
                    <span key={t} className="inline-flex rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{t}</span>
                  ))}
                </div>
              )}
            </>
          ) : (
            <>
              <div className="font-semibold text-foreground">{hoverNode.label}</div>
              <div className="text-muted-foreground mt-0.5">
                {hoverNode.type} · {(hoverNode as any).count ?? hoverNode.degree ?? 0} papers
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
