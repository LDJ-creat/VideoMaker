import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useTaskProgress } from "@/features/tasks/useTaskProgress";
import { fixtureTaskEvent } from "@/fixtures";

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  close() {
    /* noop */
  }

  emit(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }

  fail() {
    this.onerror?.();
  }
}

describe("useTaskProgress", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ ...fixtureTaskEvent, progress: 99 }),
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("prefers SSE and updates from EventSource messages", async () => {
    const { result } = renderHook(() =>
      useTaskProgress({
        apiBaseUrl: "http://localhost:8000",
        taskId: "task-demo-001",
      }),
    );

    await waitFor(() => expect(result.current.mode).toBe("sse"));

    const source = MockEventSource.instances[0];
    act(() => {
      source.emit({ ...fixtureTaskEvent, progress: 75 });
    });

    expect(result.current.event?.progress).toBe(75);
    expect(result.current.mode).toBe("sse");
  });

  it("falls back to polling after three SSE failures", async () => {
    const { result } = renderHook(() =>
      useTaskProgress({
        apiBaseUrl: "http://localhost:8000",
        taskId: "task-demo-001",
      }),
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0];

    act(() => {
      source.fail();
      source.fail();
      source.fail();
    });

    await waitFor(() => expect(result.current.mode).toBe("polling"));
    expect(result.current.sseFailureCount).toBeGreaterThanOrEqual(3);

    await waitFor(() => expect(fetch).toHaveBeenCalled());
  });
});
