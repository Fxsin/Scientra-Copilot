import { HelpCircle } from "lucide-react";

interface ResearchQuestionCardProps {
  question: string;
}

export function ResearchQuestionCard({ question }: ResearchQuestionCardProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <HelpCircle className="size-4" strokeWidth={1.5} />
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Research Question
          </span>
          <p className="text-sm font-medium text-foreground leading-relaxed italic">
            {question}
          </p>
        </div>
      </div>
    </div>
  );
}
