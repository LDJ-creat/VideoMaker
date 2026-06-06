import type { ReactNode } from "react";

type Block =
  | { type: "heading"; level: 1 | 2 | 3; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; items: string[] }
  | { type: "code"; text: string };

function parseMarkdownBlocks(source: string): Block[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let codeLines: string[] | null = null;

  const flushParagraph = () => {
    if (paragraph.length === 0) return;
    blocks.push({ type: "paragraph", text: paragraph.join(" ").trim() });
    paragraph = [];
  };

  const flushList = () => {
    if (listItems.length === 0) return;
    blocks.push({ type: "list", items: [...listItems] });
    listItems = [];
  };

  for (const line of lines) {
    if (codeLines !== null) {
      if (line.trim().startsWith("```")) {
        blocks.push({ type: "code", text: codeLines.join("\n") });
        codeLines = null;
      } else {
        codeLines.push(line);
      }
      continue;
    }

    if (line.trim().startsWith("```")) {
      flushParagraph();
      flushList();
      codeLines = [];
      continue;
    }

    const headingMatch = /^(#{1,3})\s+(.+)$/.exec(line.trim());
    if (headingMatch) {
      flushParagraph();
      flushList();
      blocks.push({
        type: "heading",
        level: headingMatch[1]!.length as 1 | 2 | 3,
        text: headingMatch[2]!.trim(),
      });
      continue;
    }

    if (/^[-*]\s+/.test(line.trim())) {
      flushParagraph();
      listItems.push(line.trim().replace(/^[-*]\s+/, ""));
      continue;
    }

    if (line.trim() === "") {
      flushParagraph();
      flushList();
      continue;
    }

    flushList();
    paragraph.push(line.trim());
  }

  flushParagraph();
  flushList();
  if (codeLines !== null) {
    blocks.push({ type: "code", text: codeLines.join("\n") });
  }

  return blocks;
}

function renderInline(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("**")) {
      parts.push(
        <strong key={key++} className="font-semibold text-foreground">
          {token.slice(2, -2)}
        </strong>,
      );
    } else if (token.startsWith("`")) {
      parts.push(
        <code
          key={key++}
          className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground"
        >
          {token.slice(1, -1)}
        </code>,
      );
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}

type MarkdownContentProps = {
  markdown: string;
  className?: string;
};

export function MarkdownContent({ markdown, className }: MarkdownContentProps) {
  const blocks = parseMarkdownBlocks(markdown);

  return (
    <article className={className}>
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          const Tag = block.level === 1 ? "h2" : block.level === 2 ? "h3" : "h4";
          const size =
            block.level === 1
              ? "text-base font-semibold"
              : block.level === 2
                ? "text-sm font-semibold"
                : "text-sm font-medium";
          return (
            <Tag
              key={`h-${index}`}
              className={`${size} mb-2 mt-4 first:mt-0 text-foreground`}
            >
              {renderInline(block.text)}
            </Tag>
          );
        }
        if (block.type === "paragraph") {
          return (
            <p
              key={`p-${index}`}
              className="text-sm leading-relaxed text-muted-foreground"
            >
              {renderInline(block.text)}
            </p>
          );
        }
        if (block.type === "list") {
          return (
            <ul
              key={`ul-${index}`}
              className="my-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground"
            >
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInline(item)}</li>
              ))}
            </ul>
          );
        }
        return (
          <pre
            key={`code-${index}`}
            className="my-3 overflow-x-auto rounded-lg border border-border bg-muted/40 p-3 font-mono text-xs leading-relaxed text-foreground"
          >
            {block.text}
          </pre>
        );
      })}
    </article>
  );
}

export { parseMarkdownBlocks };
