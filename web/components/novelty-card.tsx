import { Sparkles } from "lucide-react";
import type { NoveltyItem } from "@/lib/knowledge";

interface NoveltyCardProps {
  items: NoveltyItem[];
}

export function NoveltyCard({ items }: NoveltyCardProps) {
  if (items.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <div className="flex size-7 items-center justify-center rounded-md bg-violet-100 text-violet-700">
          <Sparkles className="size-3.5" strokeWidth={2} />
        </div>
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Novelty
        </span>
      </div>
      <div className="flex flex-col gap-3">
        {items.map((item, i) => (
          <div key={i} className="flex flex-col gap-1.5">
            <div className="flex flex-wrap gap-1.5">
              {item.tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center rounded-full bg-violet-100 px-2 py-0.5 text-[11px] font-semibold text-violet-800"
                >
                  {tag}
                </span>
              ))}
            </div>
            <p className="text-sm text-foreground/80 leading-relaxed">
              {item.text.length > 240
                ? item.text.slice(0, 240) + "…"
                : item.text}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
