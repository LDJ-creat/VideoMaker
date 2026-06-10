import type { TaskEvent } from "@videomaker/contracts";
import { describe, expect, it } from "vitest";

import { mergeTaskEvents, preferTaskError } from "@/lib/taskEventMerge";

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

  it("prefers fresh running events over stale failed errors", () => {
    const previous: TaskEvent = {
      taskId: "task-1",
      status: "failed",
      stage: "analyzing_assets",
      progress: 0,
      message: "Worker crashed: name 'reconcile_gap_finish_from_storyboard' is not defined",
      updatedAt: "2026-06-10T00:27:05.275955Z",
      error: {
        code: "worker_unhandled_error",
        message: "name 'reconcile_gap_finish_from_storyboard' is not defined",
        retryable: true,
      },
    };
    const next: TaskEvent = {
      taskId: "task-1",
      status: "retrying",
      stage: "analyzing_assets",
      progress: 0,
      message: "Retry requested, resuming from checkpoint",
      updatedAt: "2026-06-10T01:58:27.489946Z",
    };

    const merged = preferTaskError(previous, next);
    expect(merged.status).toBe("retrying");
    expect(merged.error).toBeUndefined();
  });

  it("does not inherit specific errors from an earlier retry attempt", () => {
    const previous: TaskEvent = {
      taskId: "task-1",
      status: "failed",
      stage: "analyzing_assets",
      progress: 0,
      message: "Worker crashed: name 'install_registry_blocks' is not defined",
      updatedAt: "2026-06-10T05:51:23.411993Z",
      error: {
        code: "worker_unhandled_error",
        message: "name 'install_registry_blocks' is not defined",
        retryable: true,
      },
    };
    const next: TaskEvent = {
      taskId: "task-1",
      status: "failed",
      stage: "analyzing_assets",
      progress: 0,
      message: "Generation failed",
      updatedAt: "2026-06-10T06:01:08.553295Z",
      error: {
        code: "generation_failed",
        message: "Worker task failed",
        retryable: true,
      },
    };

    const merged = preferTaskError(previous, next);
    expect(merged.error?.code).toBe("generation_failed");
    expect(merged.message).toBe("Generation failed");
  });
});

describe("mergeTaskEvents", () => {
  it("prefers newer settled running over stale live failed", () => {
    const settled: Record<string, TaskEvent> = {
      "task-1": {
        taskId: "task-1",
        status: "running",
        stage: "generating_material",
        progress: 65,
        message: "Authoring HyperFrames material spec",
        updatedAt: "2026-06-10T02:02:00.000Z",
      },
    };
    const live: Record<string, TaskEvent> = {
      "task-1": {
        taskId: "task-1",
        status: "failed",
        stage: "analyzing_assets",
        progress: 0,
        message: "Worker crashed: name 'reconcile_gap_finish_from_storyboard' is not defined",
        updatedAt: "2026-06-10T00:27:05.275955Z",
        error: {
          code: "worker_unhandled_error",
          message: "name 'reconcile_gap_finish_from_storyboard' is not defined",
          retryable: true,
        },
      },
    };

    const merged = mergeTaskEvents(settled, live);
    expect(merged["task-1"]?.status).toBe("running");
  });

  it("keeps specific tts error when newer generic generation_failed arrives", () => {
    const settled: Record<string, TaskEvent> = {
      "task-1": {
        taskId: "task-1",
        status: "failed",
        stage: "generating_material",
        progress: 60,
        message: "Material generation failed",
        updatedAt: "2026-06-10T02:25:51.627323Z",
        error: {
          code: "tts_failed",
          message:
            'HTTP 401: {"header":{"code":45000010,"message":"Invalid X-Api-Key"}}',
          retryable: true,
        },
      },
    };
    const live: Record<string, TaskEvent> = {
      "task-1": {
        taskId: "task-1",
        status: "failed",
        stage: "analyzing_assets",
        progress: 0,
        message: "Generation failed",
        updatedAt: "2026-06-10T02:25:51.830535Z",
        error: {
          code: "generation_failed",
          message: "Worker task failed",
          retryable: true,
        },
      },
    };

    const merged = mergeTaskEvents(settled, live);
    expect(merged["task-1"]?.error?.code).toBe("tts_failed");
    expect(merged["task-1"]?.message).toBe("Material generation failed");
  });
});
