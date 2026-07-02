import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MaterialReviewPanel } from "@/features/material-review/MaterialReviewPanel";

vi.mock("@/lib/apiClient", () => ({
  fetchMaterialReview: vi.fn().mockResolvedValue({
    data: {
      state: {
        generationId: "gen-fork",
        projectId: "proj-1",
        variant: "high_click",
        status: "draft",
        slots: {
          "slot-1": { status: "agent_passed" },
          "slot-6": { status: "pending" },
        },
      },
      reports: {},
      slotPreviewUrls: {},
      reviseContext: {
        scope: "scoped",
        sourceGenerationId: "gen-source",
        affectedSlotIds: ["slot-6"],
      },
    },
  }),
  approveMaterialReview: vi.fn(),
  reviseMaterialSlot: vi.fn(),
}));

describe("MaterialReviewPanel", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("highlights revise fork affected slots", async () => {
    render(
      <MaterialReviewPanel
        projectId="proj-1"
        generationId="gen-fork"
        stage="awaiting_material_review"
      />,
    );

    expect(await screen.findByText(/改片 fork/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /slot-6 · pending · 改片/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /slot-1 · agent_passed · 继承/ })).toBeInTheDocument();
  });
});
