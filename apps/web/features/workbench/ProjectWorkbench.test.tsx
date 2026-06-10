import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { TaskEvent } from "@videomaker/contracts";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectWorkbench } from "@/features/workbench/ProjectWorkbench";
import {
  fixtureEditIntent,
  fixtureRevisePlan,
  fixtureReviseSession,
  fixtureAgentRuns,
  fixtureGenerationPlan,
  fixtureGenerationPlanHighClick,
  fixtureGenerationPlanRevised,
  fixtureMultiVariantGenerations,
  fixtureTaskEvent,
  fixtureVideoStructure,
} from "@/fixtures";
import * as apiClient from "@/lib/apiClient";
import * as projectSession from "@/lib/project-session";

vi.mock("@/lib/project-session", () => ({
  loadProjectSession: vi.fn(() => null),
  saveProjectSession: vi.fn(),
}));

let capturedOnTerminal: ((event: TaskEvent) => void) | undefined;
let capturedOnAllGenerationTerminal:
  | ((events: Record<string, TaskEvent>) => void)
  | undefined;
let capturedOnGenerationTaskTerminal: ((event: TaskEvent) => void) | undefined;
let capturedUseTaskProgressOpts:
  | {
      taskId: string | null;
      enabled?: boolean;
      watchKey?: number;
    }
  | undefined;
let mockTaskEvent: TaskEvent | null = null;

