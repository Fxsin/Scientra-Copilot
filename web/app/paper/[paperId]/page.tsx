"use client";

import { useEffect, useState, useRef, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, FileText, Tag, Users, Calendar, BookOpen, Link2, ExternalLink,
  Lightbulb, ListChecks, Microscope, AlertTriangle, Search, ChevronDown, ChevronRight, Info,
  Hash, Circle, Copy, Check,
} from "lucide-react";
import { getPaperMetadata, getPaperSummary, getPaperTags, getRelatedPapers, getPaperEvidence, getPaperParseReport, API_BASE_URL } from "@/lib/api";
import type { PaperEvidence, ParseReportResponse } from "@/lib/types";
import { generateBibTeX, generateRIS, copyToClipboard, type CitationData } from "@/lib/citation";
import { parseAISummary, type ParsedSummary } from "@/lib/summary-parser";
import type { PaperMetadata, PaperSummary, PaperTags, RelatedPaper } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { ScientificText } from "@/components/scientific-text";
import { PaperAskCard } from "@/components/agent/PaperAskCard";
import { AIEnrichmentPanel } from "@/components/ai-enrichment-panel";

type LoadState = "loading" | "ok" | "error";

/* ─── Section IDs for Quick Navigation ─── */
const SECTION_IDS = ["takeaway", "core-findings", "evidence", "methods", "limitations", "supporting"] as const;

/* ─── Heuristic: does text suggest pathways/biology vs bench methods? ─── */
const PATHWAY_WORDS = /\b(pathway|signaling|kegg|gsea|apoptosis|mapk|endocytosis|transcriptom|proteom|phosphorylation|kinase|receptor|internalization|trafficking|lysosom|mitochondri|autophagy|caspase|ubiquitin)\b/i;
const BENCH_WORDS   = /\b(bioassay|screening|chi.square|dominance|complementation|cross(ing)?\b|backcross|f2\b|probit|elisa|sds.page|western blot|pcr\b|rt.?qpcr|rna.?seq|microinjection|diet.overlay|surface.contamination|rearing|laboratory. colony|greenhouse|field trial)\b/i;

function classifyMethods(items: string[]): { bench: string[]; pathways: string[] } {
  const bench: string[] = [];
  const pathways: string[] = [];
  for (const item of items) {
    const p = PATHWAY_WORDS.test(item);
    const b = BENCH_WORDS.test(item);
    if (p && !b) pathways.push(item);
    else if (b && !p) bench.push(item);
    else if (p && b) pathways.push(item); // lean pathways when ambiguous
    else bench.push(item);
  }
  return { bench, pathways };
}

