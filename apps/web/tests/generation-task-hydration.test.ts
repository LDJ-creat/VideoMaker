import { describe, expect, it } from "vitest";

import {
  buildGenerationStatusByTaskId,
  hasRetryableFailedGeneration,
  shouldWatchGenerationTasks,
} from "@/lib/generationTaskHydration";

describe("generationTaskHydration", () => {
  it("detects retryable failed generations", () => {
    expect(
      hasRetryableFailedGeneration([
        { status: "failed", taskId: "task-a" },
        { status: "succeeded", taskId: "task-b" },
      ]),
    ).toBe(true);
    expect(
      hasRetryableFailedGeneration([{ status: "failed", taskId: null }]),
    ).toBe(false);
  });

  it("builds task status map from generation snapshots", () => {
    expect(
      buildGenerationStatusByTaskId([
        { status: "failed", taskId: "task-a" },
        { status: "running", taskId: "task-b" },
      ]),
    ).toEqual({
      "task-a": "failed",
      "task-b": "running",
    });
  });

  it("does not watch terminal failed tasks", () => {
    expect(
      shouldWatchGenerationTasks(
        [
          { taskId: "task-a", status: "failed" },
          { taskId: "task-b", status: "succeeded" },
        ],
        { "task-a": "failed", "task-b": "succeeded" },
      ),
    ).toBe(false);
  });

  it("watches only in-flight generation tasks", () => {
    expect(
      shouldWatchGenerationTasks(
        [
          { taskId: "task-a", status: "failed" },
          { taskId: "task-b", status: "running" },
        ],
        { "task-a": "failed", "task-b": "running" },
      ),
    ).toBe(true);
  });
});
