import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useTaskProgress } from "@/features/tasks/useTaskProgress";
import { fixtureTaskEvent } from "@/fixtures";
import * as apiClient from "@/lib/apiClient";

class MockEventSource {
  static instances: MockEventSource[] = [];
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  url: string;
  readyState = MockEventSource.OPEN;
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
    vi.mocked(apiClient.getTask).mockResolvedValue({
      data: { ...fixtureTaskEvent, status: "running", progress: 50 },
      meta: { dataSource: "api" },
    });

    const { result } = renderHook(() =>
      useTaskProgress({ taskId: "task-demo-001" }),
    );

    await waitFor(() => expect(result.current.mode).toBe("sse"));
    const source = MockEventSource.instances[0]!;

    act(() => {
      source.fail();
      source.fail();
      source.fail();
    });

    await waitFor(() => expect(result.current.mode).toBe("polling"));
    expect(apiClient.getTask).toHaveBeenCalled();
  });

  it("accepts terminal failed snapshots even when timestamp is older than running", async () => {
    vi.mocked(apiClient.getTask).mockResolvedValue({
      data: {
        ...fixtureTaskEvent,
        taskId: "task-demo-001",
        status: "running",
        progress: 55,
        message: "Direct multimodal structure extraction",
        updatedAt: "2026-06-10T12:10:00.000Z",
      },
      meta: { dataSource: "api" },
    });

    const { result } = renderHook(() =>
      useTaskProgress({ taskId: "task-demo-001" }),
    );

    await waitFor(() => expect(result.current.event?.status).toBe("running"));

    const source = MockEventSource.instances[0]!;
    act(() => {
      source.emitTask({
        ...fixtureTaskEvent,
        taskId: "task-demo-001",
        status: "failed",
        progress: 72,
        message: "Direct multimodal structure extraction failed",
        updatedAt: "2026-06-10T12:09:00.000Z",
        error: {
          code: "direct_multimodal_failed",
          message: "Server disconnected without sending a response.",
          retryable: true,
        },
      });
    });

    expect(result.current.event?.status).toBe("failed");
    expect(result.current.event?.error?.code).toBe("direct_multimodal_failed");
  });

  it("invokes onMilestone for status changes", async () => {
    const onMilestone = vi.fn();
    renderHook(() =>
      useTaskProgress({ taskId: "task-demo-001", onMilestone }),
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0]!;

    act(() => {
      source.emitTask({
        ...fixtureTaskEvent,
        taskId: "task-demo-001",
        status: "awaiting_review",
        stage: "awaiting_master_review",
      });
    });

    expect(onMilestone).toHaveBeenCalled();
  });

  it("completes on terminal SSE event without sse failure count", async () => {
    vi.mocked(apiClient.getTask).mockResolvedValue({
      data: { ...fixtureTaskEvent, status: "running", progress: 50 },
      meta: { dataSource: "api" },
    });

    const onTerminal = vi.fn();
    const { result } = renderHook(() =>
      useTaskProgress({ taskId: "task-demo-001", onTerminal }),
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0]!;

    act(() => {
      source.emitTask({
        ...fixtureTaskEvent,
        status: "succeeded",
        progress: 100,
      });
    });

    await waitFor(() => expect(result.current.mode).toBe("completed"));
    expect(result.current.sseFailureCount).toBe(0);
    expect(onTerminal).toHaveBeenCalled();
  });
});
