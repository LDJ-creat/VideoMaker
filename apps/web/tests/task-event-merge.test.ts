import type { TaskEvent } from "@videomaker/contracts";
import { describe, expect, it } from "vitest";

import { preferTaskError } from "@/lib/taskEventMerge";

describe("preferTaskError", () => {
  it("keeps specific material error over generic generation_failed wrapper", () => {
    const previous: TaskEvent = {
      taskId: "task-1",
      status: "failed",
      stage: "generating_material",
      progress: 60,
      message: "Material generation failed",
      updatedAt: "2026-06-02T10:00:11.312501Z",
      error: {
        code: "video_generation_failed",
        message: "HTTP 404: ",
        retryable: true,
      },
    };
    const next: TaskEvent = {
      taskId: "task-1",
      status: "failed",
      stage: "analyzing_assets",
      progress: 0,
      message: "Generation failed",
      updatedAt: "2026-06-02T10:00:11.624802Z",
      error: {
        code: "generation_failed",
        message: "Worker task failed",
        retryable: true,
      },
    };

    const merged = preferTaskError(previous, next);
    expect(merged.error?.code).toBe("video_generation_failed");
    expect(merged.message).toBe("Material generation failed");
  });
});
