"use client";

import React, { type ReactNode } from "react";

/* ─── Token types ─── */
type TokenType = "plain" | "species" | "sub50" | "sub90" | "sub50_generic" | "unit" | "italic_p" | "chi_sq" | "sup2";

interface Token {
  type: TokenType;
  text: string;
}

/* ─── Whitelists ─── */

// Species: canonical genus+species or abbreviated genus. species
const SPECIES_PATTERNS: [RegExp, string][] = [
  // Full binomial (genus species)
  [/\bSpodoptera\s+frugiperda\b/gi, "Spodoptera frugiperda"],
  [/\bSpodoptera\s+exigua\b/gi, "Spodoptera exigua"],
  [/\bSpodoptera\s+litura\b/gi, "Spodoptera litura"],
  [/\bSpodoptera\s+littoralis\b/gi, "Spodoptera littoralis"],
  [/\bHelicoverpa\s+zea\b/gi, "Helicoverpa zea"],
  [/\bHelicoverpa\s+armigera\b/gi, "Helicoverpa armigera"],
  [/\bHeliothis\s+virescens\b/gi, "Heliothis virescens"],
  [/\bOstrinia\s+furnacalis\b/gi, "Ostrinia furnacalis"],
  [/\bOstrinia\s+nubilalis\b/gi, "Ostrinia nubilalis"],
  [/\bPlutella\s+xylostella\b/gi, "Plutella xylostella"],
  [/\bMythimna\s+separata\b/gi, "Mythimna separata"],
  [/\bChilo\s+suppressalis\b/gi, "Chilo suppressalis"],
  [/\bAgrotis\s+ipsilon\b/gi, "Agrotis ipsilon"],
  [/\bDiatraea\s+saccharalis\b/gi, "Diatraea saccharalis"],
  [/\bTrichoplusia\s+ni\b/gi, "Trichoplusia ni"],
  [/\bAedes\s+aegypti\b/gi, "Aedes aegypti"],
  [/\bBombyx\s+mori\b/gi, "Bombyx mori"],
  [/\bDrosophila\s+melanogaster\b/gi, "Drosophila melanogaster"],
  [/\bBacillus\s+thuringiensis\b/gi, "Bacillus thuringiensis"],
  [/\bEscherichia\s+coli\b/gi, "Escherichia coli"],
  [/\bSaccharomyces\s+cerevisiae\b/gi, "Saccharomyces cerevisiae"],
  [/\bAnopheles\s+gambiae\b/gi, "Anopheles gambiae"],
  // Abbreviated (G. species)
  [/\bS\.\s*frugiperda\b/gi, "S. frugiperda"],
  [/\bS\.\s*exigua\b/gi, "S. exigua"],
  [/\bS\.\s*litura\b/gi, "S. litura"],
  [/\bS\.\s*littoralis\b/gi, "S. littoralis"],
  [/\bH\.\s*zea\b/gi, "H. zea"],
  [/\bH\.\s*armigera\b/gi, "H. armigera"],
  [/\bH\.\s*virescens\b/gi, "H. virescens"],
  [/\bO\.\s*furnacalis\b/gi, "O. furnacalis"],
  [/\bO\.\s*nubilalis\b/gi, "O. nubilalis"],
  [/\bP\.\s*xylostella\b/gi, "P. xylostella"],
  [/\bM\.\s*separata\b/gi, "M. separata"],
  [/\bM\.\s*brassicae\b/gi, "M. brassicae"],
  [/\bC\.\s*suppressalis\b/gi, "C. suppressalis"],
  [/\bA\.\s*ipsilon\b/gi, "A. ipsilon"],
  [/\bA\.\s*aegypti\b/gi, "A. aegypti"],
  [/\bB\.\s*mori\b/gi, "B. mori"],
  [/\bD\.\s*melanogaster\b/gi, "D. melanogaster"],
  [/\bB\.\s*thuringiensis\b/gi, "B. thuringiensis"],
  [/\bE\.\s*coli\b/gi, "E. coli"],
  [/\bT\.\s*ni\b/gi, "T. ni"],
];

