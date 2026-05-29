import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { TaskEvent } from "@videomaker/contracts";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectWorkbench } from "@/features/workbench/ProjectWorkbench";
import {
  fixtureEditIntent,
  fixtureAgentRuns,
  fixtureGenerationPlan,
  fixtureGenerationPlanHighClick,
  fixtureGenerationPlanRevised,
  fixtureModelGatewayStatus,
  fixtureMultiVariantGenerations,
  fixtureTaskEvent,
  fixtureVideoStructure,
} from "@/fixtures";
import * as apiClient from "@/lib/apiClient";

vi.mock("@/lib/project-session", () => ({
  loadProjectSession: vi.fn(() => null),
  saveProjectSession: vi.fn(),
}));

let capturedOnTerminal: ((event: TaskEvent) => void) | undefined;
let capturedOnAllGenerationTerminal:
  | ((events: Record<string, TaskEvent>) => void)
  | undefined;
let capturedOnGenerationTaskTerminal: ((event: TaskEvent) => void) | undefined;
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

vi.mock("@/features/tasks/useMultiTaskProgress", () => ({
  useMultiTaskProgress: (opts: {
    onTaskTerminal?: (event: TaskEvent) => void;
    onAllTerminal?: (events: Record<string, TaskEvent>) => void;
  }) => {
    capturedOnGenerationTaskTerminal = opts.onTaskTerminal;
    capturedOnAllGenerationTerminal = opts.onAllTerminal;
    return {
      events: {},
      modes: {},
      sseFailureCount: 0,
      sseFailureCounts: {},
      byTaskId: {},
      error: null,
      allTerminal: false,
      anyFailed: false,
    };
  },
}));

