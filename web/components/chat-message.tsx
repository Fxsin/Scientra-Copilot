import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  role: "user" | "system";
  children: ReactNode;
  className?: string;
}

export function ChatMessage({ role, children, className }: ChatMessageProps) {
  return (
    <div
      className={cn(
        "flex gap-3",
        role === "user" ? "justify-end" : "justify-start",
        className,
      )}
    >
      <div
        className={cn(
          "max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed",
          role === "user"
            ? "bg-primary text-primary-foreground"
            : "border border-border bg-card text-foreground",
        )}
      >
        {children}
      </div>
    </div>
  );
}
