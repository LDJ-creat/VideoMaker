"use client";

import { MarkdownContent } from "@/lib/markdown/MarkdownContent";
import { cn } from "@/lib/utils";

type KnowledgeMarkdownPreviewProps = {
  markdown: string;
  className?: string;
  title?: string;
};

export function KnowledgeMarkdownPreview({
  markdown,
  className,
  title = "Skill 预览",
}: KnowledgeMarkdownPreviewProps) {
  return (
    <section
      className={cn(
        "flex min-h-0 flex-col rounded-xl border border-border bg-muted/10",
        className,
      )}
      data-testid="knowledge-markdown-preview"
    >
      <header className="shrink-0 border-b border-border px-4 py-3">
        <h3 className="font-serif text-sm font-semibold text-foreground">{title}</h3>
        <p className="mt-0.5 text-xs text-muted-foreground">
          支持标题、列表、粗体与代码块渲染
        </p>
      </header>
      <div className="max-h-[min(70vh,560px)] min-h-[12rem] overflow-y-auto px-4 py-4">
        <MarkdownContent markdown={markdown} />
      </div>
    </section>
  );
}

export function KnowledgeReasonTags({ reasons }: { reasons: string[] }) {
  if (reasons.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {reasons.map((reason) => (
        <span
          key={reason}
          className="inline-flex items-center rounded-md bg-secondary px-2 py-0.5 text-xs text-secondary-foreground"
        >
          {reason}
        </span>
      ))}
    </div>
  );
}