export default function PaperDetailPage() {
  const { paperId } = useParams<{ paperId: string }>();
  const router = useRouter();

  const [metadata, setMetadata] = useState<PaperMetadata | null>(null);
  const [summary, setSummary] = useState<PaperSummary | null>(null);
  const [tags, setTags] = useState<PaperTags | null>(null);
  const [parsed, setParsed] = useState<ParsedSummary | null>(null);
  const [parseReport, setParseReport] = useState<ParseReportResponse | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const [showAllSupporting, setShowAllSupporting] = useState(false);

  // Quick-nav active section
  const [activeSection, setActiveSection] = useState<string>("takeaway");
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    if (!paperId) return;
    let cancelled = false;
    async function load() {
      setState("loading");
      try {
        const [m, s, t, pr] = await Promise.all([
          getPaperMetadata(paperId).catch(() => null),
          getPaperSummary(paperId).catch(() => null),
          getPaperTags(paperId).catch(() => null),
          getPaperParseReport(paperId).catch(() => null),
        ]);
        if (cancelled) return;
        if (!m) { setErrorMsg("Paper not found."); setState("error"); return; }
        setMetadata(m);
        setSummary(s);
        setTags(t);
        setParseReport(pr);
        setParsed(parseAISummary(s?.text));
        setState("ok");
      } catch {
        if (!cancelled) { setErrorMsg("Failed to load paper data."); setState("error"); }
      }
    }
    load();
    return () => { cancelled = true; };
  }, [paperId]);

  // Scroll-spy
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActiveSection(entry.target.id);
        }
      },
      { rootMargin: "-10% 0px -70% 0px" },
    );
    for (const id of SECTION_IDS) {
      const el = sectionRefs.current[id];
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [parsed]);

  const classified = useMemo(() => parsed ? classifyMethods(parsed.methods) : { bench: [], pathways: [] }, [parsed]);

  if (state === "loading") return <LoadingSkeleton />;
  if (state === "error" || !metadata) return <ErrorState msg={errorMsg || "Paper not found."} onBack={() => router.back()} />;

  const allTags = tags?.tags ?? metadata.tags ?? [];
  const hasSummary = parsed != null;

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-16">
      {/* ── Back + Actions ── */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={() => router.push("/library")}>
          <ArrowLeft className="size-4 mr-1" /> Back to Library
        </Button>
        <div className="flex items-center gap-2">
          <CopyLinkButton />
          <ExportCitationButton metadata={metadata} />
        </div>
      </div>

      {/* ── Header ── */}
      <PaperHeader metadata={metadata} tags={allTags} />

      {/* ── Body ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* ━━━ LEFT (68%) ━━━ */}
        <div className="lg:col-span-8 space-y-8">
          {hasSummary ? (
            <StructuredSummary
              parsed={parsed}
              classified={classified}
              raw={summary!.text!}
              showAllSupporting={showAllSupporting}
              setShowAllSupporting={setShowAllSupporting}
              sectionRefs={sectionRefs}
              paperId={paperId}
            />
          ) : (
            <EmptySummary />
          )}
          {/* ── AI Enrichment (Phase 2.2) ── */}
          <AIEnrichmentPanel paperId={paperId} />

          {/* ── Ask this paper (Phase 0.9B) ── */}
          <PaperAskCard paperId={paperId} />

        </div>

        {/* ━━━ RIGHT (32%) — sticky ━━━ */}
        <div className="lg:col-span-4">
          <div className="space-y-4 lg:sticky lg:top-20">
            {hasSummary && <QuickNav parsed={parsed} classified={classified} activeSection={activeSection} sectionRefs={sectionRefs} />}
            <PaperInfoCard metadata={metadata} hasSummary={hasSummary} tagCount={allTags.length} />
            <TagsCard tags={allTags} />
            <ParserStatusCard parseReport={parseReport} />
            <MetadataPanel metadata={metadata} tags={tags} />
            <RelatedPapersSection paperId={paperId} />
          </div>
        </div>
      </div>

    </div>
  );
}

/* ═══════════════════════════════════════════════
   Sub-components
   ═══════════════════════════════════════════════ */

function LoadingSkeleton() {
  return (
    <div className="space-y-8 animate-pulse max-w-7xl mx-auto pb-16">
      <div className="h-4 w-24 bg-slate-100 rounded" />
      <div className="space-y-2"><div className="h-7 bg-slate-100 rounded w-3/4" /><div className="h-4 bg-slate-50 rounded w-1/2" /></div>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-8 space-y-4">
          <div className="h-24 bg-slate-50 rounded-xl" />
          <div className="h-32 bg-slate-50 rounded-xl" />
        </div>
        <div className="lg:col-span-4 space-y-3">
          <div className="h-32 bg-slate-50 rounded-xl" />
          <div className="h-20 bg-slate-50 rounded-xl" />
        </div>
      </div>
    </div>
  );
}

function ErrorState({ msg, onBack }: { msg: string; onBack: () => void }) {
  return <div className="space-y-4"><Button variant="ghost" size="sm" onClick={onBack}><ArrowLeft className="size-4 mr-1" /> Back</Button><div className="text-sm text-red-600 bg-red-50 rounded-lg p-4">{msg}</div></div>;
}

/* ── Header ── */

