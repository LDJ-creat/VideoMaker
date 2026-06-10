import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StructureEvidencePanel } from "@/features/structure-evidence/StructureEvidencePanel";
import { fixtureVideoStructure } from "@/fixtures";

describe("StructureEvidencePanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows timeline master-detail with Chinese role labels", () => {
    render(
      <StructureEvidencePanel
        structure={fixtureVideoStructure}
        onHighlightSlot={() => undefined}
      />,
    );

    expect(screen.getByTestId("structure-evidence-panel")).toBeInTheDocument();
    expect(screen.getByTestId("structure-hero")).toBeInTheDocument();
    expect(screen.getByTestId("narrative-timeline")).toBeInTheDocument();
    expect(screen.getByTestId("segment-detail-panel")).toBeInTheDocument();
    expect(
      screen.getByTestId("segment-detail-panel").textContent,
    ).toContain("开场钩子");
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

  it("invokes highlight callback when timeline segment clicked", async () => {
    const user = userEvent.setup();
    const onHighlightSlot = vi.fn();
    const secondSegment = fixtureVideoStructure.narrative.segments[1];
    if (!secondSegment) return;

    render(
      <StructureEvidencePanel
        structure={fixtureVideoStructure}
        onHighlightSlot={onHighlightSlot}
      />,
    );

    await user.click(screen.getByTestId(`timeline-segment-${secondSegment.id}`));
    expect(onHighlightSlot).toHaveBeenCalled();
  });

  it("shows v3 track panel inside expanded details by default", () => {
    render(
      <StructureEvidencePanel
        structure={fixtureVideoStructure}
        onHighlightSlot={() => undefined}
      />,
    );

    const summary = screen.getByText("四轨深度洞察");
    expect(summary).toBeInTheDocument();
    expect(summary.closest("details")).toHaveAttribute("open");
  });
});
