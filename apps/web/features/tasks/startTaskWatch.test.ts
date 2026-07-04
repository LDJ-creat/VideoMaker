import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fixtureTaskEvent } from "@/fixtures";
import * as apiClient from "@/lib/apiClient";
import { SSE_FAILURE_THRESHOLD } from "@/features/tasks/taskProgressConstants";
import { startTaskWatch } from "@/features/tasks/startTaskWatch";

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  readyState = 1;
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
    this.readyState = 2;
  }

  emitTask(data: unknown) {
    const handler = this.listeners.get("task");
    handler?.({ data: JSON.stringify(data) } as MessageEvent);
  }

  fail() {
    this.onerror?.();
  }
}

describe("startTaskWatch", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
    vi.spyOn(apiClient, "getTask").mockResolvedValue({
      data: { ...fixtureTaskEvent, status: "running", progress: 10 },
      meta: { dataSource: "api" },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("opens SSE with after_id cursor from initialAfterId", async () => {
    const cleanup = startTaskWatch({
      taskId: "task-cursor",
      applyEvent: vi.fn(),
      setMode: vi.fn(),
      setSseFailureCount: vi.fn(),
      setError: vi.fn(),
      isDisposed: () => false,
      initialAfterId: 42,
    });

    await vi.waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    expect(MockEventSource.instances[0]?.url).toBe(
      "/api/tasks/task-cursor/events?after_id=42",
    );
    cleanup();
  });

  it("counts SSE errors even when readyState is not OPEN", async () => {
    const setSseFailureCount = vi.fn();
    const cleanup = startTaskWatch({
      taskId: "task-sse-fail",
      applyEvent: vi.fn(),
      setMode: vi.fn(),
      setSseFailureCount,
      setError: vi.fn(),
      isDisposed: () => false,
    });

    await vi.waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0]!;
    source.readyState = 0;

    for (let index = 0; index < SSE_FAILURE_THRESHOLD; index += 1) {
      source.fail();
    }

    await vi.waitFor(() =>
      expect(setSseFailureCount).toHaveBeenCalledTimes(SSE_FAILURE_THRESHOLD),
    );
    cleanup();
  });

  it("does not count SSE failures after intentional terminal close", async () => {
    const setSseFailureCount = vi.fn();
    const applyEvent = vi.fn(() => true);
    const cleanup = startTaskWatch({
      taskId: "task-terminal",
      applyEvent,
      setMode: vi.fn(),
      setSseFailureCount,
      setError: vi.fn(),
      isDisposed: () => false,
    });

    await vi.waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0]!;

    source.emitTask({
      ...fixtureTaskEvent,
      taskId: "task-terminal",
      status: "succeeded",
      progress: 100,
    });

    const callsBeforeFailure = setSseFailureCount.mock.calls.length;
    source.fail();
    source.fail();

    expect(setSseFailureCount.mock.calls.length).toBe(callsBeforeFailure);
    cleanup();
  });
});
