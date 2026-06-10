export interface ParsedSummary {
  takeaway: string | null;
  coreFindings: string[];
  evidence: string[];
  methods: string[];
  limitations: string[];
  gaps: string[];
  others: string[];
}

/**
 * Parse AI summary text into structured sections.
 *
 * Recognizes markdown bold labels like:
 *   **Core Finding**: text
 *   **Evidence**: text
 *   **Method** or **Methods**: text
 *   **Pathway** or **Pathways**: text
 *   **Limitation** or **Limitations**: text
 *   **Gap** or **Gaps**: text
 *
 * Everything not matching a known label goes into `others`.
 * The first Core Finding becomes the `takeaway`.
 */
/**
 * Clean a raw summary text into a readable 1-2 line snippet for card previews.
 * Strips markdown, JSON artifacts, YAML frontmatter, field labels, and tool metadata.
 */
export function cleanSummarySnippet(raw: string | null | undefined, maxLen = 200): string | null {
  if (!raw) return null;
  let text = raw.trim();
  if (!text) return null;

  // ── 1. Detect JSON summary — extract first Core Finding text ──
  if (text.startsWith("{") && text.endsWith("}")) {
    try {
      const obj = JSON.parse(text);
      const cf = obj["Core Finding"] ?? obj["core_finding"] ?? obj["core_findings"];
      if (Array.isArray(cf) && cf.length > 0) {
        const first = cf[0];
        text = typeof first === "string" ? first : (first.text ?? first.content ?? JSON.stringify(first));
      }
    } catch { /* not valid JSON, continue */ }
  }

  // ── 2. Strip YAML frontmatter ──
  text = text.replace(/^---[\s\S]*?---\s*/g, "");

  // ── 3. Remove tool metadata lines ──
  const metaKeys = [
    "summary_tool", "summary_date", "summary_agent", "prompt_version",
    "generated_at", "model", "title:", "framework:", "paper_id:",
    "Scientra Copilot Summary Agent",
  ];
  for (const key of metaKeys) {
    text = text.replace(new RegExp(`^${key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}.*$`, "gmi"), "");
  }

  // ── 4. Extract first Core Finding ──
  const coreRe = /\*\*Core Finding\*\*:?\s*/i;
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    if (coreRe.test(line)) {
      let content = line.replace(coreRe, "").trim();
      if (i + 1 < lines.length && lines[i + 1].trim() && !/^\*\*/.test(lines[i + 1])) {
        content += " " + lines[i + 1].trim();
      }
      text = content;
      break;
    }
  }

  // ── 5. Strip all markdown bold labels ──
  text = text.replace(/\*\*[^*]+\*\*:?\s*/g, "");

  // ── 6. Strip field-name prefixes (text:, title:, etc.) ──
  text = text.replace(/^"?text"?:\s*/gi, "");
  text = text.replace(/^"?title"?:\s*/gi, "");
  text = text.replace(/^"?content"?:\s*/gi, "");

  // ── 7. Strip JSON/structural artifacts ──
  text = text.replace(/[{}[\]\\]/g, "");
  text = text.replace(/"([^"]{1,40})":\s*/g, "");  // "key":
  text = text.replace(/^[-—–•·]\s*/g, "");

  // ── 8. Strip leading/trailing quotes ──
  text = text.replace(/^["']|["']$/g, "");

  // ── 9. Collapse whitespace ──
  text = text.replace(/\s+/g, " ").trim();

  // ── 10. Truncate cleanly ──
  if (text.length > maxLen) {
    text = text.slice(0, maxLen).replace(/\s\S*$/, "") + "…";
  }
  return text || null;
}

export function parseAISummary(raw: string | null | undefined): ParsedSummary | null {
  if (!raw) return null;

  const text = raw.trim();
  if (!text) return null;

  // Split on lines that start with **Label**:
  const sectionRe = /^\*\*([^*]+)\*\*:?\s*/;
  const lines = text.split("\n");
  const sections: { label: string; content: string[] }[] = [];
  let current: { label: string; content: string[] } | null = null;

  for (const line of lines) {
    const m = line.match(sectionRe);
    if (m) {
      const label = m[1].trim().toLowerCase();
      const after = line.slice(m[0].length).trim();
      current = { label, content: after ? [after] : [] };
      sections.push(current);
    } else if (current) {
      const trimmed = line.trim();
      if (trimmed) current.content.push(trimmed);
    }
  }

  // Categorise
  const result: ParsedSummary = {
    takeaway: null,
    coreFindings: [],
    evidence: [],
    methods: [],
    limitations: [],
    gaps: [],
    others: [],
  };

  const methodLabels = new Set(["method", "methods", "pathway", "pathways"]);
  const limitLabels = new Set(["limitation", "limitations"]);
  const gapLabels = new Set(["gap", "gaps"]);

  for (const sec of sections) {
    const body = sec.content.join(" ").trim();
    if (!body) continue;
    if (sec.label === "core finding") {
      if (!result.takeaway) result.takeaway = body;
      result.coreFindings.push(body);
    } else if (sec.label === "evidence") {
      result.evidence.push(body);
    } else if (methodLabels.has(sec.label)) {
      result.methods.push(body);
    } else if (limitLabels.has(sec.label)) {
      result.limitations.push(body);
    } else if (gapLabels.has(sec.label)) {
      result.gaps.push(body);
    } else {
      result.others.push(body);
    }
  }

  // Fallback takeaway: first 200 chars
  if (!result.takeaway && result.others.length > 0) {
    result.takeaway = result.others[0].slice(0, 200);
  }

  return result;
}
