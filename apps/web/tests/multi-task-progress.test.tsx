import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useMultiTaskProgress } from "@/features/tasks/useMultiTaskProgress";
import { fixtureMaterialTaskEvent, fixtureTaskEvent } from "@/fixtures";
import * as apiClient from "@/lib/apiClient";

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onerror: (() => void) | null = null;
  private listeners = new Map<string, (event: MessageEvent) => void>();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (event: MessageEvent) => void) {
    this.listeners.set(type, handler);
  }

  close() {
    /* noop */
  }

  emitTask(data: unknown) {
    const handler = this.listeners.get("task");
    handler?.({ data: JSON.stringify(data) } as MessageEvent);
  }
}

describe("useMultiTaskProgress", () => {
  const dualTasks = [
    { taskId: "task-a", label: "A" },
    { taskId: "task-b", label: "B" },
  ];
  const pairTasks = [{ taskId: "task-a" }, { taskId: "task-b" }];

  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
    vi.spyOn(apiClient, "getTask").mockImplementation(async (taskId) => ({
      data: { ...fixtureTaskEvent, taskId, status: "running" as const },
      meta: { dataSource: "api" },
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("tracks multiple tasks independently", async () => {
    const { result } = renderHook(() =>
      useMultiTaskProgress({
        tasks: dualTasks,
      }),
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBe(2));

    act(() => {
      MockEventSource.instances[0]!.emitTask({
        ...fixtureMaterialTaskEvent,
        taskId: "task-a",
        progress: 40,
      });
    });

    expect(result.current.events["task-a"]?.progress).toBe(40);
    expect(result.current.events["task-b"]?.status).toBe("running");
    expect(result.current.allTerminal).toBe(false);
    expect(result.current.byTaskId["task-a"]?.event?.progress).toBe(40);
  });

  it("reports allTerminal and anyFailed", async () => {
    const { result } = renderHook(() =>
      useMultiTaskProgress({
        tasks: pairTasks,
      }),
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBe(2));

    act(() => {
      MockEventSource.instances[0]!.emitTask({
        ...fixtureTaskEvent,
        taskId: "task-a",
        status: "succeeded",
        progress: 100,
      });
    });

    act(() => {
      MockEventSource.instances[1]!.emitTask({
        ...fixtureTaskEvent,
        taskId: "task-b",
        status: "failed",
        progress: 50,
        error: { code: "gateway_not_configured", message: "missing", retryable: true },
      });
    });

    await waitFor(() => expect(result.current.allTerminal).toBe(true));
    expect(result.current.anyFailed).toBe(true);
  });
});
