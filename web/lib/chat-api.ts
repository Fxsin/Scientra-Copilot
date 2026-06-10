// @ts-nocheck — pre-existing type issues, needs full rewrite
import { queryLiterature, getPaperSummary } from "./api";
import type {
  QueryResponse,
  QueryResultItem,
  PaperSummary,
  ParsedCitationAnchor,
} from "./types";

/* ── Context Pack (the payload that would go to an LLM) ── */

export interface ContextPack {
  question: string;
  papers: ContextPaper[];
  evidenceChunks: QueryResultItem[];
  summaries: ContextSummary[];
  citationAnchors: ParsedCitationAnchor[];
  tokenEstimate: number;
  totalPaperCount: number;
  totalChunkCount: number;
  elapsedMs: number;
}

export interface ContextPaper {
  paper_id: string;
  title: string | null;
  year: number | null;
  doi: string | null;
  score: number;
  matchedTags: string[];
  level: string;
}

export interface ContextSummary {
  paper_id: string;
  title: string | null;
  text: string;
  citationAnchors: string[];
}

/* ── Token estimation ── */

/** Rough token count: ~4 chars per token for English text. */
function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

/* ── Parse citation anchors from summary text ── */

function parseAnchors(summary: string, ids: string[]): ParsedCitationAnchor[] {
  const results: ParsedCitationAnchor[] = [];
  const seen = new Set<string>();

  for (const id of ids) {
    if (seen.has(id)) continue;
    seen.add(id);

    // Try to find detail block for this anchor in the summary text
    const detailRe = new RegExp(
      `${id}\\s+((?:[a-z_]+=[^\\s;)]+[;\\s]*)+)`,
      "gi",
    );
    const m = detailRe.exec(summary);
    let sourceSection: string | null = null;
    let page: string | null = null;
    let paragraph: number | null = null;

    if (m) {
      const props = m[1];
      sourceSection =
        props.match(/source_section=([^\s;)]+)/i)?.[1]?.replace(/[,)]$/, "") ??
        null;
      page =
        props.match(/page=([^\s;)]+)/i)?.[1]?.replace(/[,)]$/, "") ?? null;
      if (page === "unknown") page = null;
      const pStr = props.match(/paragraph=([^\s;)]+)/i)?.[1];
      if (pStr) paragraph = parseInt(pStr, 10) || null;
    }

    results.push({
      id,
      source_section: sourceSection,
      page,
      paragraph,
    });
  }

  return results;
}

/* ── Main entry point ── */

/**
 * Build a Context Pack for a natural-language question.
 *
 * Flow:
 *   1. Search all levels (metadata + summary + chunks)
 *   2. Deduplicate papers by paper_id
 *   3. Fetch summaries for top papers
 *   4. Collect evidence chunks
 *   5. Extract citation anchors
 *   6. Estimate token count
 *
 * This does NOT call any AI model. It only gathers the context that
 * would be sent to one in a future implementation.
 */
export async function askLiterature(
  question: string,
  topK = 10,
): Promise<ContextPack> {
  const startedAt = Date.now();

  // Step 1: query across all levels
  const queryResult: QueryResponse = await queryLiterature({
    query: question,
    mode: "hybrid",
    top_k: topK,
    level: "all",
    include_candidate_tags: true,
  });

  // Step 2: deduplicate papers by paper_id, keep best score
  const paperMap = new Map<string, ContextPaper>();
  const evidenceChunks: QueryResultItem[] = [];

  for (const item of queryResult.results) {
    const existing = paperMap.get(item.paper_id);
    if (!existing || item.score > existing.score) {
      paperMap.set(item.paper_id, {
        paper_id: item.paper_id,
        title: item.title,
        year: item.year,
        doi: item.doi,
        score: item.score,
        matchedTags: item.matched_tags ?? [],
        level: item.level,
      });
    }
    if (item.level === "chunk" || item.level === "chunks") {
      evidenceChunks.push(item);
    }
  }

  const papers = [...paperMap.values()]
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);

  // Step 3: fetch summaries for top papers
  const summaries: ContextSummary[] = [];
  const allAnchors: ParsedCitationAnchor[] = [];

  for (const paper of papers.slice(0, 5)) {
    try {
      const summary: PaperSummary = await getPaperSummary(paper.paper_id);
      summaries.push({
        paper_id: paper.paper_id,
        title: summary.title ?? paper.title,
        text: summary.summary,
        citationAnchors: summary.citation_anchors,
      });
      const anchors = parseAnchors(
        summary.summary,
        summary.citation_anchors,
      );
      allAnchors.push(...anchors);
    } catch {
      // Summary may not exist for all papers — that's OK
    }
  }

  // Step 4: estimate tokens
  let totalText = `Question: ${question}\n\n`;
  totalText += `--- Papers (${papers.length}) ---\n`;
  for (const p of papers) {
    totalText += `- ${p.title ?? "Untitled"} (${p.year ?? "?"}) doi:${p.doi ?? "N/A"} score:${p.score.toFixed(3)}\n`;
  }
  for (const s of summaries) {
    totalText += `\n--- Summary: ${s.paper_id} ---\n${s.text}\n`;
  }
  for (const c of evidenceChunks.slice(0, 20)) {
    totalText += `\n--- Evidence: ${c.paper_id} ---\n${c.text_preview}\n`;
  }
  const tokenEstimate = estimateTokens(totalText);

  return {
    question,
    papers,
    evidenceChunks: evidenceChunks.slice(0, 20),
    summaries,
    citationAnchors: allAnchors,
    tokenEstimate,
    totalPaperCount: queryResult.total,
    totalChunkCount: queryResult.results.filter(
      (r) => r.level === "chunk" || r.level === "chunks",
    ).length,
    elapsedMs: Date.now() - startedAt,
  };
}
