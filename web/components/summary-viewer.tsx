import ReactMarkdown from "react-markdown";

interface SummaryViewerProps {
  summary: string;
}

/** Split summary by ##/### headings, keeping headings as section keys. */
function parseSections(markdown: string): { heading: string; body: string }[] {
  const lines = markdown.split("\n");
  const sections: { heading: string; body: string }[] = [];
  let currentHeading = "Overview";
  let currentBody: string[] = [];

  for (const line of lines) {
    const h2 = line.match(/^##\s+(.+)/);
    const h1 = line.match(/^#\s+(.+)/);
    if (h2 || h1) {
      if (currentBody.length > 0) {
        sections.push({
          heading: currentHeading,
          body: currentBody.join("\n").trim(),
        });
      }
      currentHeading = (h2 ?? h1)![1].trim();
      currentBody = [];
    } else {
      currentBody.push(line);
    }
  }

  if (currentBody.length > 0 || currentHeading) {
    sections.push({
      heading: currentHeading,
      body: currentBody.join("\n").trim(),
    });
  }

  return sections;
}

export function SummaryViewer({ summary }: SummaryViewerProps) {
  if (!summary) {
    return (
      <p className="text-sm text-muted-foreground italic">
        No summary available for this paper.
      </p>
    );
  }

  const sections = parseSections(summary);

  return (
    <div className="flex flex-col gap-4">
      {sections.map((section, i) => (
        <div
          key={i}
          className="rounded-xl border border-border bg-card p-5 shadow-sm"
        >
          <h3 className="text-sm font-semibold text-foreground mb-3 pb-2 border-b border-border">
            {section.heading}
          </h3>
          <div className="prose prose-sm max-w-none dark:prose-invert prose-headings:text-foreground prose-p:text-foreground/85 prose-li:text-foreground/85 prose-strong:text-foreground prose-a:text-accent-foreground prose-code:bg-muted prose-code:rounded prose-code:px-1 prose-code:text-xs">
            <ReactMarkdown>{section.body}</ReactMarkdown>
          </div>
        </div>
      ))}
    </div>
  );
}
