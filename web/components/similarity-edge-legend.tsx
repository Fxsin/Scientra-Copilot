export function SimilarityEdgeLegend() {
  return (
    <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
      <span className="flex items-center gap-1">
        <span className="inline-block w-4 border-t border-dashed border-muted-foreground/50" />
        similarity
      </span>
      <span className="flex items-center gap-1">
        <span className="inline-block w-4 border-t border-muted-foreground/80" />
        highlighted
      </span>
    </div>
  );
}
