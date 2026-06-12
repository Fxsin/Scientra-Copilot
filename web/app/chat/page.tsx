"use client";

import { useState, useCallback } from "react";
import { Send, Loader2, Search, X } from "lucide-react";
import { askLiteratureAgent } from "@/lib/api";
import type { AgentAskResponse } from "@/lib/types";
import { AgentAnswerPanel } from "@/components/agent/AgentAnswerPanel";
import { AgentCitationCards } from "@/components/agent/AgentCitationCards";
import { AgentContextCards } from "@/components/agent/AgentContextCards";
import { AgentWarnings } from "@/components/agent/AgentWarnings";
import { AgentAdvancedOptions } from "@/components/agent/AgentAdvancedOptions";

/* ── Domain-agnostic example questions ── */

const EXAMPLE_CATEGORIES: Record<string, string[]> = {
  Methods: [
    "What methods are commonly used in this literature library?",
    "Find evidence related to protein expression.",
  ],
  Results: [
    "Which results are most frequently reported?",
    "What experimental outcomes are described?",
  ],
  Claims: [
    "What claims need stronger evidence?",
    "What conclusions are drawn across papers?",
  ],
  "Research Gaps": [
    "What research gaps can be inferred from this database?",
    "What evidence is missing for key mechanisms?",
  ],
};

/* ── Page ── */

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<AgentAskResponse | null>(null);
  const [highlightedRef, setHighlightedRef] = useState<string | null>(null);
  const [chatMode, setChatMode] = useState<"library" | string>("library");

  // Advanced options
  const [useLlm, setUseLlm] = useState(false);
  const [includeAssets, setIncludeAssets] = useState(true);
  const [includeEvidence, setIncludeEvidence] = useState(true);
  const [returnContext, setReturnContext] = useState(true);
  const [topK, setTopK] = useState(10);
  const [chunkTypes, setChunkTypes] = useState<string[]>([]);

  const handleAsk = useCallback(async (q: string) => {
    const query = q || question.trim();
    if (!query) return;
    setLoading(true);
    setError(null);
    setResponse(null);
    setHighlightedRef(null);
    setChatMode("library");
    try {
      const result = await askLiteratureAgent({
        question: query,
        top_k: topK,
        chunk_types: chunkTypes.length > 0 ? chunkTypes : undefined,
        include_assets: includeAssets,
        include_evidence: includeEvidence,
        use_llm: useLlm,
        return_context: returnContext,
      });
      setResponse(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [question, topK, chunkTypes, includeAssets, includeEvidence, useLlm, returnContext]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAsk(question);
    }
  };

  const toggleChunkType = (ct: string) => {
    setChunkTypes(prev =>
      prev.includes(ct) ? prev.filter(c => c !== ct) : [...prev, ct]
    );
  };

  const scrollToRef = (refId: string) => {
    setHighlightedRef(refId);
    const el = document.getElementById(`ctx-${refId.replace(/[^a-zA-Z0-9]/g, "-")}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const handleClear = () => {
    setQuestion("");
    setResponse(null);
    setError(null);
    setHighlightedRef(null);
  };

  return (
    <div className="flex flex-col gap-4">
      {/* ── Header ── */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Literature Chat</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Ask questions about your literature library. Answers are grounded in retrieved evidence and citations.
        </p>
        {chatMode !== "library" && (
          <span className="inline-block mt-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            Paper-specific mode: {chatMode}
          </span>
        )}
      </div>

      {/* ── Question Panel ── */}
      <div className="rounded-xl border bg-card p-4 shadow-sm">
        <div className="flex gap-2">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a research question about the literature..."
            rows={2}
            className="flex-1 resize-none rounded-lg border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
            disabled={loading}
          />
          <div className="flex flex-col gap-1 shrink-0 self-end">
            <button
              onClick={() => handleAsk(question)}
              disabled={loading || !question.trim()}
              className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              aria-label="Ask Literature"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </button>
            {response && (
              <button
                onClick={handleClear}
                className="flex h-6 w-10 items-center justify-center rounded border text-[10px] text-muted-foreground hover:bg-muted transition-colors"
                aria-label="Clear chat"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>
        </div>

        {/* Example questions by category */}
        <div className="mt-3 space-y-2">
          {Object.entries(EXAMPLE_CATEGORIES).map(([category, questions]) => (
            <div key={category} className="flex items-start gap-2">
              <span className="text-[10px] font-medium text-muted-foreground mt-0.5 w-16 shrink-0 text-right">
                {category}
              </span>
              <div className="flex flex-wrap gap-1">
                {questions.map((eq) => (
                  <button
                    key={eq}
                    onClick={() => { setQuestion(eq); handleAsk(eq); }}
                    disabled={loading}
                    className="rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground transition-colors disabled:opacity-50"
                  >
                    {eq}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        <AgentAdvancedOptions
          useLlm={useLlm} setUseLlm={setUseLlm}
          includeAssets={includeAssets} setIncludeAssets={setIncludeAssets}
          includeEvidence={includeEvidence} setIncludeEvidence={setIncludeEvidence}
          returnContext={returnContext} setReturnContext={setReturnContext}
          topK={topK} setTopK={setTopK}
          chunkTypes={chunkTypes} toggleChunkType={toggleChunkType}
        />
      </div>

      {/* ── Warnings & Errors ── */}
      <AgentWarnings response={response} error={error} useLlm={useLlm} />

      {/* ── Response ── */}
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
          />
          <AgentCitationCards
            citations={response.citations}
            highlightedRef={highlightedRef}
            onRefClick={scrollToRef}
          />
          {response.context?.chunks && (
            <AgentContextCards
              chunks={response.context.chunks}
              highlightedRef={highlightedRef}
            />
          )}
        </>
      )}

      {/* ── Empty State ── */}
      {!response && !loading && !error && (
        <div className="flex flex-col items-center justify-center py-16 text-center text-muted-foreground">
          <Search className="h-12 w-12 mb-4 opacity-30" />
          <p className="text-lg font-medium">Ask a research question</p>
          <p className="text-sm mt-1 max-w-md">
            Type a question above or click an example to search the literature database.
            Answers are grounded in retrieved evidence with traceable citations.
          </p>
        </div>
      )}
    </div>
  );
}