// Protected: never modify these
const PROTECTED = [
  /https?:\/\/\S+/g,                           // URLs
  /\b10\.\d{4,}\/[^\s]+/g,                      // DOIs
  /\bVip3[Aa]\w*\b/g,                            // Vip3Aa, Vip3Aa19, etc.
  /\bVip3[A-Za-z]\w*\b/g,                        // Vip3Af, Vip3Ad, Vip3Ae, Vip3Ca, Vip3Bc1 etc.
  /\bCry[0-9][A-Za-z]+\b/g,                      // Cry1Ac, Cry2Ab, Cry1Fa etc.
  /\bMAPK[0-9]*\w*\b/g,                          // MAPK, MAPK1, MAP2K4
  /\bMAP\d?K\d+\b/gi,                            // MAP2K4, MAP3K7
  /\b[A-Z]\d+-[A-Z]{2}\b/g,                      // R2-RR, R15-RR, AC4-RR etc. (strain names)
  /\b[A-Z]+-\w+\b/g,                             // general strain names like Vip-Sel, LA-RR, TRE-RR
  /\bR\d+\b/g,                                   // R2, R15 (standalone, but be careful)
  /\bG\d+\b/g,                                   // G0, G1
  /\bF\d+\b/g,                                   // F1, F2, F7
  /\bT\d+\b/g,                                   // T0, T2
  /\bS\d+\b/g,                                   // S1, S001 etc.
];

/* ───  Tokenizer ─── */

function tokenize(text: string): Token[] {
  // Phase 1: protect URLs and DOIs
  const placeholders = new Map<string, string>();
  let counter = 0;
  let protected_text = text;

  // Protect URLs
  protected_text = protected_text.replace(/https?:\/\/\S+/g, (m) => {
    const ph = `__PH_URL_${counter++}__`;
    placeholders.set(ph, m);
    return ph;
  });
  // Protect DOIs
  protected_text = protected_text.replace(/\b10\.\d{4,}\/[^\s,;.)]+/g, (m) => {
    const ph = `__PH_DOI_${counter++}__`;
    placeholders.set(ph, m);
    return ph;
  });

  // Phase 2: tokenize the protected text
  const tokens: Token[] = [];
  let remaining = protected_text;

  // Build combined regex: species + stats + units
  const patterns: { re: RegExp; type: TokenType }[] = [];

  // LC50 / LD50 / IC50 / EC50  — but only when followed by non-gene context
  patterns.push({ re: /\bLC50\b/g, type: "sub50" });   // exact LC50
  patterns.push({ re: /\bLC90\b/g, type: "sub90" });   // exact LC90
  patterns.push({ re: /\bLD50\b/g, type: "sub50_generic" });
  patterns.push({ re: /\bIC50\b/g, type: "sub50_generic" });
  patterns.push({ re: /\bEC50\b/g, type: "sub50_generic" });

  // Units
  patterns.push({ re: /\bug\/cm2\b/g, type: "unit" });
  patterns.push({ re: /\bug\/g\b/g, type: "unit" });
  patterns.push({ re: /\bng\/cm2\b/g, type: "unit" });
  patterns.push({ re: /\bcm2\b/g, type: "unit" });
  patterns.push({ re: /\bmm2\b/g, type: "unit" });
  patterns.push({ re: /micrograms?\/cm2\b/g, type: "unit" });
  patterns.push({ re: /micrograms?\/g\b/g, type: "unit" });

  // p-value
  patterns.push({ re: /\bp\s*[<>≤≥=]\s*0?\.?\d+/gi, type: "italic_p" });
  patterns.push({ re: /\bp-value[s]?\b/gi, type: "italic_p" });
  patterns.push({ re: /\bP\s*[<>≤≥=]\s*0?\.?\d+/g, type: "italic_p" });
  patterns.push({ re: /\bP-value[s]?\b/g, type: "italic_p" });

  // chi-square with superscript 2
  patterns.push({ re: /χ2\b/g, type: "chi_sq" });
  patterns.push({ re: /Chi-square\b/gi, type: "plain" }); // keep as-is

  // Species patterns
  for (const [re] of SPECIES_PATTERNS) {
    patterns.push({ re: new RegExp(re.source, re.flags), type: "species" });
  }

  // Split remaining by pattern matches
  // Simple approach: find all matches, sort by position, build token list
  interface Match { start: number; end: number; type: TokenType; text: string; }
  const matches: Match[] = [];

  for (const { re, type } of patterns) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(protected_text)) !== null) {
      // Skip if this match overlaps with a placeholder
      const substr = protected_text.substring(m.index, m.index + m[0].length);
      if (substr.includes("__PH_")) continue;
      matches.push({ start: m.index, end: m.index + m[0].length, type, text: m[0] });
    }
  }

  // Sort and deduplicate (prefer first match when overlapping)
  matches.sort((a, b) => a.start - b.start || b.end - a.end);
  const filtered: Match[] = [];
  for (const match of matches) {
    if (filtered.length === 0 || match.start >= filtered[filtered.length - 1].end) {
      filtered.push(match);
    }
  }

  // Build token list
  let pos = 0;
  for (const match of filtered) {
    if (match.start > pos) {
      tokens.push({ type: "plain", text: protected_text.slice(pos, match.start) });
    }
    tokens.push({ type: match.type, text: match.text });
    pos = match.end;
  }
  if (pos < protected_text.length) {
    tokens.push({ type: "plain", text: protected_text.slice(pos) });
  }

  // Phase 3: restore placeholders in tokens
  return tokens.map((t) => {
    let txt = t.text;
    for (const [ph, original] of placeholders) {
      txt = txt.replace(ph, original);
    }
    return { ...t, text: txt };
  });
}

