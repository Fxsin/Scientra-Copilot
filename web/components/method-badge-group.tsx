import { Microscope } from "lucide-react";

interface MethodBadgeGroupProps {
  methods: string[];
  summaryMethods: string[];
}

export function MethodBadgeGroup({
  methods,
  summaryMethods,
}: MethodBadgeGroupProps) {
  const all = [...new Set([...methods, ...summaryMethods])];

  // Extract method mentions from summary text
  const fromText = summaryMethods
    .join(" ")
    .match(/(RNAi|CRISPR|LigandBlot|SPR|MST|AlphaFold|RNA\s*interference|Cas9|sgRNA)/gi)
    ?.map((m) => m.replace(/\s+/g, ""))
    .filter((m) => !all.includes(m)) ?? [];

  const display = [...all, ...fromText].slice(0, 12);

  if (display.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <div className="flex size-7 items-center justify-center rounded-md bg-sky-100 text-sky-700">
          <Microscope className="size-3.5" strokeWidth={2} />
        </div>
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Methods
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {display.map((method) => (
          <span
            key={method}
            className="inline-flex items-center rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-800"
          >
            {method}
          </span>
        ))}
      </div>
    </div>
  );
}
