import { Check, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { WORKFLOW_STEPS, type ImportStatus } from "@/lib/import-types";

interface WorkflowProgressProps {
  status: ImportStatus;
  progress: number;
  currentStep: string;
  error: string | null;
}

export function WorkflowProgress({
  status,
  progress,
  currentStep,
  error,
}: WorkflowProgressProps) {
  // Find the active step index
  const activeIndex = WORKFLOW_STEPS.findIndex((s) => s.key === status);
  const isFailed = status === "failed";
  const isDone = status === "completed";

  return (
    <div className="flex flex-col gap-2">
      {/* Current step label */}
      <div className="flex items-center gap-2">
        {isFailed ? (
          <X className="size-3.5 text-destructive" />
        ) : isDone ? (
          <Check className="size-3.5 text-secondary" />
        ) : (
          <Loader2 className="size-3.5 animate-spin text-muted-foreground" />
        )}
        <span className="text-xs font-medium text-foreground">
          {isFailed ? error ?? "Failed" : currentStep}
        </span>
        {!isFailed && !isDone && (
          <span className="ml-auto font-mono text-[10px] text-muted-foreground">
            {progress}%
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500",
            isFailed
              ? "bg-destructive"
              : isDone
                ? "bg-secondary"
                : "bg-primary",
          )}
          style={{ width: `${isFailed ? progress : isDone ? 100 : progress}%` }}
        />
      </div>

      {/* Step dots */}
      <div className="flex items-center justify-between mt-1">
        {WORKFLOW_STEPS.map((step, i) => {
          const past = isDone || i < activeIndex;
          const active = i === activeIndex && !isFailed;
          const future = i > activeIndex;

          return (
            <div
              key={step.key}
              className="flex flex-col items-center gap-0.5"
              title={step.label}
            >
              <div
                className={cn(
                  "flex size-4 items-center justify-center rounded-full text-[9px] font-bold transition-colors",
                  past
                    ? "bg-secondary text-secondary-foreground"
                    : active
                      ? "bg-primary text-primary-foreground ring-2 ring-ring/30"
                      : future
                        ? "bg-muted text-muted-foreground"
                        : "bg-destructive text-white",
                )}
              >
                {past ? (
                  <Check className="size-2.5" strokeWidth={3} />
                ) : isFailed && i === activeIndex ? (
                  <X className="size-2.5" strokeWidth={3} />
                ) : (
                  i + 1
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
