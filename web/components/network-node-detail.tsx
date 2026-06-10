"use client";

import Link from "next/link";
import { X, ExternalLink } from "lucide-react";
import { TagBadge } from "@/components/tag-badge";
import type { NetworkNode } from "@/lib/types";

interface NetworkNodeDetailProps {
  node: NetworkNode | null;
  onClose: () => void;
}

export function NetworkNodeDetail({ node, onClose }: NetworkNodeDetailProps) {
  if (!node) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span
            className="size-3 rounded-full shrink-0"
            style={{ backgroundColor: node.color }}
          />
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {node.type}
          </span>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
          <X className="size-3.5" />
        </button>
      </div>

      {node.type === "paper" ? (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold text-foreground leading-snug">
            {node.title || node.label}
          </h3>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            {node.year && <span>{node.year}</span>}
            {node.journal && (
              <span className="italic line-clamp-1">{node.journal}</span>
            )}
          </div>
          {node.tags && node.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {node.tags.slice(0, 8).map((t) => (
                <TagBadge key={t} label={t} />
              ))}
            </div>
          )}
          <Link
            href={`/papers/${node.id}`}
            className="inline-flex items-center gap-1 mt-1 text-xs font-medium text-primary hover:underline"
          >
            Open Paper <ExternalLink className="size-3" />
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold text-foreground">
            {node.label}
          </h3>
          <span className="text-xs text-muted-foreground">
            Connected to{" "}
            <strong className="text-foreground">{node.count ?? 0}</strong> paper
            {(node.count ?? 0) !== 1 ? "s" : ""}
          </span>
        </div>
      )}
    </div>
  );
}
