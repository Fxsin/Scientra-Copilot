import { cn } from "@/lib/utils";
import { STATUS_CONFIG, type ImportStatus } from "@/lib/import-types";

interface FileStatusBadgeProps {
  status: ImportStatus;
  className?: string;
}

export function FileStatusBadge({ status, className }: FileStatusBadgeProps) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap",
        config.color,
        className,
      )}
    >
      {status === "completed" && (
        <span className="mr-1 text-[10px]">&#x2022;</span>
      )}
      {status === "failed" && (
        <span className="mr-1 text-[10px]">&#x2022;</span>
      )}
      {status !== "completed" &&
        status !== "failed" &&
        status !== "waiting" && (
          <span className="mr-1 inline-block size-1.5 rounded-full bg-current animate-pulse" />
        )}
      {config.label}
    </span>
  );
}
