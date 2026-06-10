import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GenerationMigrationProgressPanel } from "@/features/structure-migration/GenerationMigrationProgressPanel";
import { fixtureTaskEvent, fixtureVideoStructure } from "@/fixtures";

vi.mock("@/features/structure-migration/useGenerationMigrationArtifacts", () => ({
  useGenerationMigrationArtifacts: () => ({
    artifacts: {
      slotMatches: [],
      gapReport: {
        id: "gap-1",
        projectId: "p1",
        structureId: "s1",
        inventoryId: "i1",
        summary: "gaps",
        slotMatches: [],
        weakSlots: [],
        missingSlots: [
          {
            slotId: "slot-cta",
            reason: "missing visual",
            impact: "high",
            suggestedFixes: ["hyperframes_material"],
          },
        ],
      },
      completionActions: [
        {
          id: "action-cta",
          slotId: "slot-cta",
          provider: "hyperframes_material",
          strategy: "hyperframes_material",
          reason: "fill",
          outputRef: "x",
        },
      ],
      materialState: null,
    },
    progressGroup: "completing" as const,
  }),
}));

describe("GenerationMigrationProgressPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows active migration table during running_agent HyperFrames work", () => {
    render(
      <GenerationMigrationProgressPanel
        context={{
          projectId: "proj-1",
          generationId: "gen-1",
          structure: fixtureVideoStructure,
          variantLabel: "高转化版",
        }}
        event={{
          ...fixtureTaskEvent,
          stage: "running_agent",
          status: "running",
          message: "Authoring HyperFrames material spec for slot-cta",
        }}
      />,
    );

    expect(screen.queryByTestId("migration-pre-stage-shell")).not.toBeInTheDocument();
    expect(screen.getByTestId("generation-migration-progress-panel")).toBeInTheDocument();
    expect(screen.getByText(/补全策略已确定/)).toBeInTheDocument();
  });
});