vi.mock("@/features/tasks/useTaskProgress", () => ({
  useTaskProgress: (opts: {
    taskId: string | null;
    enabled?: boolean;
    watchKey?: number;
    onTerminal?: (event: TaskEvent) => void;
  }) => {
    capturedOnTerminal = opts.onTerminal;
    capturedUseTaskProgressOpts = opts;
    const subscribed = Boolean(opts.enabled && opts.taskId);
    return {
      event: subscribed ? mockTaskEvent : null,
      mode: subscribed ? ("polling" as const) : ("idle" as const),
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
    capturedUseTaskProgressOpts = undefined;
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
    vi.spyOn(apiClient, "getSampleKeyframes").mockResolvedValue({
      data: { sampleId: "sample-upload-1", keyframes: [] },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "getKnowledgeSelection").mockResolvedValue({
      data: { selection: null },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "recommendKnowledge").mockResolvedValue({
      data: {
        recommendation: {
          projectId: "proj-test",
          candidates: [],
          suggestedPrimaryId: "",
          computedAt: "2026-06-03T00:00:00Z",
        },
        selection: null,
      },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "listKnowledgeEntries").mockResolvedValue({
      data: { entries: [] },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "getDurationRecommendation").mockResolvedValue({
      data: {
        recommendedSec: 60,
        defaultTargetSec: 60,
        maxTargetSec: 600,
        structureDurationSec: 60,
      },
      meta: { dataSource: "api" },
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("switches between input, progress, structure, narration, and result panels", async () => {
    const user = userEvent.setup();
    render(<ProjectWorkbench projectId="proj-test" />);

    expect(screen.getByTestId("input-wizard-step-1")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "进度" }));
    expect(screen.getByText(/任务进度/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "加载演示数据" }));
    await user.click(screen.getByRole("button", { name: "样例分析" }));
    expect(
      screen.getByText("已分析样例"),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "全片拆解" }));
    expect(
      screen.getByRole("heading", { name: "全片拆解" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("master-narration-text")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "结果" }));
    expect(
      screen.getByRole("heading", { name: "生成结果" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/时间线预览/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "录入" }));
    expect(screen.getByText(/创作 Brief/i)).toBeInTheDocument();
  });

  it("loads sample structure after upload task succeeds", async () => {
    vi.spyOn(apiClient, "uploadSampleBatch").mockResolvedValue({
      data: {
        batchId: "batch-1",
        samples: [{ id: "sample-upload-1", taskId: "task-upload-1" }],
      },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "startSampleAnalysis").mockResolvedValue({
      data: { taskId: "task-upload-1" },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "getSampleAnalysis").mockResolvedValue({
      data: {
        metadata: { durationSec: 60 },
        transcript: {},
        shots: [],
        keyframes: [],
        structureAnalysisRoute: "map_reduce",
      },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "listProjectSamples").mockResolvedValue({
      data: {
        samples: [
          {
            id: "sample-upload-1",
            sourceKind: "local",
            status: "analyzed",
            hasStructure: true,
            fileName: "demo.mp4",
          },
        ],
      },
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

    await waitFor(() =>
      expect(apiClient.uploadSampleBatch).toHaveBeenCalled(),
    );

    await user.click(screen.getByRole("button", { name: "开始样例分析" }));

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

    await user.click(screen.getByRole("button", { name: "样例分析" }));

    expect(screen.getByText("叙事分段 · 结构解读")).toBeInTheDocument();
  });

  it("calls retryTask with the same task id when retry is clicked", async () => {
    vi.spyOn(projectSession, "loadProjectSession").mockReturnValue({
      taskId: "task-retry-1",
      sampleId: "sample-retry-1",
      generationId: null,
      lastAction: "analysis",
    });
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
    vi.spyOn(apiClient, "getTask").mockImplementation(async () => ({
      data: {
        ...fixtureTaskEvent,
        taskId: "task-retry-1",
        status: "retrying",
        progress: 45,
        stage: "transcribing",
        message: "Retry requested, resuming from checkpoint",
      },
      meta: { dataSource: "api" },
    }));

    const user = userEvent.setup();
    render(<ProjectWorkbench projectId="proj-test" />);
    await user.click(screen.getByRole("button", { name: "进度" }));
    await user.click(screen.getByRole("button", { name: "重试样例分析" }));

    expect(retryTaskSpy).toHaveBeenCalledWith("task-retry-1");
    await waitFor(() => {
      expect(capturedUseTaskProgressOpts?.taskId).toBe("task-retry-1");
      expect(capturedUseTaskProgressOpts?.enabled).toBe(true);
    });
    expect(
      screen.queryByText(
        "暂无进行中的任务。若样例已分析完成，请前往「样例分析」查看结果；开始新任务后进度会显示在这里。",
      ),
    ).not.toBeInTheDocument();
  });

  it("shows revise intents during revise task and diff after completion", async () => {
    const planReviseSpy = vi.spyOn(apiClient, "planReviseGeneration").mockResolvedValue({
      data: {
        plan: fixtureRevisePlan,
        sessionId: fixtureRevisePlan.sessionId,
      },
      meta: { dataSource: "fixture" },
    });
    vi.spyOn(apiClient, "getReviseSession").mockResolvedValue({
      data: { session: fixtureReviseSession, plans: [fixtureRevisePlan] },
      meta: { dataSource: "fixture" },
    });
    const executeReviseSpy = vi.spyOn(apiClient, "executeRevisePlan").mockResolvedValue({
      data: {
        sourceGenerationId: fixtureGenerationPlan.id,
        generationId: fixtureGenerationPlanRevised.id,
        taskId: "task-fixture-revise",
        executionMode: "fork",
        plan: { ...fixtureRevisePlan, status: "executed" },
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

    expect(planReviseSpy).toHaveBeenCalledWith(
      fixtureGenerationPlan.id,
      "开头更抓人，减少字幕",
      { newSession: false },
    );
    expect(screen.getByTestId("revise-plan-card")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "确认执行" }));
    expect(executeReviseSpy).toHaveBeenCalledWith(
      fixtureGenerationPlan.id,
      fixtureRevisePlan.planId,
    );

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
        status: "analyzed",
        sourceKind: "local",
        hasStructure: true,
      },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "listProjectSamples").mockResolvedValue({
      data: {
        samples: [
          {
            id: "sample-1",
            sourceKind: "local",
            status: "analyzed",
            hasStructure: true,
            fileName: "demo.mp4",
          },
        ],
      },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "getSampleStructure").mockResolvedValue({
      data: fixtureVideoStructure,
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "getSampleAnalysis").mockResolvedValue({
      data: {
        metadata: { durationSec: 60 },
        transcript: {},
        shots: [],
        keyframes: [],
        structureAnalysisRoute: "map_reduce",
      },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "getSampleSelection").mockResolvedValue({
      data: {
        selection: {
          projectId: "proj-test",
          primarySampleId: "sample-1",
          referenceSampleIds: [],
          mode: "auto",
          updatedAt: "2026-06-06T00:00:00Z",
        },
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
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "开始生成视频" })).toBeEnabled(),
    );
    await user.click(screen.getByRole("button", { name: "开始生成视频" }));

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
    const highClickPlan = {
      ...fixtureRevisePlan,
      sourceGenerationId: fixtureGenerationPlanHighClick.id,
    };
    vi.spyOn(apiClient, "planReviseGeneration").mockResolvedValue({
      data: { plan: highClickPlan, sessionId: highClickPlan.sessionId },
      meta: { dataSource: "fixture" },
    });
    vi.spyOn(apiClient, "getReviseSession").mockResolvedValue({
      data: { session: fixtureReviseSession, plans: [highClickPlan] },
      meta: { dataSource: "fixture" },
    });
    vi.spyOn(apiClient, "executeRevisePlan").mockResolvedValue({
      data: {
        sourceGenerationId: fixtureGenerationPlanHighClick.id,
        generationId: "gen-demo-high-click-revised",
        taskId: "task-fixture-revise-high-click",
        executionMode: "fork",
        plan: { ...highClickPlan, status: "executed" },
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

    expect(screen.getByTestId("revise-plan-card")).toBeInTheDocument();
  });

  it("starts generation from brief only without sample analysis", async () => {
    vi.spyOn(apiClient, "getBrief").mockResolvedValue({
      data: {
        brief: {
          topic: "效率提升",
          sellingPoints: ["多创作"],
          mustMention: [],
          avoidMention: [],
        },
      },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "listProjectSamples").mockResolvedValue({
      data: { samples: [] },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "listKnowledgeEntries").mockResolvedValue({
      data: {
        entries: [
          {
            id: "entry-1",
            title: "知识模板",
            category: "教育",
            style: "标准",
            summary: "测试",
            status: "published",
            slotPattern: "hook→cta",
            skillMdUri: "knowledge/edu/entry-1/structure-skill.md",
            structureJsonUri: "knowledge/edu/entry-1/video-structure.json",
            version: 1,
            createdAt: "2026-06-01T00:00:00Z",
            updatedAt: "2026-06-01T00:00:00Z",
          },
        ],
      },
      meta: { dataSource: "api" },
    });
    const saveBriefSpy = vi.spyOn(apiClient, "saveBrief").mockResolvedValue({
      data: { ok: true },
      meta: { dataSource: "api" },
    });
    const createPlanSpy = vi.spyOn(apiClient, "createGenerationPlan").mockResolvedValue({
      data: { generations: fixtureMultiVariantGenerations },
      meta: { dataSource: "api" },
    });

    const user = userEvent.setup();
    render(<ProjectWorkbench projectId="proj-test" />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "开始生成视频" })).toBeEnabled(),
    );
    await user.click(screen.getByRole("button", { name: "开始生成视频" }));

    await waitFor(() => expect(saveBriefSpy).toHaveBeenCalled());
    await waitFor(() => expect(createPlanSpy).toHaveBeenCalled());
    const planBody = createPlanSpy.mock.calls[0]?.[1];
    expect(planBody).toBeDefined();
    expect(planBody).not.toHaveProperty("sampleSelection");
  });

  it("loads agent runs from result panel", async () => {
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
