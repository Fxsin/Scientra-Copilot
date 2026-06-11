/**
 * Citation generators for BibTeX and RIS formats.
 * Pure functions — no side effects, no domain-specific logic.
 */

export interface CitationData {
  paper_id: string;
  title?: string | null;
  authors?: string[] | null;
  year?: number | null;
  journal?: string | null;
  doi?: string | null;
}

function safe(v: string | null | undefined): string {
  return (v ?? "").replace(/[{}]/g, "");
}

function authorList(authors: string[] | null | undefined): string {
  if (!authors || authors.length === 0) return "";
  return authors.map((a) => safe(a)).join(" and ");
}

function sanitizeKey(id: string): string {
  return id.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 40);
}

/** Generate a BibTeX entry string */
export function generateBibTeX(paper: CitationData): string {
  const key = sanitizeKey(paper.paper_id);
  const lines = [`@article{${key},`];
  if (paper.title) lines.push(`  title = {${safe(paper.title)}},`);
  const auth = authorList(paper.authors);
  if (auth) lines.push(`  author = {${auth}},`);
  if (paper.journal) lines.push(`  journal = {${safe(paper.journal)}},`);
  if (paper.year) lines.push(`  year = {${paper.year}},`);
  if (paper.doi) lines.push(`  doi = {${paper.doi}},`);
  lines.push("}");
  return lines.join("\n");
}

/** Generate a RIS entry string */
export function generateRIS(paper: CitationData): string {
  const lines: string[] = ["TY  - JOUR"];
  if (paper.title) lines.push(`TI  - ${safe(paper.title)}`);
  for (const a of paper.authors ?? []) {
    if (a) lines.push(`AU  - ${safe(a)}`);
  }
  if (paper.year) lines.push(`PY  - ${paper.year}`);
  if (paper.journal) lines.push(`JO  - ${safe(paper.journal)}`);
  if (paper.doi) lines.push(`DO  - ${paper.doi}`);
  lines.push(`ID  - ${paper.paper_id}`);
  lines.push("ER  - ");
  return lines.join("\n");
}

/** Copy text to clipboard; returns true if successful */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback for older browsers
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      return true;
    } catch {
      return false;
    }
  }
}
