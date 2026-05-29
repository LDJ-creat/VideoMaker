import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GeneratedAssetBadge } from "@/features/aigc-preview/GeneratedAssetBadge";
import { StructureEvidencePanel } from "@/features/structure-evidence/StructureEvidencePanel";
import { fixtureVideoStructure } from "@/fixtures";

describe("StructureEvidencePanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows segment evidence and transcript excerpts", () => {
    render(
      <StructureEvidencePanel
        structure={fixtureVideoStructure}
        onHighlightSlot={() => undefined}
      />,
    );

    expect(screen.getByTestId("structure-evidence-panel")).toBeInTheDocument();
    expect(screen.getAllByText(/转写：/).length).toBeGreaterThan(0);
    expect(screen.getByTestId("evidence-card-seg-hook")).toBeInTheDocument();
  });

  it("shows analysis message during structure extraction", () => {
    render(
      <StructureEvidencePanel
        structure={fixtureVideoStructure}
        analysisStage="extracting_structure"
      />,
    );

    expect(screen.getByText("AI 正在分析样例结构…")).toBeInTheDocument();
  });

  it("invokes highlight callback when evidence card clicked", async () => {
    const user = userEvent.setup();
    const onHighlightSlot = vi.fn();

    render(
      <StructureEvidencePanel
        structure={fixtureVideoStructure}
        onHighlightSlot={onHighlightSlot}
      />,
    );

    await user.click(screen.getByTestId("evidence-card-seg-hook"));
    expect(onHighlightSlot).toHaveBeenCalledWith("slot-hook-visual");
  });
});

describe("GeneratedAssetBadge", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders provider label and tooltip metadata", () => {
    render(
      <GeneratedAssetBadge
        provider="image_generation"
        generatedBy={{ provider: "image_generation", model: "dall-e-3" }}
      />,
    );

    const badge = screen.getByTestId("generated-asset-badge");
    expect(badge).toHaveTextContent("AI 生图");
    expect(badge).toHaveAttribute("title", "模型 dall-e-3");
  });
});
