import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { TaskEvent } from "@videomaker/contracts";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectWorkbench } from "@/features/workbench/ProjectWorkbench";
import { fixtureTaskEvent, fixtureVideoStructure } from "@/fixtures";
import * as apiClient from "@/lib/apiClient";

vi.mock("@/lib/project-session", () => ({
  loadProjectSession: vi.fn(() => null),
  saveProjectSession: vi.fn(),
}));

let capturedOnTerminal: ((event: TaskEvent) => void) | undefined;
let mockTaskEvent: TaskEvent | null = null;

vi.mock("@/features/tasks/useTaskProgress", () => ({
  useTaskProgress: (opts: { onTerminal?: (event: TaskEvent) => void }) => {
    capturedOnTerminal = opts.onTerminal;
    return {
      event: mockTaskEvent,
      mode: mockTaskEvent ? ("polling" as const) : ("idle" as const),
      sseFailureCount: 0,
      error: null,
    };
  },
}));

describe("ProjectWorkbench", () => {
  beforeEach(() => {
    capturedOnTerminal = undefined;
    mockTaskEvent = null;
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getBrief").mockRejectedValue(new Error("no brief"));
    vi.spyOn(apiClient, "listProjectAssets").mockResolvedValue({
      data: { assets: [] },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "listProjectSamples").mockResolvedValue({
      data: { samples: [] },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "getActiveSample").mockRejectedValue(new Error("no sample"));
  });

  afterEach(() => {
    cleanup();
  });

  it("switches between input, progress, structure, gap, timeline, and result panels", async () => {
    const user = userEvent.setup();
    render(<ProjectWorkbench projectId="proj-test" />);

    expect(screen.getByRole("heading", { name: "样例视频" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "进度" }));
    expect(screen.getByText(/任务进度/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "加载演示数据" }));
    await user.click(screen.getByRole("button", { name: "样例分析" }));
    expect(
      screen.getByRole("heading", { name: "样例分析" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "结构槽" }));
    expect(screen.getByText(/结构槽位/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "缺口" }));
    expect(screen.getByText(/缺口报告/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "时间线" }));
    expect(screen.getByText(/时间线预览/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "结果" }));
    expect(screen.getByText(/生成结果/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "录入" }));
    expect(screen.getByText(/创作 Brief/i)).toBeInTheDocument();
  });

  it("loads sample structure after upload task succeeds", async () => {
    vi.spyOn(apiClient, "uploadSampleVideo").mockResolvedValue({
      data: { id: "sample-upload-1", taskId: "task-upload-1" },
      meta: { dataSource: "api" },
    });
    const getStructure = vi.spyOn(apiClient, "getSampleStructure").mockResolvedValue({
      data: { ...fixtureVideoStructure, sourceVideoId: "sample-upload-1" },
      meta: { dataSource: "api" },
    });

    const user = userEvent.setup();
    render(<ProjectWorkbench projectId="proj-test" />);

    const file = new File(["video"], "demo.mp4", { type: "video/mp4" });
    await user.upload(screen.getByLabelText(/上传样例视频/i), file);

    await waitFor(() => expect(capturedOnTerminal).toBeDefined());

    act(() => {
      capturedOnTerminal?.({
        ...fixtureTaskEvent,
        taskId: "task-upload-1",
        status: "succeeded",
        progress: 100,
      });
    });

    await waitFor(() =>
      expect(getStructure).toHaveBeenCalledWith("sample-upload-1"),
    );

    expect(
      screen.getByRole("heading", { name: "样例分析" }),
    ).toBeInTheDocument();
  });

    it("calls retryTask with the same task id when retry is clicked", async () => {
    mockTaskEvent = {
      ...fixtureTaskEvent,
      taskId: "task-retry-1",
      status: "failed",
      progress: 45,
      stage: "transcribing",
      message: "transcription failed",
    };

    const retryTaskSpy = vi.spyOn(apiClient, "retryTask").mockResolvedValue({
      data: {
        ...fixtureTaskEvent,
        taskId: "task-retry-1",
        status: "retrying",
        progress: 45,
      },
      meta: { dataSource: "api" },
    });

    const user = userEvent.setup();
    render(<ProjectWorkbench projectId="proj-test" />);
    await user.click(screen.getByRole("button", { name: "进度" }));
    await user.click(screen.getByRole("button", { name: "重试样例分析" }));

    expect(retryTaskSpy).toHaveBeenCalledWith("task-retry-1");
  });
});
