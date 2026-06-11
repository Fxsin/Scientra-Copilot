export interface ParsedSummary {
  takeaway: string | null;
  coreFindings: string[];
  evidence: string[];
  methods: string[];
  limitations: string[];
  gaps: string[];
  others: string[];
}

/* ═══════════════════════════════════════════════════════
   Public API
   ═══════════════════════════════════════════════════════ */

export function parseAISummary(raw: string | null | undefined): ParsedSummary | null {
  if (!raw) return null;

  // ── 1. Normalize input ──
  const text = normalizeSummaryInput(raw);
  if (!text) return null;

  // ── 2. Strip YAML frontmatter ──
  const stripped = stripFrontmatter(text);

  // ── 3. Try JSON parse ──
  if (isJsonLikeSummary(stripped)) {
    const parsed = safeJsonParse(stripped);
    if (parsed) {
      return _parseFromObject(parsed);
    }
    // Broken JSON — try tolerant extraction
    const extracted = extractFromBrokenJsonLike(stripped);
    if (extracted) return extracted;
    // Totally unparseable — return empty structured result, NOT raw lines
    return emptyResult();
  }

  // ── 4. Markdown-like: **Label**: text ──
  const sectionRe = /^\*\*([^*]+)\*\*:?\s*/;
  const lines = stripped.split("\n");
  const sections: { label: string; content: string[] }[] = [];
  let current: { label: string; content: string[] } | null = null;

  for (const line of lines) {
    const m = line.match(sectionRe);
    if (m) {
      current = { label: m[1].trim().toLowerCase(), content: [] };
      const after = line.slice(m[0].length).trim();
      if (after) current.content.push(after);
      sections.push(current);
    } else if (current) {
      const t = line.trim();
      if (t && !_isJsonStructural(t)) current.content.push(t);
    }
  }

  if (sections.length > 0) {
    return _categoriseSections(sections);
  }

  // ── 5. Plain text fallback ──
  const plain = stripped.split("\n").map(l => l.trim()).filter(l => l && !_isJsonStructural(l));
  if (plain.length > 0) {
    return {
      takeaway: plain[0].slice(0, 300),
      coreFindings: [], evidence: [], methods: [], limitations: [], gaps: [],
      others: plain.slice(1),
    };
  }

  return null;
}

/* ═══════════════════════════════════════════════════════
   Input normalization
   ═══════════════════════════════════════════════════════ */

function normalizeSummaryInput(input: string): string {
  // Explicit BOM removal — String.trim() does NOT remove ﻿ in JS
  let s = input.replace(/^﻿/, "").replace(/﻿/g, "");
  // Normalize line endings
  s = s.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  return s.trim();
}

function stripFrontmatter(text: string): string {
  // Must run AFTER BOM removal
  let s = text.trim();
  if (s.startsWith("---")) {
    const closing = s.indexOf("\n---", 3);
    if (closing > 0) {
      s = s.slice(closing + 4).trim();
    } else {
      // Try "---" on its own line later
      const re = /^---[\s\S]*?\n---\s*/;
      s = s.replace(re, "").trim();
    }
  }
  return s;
}

/* ═══════════════════════════════════════════════════════
   JSON detection & parsing
   ═══════════════════════════════════════════════════════ */

function isJsonLikeSummary(text: string): boolean {
  const s = text.trim();
  if (s.startsWith("{")) return true;
  // Heuristic: contains JSON quoted keys with structured fields
  if (/"(Core Finding|Evidence|Method|Limitation|Gap|text|citations)"/i.test(s) && s.includes("{")) return true;
  return false;
}

function safeJsonParse(input: string): Record<string, unknown> | null {
  let cleaned = input.trim();
  // 1. Direct parse
  try { return JSON.parse(cleaned) as Record<string, unknown>; } catch { /* ok */ }
  // 2. Extract { … }
  const fb = cleaned.indexOf("{");
  const lb = cleaned.lastIndexOf("}");
  if (fb >= 0 && lb > fb) {
    try {
      return JSON.parse(cleaned.slice(fb, lb + 1)) as Record<string, unknown>;
    } catch { /* ok */ }
  }
  return null;
}

/* ═══════════════════════════════════════════════════════
   Broken/tolerant JSON extraction
   ═══════════════════════════════════════════════════════ */

function extractFromBrokenJsonLike(text: string): ParsedSummary | null {
  const result = emptyResult();

  // Find all complete "text": "..." strings
  const textRe = /"text"\s*:\s*"((?:[^"\\]|\\.)*)"/g;
  const allTexts: string[] = [];
  let m: RegExpExecArray | null;
  while ((m = textRe.exec(text)) !== null) {
    const val = m[1].replace(/\\"/g, '"').replace(/\\n/g, " ");
    if (val.trim().length > 4 && !_isJsonStructural(val)) {
      allTexts.push(val.trim());
    }
  }

  if (allTexts.length === 0) return null;

  // Determine which section each text belongs to
  const sectionHeads: { re: RegExp; field: keyof Pick<ParsedSummary, "coreFindings" | "evidence" | "methods" | "limitations" | "gaps"> }[] = [
    { re: /"Core Finding(s)?"/i, field: "coreFindings" },
    { re: /"Evidence"/i, field: "evidence" },
    { re: /"Method(s)?"/i, field: "methods" },
    { re: /"Pathway(s)?"/i, field: "methods" },
    { re: /"Limitation(s)?"/i, field: "limitations" },
    { re: /"(Research )?Gap(s)?"/i, field: "gaps" },
  ];

  for (const t of allTexts) {
    // Find the nearest section heading before this text
    const idx = text.indexOf(t);
    const before = idx >= 0 ? text.slice(Math.max(0, idx - 500), idx) : "";
    let assigned = false;
    for (const head of sectionHeads) {
      if (head.re.test(before)) {
        result[head.field].push(t);
        assigned = true;
        break;
      }
    }
    if (!assigned) result.others.push(t);
  }

  // Takeaway
  result.takeaway = result.coreFindings[0] || result.evidence[0] || result.methods[0] || result.others[0] || null;

  // If we got nothing useful, return null so caller can show empty state
  const total = result.coreFindings.length + result.evidence.length + result.methods.length + result.limitations.length + result.gaps.length + result.others.length;
  return total > 0 ? result : null;
}

