import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TaskEvent } from "@videomaker/contracts";

import { fixtureTaskEvent } from "@/fixtures";
import * as apiClient from "@/lib/apiClient";

import { ProjectWorkbench } from "./ProjectWorkbench";

const activeGenerations = [
  {
    generationId: "gen-high-click",
    variant: "high_click",
    taskId: "task-gen-a",
    label: "高点击",
    status: "running",
  },
  {
    generationId: "gen-high-conversion",
    variant: "high_conversion",
    taskId: "task-gen-b",
    label: "高转化",
    status: "running",
  },
];

let sessionActiveGenerations = [...activeGenerations];
let mockGenerationEvents: Record<string, TaskEvent> = {};

function runningEvent(taskId: string, progress: number): TaskEvent {
  return {
    ...fixtureTaskEvent,
    taskId,
    status: "running",
    stage: "generating_material",
    progress,
    message: `slot ${taskId}`,
    updatedAt: `2026-06-10T12:00:${String(progress).padStart(2, "0")}.000Z`,
  };
}

let capturedMultiTaskOpts: { enabled?: boolean } | null = null;

vi.mock("@/features/tasks/useTaskProgress", () => ({
  useTaskProgress: () => ({
    event: null,
    mode: "idle" as const,
    sseFailureCount: 0,
    error: null,
  }),
}));

vi.mock("@/features/tasks/useMultiTaskProgress", () => ({
  useMultiTaskProgress: (opts: { enabled?: boolean }) => {
    capturedMultiTaskOpts = opts;
    return {
      events: mockGenerationEvents,
      modes: {},
      sseFailureCounts: {},
      error: null,
      byTaskId: {},
      allTerminal: false,
      anyFailed: false,
    };
  },
}));

vi.mock("@/lib/project-session", () => ({
  loadProjectSession: () => ({
    taskId: null,
    sampleId: null,
    generationId: null,
    lastAction: "generation",
    activeGenerations: sessionActiveGenerations,
  }),
  saveProjectSession: vi.fn(),
}));

function mockProjectBootstrap() {
  vi.spyOn(apiClient, "getBrief").mockRejectedValue(new Error("no brief"));
  vi.spyOn(apiClient, "listProjectAssets").mockResolvedValue({
    data: { assets: [] },
    meta: { dataSource: "api" },
  });
  vi.spyOn(apiClient, "listProjectSamples").mockResolvedValue({
    data: { samples: [] },
    meta: { dataSource: "api" },
  });
  vi.spyOn(apiClient, "getLatestGenerations").mockRejectedValue(
    new Error("no generation"),
  );
  vi.spyOn(apiClient, "getActiveSample").mockRejectedValue(new Error("no sample"));
  vi.spyOn(apiClient, "getKnowledgeSelection").mockResolvedValue({
    data: { selection: null },
    meta: { dataSource: "api" },
  });
  vi.spyOn(apiClient, "getSampleSelection").mockResolvedValue({
    data: { selection: null },
    meta: { dataSource: "api" },
  });
  vi.spyOn(apiClient, "listKnowledgeEntries").mockResolvedValue({
    data: { entries: [] },
    meta: { dataSource: "api" },
  });
  vi.spyOn(apiClient, "getProject").mockResolvedValue({
    data: { id: "proj-test", name: "Test", createdAt: "2026-01-01T00:00:00Z" },
    meta: { dataSource: "api" },
  });
}

describe("ProjectWorkbench generation polling", () => {
  beforeEach(() => {
    capturedMultiTaskOpts = null;
    sessionActiveGenerations = [...activeGenerations];
    mockGenerationEvents = {
      "task-gen-a": runningEvent("task-gen-a", 40),
      "task-gen-b": runningEvent("task-gen-b", 41),
    };
    mockProjectBootstrap();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not call getTask while generation tasks are actively watched", async () => {
    const getTaskSpy = vi.spyOn(apiClient, "getTask");

    render(<ProjectWorkbench projectId="proj-test" />);

    await waitFor(() => expect(capturedMultiTaskOpts?.enabled).toBe(true));

    await new Promise((resolve) => setTimeout(resolve, 150));

    expect(getTaskSpy).not.toHaveBeenCalled();
  });

  it("hydrates settled events once when watch ends", async () => {
    sessionActiveGenerations = activeGenerations.map((entry) => ({
      ...entry,
      status: "succeeded",
    }));
    mockGenerationEvents = {
      "task-gen-a": {
        ...fixtureTaskEvent,
        taskId: "task-gen-a",
        status: "succeeded",
        stage: "completed",
        progress: 100,
        message: "done a",
        updatedAt: "2026-06-10T12:01:00.000Z",
      },
      "task-gen-b": {
        ...fixtureTaskEvent,
        taskId: "task-gen-b",
        status: "succeeded",
        stage: "completed",
        progress: 100,
        message: "done b",
        updatedAt: "2026-06-10T12:01:01.000Z",
      },
    };

    const getTaskSpy = vi.spyOn(apiClient, "getTask").mockImplementation(
      async (taskId: string) => ({
        data: mockGenerationEvents[taskId]!,
        meta: { dataSource: "api" },
      }),
    );

    render(<ProjectWorkbench projectId="proj-test" />);

    await waitFor(() => expect(getTaskSpy.mock.calls.length).toBe(2));
    await new Promise((resolve) => setTimeout(resolve, 150));
    expect(getTaskSpy.mock.calls.length).toBe(2);
  });
});
