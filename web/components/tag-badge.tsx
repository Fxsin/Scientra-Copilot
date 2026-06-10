import { cn } from "@/lib/utils";

const CATEGORY_STYLES: Record<string, string> = {
  TOXIN: "bg-amber-100 text-amber-900 border-amber-200",
  HOST: "bg-emerald-100 text-emerald-900 border-emerald-200",
  MECHANISM: "bg-violet-100 text-violet-900 border-violet-200",
  METHOD: "bg-sky-100 text-sky-900 border-sky-200",
};

interface TagBadgeProps {
  label: string;
  variant?: string;
  className?: string;
}

export function TagBadge({ label, variant, className }: TagBadgeProps) {
  // Auto-detect category from prefix (e.g. "TOXIN:Cry" → TOXIN)
  const prefix = label.includes(":") ? label.split(":")[0] : "";
  const style =
    CATEGORY_STYLES[prefix] ??
    "bg-muted text-muted-foreground border-border";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap",
        style,
        className,
      )}
      title={variant ? `${variant}: ${label}` : label}
    >
      {label}
    </span>
  );
}
