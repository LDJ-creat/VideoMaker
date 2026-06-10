import { describe, expect, it } from "vitest";

import type { TaskEvent } from "@videomaker/contracts";

import { fixtureTaskEvent } from "@/fixtures";
import {
  mergeTaskEventsIfChanged,
  preferTaskError,
  shouldAcceptTaskEventUpdate,
  taskEventEquals,
} from "@/lib/taskEventMerge";

function taskEvent(overrides: Partial<TaskEvent> = {}): TaskEvent {
  return {
    ...fixtureTaskEvent,
    taskId: "task-1",
    status: "running",
    stage: "generating_material",
    progress: 42,
    message: "working",
    updatedAt: "2026-06-10T12:00:00.000Z",
    ...overrides,
  };
}

describe("taskEventEquals", () => {
  it("returns true for semantically equal events", () => {
    expect(taskEventEquals(taskEvent(), taskEvent())).toBe(true);
  });

  it("returns false when progress changes", () => {
    expect(
      taskEventEquals(taskEvent(), taskEvent({ progress: 43 })),
    ).toBe(false);
  });
});

describe("mergeTaskEventsIfChanged", () => {
  it("returns null when patch does not change snapshots", () => {
    const previous = { "task-1": taskEvent() };
    const patch = { "task-1": taskEvent() };
    expect(mergeTaskEventsIfChanged(previous, patch)).toBeNull();
  });

  it("returns merged map when patch changes a snapshot", () => {
    const previous = { "task-1": taskEvent() };
    const patch = { "task-1": taskEvent({ progress: 50 }) };
    const merged = mergeTaskEventsIfChanged(previous, patch);
    expect(merged?.["task-1"]?.progress).toBe(50);
  });
});

describe("preferTaskError", () => {
  it("strips error from active retry/running snapshots", () => {
    const merged = preferTaskError(
      taskEvent({
        status: "failed",
        progress: 72,
        error: {
          code: "direct_multimodal_failed",
          message: "Server disconnected without sending a response.",
          retryable: true,
        },
      }),
      taskEvent({
        status: "running",
        progress: 55,
        message: "Direct multimodal structure extraction",
        error: {
          code: "direct_multimodal_failed",
          message: "Server disconnected without sending a response.",
          retryable: true,
        },
      }),
    );
    expect(merged.status).toBe("running");
    expect(merged.error).toBeUndefined();
  });
});

describe("shouldAcceptTaskEventUpdate", () => {
  it("rejects stale failed snapshots after a newer running event", () => {
    const running = taskEvent({
      status: "running",
      progress: 55,
      updatedAt: "2026-06-10T12:10:00.000Z",
    });
    const staleFailed = taskEvent({
      status: "failed",
      progress: 72,
      updatedAt: "2026-06-10T12:09:00.000Z",
      error: {
        code: "direct_multimodal_failed",
        message: "Server disconnected without sending a response.",
        retryable: true,
      },
    });
    expect(shouldAcceptTaskEventUpdate(running, staleFailed)).toBe(false);
  });
});