function emptyResult(): ParsedSummary {
  return { takeaway: null, coreFindings: [], evidence: [], methods: [], limitations: [], gaps: [], others: [] };
}

/* ═══════════════════════════════════════════════════════
   Object parser
   ═══════════════════════════════════════════════════════ */

function _parseFromObject(obj: Record<string, unknown>): ParsedSummary {
  const result = emptyResult();

  const fieldMap: Record<string, keyof Pick<ParsedSummary, "coreFindings" | "evidence" | "methods" | "limitations" | "gaps" | "others">> = {
    "core finding": "coreFindings", "core findings": "coreFindings",
    "core_finding": "coreFindings", "core_findings": "coreFindings",
    "corefinding": "coreFindings", "corefindings": "coreFindings",
    "evidence": "evidence",
    "method": "methods", "methods": "methods",
    "pathway": "methods", "pathways": "methods",
    "limitation": "limitations", "limitations": "limitations",
    "gap": "gaps", "gaps": "gaps",
    "research gap": "gaps", "research gaps": "gaps",
    "research_gap": "gaps", "research_gaps": "gaps",
    "key result": "others", "key results": "others",
  };

  for (const [key, value] of Object.entries(obj)) {
    const keyNormal = key.toLowerCase().replace(/[\s_-]+/g, " ").trim();
    const target = fieldMap[keyNormal] || fieldMap[keyNormal.replace(/\s/g, "")];
    if (!target) continue;
    const items = _extractTextItems(value);
    if (target === "coreFindings") result.coreFindings.push(...items);
    else if (target === "evidence") result.evidence.push(...items);
    else if (target === "methods") result.methods.push(...items);
    else if (target === "limitations") result.limitations.push(...items);
    else if (target === "gaps") result.gaps.push(...items);
    else result.others.push(...items);
  }

  result.takeaway = result.coreFindings[0] || result.evidence[0] || result.methods[0] || result.others[0] || null;
  return result;
}

function _extractTextItems(value: unknown): string[] {
  const items: string[] = [];
  if (typeof value === "string") {
    const s = value.trim();
    if (s && !_isJsonStructural(s) && s.length > 4) items.push(s);
  } else if (Array.isArray(value)) {
    for (const item of value) {
      if (typeof item === "string") {
        const s = item.trim();
        if (s && !_isJsonStructural(s) && s.length > 4) items.push(s);
      } else if (item && typeof item === "object") {
        const rec = item as Record<string, unknown>;
        const t = rec.text || rec.content || rec.summary;
        if (typeof t === "string" && t.trim().length > 4) items.push(t.trim());
      }
    }
  } else if (value && typeof value === "object") {
    const rec = value as Record<string, unknown>;
    const t = rec.text || rec.content || rec.summary;
    if (typeof t === "string" && t.trim()) items.push(t.trim());
  }
  return items;
}

function _isJsonStructural(s: string): boolean {
  if (/^[{}[\]],?\s*$/.test(s)) return true;
  if (/^"[A-Za-z_][A-Za-z0-9_ ]*":\s*[\[{]?\s*$/.test(s)) return true;
  if (/^"text":/.test(s) || /^"content":/.test(s) || /^"citations?":/.test(s)) return true;
  if (/^"S\d{3,}"[,]?\s*$/.test(s)) return true;
  if (/^\d+$/.test(s) && s.length < 5) return true;
  if (s === "null" || s === "true" || s === "false") return true;
  return false;
}

/* ═══════════════════════════════════════════════════════
   Markdown categoriser
   ═══════════════════════════════════════════════════════ */

function _categoriseSections(sections: { label: string; content: string[] }[]): ParsedSummary {
  const result = emptyResult();
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
  if (!result.takeaway && result.others.length > 0) {
    result.takeaway = result.others[0].slice(0, 200);
  }
  return result;
}

/* ═══════════════════════════════════════════════════════
   Snippet cleaner (unchanged public API)
   ═══════════════════════════════════════════════════════ */

export function cleanSummarySnippet(raw: string | null | undefined, maxLen = 200): string | null {
  if (!raw) return null;
  let text = raw.trim();
  if (!text) return null;

  // Try JSON first
  if (text.startsWith("{") && text.endsWith("}")) {
    try {
      const obj = JSON.parse(text);
      const cf = obj["Core Finding"] ?? obj["core_finding"] ?? obj["core_findings"];
      if (Array.isArray(cf) && cf.length > 0) {
        const first = cf[0];
        text = typeof first === "string" ? first : (first.text ?? first.content ?? JSON.stringify(first));
      }
    } catch { /* ok */ }
  }

  text = text.replace(/^---[\s\S]*?---\s*/g, "");
  text = text.replace(/\*\*[^*]+\*\*:?\s*/g, "");
  text = text.replace(/[{}[\]\\]/g, "");
  text = text.replace(/"([^"]{1,40})":\s*/g, "");
  text = text.replace(/^"?text"?:\s*/gi, "");
  text = text.replace(/\s+/g, " ").trim();

  if (text.length > maxLen) {
    text = text.slice(0, maxLen).replace(/\s\S*$/, "") + "…";
  }
  return text || null;
}
