import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { MarkdownContent, parseMarkdownBlocks } from "@/lib/markdown/MarkdownContent";

describe("MarkdownContent", () => {
  it("parses headings and lists", () => {
    const blocks = parseMarkdownBlocks("## Hook\n\n- item one\n- item two");
    expect(blocks).toEqual([
      { type: "heading", level: 2, text: "Hook" },
      { type: "list", items: ["item one", "item two"] },
    ]);
  });

  it("renders bold inline markdown", () => {
    render(<MarkdownContent markdown="**slotPattern**: hook → cta" />);
    expect(screen.getByText("slotPattern")).toBeInTheDocument();
  });
});
