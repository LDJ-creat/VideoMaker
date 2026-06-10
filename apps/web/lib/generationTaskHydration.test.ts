import { describe, expect, it } from "vitest";

import {
  buildGenerationStatusByTaskId,
  canRetryGenerationTask,
  hasRetryableFailedGeneration,
  isGenerationRenderIncomplete,
} from "@/lib/generationTaskHydration";

describe("generationTaskHydration", () => {
  it("detects succeeded generations without render video as incomplete", () => {
    expect(
      isGenerationRenderIncomplete({
        status: "succeeded",
        taskId: "task-1",
        plan: { renderVideoUrl: undefined },
      }),
    ).toBe(true);
  });

  it("allows retry for render-incomplete succeeded generations", () => {
    expect(
      canRetryGenerationTask({
        status: "succeeded",
        taskId: "task-1",
      }),
    ).toBe(true);
    expect(hasRetryableFailedGeneration([{ status: "failed", taskId: "task-2" }])).toBe(
      true,
    );
  });

  it("prefers live status map over static generation entry status", () => {
    const statuses = buildGenerationStatusByTaskId(
      [{ taskId: "task-1", status: "queued" }],
      { "task-1": "running" },
    );
    expect(statuses["task-1"]).toBe("running");
  });

  it("does not retry succeeded generations with render video", () => {
    expect(
      canRetryGenerationTask({
        status: "succeeded",
        taskId: "task-1",
        renderVideoUrl: "/api/projects/p/media/file/renders/g/output.mp4",
      }),
    ).toBe(false);
  });
});