function PaperHeader({ metadata, tags }: { metadata: PaperMetadata; tags: string[] }) {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold tracking-tight leading-snug text-foreground/90">{metadata.title}</h1>

      {/* Meta chips */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {metadata.authors.length > 0 && (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-100 text-slate-700">
            <Users className="size-3" /> {metadata.authors.slice(0, 3).join(", ")}{metadata.authors.length > 3 && ` +${metadata.authors.length - 3}`}
          </span>
        )}
        {metadata.year && (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-100 text-slate-600">
            <Calendar className="size-3" /> {metadata.year}
          </span>
        )}
        {metadata.journal && (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 truncate max-w-[300px]">
            <BookOpen className="size-3" /> {metadata.journal}
          </span>
        )}
        {metadata.doi && (
          <a
            href={`https://doi.org/${metadata.doi}`}
            target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors font-medium"
          >
            <ExternalLink className="size-3" /> Open DOI ↗
          </a>
        )}
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-100 text-slate-500 font-mono text-[10px]">
          <Hash className="size-3" /> {metadata.paper_id.slice(-12)}
        </span>
      </div>

      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.slice(0, 12).map((t) => (
            <span key={t} className="inline-flex items-center rounded-full bg-blue-50/70 px-2.5 py-0.5 text-[11px] text-blue-700/80">
              <Tag className="size-3 mr-1" /> {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Quick Navigation (right sidebar) ── */

function QuickNav({ parsed, classified, activeSection, sectionRefs }: {
  parsed: ParsedSummary;
  classified: { bench: string[]; pathways: string[] };
  activeSection: string;
  sectionRefs: React.MutableRefObject<Record<string, HTMLElement | null>>;
}) {
  const items: { id: string; label: string; count: number; icon: React.ReactNode }[] = [];
  if (parsed.takeaway) items.push({ id: "takeaway", label: "Takeaway", count: 1, icon: <Lightbulb className="size-3" /> });
  if (parsed.coreFindings.length > 0) items.push({ id: "core-findings", label: "Core Findings", count: parsed.coreFindings.length, icon: <ListChecks className="size-3" /> });
  if (parsed.evidence.length > 0) items.push({ id: "evidence", label: "Evidence", count: parsed.evidence.length, icon: <Microscope className="size-3" /> });
  if (classified.bench.length > 0 || classified.pathways.length > 0) items.push({ id: "methods", label: "Methods", count: classified.bench.length + classified.pathways.length, icon: <FileText className="size-3" /> });
  if (parsed.limitations.length > 0) items.push({ id: "limitations", label: "Limitations", count: parsed.limitations.length, icon: <AlertTriangle className="size-3" /> });
  if (parsed.others.length > 0 || parsed.gaps.length > 0) items.push({ id: "supporting", label: "Supporting Details", count: parsed.others.length + parsed.gaps.length, icon: <Info className="size-3" /> });

  const scrollTo = (id: string) => {
    sectionRefs.current[id]?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="rounded-xl border border-slate-200/50 bg-white/80 shadow-[0_2px_8px_rgba(15,23,42,0.03)] p-3.5 space-y-0.5">
      <h3 className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2 ml-1">On This Page</h3>
      {items.map((item) => (
        <button
          key={item.id}
          onClick={() => scrollTo(item.id)}
          className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-[11px] transition-colors text-left
            ${activeSection === item.id ? "bg-slate-100 text-slate-800 font-medium" : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"}`}
        >
          <span className="shrink-0 opacity-60">{item.icon}</span>
          <span className="flex-1">{item.label}</span>
          <span className="text-[10px] tabular-nums text-slate-300 font-medium">{item.count}</span>
        </button>
      ))}
    </div>
  );
}

/* ── Structured Summary (left column) ── */

function StructuredSummary({ parsed, classified, raw, showAllSupporting, setShowAllSupporting, sectionRefs, paperId }: {
  parsed: ParsedSummary;
  classified: { bench: string[]; pathways: string[] };
  raw: string;
  showAllSupporting: boolean;
  setShowAllSupporting: (v: boolean) => void;
  sectionRefs: React.MutableRefObject<Record<string, HTMLElement | null>>;
  paperId: string;
}) {
  const setRef = (id: string) => (el: HTMLElement | null) => { sectionRefs.current[id] = el; };

  return (
    <div className="space-y-8">
      {/* One-sentence Takeaway */}
      {parsed.takeaway && (
        <section id="takeaway" ref={setRef("takeaway")}>
          <div className="rounded-xl border-l-2 border-amber-300 bg-amber-50/40 p-5">
            <div className="flex items-center gap-2 mb-2">
              <Lightbulb className="size-4 text-amber-500" />
              <h2 className="text-sm font-semibold text-amber-800">One-sentence Takeaway</h2>
            </div>
            <p className="text-[15px] leading-relaxed text-amber-900/80"><ScientificText text={parsed.takeaway} /></p>
          </div>
        </section>
      )}

      {/* Core Findings */}
      {parsed.coreFindings.length > 0 && (
        <section id="core-findings" ref={setRef("core-findings")}>
          <SectionBlock icon={<ListChecks className="size-4" />} title="Core Findings" count={parsed.coreFindings.length}>
            {parsed.coreFindings.map((f, i) => (
              <FindingCard key={i} index={i + 1} text={f} />
            ))}
          </SectionBlock>
        </section>
      )}

      {/* Evidence */}
      {parsed.evidence.length > 0 && (
        <section id="evidence" ref={setRef("evidence")}>
          <SectionBlock icon={<Microscope className="size-4" />} title="Evidence" count={parsed.evidence.length}>
            {parsed.evidence.map((e, i) => <EvidenceItem key={i} index={i + 1} text={e} />)}
          </SectionBlock>
        </section>
      )}

      {/* Methods / Pathways — dynamic */}
      {(classified.bench.length > 0 || classified.pathways.length > 0) && (
        <section id="methods" ref={setRef("methods")}>
          {classified.bench.length > 0 && (
            <div className={classified.pathways.length > 0 ? "mb-5" : ""}>
              <SectionBlock icon={<FileText className="size-4" />} title="Methods" count={classified.bench.length}>
                {classified.bench.map((m, i) => <FindingCard key={i} index={i + 1} text={m} muted />)}
              </SectionBlock>
            </div>
          )}
          {classified.pathways.length > 0 && (
            <SectionBlock icon={<Microscope className="size-4" />} title="Pathways & Biological Processes" count={classified.pathways.length}>
              {classified.pathways.map((p, i) => <FindingCard key={i} index={i + 1} text={p} muted />)}
            </SectionBlock>
          )}
        </section>
      )}

      {/* Limitations */}
      {parsed.limitations.length > 0 && (
        <section id="limitations" ref={setRef("limitations")}>
          <SectionBlock icon={<AlertTriangle className="size-4" />} title="Limitations" count={parsed.limitations.length}>
            {parsed.limitations.map((l, i) => <FindingCard key={i} index={i + 1} text={l} subtle />)}
          </SectionBlock>
        </section>
      )}

      {/* Supporting Details */}
      {(parsed.others.length > 0 || parsed.gaps.length > 0) && (() => {
        const allItems = [
          ...parsed.gaps.map((g, i) => ({ key: `gap-${i}`, index: i + 1, text: g })),
          ...parsed.others.map((o, i) => ({ key: `other-${i}`, index: parsed.gaps.length + i + 1, text: o })),
        ];
        const total = allItems.length;
        const visible = showAllSupporting ? allItems : allItems.slice(0, 3);
        return (
          <section id="supporting" ref={setRef("supporting")}>
            <SectionBlock icon={<Info className="size-4" />} title="Supporting Details" count={total}>
              {visible.map((item) => <FindingCard key={item.key} index={item.index} text={item.text} subtle />)}
              {total > 3 && (
                <button
                  onClick={() => setShowAllSupporting(!showAllSupporting)}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors mt-1"
                >
                  {showAllSupporting ? "Show less ▲" : `Show all details (${total - 3} more) ▼`}
                </button>
              )}
            </SectionBlock>
          </section>
        );
      })()}

      {/* Developer & Raw Data (collapsed by default, out of main reading flow) */}
      <section className="border-t border-border/20 pt-4 mt-8">
        <details className="group">
          <summary className="cursor-pointer list-none flex items-center gap-1.5 text-xs text-muted-foreground/50 hover:text-muted-foreground/70 transition-colors">
            <ChevronRight className="size-3 group-open:rotate-90 transition-transform" />
            Developer &amp; Raw Data
          </summary>
          <div className="mt-3 space-y-3 ml-5">
            {/* Raw AI Summary sub-section */}
            <details>
              <summary className="cursor-pointer text-xs text-muted-foreground/60 hover:text-muted-foreground/80">
                Raw AI Summary
              </summary>
              <div className="mt-2 rounded-lg border border-border/15 bg-muted/10 p-3 text-xs leading-relaxed text-muted-foreground/70 whitespace-pre-line max-h-64 overflow-y-auto">
                {raw}
              </div>
            </details>
            {/* API Debug sub-section */}
            <details>
              <summary className="cursor-pointer text-xs text-muted-foreground/60 hover:text-muted-foreground/80">
                API Debug
              </summary>
              <div className="mt-2 rounded-lg border border-border/15 bg-muted/10 p-3 text-[11px] font-mono text-muted-foreground/70 space-y-0.5">
                <p>API: {API_BASE_URL} | Paper: {paperId}</p>
              </div>
            </details>
          </div>
        </details>
      </section>
    </div>
  );
}

/* ── Section wrapper (lighter) ── */

function SectionBlock({ icon, title, count, children }: { icon: React.ReactNode; title: string; count: number; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-primary/50">{icon}</span>
        <h2 className="text-sm font-semibold text-foreground/80">{title}</h2>
        <span className="text-[11px] text-muted-foreground/60 ml-auto">{count}</span>
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

/* ── Finding card ── */

function FindingCard({ index, text, muted, subtle }: { index: number; text: string; muted?: boolean; subtle?: boolean }) {
  return (
    <div className={`rounded-lg px-4 py-2.5 flex gap-3 ${subtle ? "bg-muted/20" : muted ? "bg-slate-50/60" : "bg-blue-50/30 border-l-2 border-blue-200/50"}`}>
      <span className="text-[11px] font-medium text-muted-foreground/50 mt-0.5 shrink-0 w-5 text-right tabular-nums">{index}</span>
      <p className="text-sm leading-relaxed text-foreground/80"><ScientificText text={text} /></p>
    </div>
  );
}

/* ── Evidence item ── */

function EvidenceItem({ index, text }: { index: number; text: string }) {
  return (
    <div className="rounded-lg bg-emerald-50/30 border-l-2 border-emerald-200/60 px-4 py-3 flex gap-3">
      <span className="text-[10px] font-semibold text-emerald-600/60 mt-0.5 shrink-0 uppercase tracking-wide">E{index}</span>
      <p className="text-sm leading-relaxed text-foreground/80"><ScientificText text={text} /></p>
    </div>
  );
}

/* ── Empty summary ── */

function EmptySummary() {
  return (
    <div className="rounded-xl border border-border/30 bg-muted/20 p-10 text-center space-y-2">
      <FileText className="size-10 text-muted-foreground/30 mx-auto" />
      <p className="text-sm text-muted-foreground">AI summary not yet generated.</p>
      <p className="text-xs text-muted-foreground/60">Run the summary workflow step to generate structured summaries for this paper.</p>
    </div>
  );
}

/* ━━━ Right sidebar cards ━━━ */

const SIDEBAR_CARD = "rounded-xl border border-slate-200/50 bg-white/80 shadow-[0_2px_8px_rgba(15,23,42,0.03)] p-3.5";
const SIDEBAR_TITLE = "text-[10px] font-semibold uppercase tracking-wider text-slate-400";

function PaperInfoCard({ metadata, hasSummary, tagCount }: { metadata: PaperMetadata; hasSummary: boolean; tagCount: number }) {
  return (
    <div className={SIDEBAR_CARD + " space-y-2"}>
      <div className="flex items-center gap-2"><Info className="size-3.5 text-slate-400" /><h3 className={SIDEBAR_TITLE}>Paper Info</h3></div>
      <div className="space-y-1.5 text-[11px]">
        <Row label="Year" value={metadata.year ? String(metadata.year) : "—"} />
        <Row label="Journal" value={metadata.journal || "—"} />
        <Row label="DOI" value={metadata.doi ? (
          <a href={`https://doi.org/${metadata.doi}`} target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-blue-600 transition-colors inline-flex items-center gap-0.5">
            <ExternalLink className="size-3" /> Open DOI ↗
          </a>
        ) : "—"} />
        <Row label="Paper ID" value={<code className="text-[10px] text-slate-400">{metadata.paper_id.slice(-12)}</code>} />
        <Row label="Summary" value={hasSummary ? <span className="text-emerald-600/70">Available</span> : <span className="text-slate-300">—</span>} />
        <Row label="Tags" value={tagCount > 0 ? `${tagCount}` : <span className="text-slate-300">None</span>} />
        <Row label="Metadata" value={<span className="text-slate-500">Available</span>} />
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-slate-400 shrink-0">{label}</span>
      <span className="text-right truncate text-slate-600">{value || "—"}</span>
    </div>
  );
}

function TagsCard({ tags }: { tags: string[] }) {
  if (!tags.length) return null;
  return (
    <div className={SIDEBAR_CARD + " space-y-2"}>
      <div className="flex items-center gap-2"><Tag className="size-3.5 text-slate-400" /><h3 className={SIDEBAR_TITLE}>Tags</h3></div>
      <div className="flex flex-wrap gap-1">
        {tags.slice(0, 12).map((t) => <span key={t} className="inline-flex rounded-md border border-slate-200/70 bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-500">{t}</span>)}
      </div>
    </div>
  );
}

function MetadataPanel({ metadata, tags }: { metadata: PaperMetadata; tags: PaperTags | null }) {
  const [open, setOpen] = useState(false);
  const fields = [
    { k: "Species", v: tags?.species ?? metadata.species },
    { k: "Toxin", v: tags?.toxin ?? metadata.toxin },
    { k: "Method", v: tags?.method ?? metadata.method },
    { k: "Mechanism", v: tags?.mechanism ?? metadata.mechanism },
  ].filter(f => Array.isArray(f.v) && f.v.length > 0);

  if (!fields.length) return null;

  return (
    <div className={SIDEBAR_CARD + " space-y-2"}>
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 w-full text-left">
        <Info className="size-3.5 text-slate-400" />
        <h3 className={SIDEBAR_TITLE + " flex-1"}>Metadata</h3>
        {open ? <ChevronDown className="size-3.5 text-slate-400" /> : <ChevronRight className="size-3.5 text-slate-400" />}
      </button>
      {open && (
        <div className="space-y-2 pt-1">
          {fields.map((f) => (
            <div key={f.k}>
              <span className="text-[10px] font-medium text-muted-foreground uppercase">{f.k}</span>
              <div className="flex flex-wrap gap-0.5 mt-0.5">
                {(f.v as string[]).slice(0, 8).map((item) => (
                  <span key={item} className="inline-flex text-[10px] bg-muted/40 px-1.5 py-0.5 rounded">{item}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Copy Link ─── */

function CopyLinkButton() {
  const [copied, setCopied] = useState(false);
  const handle = async () => {
    const ok = await copyToClipboard(window.location.href);
    if (ok) { setCopied(true); setTimeout(() => setCopied(false), 2000); }
  };
  return (
    <button onClick={handle} className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1.5 text-[11px] text-slate-500 hover:bg-slate-50 transition-colors">
      {copied ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
      {copied ? "Copied" : "Copy Link"}
    </button>
  );
}

/* ─── Export Citation ─── */

function ExportCitationButton({ metadata }: { metadata: CitationData }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState("");
  const cite: CitationData = {
    paper_id: metadata.paper_id,
    title: metadata.title,
    authors: metadata.authors,
    year: metadata.year,
    journal: metadata.journal,
    doi: metadata.doi,
  };

  const copy = async (label: string, text: string) => {
    const ok = await copyToClipboard(text);
    if (ok) { setCopied(label); setTimeout(() => setCopied(""), 2000); }
  };

  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1.5 text-[11px] text-slate-500 hover:bg-slate-50 transition-colors">
        <FileText className="size-3" /> Cite
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-40 w-48 rounded-lg border border-slate-200 bg-white shadow-lg p-1.5 space-y-0.5">
          <button onClick={() => copy("BibTeX", generateBibTeX(cite))}
            className="w-full text-left px-2.5 py-1.5 rounded text-[11px] text-slate-600 hover:bg-slate-50 flex items-center justify-between">
            {copied === "BibTeX" ? "Copied BibTeX" : "Copy BibTeX"}
            {copied === "BibTeX" && <Check className="size-3 text-emerald-500" />}
          </button>
          <button onClick={() => copy("RIS", generateRIS(cite))}
            className="w-full text-left px-2.5 py-1.5 rounded text-[11px] text-slate-600 hover:bg-slate-50 flex items-center justify-between">
            {copied === "RIS" ? "Copied RIS" : "Copy RIS"}
            {copied === "RIS" && <Check className="size-3 text-emerald-500" />}
          </button>
        </div>
      )}
    </div>
  );
}

function RelatedPapersSection({ paperId }: { paperId: string }) {
  const [items, setItems] = useState<RelatedPaper[]>([]);
  const [source, setSource] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setErr(null);
    getRelatedPapers(paperId, 5)
      .then((r) => { if (!cancelled) { setItems(r.related); setSource(r.source); } })
      .catch((e) => { if (!cancelled) setErr(e instanceof Error ? e.message : "Failed"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [paperId]);

  return (
    <div className={SIDEBAR_CARD + " space-y-2"}>
      <div className="flex items-center gap-2">
        <Search className="size-3.5 text-slate-400" />
        <h3 className={SIDEBAR_TITLE}>Similar Papers</h3>
        {source === "vector" && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-600/70 font-medium">Vector</span>}
        {source === "keyword" && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-600/70 font-medium">Keyword</span>}
      </div>

      {loading && <div className="space-y-2 py-1">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-8 bg-slate-100 rounded-md animate-pulse" />)}</div>}

      {err && <p className="text-[11px] text-red-400">Unable to load related papers.</p>}

      {!loading && !err && items.length === 0 && (
        <p className="text-[11px] text-slate-300 italic leading-relaxed">Similar papers will appear here once similarity indexing is enabled.</p>
      )}

      {!loading && !err && items.map((rp) => (
        <button
          key={rp.paper_id}
          onClick={() => router.push(`/paper/${rp.paper_id}`)}
          className="w-full text-left rounded-lg hover:bg-muted/40 px-2 py-1.5 -mx-2 transition-colors group"
        >
          <p className="text-xs font-medium leading-snug line-clamp-2 group-hover:text-primary/80">{rp.title}</p>
          <div className="flex items-center gap-x-2 mt-0.5 text-[10px] text-muted-foreground/70">
            {rp.authors?.[0] && <span>{rp.authors[0]}{rp.authors.length > 1 ? " et al." : ""}</span>}
            {rp.year && <><span className="text-border">·</span><span>{rp.year}</span></>}
            {rp.similarity != null && (
              <span className="ml-auto text-[10px] font-medium text-slate-400">{(rp.similarity * 100).toFixed(0)}%</span>
            )}
          </div>
        </button>
      ))}
    </div>
  );
}

/* ── Parser Status Card ── */

function ParserStatusCard({ parseReport }: { parseReport: ParseReportResponse | null }) {
  if (!parseReport) {
    return (
      <div className="rounded-xl border border-border bg-card p-4 space-y-3">
        <div className="flex items-center gap-2">
          <FileText className="size-3.5 text-slate-400" />
          <span className="text-xs font-semibold tracking-tight text-foreground/80">Parser Status</span>
        </div>
        <p className="text-[11px] text-muted-foreground/60 italic">Loading parse report…</p>
      </div>
    );
  }

  const isHybrid = parseReport.status === "hybrid_parsed";
  const qr = parseReport.quality_report;
  const parserUsed = parseReport.parser_used;

  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
      <div className="flex items-center gap-2">
        <FileText className="size-3.5 text-slate-400" />
        <span className="text-xs font-semibold tracking-tight text-foreground/80">Parser Status</span>
      </div>

      {isHybrid && parserUsed ? (
        <div className="space-y-2">
          {/* Parser source lines */}
          <ParserSourceLine label="Metadata" source={parserUsed.metadata_source} />
          <ParserSourceLine label="Markdown" source={parserUsed.markdown_source} />
          <ParserSourceLine label="Layout" source={parserUsed.layout_source} />
          <ParserSourceLine label="Figures" source={parserUsed.figures_source} />
          <ParserSourceLine label="Tables" source={parserUsed.tables_source} />

          {/* Quality Score */}
          {qr && (
            <div className="pt-2 border-t border-border">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground/60">Overall Parse Quality</span>
                <QualityBadge score={qr.overall_score} />
              </div>
            </div>
          )}

          {/* Warnings */}
          {(parseReport.warnings && parseReport.warnings.length > 0) && (
            <div className="pt-1">
              <span className="text-[9px] font-medium text-amber-600">{parseReport.warnings.length} warning(s)</span>
            </div>
          )}
          {/* Errors */}
          {(parseReport.errors && parseReport.errors.length > 0) && (
            <div className="pt-0.5">
              <span className="text-[9px] font-medium text-red-500">{parseReport.errors.length} error(s)</span>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-1.5">
          <p className="text-[11px] text-muted-foreground/70 leading-relaxed">
            {parseReport.message || "Legacy parser only / No hybrid parse report available"}
          </p>
          {parseReport.hint && (
            <p className="text-[10px] text-muted-foreground/50 italic">{parseReport.hint}</p>
          )}
          {parseReport.legacy_files && parseReport.legacy_files.length > 0 && (
            <div className="text-[10px] text-muted-foreground/50 truncate">
              Legacy: {parseReport.legacy_files[0]}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ParserSourceLine({ label, source }: { label: string; source: string }) {
  const isActive = source && source !== "none" && source !== "unknown";
  const colorClass = isActive
    ? (source.includes("grobid") ? "text-emerald-600" :
       source.includes("opendataloader") ? "text-blue-600" :
       source.includes("marker") ? "text-purple-600" :
       source.includes("pymupdf") ? "text-amber-600" :
       "text-slate-500")
    : "text-slate-300";

  return (
    <div className="flex items-center justify-between text-[10px]">
      <span className="text-muted-foreground/60">{label}</span>
      <span className={`font-medium ${colorClass}`}>
        {isActive ? source.replace(/_/g, " ") : "—"}
      </span>
    </div>
  );
}

function QualityBadge({ score }: { score: number }) {
  let color = "bg-slate-100 text-slate-500";
  let label = "Low";
  if (score >= 0.7) { color = "bg-emerald-50 text-emerald-600"; label = "Good"; }
  else if (score >= 0.4) { color = "bg-amber-50 text-amber-600"; label = "Fair"; }

  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${color}`}>
      {label} ({(score * 100).toFixed(0)}%)
    </span>
  );
}
