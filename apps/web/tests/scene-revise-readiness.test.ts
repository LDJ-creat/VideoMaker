import { describe, expect, it } from "vitest";

import { fixtureGenerationPlan } from "@/fixtures";
import { isGenerationReadyForSceneRevise } from "@/lib/sceneReviseReadiness";

describe("isGenerationReadyForSceneRevise", () => {
  it("allows scene revise while awaiting material review", () => {
    expect(
      isGenerationReadyForSceneRevise(
        {
          taskId: "task-1",
          status: "awaiting_review",
          stage: "awaiting_material_review",
          progress: 72,
          message: "Review materials",
          updatedAt: "2026-06-30T00:00:00.000Z",
        },
        fixtureGenerationPlan,
      ),
    ).toBe(true);
  });

  it("allows scene revise after succeeded", () => {
    expect(
      isGenerationReadyForSceneRevise(
        {
          taskId: "task-1",
          status: "succeeded",
          stage: "completed",
          progress: 100,
          message: "Done",
          updatedAt: "2026-06-30T00:00:00.000Z",
        },
        fixtureGenerationPlan,
      ),
    ).toBe(true);
  });

  it("blocks scene revise while material is still generating", () => {
    expect(
      isGenerationReadyForSceneRevise(
        {
          taskId: "task-1",
          status: "running",
          stage: "generating_material",
          progress: 60,
          message: "Generating",
          updatedAt: "2026-06-30T00:00:00.000Z",
        },
        fixtureGenerationPlan,
      ),
    ).toBe(false);
  });
});
