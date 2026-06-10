interface NetworkLegendProps {
  activeTypes: string[];
}

const ITEMS = [
  { type: "paper", label: "Paper", color: "#0d1f39" },
  { type: "toxin", label: "Toxin", color: "#ebc146" },
  { type: "host", label: "Host", color: "#16512b" },
  { type: "mechanism", label: "Mechanism", color: "#8b5cf6" },
  { type: "method", label: "Method", color: "#06b6d4" },
];

export function NetworkLegend({ activeTypes }: NetworkLegendProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 px-1">
      {ITEMS.map((item) => {
        const active = activeTypes.includes(item.type);
        return (
          <div key={item.type} className="flex items-center gap-1.5">
            <span
              className="size-2.5 rounded-full shrink-0"
              style={{
                backgroundColor: item.color,
                opacity: active ? 1 : 0.25,
              }}
            />
            <span
              className={`text-[11px] font-medium ${
                active ? "text-foreground" : "text-muted-foreground/50"
              }`}
            >
              {item.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
