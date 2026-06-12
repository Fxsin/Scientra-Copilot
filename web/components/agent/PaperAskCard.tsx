"use client";

import { useState, useCallback } from "react";
import { Send, Loader2, MessageCircle, ChevronDown, ChevronUp } from "lucide-react";
import { askLiteratureAgent } from "@/lib/api";
import type { AgentAskResponse, AgentAnswerMode } from "@/lib/types";
import { AgentAnswerPanel } from "./AgentAnswerPanel";
import { AgentCitationCards } from "./AgentCitationCards";
import { AgentContextCards } from "./AgentContextCards";
import { AgentWarnings } from "./AgentWarnings";

const QUICK_QUESTIONS = [
  "Summarize this paper's methods",
  "What are the key results?",
  "What claims are made in this paper?",
  "Which claims need stronger evidence?",
  "What evidence supports the main conclusion?",
];

interface PaperAskCardProps {
  paperId: string;
  defaultOpen?: boolean;
}

export function PaperAskCard({ paperId, defaultOpen = false }: PaperAskCardProps) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<AgentAskResponse | null>(null);
  const [highlightedRef, setHighlightedRef] = useState<string | null>(null);
  const [open, setOpen] = useState(defaultOpen);
  const [answerMode, setAnswerMode] = useState<AgentAnswerMode>("auto");

  const ask = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setResponse(null);
    setHighlightedRef(null);
    const useLlm = answerMode !== "evidence_only";
    try {
      const result = await askLiteratureAgent({
        question: q,
        top_k: 8,
        include_assets: true,
        include_evidence: true,
        use_llm: useLlm,
        return_context: true,
        paper_id: paperId,
      });
      setResponse(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [paperId]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      ask(question);
    }
  };

  const scrollToRef = (refId: string) => {
    setHighlightedRef(refId);
    const el = document.getElementById(`ctx-${refId.replace(/[^a-zA-Z0-9]/g, "-")}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm space-y-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full text-left"
      >
        <MessageCircle className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">Ask this paper</h3>
        {open ? <ChevronUp className="h-4 w-4 ml-auto" /> : <ChevronDown className="h-4 w-4 ml-auto" />}
      </button>

      {open && (
        <>
          {/* Question input */}
          <div className="flex gap-2">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about this paper..."
              className="flex-1 rounded-lg border bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
              disabled={loading}
            />
            <button
              onClick={() => ask(question)}
              disabled={loading || !question.trim()}
              className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 shrink-0"
              aria-label="Ask"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </button>
          </div>

          {/* Quick questions */}
          <div className="flex flex-wrap gap-1.5">
            {QUICK_QUESTIONS.map((qq) => (
              <button
                key={qq}
                onClick={() => ask(qq)}
                disabled={loading}
                className="rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground transition-colors disabled:opacity-50"
              >
                {qq}
              </button>
            ))}
          </div>

          <AgentWarnings response={response} error={error} answerMode={answerMode} />

          {response && (
            <>
              <AgentAnswerPanel
                answer={response.answer}
                intent={response.intent}
                model={response.model}
                elapsedMs={response.elapsed_ms}
                contextUsed={response.context_used}
                papersCited={response.papers_cited}
                highlightedRef={highlightedRef}
                onRefClick={scrollToRef}
                answerMode={answerMode}
                tokenUsage={response?.token_usage as Record<string,unknown> | null}
              />
              <AgentCitationCards
                citations={response.citations}
                highlightedRef={highlightedRef}
                onRefClick={scrollToRef}
                contextExists={(response.context_used ?? 0) > 0}
              />
              {response.context?.chunks && (
                <AgentContextCards
                  chunks={response.context.chunks}
                  highlightedRef={highlightedRef}
                  defaultOpen={false}
                />
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