/* ─── Unit normalisation ─── */

function formatUnit(text: string): string {
  return text
    .replace(/micrograms?\/cm2/gi, "μg/cm²")
    .replace(/micrograms?\/g/gi, "μg/g")
    .replace(/ug\/cm2/gi, "μg/cm²")
    .replace(/ug\/g/gi, "μg/g")
    .replace(/ng\/cm2/gi, "ng/cm²")
    .replace(/\bcm2\b/g, "cm²")
    .replace(/\bmm2\b/g, "mm²");
}

/* ─── Render token ─── */

function renderToken(token: Token, idx: number): ReactNode {
  const { type, text } = token;

  switch (type) {
    case "species":
      return <em key={idx}>{text}</em>;

    case "sub50":
      return <React.Fragment key={idx}>LC<sub>50</sub></React.Fragment>;

    case "sub90":
      return <React.Fragment key={idx}>LC<sub>90</sub></React.Fragment>;

    case "sub50_generic": {
      const m = text.match(/^([A-Z]+)(\d+)$/);
      if (m) return <React.Fragment key={idx}>{m[1]}<sub>{m[2]}</sub></React.Fragment>;
      return <React.Fragment key={idx}>{text}</React.Fragment>;
    }

    case "italic_p": {
      // Wrap the p/P but keep value as-is
      const mp = text.match(/^([pP])(.*)$/);
      if (mp) return <React.Fragment key={idx}><em>{mp[1]}</em>{mp[2]}</React.Fragment>;
      return <em key={idx}>{text}</em>;
    }

    case "chi_sq":
      return <React.Fragment key={idx}>χ<sup>2</sup></React.Fragment>;

    case "unit":
      return <React.Fragment key={idx}>{formatUnit(text)}</React.Fragment>;

    default:
      return <React.Fragment key={idx}>{text}</React.Fragment>;
  }
}

/* ─── Public component ─── */

interface ScientificTextProps {
  text: string | null | undefined;
}

export function ScientificText({ text }: ScientificTextProps): ReactNode {
  if (!text) return null;
  try {
    const tokens = tokenize(text);
    return <>{tokens.map((t, i) => renderToken(t, i))}</>;
  } catch {
    return <>{text}</>;
  }
}
