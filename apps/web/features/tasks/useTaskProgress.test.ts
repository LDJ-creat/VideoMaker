import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useTaskProgress } from "@/features/tasks/useTaskProgress";
import { fixtureTaskEvent } from "@/fixtures";
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

  fail() {
    this.onerror?.();
  }
}

describe("useTaskProgress", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
    vi.spyOn(apiClient, "getTask").mockResolvedValue({
      data: { ...fixtureTaskEvent, progress: 99, status: "running" },
      meta: { dataSource: "api" },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("listens for task SSE events", async () => {
    const { result } = renderHook(() =>
      useTaskProgress({ taskId: "task-demo-001" }),
    );

    await waitFor(() => expect(result.current.mode).toBe("sse"));

    const source = MockEventSource.instances[0]!;
    expect(source.url).toBe("/api/tasks/task-demo-001/events");

    act(() => {
      source.emitTask({ ...fixtureTaskEvent, progress: 75 });
    });

    expect(result.current.event?.progress).toBe(75);
  });

  it("falls back to polling after three SSE failures", async () => {
    const { result } = renderHook(() =>
      useTaskProgress({ taskId: "task-demo-001" }),
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0]!;

    act(() => {
      source.fail();
      source.fail();
      source.fail();
    });

    await waitFor(() => expect(result.current.mode).toBe("polling"));
    expect(apiClient.getTask).toHaveBeenCalled();
  });

  it("stops polling on terminal status", async () => {
    vi.mocked(apiClient.getTask).mockResolvedValue({
      data: { ...fixtureTaskEvent, status: "succeeded", progress: 100 },
      meta: { dataSource: "api" },
    });

    const onTerminal = vi.fn();
    const { result } = renderHook(() =>
      useTaskProgress({ taskId: "task-demo-001", onTerminal }),
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0]!;

    act(() => {
      source.fail();
      source.fail();
      source.fail();
    });

    await waitFor(() => expect(result.current.mode).toBe("completed"));
    expect(onTerminal).toHaveBeenCalled();
    const callsAfterTerminal = vi.mocked(apiClient.getTask).mock.calls.length;

    await new Promise((r) => setTimeout(r, 100));
    expect(vi.mocked(apiClient.getTask).mock.calls.length).toBe(
      callsAfterTerminal,
    );
  });
});
