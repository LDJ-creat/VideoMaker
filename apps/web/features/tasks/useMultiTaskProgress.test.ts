import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useMultiTaskProgress } from "@/features/tasks/useMultiTaskProgress";
import { fixtureTaskEvent } from "@/fixtures";
import * as apiClient from "@/lib/apiClient";

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
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

  it("stops SSE subscriptions when a task reaches a terminal status", async () => {
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

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0]!;

    await waitFor(() =>
      expect(result.current.events["task-done"]?.status).toBe("succeeded"),
    );
    expect(result.current.modes["task-done"]).toBe("completed");
    expect(source.closed).toBe(true);

    const getTaskCalls = vi.mocked(apiClient.getTask).mock.calls.length;
    await new Promise((resolve) => setTimeout(resolve, 150));
    expect(vi.mocked(apiClient.getTask).mock.calls.length).toBe(getTaskCalls);
  });

  it("closes EventSource after terminal task event over SSE", async () => {
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
  });
});
