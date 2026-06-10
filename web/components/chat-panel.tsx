"use client";

import { useState, type FormEvent } from "react";
import { Send, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ChatPanelProps {
  onSend: (question: string) => void;
  loading: boolean;
}

export function ChatPanel({ onSend, loading }: ChatPanelProps) {
  const [value, setValue] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    if (!q || loading) return;
    onSend(q);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5 shadow-sm"
    >
      <div className="flex items-center gap-2">
        <div className="flex size-8 items-center justify-center rounded-lg bg-accent/20 text-accent-foreground">
          <span className="text-sm font-bold">?</span>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Context Preview Mode
          </h3>
          <p className="text-xs text-muted-foreground">
            Ask a research question — the system will gather relevant literature
            context. No AI answer is generated yet.
          </p>
        </div>
      </div>

      <div className="relative">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
          placeholder="Ask a research question… e.g. Vip3A receptor, Cry toxin mechanism, CRISPR screening"
          rows={2}
          disabled={loading}
          className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:opacity-50"
        />
      </div>

      <div className="flex items-center justify-between">
        <span className="text-[10px] text-muted-foreground">
          Press Enter to send · Shift+Enter for newline
        </span>
        <Button type="submit" disabled={!value.trim() || loading} size="sm">
          {loading ? (
            <>
              <Loader2 className="size-3.5 animate-spin" />
              Gathering context…
            </>
          ) : (
            <>
              <Send className="size-3.5" />
              Send
            </>
          )}
        </Button>
      </div>
    </form>
  );
}