describe("ProjectWorkbench", () => {
  beforeEach(() => {
    capturedOnTerminal = undefined;
    capturedOnAllGenerationTerminal = undefined;
    capturedOnGenerationTaskTerminal = undefined;
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
    vi.spyOn(apiClient, "getLatestGenerations").mockRejectedValue(new Error("no generation"));
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

  it("shows revise intents during revise task and diff after completion", async () => {
    const reviseGenerationSpy = vi.spyOn(apiClient, "reviseGeneration").mockResolvedValue({
      data: {
        sourceGenerationId: fixtureGenerationPlan.id,
        generationId: fixtureGenerationPlanRevised.id,
        taskId: "task-fixture-revise",
        intents: fixtureEditIntent.intents,
      },
      meta: { dataSource: "fixture" },
    });
    const getGenerationSpy = vi.spyOn(apiClient, "getGeneration").mockResolvedValue({
      data: { ...fixtureGenerationPlanRevised, gapReport: undefined },
      meta: { dataSource: "fixture" },
    });

    const user = userEvent.setup();
    render(<ProjectWorkbench projectId="proj-test" />);

    await user.click(screen.getByRole("button", { name: "加载演示数据" }));
    await user.click(screen.getByRole("button", { name: "结果" }));

    await user.type(screen.getByLabelText("改片指令"), "开头更抓人，减少字幕");
    await user.click(screen.getByRole("button", { name: "提交改片" }));

    expect(reviseGenerationSpy).toHaveBeenCalledWith(
      fixtureGenerationPlan.id,
      "开头更抓人，减少字幕",
    );
    expect(screen.getByTestId("edit-intent-list")).toBeInTheDocument();
    expect(screen.getByText("强化开头 hook")).toBeInTheDocument();

    await waitFor(() => expect(capturedOnTerminal).toBeDefined());

    act(() => {
      capturedOnTerminal?.({
        ...fixtureTaskEvent,
        taskId: "task-fixture-revise",
        status: "succeeded",
        progress: 100,
        stage: "completed",
        message: "改片已完成",
      });
    });

    await waitFor(() =>
      expect(getGenerationSpy).toHaveBeenCalledWith(fixtureGenerationPlanRevised.id),
    );

    expect(screen.getByTestId("timeline-diff-summary")).toBeInTheDocument();
    expect(screen.getByTestId("timeline-diff-summary")).toHaveTextContent(
      "轻字幕 + 强 hook 开场",
    );
  });

  it("loads all variant plans after multi-variant generation succeeds", async () => {
    vi.spyOn(apiClient, "getActiveSample").mockResolvedValue({
      data: {
        id: "sample-1",
        status: "ready",
        sourceKind: "local",
        hasStructure: true,
      },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "saveBrief").mockResolvedValue({
      data: { ok: true },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "createGenerationPlan").mockResolvedValue({
      data: { generations: fixtureMultiVariantGenerations },
      meta: { dataSource: "api" },
    });
    const getGenerationSpy = vi
      .spyOn(apiClient, "getGeneration")
      .mockImplementation(async (generationId) => {
        const plan =
          generationId === fixtureGenerationPlanHighClick.id
            ? fixtureGenerationPlanHighClick
            : { ...fixtureGenerationPlan, id: generationId };
        return {
          data: { ...plan, gapReport: undefined },
          meta: { dataSource: "api" },
        };
      });

    const user = userEvent.setup();
    render(<ProjectWorkbench projectId="proj-test" />);
    await user.click(screen.getByRole("button", { name: "开始生成计划" }));

    await waitFor(() => expect(capturedOnAllGenerationTerminal).toBeDefined());

    for (const entry of fixtureMultiVariantGenerations) {
      act(() => {
        capturedOnGenerationTaskTerminal?.({
          ...fixtureTaskEvent,
          taskId: entry.taskId,
          status: "succeeded",
          progress: 100,
          stage: "completed",
          message: "生成完成",
        });
      });
    }

    act(() => {
      capturedOnAllGenerationTerminal?.({
        [fixtureMultiVariantGenerations[0]!.taskId]: {
          ...fixtureTaskEvent,
          taskId: fixtureMultiVariantGenerations[0]!.taskId,
          status: "succeeded",
          progress: 100,
          stage: "completed",
          message: "生成完成",
        },
        [fixtureMultiVariantGenerations[1]!.taskId]: {
          ...fixtureTaskEvent,
          taskId: fixtureMultiVariantGenerations[1]!.taskId,
          status: "succeeded",
          progress: 100,
          stage: "completed",
          message: "生成完成",
        },
      });
    });

    await waitFor(() =>
      expect(getGenerationSpy).toHaveBeenCalledWith(
        fixtureMultiVariantGenerations[0]!.generationId,
      ),
    );
    await waitFor(() =>
      expect(getGenerationSpy).toHaveBeenCalledWith(
        fixtureMultiVariantGenerations[1]!.generationId,
      ),
    );

    expect(screen.getByTestId("variant-compare-view")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "高点击版" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "高转化版" })).toBeInTheDocument();
  });

  it("revises the active variant tab in multi-variant demo", async () => {
    const reviseGenerationSpy = vi.spyOn(apiClient, "reviseGeneration").mockResolvedValue({
      data: {
        sourceGenerationId: fixtureGenerationPlanHighClick.id,
        generationId: "gen-demo-high-click-revised",
        taskId: "task-fixture-revise-high-click",
        intents: fixtureEditIntent.intents,
      },
      meta: { dataSource: "fixture" },
    });
    vi.spyOn(apiClient, "getGeneration").mockResolvedValue({
      data: {
        ...fixtureGenerationPlanHighClick,
        id: "gen-demo-high-click-revised",
        packagingPlan: {
          ...fixtureGenerationPlanHighClick.packagingPlan,
          styleSummary: "改片后高点击包装",
        },
      },
      meta: { dataSource: "fixture" },
    });

    const user = userEvent.setup();
    render(<ProjectWorkbench projectId="proj-test" />);

    await user.click(screen.getByRole("button", { name: "加载演示数据" }));
    await user.click(screen.getByRole("button", { name: "结果" }));
    await user.click(screen.getByRole("tab", { name: "高点击版" }));

    await user.type(screen.getByLabelText("改片指令"), "开头更抓人");
    await user.click(screen.getByRole("button", { name: "提交改片" }));

    expect(reviseGenerationSpy).toHaveBeenCalledWith(
      fixtureGenerationPlanHighClick.id,
      "开头更抓人",
    );
    expect(screen.getByTestId("edit-intent-list")).toBeInTheDocument();
  });

  it("shows model gateway status panel on mount", async () => {
    vi.spyOn(apiClient, "getModelGatewayStatus").mockResolvedValue({
      data: fixtureModelGatewayStatus,
      meta: { dataSource: "fixture" },
    });

    render(<ProjectWorkbench projectId="proj-test" />);

    expect(await screen.findByTestId("model-gateway-status-panel")).toBeInTheDocument();
    expect(screen.getByText("Fixture 模式")).toBeInTheDocument();
  });

  it("loads agent runs from result panel", async () => {
    vi.spyOn(apiClient, "getModelGatewayStatus").mockResolvedValue({
      data: fixtureModelGatewayStatus,
      meta: { dataSource: "fixture" },
    });
    const getAgentRunsSpy = vi.spyOn(apiClient, "getGenerationAgentRuns").mockResolvedValue({
      data: { runs: fixtureAgentRuns },
      meta: { dataSource: "fixture" },
    });

    const user = userEvent.setup();
    render(<ProjectWorkbench projectId="proj-test" />);

    await user.click(screen.getByRole("button", { name: "加载演示数据" }));
    await user.click(screen.getByRole("button", { name: "结果" }));
    await user.click(screen.getByTestId("agent-runs-trigger"));

    await waitFor(() =>
      expect(getAgentRunsSpy).toHaveBeenCalledWith(fixtureGenerationPlan.id),
    );
    expect(screen.getByTestId("agent-runs-drawer")).toBeInTheDocument();
    expect(screen.getByText("structure_analyst")).toBeInTheDocument();
  });
});
