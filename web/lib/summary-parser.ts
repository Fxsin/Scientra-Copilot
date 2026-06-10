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
