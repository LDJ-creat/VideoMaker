import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CompositionPatternPromotePanel } from "@/features/knowledge/CompositionPatternPromotePanel";

vi.mock("@/lib/apiClient", () => ({
  getCompositionPatterns: vi.fn(),
  promoteCompositionPattern: vi.fn(),
}));

import {
  getCompositionPatterns,
  promoteCompositionPattern,
} from "@/lib/apiClient";

describe("CompositionPatternPromotePanel", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getCompositionPatterns).mockResolvedValue({
      data: {
        generationId: "gen-1",
        patterns: [
          {
            slotId: "slot-1",
            slotRole: "benefit_card",
            storyboardSummary: "核心卖点展示",
            draftReady: true,
          },
        ],
      },
      meta: { dataSource: "api" },
    });
    vi.mocked(promoteCompositionPattern).mockResolvedValue({
      data: {
        entry: {
          id: "comp-gen-1-slot-1",
          title: "Benefit Card",
          updatedAt: "2026-06-08T00:00:00Z",
        },
      },
      meta: { dataSource: "api" },
    } as never);
  });

  it("renders promote button and completes promote", async () => {
    render(
      <CompositionPatternPromotePanel
        projectId="project-1"
        generationId="gen-1"
        videoReady
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("composition-pattern-promote-panel")).toBeInTheDocument();
    });

    expect(screen.getByTestId("composition-pattern-hint")).toHaveTextContent("发现 1 个可入库分镜");

    await userEvent.click(screen.getByTestId("composition-pattern-promote-slot-1"));

    await waitFor(() => {
      expect(promoteCompositionPattern).toHaveBeenCalledWith("project-1", {
        generationId: "gen-1",
        slotId: "slot-1",
        confirm: true,
      });
      expect(screen.getByTestId("composition-pattern-published-badge")).toBeInTheDocument();
    });
  });

  it("shows empty hint when no patterns are available", async () => {
    vi.mocked(getCompositionPatterns).mockResolvedValue({
      data: { generationId: "gen-1", patterns: [] },
      meta: { dataSource: "api" },
    });

    render(
      <CompositionPatternPromotePanel
        projectId="project-1"
        generationId="gen-1"
        videoReady
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("composition-pattern-empty")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("composition-pattern-promote-slot-1")).not.toBeInTheDocument();
  });

  it("does not render when video is not ready", () => {
    vi.mocked(getCompositionPatterns).mockClear();
    render(
      <CompositionPatternPromotePanel
        projectId="project-1"
        generationId="gen-1"
        videoReady={false}
      />,
    );
    expect(screen.queryByTestId("composition-pattern-promote-panel")).not.toBeInTheDocument();
    expect(getCompositionPatterns).not.toHaveBeenCalled();
  });
});
