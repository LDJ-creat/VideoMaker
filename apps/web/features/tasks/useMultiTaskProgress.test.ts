import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useMultiTaskProgress } from "@/features/tasks/useMultiTaskProgress";
import { fixtureTaskEvent } from "@/fixtures";
import * as apiClient from "@/lib/apiClient";

class MockEventSource {
  static instances: MockEventSource[] = [];
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  url: string;
  readyState = MockEventSource.OPEN;
  onerror: (() => void) | null = null;
  private listeners = new Map<string, (event: MessageEvent) => void>();
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (event: MessageEvent) => void) {
    this.listeners.set(type, handler);
  }

  close() {
    this.closed = true;
    this.readyState = MockEventSource.CLOSED;
  }

  emitTask(data: unknown) {
    const handler = this.listeners.get("task");
    handler?.({ data: JSON.stringify(data) } as MessageEvent);
  }

  fail() {
    this.onerror?.();
  }
}

describe("useMultiTaskProgress", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
    vi.spyOn(apiClient, "getTask").mockResolvedValue({
      data: { ...fixtureTaskEvent, progress: 50, status: "running" },
      meta: { dataSource: "api" },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("skips EventSource when initial poll returns a terminal status", async () => {
    vi.mocked(apiClient.getTask).mockResolvedValue({
      data: {
        ...fixtureTaskEvent,
        taskId: "task-done",
        status: "succeeded",
        progress: 100,
      },
      meta: { dataSource: "api" },
    });

    const { result } = renderHook(() =>
      useMultiTaskProgress({
        tasks: [{ taskId: "task-done", label: "Done" }],
      }),
    );

    await waitFor(() =>
      expect(result.current.events["task-done"]?.status).toBe("succeeded"),
    );
    expect(MockEventSource.instances.length).toBe(0);
    expect(result.current.modes["task-done"]).toBe("completed");
  });

  it("invokes onMilestone for awaiting_review without onTerminal", async () => {
    vi.mocked(apiClient.getTask).mockResolvedValue({
      data: {
        ...fixtureTaskEvent,
        taskId: "task-review",
        progress: 50,
        status: "running",
      },
      meta: { dataSource: "api" },
    });

    const onMilestone = vi.fn();
    const onTerminal = vi.fn();

    renderHook(() =>
      useMultiTaskProgress({
        tasks: [{ taskId: "task-review", label: "Review" }],
        onTaskMilestone: onMilestone,
        onTaskTerminal: onTerminal,
      }),
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0]!;

    act(() => {
      source.emitTask({
        ...fixtureTaskEvent,
        taskId: "task-review",
        status: "awaiting_review",
        stage: "awaiting_master_review",
        progress: 47,
      });
    });

    expect(onMilestone).toHaveBeenCalled();
    expect(onTerminal).not.toHaveBeenCalled();
  });

  it("does not increment sse failure count on terminal close", async () => {
    const { result } = renderHook(() =>
      useMultiTaskProgress({
        tasks: [{ taskId: "task-live", label: "Live" }],
      }),
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0]!;

    act(() => {
      source.emitTask({
        ...fixtureTaskEvent,
        taskId: "task-live",
        status: "failed",
        progress: 0,
      });
    });

    await waitFor(() =>
      expect(result.current.events["task-live"]?.status).toBe("failed"),
    );
    expect(result.current.modes["task-live"]).toBe("completed");
    expect(source.closed).toBe(true);
    expect(result.current.sseFailureCounts["task-live"] ?? 0).toBe(0);
  });

  it("opens EventSource only for non-terminal tasks in a dual-task watch", async () => {
    vi.mocked(apiClient.getTask).mockImplementation(async (taskId: string) => {
      if (taskId === "task-a") {
        return {
          data: {
            ...fixtureTaskEvent,
            taskId: "task-a",
            status: "running",
            progress: 40,
          },
          meta: { dataSource: "api" },
        };
      }
      return {
        data: {
          ...fixtureTaskEvent,
          taskId: "task-b",
          status: "failed",
          progress: 0,
        },
        meta: { dataSource: "api" },
      };
    });

    renderHook(() =>
      useMultiTaskProgress({
        tasks: [
          { taskId: "task-a", label: "Running" },
          { taskId: "task-b", label: "Failed" },
        ],
      }),
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    expect(MockEventSource.instances[0]?.url).toContain("task-a");
  });

  it("preserves terminal events when watch is disabled", async () => {
    vi.mocked(apiClient.getTask).mockResolvedValue({
      data: {
        ...fixtureTaskEvent,
        taskId: "task-failed",
        status: "failed",
        progress: 0,
        message: "Generation failed",
      },
      meta: { dataSource: "api" },
    });

    const { result, rerender } = renderHook(
      ({ enabled }) =>
        useMultiTaskProgress({
          tasks: [{ taskId: "task-failed", label: "Failed" }],
          enabled,
        }),
      { initialProps: { enabled: true } },
    );

    await waitFor(() =>
      expect(result.current.events["task-failed"]?.status).toBe("failed"),
    );

    rerender({ enabled: false });

    await waitFor(() =>
      expect(result.current.events["task-failed"]?.status).toBe("failed"),
    );
    expect(result.current.events["task-failed"]?.message).toBe(
      "Generation failed",
    );
  });

  it("clears terminal event when task watch key changes for retry", async () => {
    vi.mocked(apiClient.getTask).mockResolvedValue({
      data: {
        ...fixtureTaskEvent,
        taskId: "task-retry",
        status: "failed",
        progress: 0,
        message: "Worker crashed",
      },
      meta: { dataSource: "api" },
    });

    const { result, rerender } = renderHook(
      ({ taskWatchKeys }) =>
        useMultiTaskProgress({
          tasks: [{ taskId: "task-retry", label: "Retry" }],
          taskWatchKeys,
        }),
      { initialProps: { taskWatchKeys: {} as Record<string, number> } },
    );

    await waitFor(() =>
      expect(result.current.events["task-retry"]?.status).toBe("failed"),
    );

    vi.mocked(apiClient.getTask).mockResolvedValue({
      data: {
        ...fixtureTaskEvent,
        taskId: "task-retry",
        status: "retrying",
        progress: 0,
        message: "Retry requested, resuming from checkpoint",
      },
      meta: { dataSource: "api" },
    });

    rerender({ taskWatchKeys: { "task-retry": 1 } });

    await waitFor(() =>
      expect(result.current.events["task-retry"]?.status).toBe("retrying"),
    );
    expect(result.current.events["task-retry"]?.error).toBeUndefined();
  });

  it("accepts terminal failed events even when updatedAt is slightly older than running", async () => {
    vi.mocked(apiClient.getTask).mockResolvedValue({
      data: {
        ...fixtureTaskEvent,
        taskId: "task-stale-ts",
        status: "running",
        stage: "running_agent",
        progress: 65,
        updatedAt: "2026-06-10T02:06:04.547625Z",
      },
      meta: { dataSource: "api" },
    });

    const { result } = renderHook(() =>
      useMultiTaskProgress({
        tasks: [{ taskId: "task-stale-ts", label: "Live" }],
      }),
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0]!;

    act(() => {
      source.emitTask({
        ...fixtureTaskEvent,
        taskId: "task-stale-ts",
        status: "failed",
        stage: "generating_material",
        progress: 60,
        message: "Material generation failed",
        updatedAt: "2026-06-10T02:06:04.500000Z",
        error: {
          code: "material_author_failed",
          message: "material_author could not author composition spec",
          retryable: false,
        },
      });
    });

    await waitFor(() =>
      expect(result.current.events["task-stale-ts"]?.status).toBe("failed"),
    );
  });

  it("only resets watch for the task whose watch key changed", async () => {
    vi.mocked(apiClient.getTask).mockImplementation(async (taskId: string) => {
      if (taskId === "task-a") {
        return {
          data: {
            ...fixtureTaskEvent,
            taskId: "task-a",
            status: "running",
            progress: 40,
          },
          meta: { dataSource: "api" },
        };
      }
      return {
        data: {
          ...fixtureTaskEvent,
          taskId: "task-b",
          status: "failed",
          progress: 0,
        },
        meta: { dataSource: "api" },
      };
    });

    const { rerender } = renderHook(
      ({ taskWatchKeys }) =>
        useMultiTaskProgress({
          tasks: [
            { taskId: "task-a", label: "Running" },
            { taskId: "task-b", label: "Failed" },
          ],
          taskWatchKeys,
        }),
      { initialProps: { taskWatchKeys: {} as Record<string, number> } },
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBeGreaterThanOrEqual(1));
    const firstSource = MockEventSource.instances[0]!;

    rerender({ taskWatchKeys: { "task-a": 1 } });

    await waitFor(() =>
      expect(
        MockEventSource.instances.filter((source) =>
          source.url.includes("task-a"),
        ).length,
      ).toBeGreaterThanOrEqual(2),
    );
    expect(firstSource.readyState).toBe(2);
  });

  it("ignores duplicate SSE snapshots after preferTaskError merge", async () => {
    const { result } = renderHook(() =>
      useMultiTaskProgress({ tasks: [{ taskId: "task-a" }] }),
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0]!;
    const snapshot = {
      ...fixtureTaskEvent,
      taskId: "task-a",
      status: "running",
      progress: 55,
      updatedAt: "2026-06-10T12:00:55.000Z",
    };

    source.emitTask(snapshot);
    await waitFor(() => expect(result.current.events["task-a"]?.progress).toBe(55));
    const eventsAfterFirst = result.current.events;

    source.emitTask({ ...snapshot });
    await act(async () => {});

    expect(result.current.events).toBe(eventsAfterFirst);
  });

  it("passes after_id when task watch key changes after events were received", async () => {
    vi.mocked(apiClient.getTask).mockResolvedValue({
      data: {
        ...fixtureTaskEvent,
        taskId: "task-replay",
        progress: 40,
        status: "running",
      },
      meta: { dataSource: "api" },
    });

    const onMilestone = vi.fn();

    const { rerender } = renderHook(
      ({ taskWatchKeys }) =>
        useMultiTaskProgress({
          tasks: [{ taskId: "task-replay", label: "Replay" }],
          taskWatchKeys,
          onTaskMilestone: onMilestone,
        }),
      { initialProps: { taskWatchKeys: {} as Record<string, number> } },
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const firstSource = MockEventSource.instances[0]!;

    act(() => {
      firstSource.emitTask({
        ...fixtureTaskEvent,
        taskId: "task-replay",
        status: "awaiting_review",
        stage: "awaiting_master_review",
        eventId: 7,
      });
    });

    await waitFor(() => expect(onMilestone).toHaveBeenCalledTimes(1));

    vi.mocked(apiClient.getTask).mockResolvedValue({
      data: {
        ...fixtureTaskEvent,
        taskId: "task-replay",
        status: "awaiting_review",
        stage: "awaiting_master_review",
        progress: 62,
        eventId: 7,
      },
      meta: { dataSource: "api" },
    });

    onMilestone.mockClear();
    rerender({ taskWatchKeys: { "task-replay": 1 } });

    await waitFor(() => expect(MockEventSource.instances.length).toBe(2));
    expect(MockEventSource.instances[1]?.url).toContain("after_id=7");
    expect(onMilestone).not.toHaveBeenCalled();

    act(() => {
      MockEventSource.instances[1]!.emitTask({
        ...fixtureTaskEvent,
        taskId: "task-replay",
        status: "awaiting_review",
        stage: "awaiting_master_review",
        eventId: 7,
      });
    });
    expect(onMilestone).not.toHaveBeenCalled();
  });
});
