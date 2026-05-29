"use client";

import type {
  GapReport,
  GenerationPlan,
  TaskEvent,
  VideoStructure,
} from "@videomaker/contracts";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DataSourceBanner } from "@/components/data-source-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GapReportView } from "@/features/gap-report/GapReportView";
import {
  getDefaultSelectedVariantIds,
  VariantPicker,
} from "@/features/generation-variants/VariantPicker";
import { VariantTabs } from "@/features/generation-variants/VariantTabs";
import { GenerationResultView } from "@/features/generation-result/GenerationResultView";
import { AssetInputPanel } from "@/features/project-input/AssetInputPanel";
import {
  BriefEditor,
  type BriefEditorHandle,
} from "@/features/project-input/BriefEditor";
import { SampleInputPanel } from "@/features/project-input/SampleInputPanel";
import { SampleAnalysisView } from "@/features/sample-analysis/SampleAnalysisView";
import { StructureSlotBoard } from "@/features/structure-mapping/StructureSlotBoard";
import { StructureEvidencePanel } from "@/features/structure-evidence/StructureEvidencePanel";
import { MultiTaskProgressPanel } from "@/features/tasks/MultiTaskProgressPanel";
import { TaskProgressPanel } from "@/features/tasks/TaskProgressPanel";
import { useMultiTaskProgress } from "@/features/tasks/useMultiTaskProgress";
import { useTaskProgress } from "@/features/tasks/useTaskProgress";
import { TimelinePreview } from "@/features/timeline-preview/TimelinePreview";
import {
  fixtureGapReport,
  fixtureGenerationPlan,
  fixtureGenerationPlanHighClick,
  fixtureMultiVariantGenerations,
  fixtureVideoStructure,
} from "@/fixtures";
import type { DataSource } from "@/lib/api-types";
import type {
  ActiveSampleSummary,
  GenerationPlanEntry,
  LatestGenerationsResponse,
  ProjectAsset,
  UserBriefRequest,
} from "@/lib/apiClient";
import {
  createGenerationPlan,
  getActiveSample,
  getBrief,
  getGeneration,
  getLatestGenerations,
  getSampleStructure,
  getVariantLabel,
  listProjectAssets,
  listProjectSamples,
  retryTask,
  saveBrief,
  startSampleAnalysis,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";
import {
  loadProjectSession,
  saveProjectSession,
} from "@/lib/project-session";

export type WorkbenchPanel =
  | "input"
  | "progress"
  | "analysis"
  | "structure"
  | "gap"
  | "timeline"
  | "result";

const PANEL_LABELS: Record<WorkbenchPanel, string> = {
  input: "录入",
  progress: "进度",
  analysis: "样例分析",
  structure: "结构槽",
  gap: "缺口",
  timeline: "时间线",
  result: "结果",
};

type LastPipelineAction = "analysis" | "generation" | null;

function emptyBrief(): UserBriefRequest {
  return { sellingPoints: [], mustMention: [], avoidMention: [] };
}

type ActiveGeneration = GenerationPlanEntry & {
  label: string;
};

type ProjectWorkbenchProps = {
  projectId: string;
};

function applyLatestGenerations(
  data: LatestGenerationsResponse,
  setters: {
    setVariantPlans: (plans: Record<string, GenerationPlan>) => void;
    setGenerationId: (id: string | null) => void;
    setGenerationPlan: (plan: GenerationPlan | null) => void;
    setActiveVariantGenerationId: (id: string | null) => void;
    setGapReport: (report: GapReport | null) => void;
    setGapApiPending: (pending: boolean) => void;
    setActiveGenerations: (entries: ActiveGeneration[]) => void;
  },
) {
  const plans: Record<string, GenerationPlan> = {};
  for (const entry of data.generations) {
    plans[entry.generationId] = entry.plan;
  }
  setters.setVariantPlans(plans);
  setters.setActiveGenerations(
    data.generations.map((entry) => ({
      generationId: entry.generationId,
      variant: entry.variant,
      taskId: "",
      label: getVariantLabel(entry.variant),
    })),
  );
  const primary = data.generations[0];
  if (!primary) return;
  setters.setGenerationId(primary.generationId);
  setters.setGenerationPlan(primary.plan);
  setters.setActiveVariantGenerationId(primary.generationId);
  if (primary.plan.gapReport) {
    setters.setGapReport(primary.plan.gapReport);
    setters.setGapApiPending(false);
  } else {
    setters.setGapReport(null);
    setters.setGapApiPending(false);
  }
}

export function ProjectWorkbench({ projectId }: ProjectWorkbenchProps) {
  const briefEditorRef = useRef<BriefEditorHandle>(null);
  const [panel, setPanel] = useState<WorkbenchPanel>("input");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [sampleId, setSampleId] = useState<string | null>(null);
  const [generationId, setGenerationId] = useState<string | null>(null);
  const [lastAction, setLastAction] = useState<LastPipelineAction>(null);
  const [busy, setBusy] = useState(false);

  const [savedBrief, setSavedBrief] = useState<UserBriefRequest | null | undefined>(
    undefined,
  );
  const [projectAssets, setProjectAssets] = useState<ProjectAsset[]>([]);
  const [projectSamples, setProjectSamples] = useState<ActiveSampleSummary[]>([]);
  const [activeSample, setActiveSample] = useState<ActiveSampleSummary | null>(
    null,
  );

  const [structure, setStructure] = useState<VideoStructure | null>(null);
  const [gapReport, setGapReport] = useState<GapReport | null>(null);
  const [generationPlan, setGenerationPlan] = useState<GenerationPlan | null>(
    null,
  );
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);
  const [gapApiPending, setGapApiPending] = useState(false);
  const [selectedVariantIds, setSelectedVariantIds] = useState<string[]>(
    getDefaultSelectedVariantIds(),
  );
  const [highlightedSlotIds, setHighlightedSlotIds] = useState<string[]>([]);
  const [variantPlans, setVariantPlans] = useState<
    Record<string, GenerationPlan>
  >({});
  const [activeVariantGenerationId, setActiveVariantGenerationId] = useState<
    string | null
  >(null);
  const [activeGenerations, setActiveGenerations] = useState<ActiveGeneration[]>(
    [],
  );

  const loadAnalysisResults = useCallback(async (currentSampleId: string) => {
    setDataLoading(true);
    setDataError(null);
    try {
      const { data, meta } = await getSampleStructure(currentSampleId);
      setStructure(data);
      setDataSource(meta.dataSource);
    } catch (err) {
      setDataError(getErrorMessage(err));
    } finally {
      setDataLoading(false);
    }
  }, []);

  const loadProjectInput = useCallback(async () => {
    const [briefResult, assetsResult, samplesResult, sampleResult] =
      await Promise.allSettled([
      getBrief(projectId),
      listProjectAssets(projectId),
      listProjectSamples(projectId),
      getActiveSample(projectId),
    ]);

    if (briefResult.status === "fulfilled") {
      setSavedBrief(briefResult.value.data.brief ?? null);
    } else {
      setSavedBrief(null);
    }

    if (assetsResult.status === "fulfilled") {
      setProjectAssets(assetsResult.value.data.assets);
    }

    if (samplesResult.status === "fulfilled") {
      setProjectSamples(samplesResult.value.data.samples);
    } else {
      setProjectSamples([]);
    }

    if (sampleResult.status === "fulfilled") {
      const sample = sampleResult.value.data;
      setActiveSample(sample);
      setSampleId(sample.id);
      if (sample.hasStructure) {
        void loadAnalysisResults(sample.id);
      }
    } else {
      setActiveSample(null);
    }
  }, [projectId, loadAnalysisResults]);

  const loadProjectResults = useCallback(async () => {
    try {
      const { data, meta } = await getLatestGenerations(projectId);
      applyLatestGenerations(data, {
        setVariantPlans,
        setGenerationId,
        setGenerationPlan,
        setActiveVariantGenerationId,
        setGapReport,
        setGapApiPending,
        setActiveGenerations,
      });
      setDataSource(meta.dataSource);
    } catch {
      /* no completed generation yet */
    }
  }, [projectId]);

  useEffect(() => {
    const saved = loadProjectSession(projectId);
    if (saved?.generationId) setGenerationId(saved.generationId);
    if (saved?.lastAction) setLastAction(saved.lastAction);
    if (saved?.taskId) {
      setTaskId(saved.taskId);
      setPanel("progress");
    }
    void loadProjectInput();
    void loadProjectResults();
  }, [projectId, loadProjectInput, loadProjectResults]);

  useEffect(() => {
    saveProjectSession(projectId, {
      taskId,
      sampleId,
      generationId,
      lastAction,
    });
  }, [projectId, taskId, sampleId, generationId, lastAction]);

  const loadGenerationIntoVariants = useCallback(
    async (currentGenerationId: string) => {
      setDataLoading(true);
      setDataError(null);
      setGapApiPending(false);
      try {
        const { data, meta } = await getGeneration(currentGenerationId);
        setGenerationPlan(data);
        setVariantPlans((prev) => ({ ...prev, [currentGenerationId]: data }));
        setDataSource(meta.dataSource);
        if (data.gapReport) {
          setGapReport(data.gapReport);
        } else if (meta.dataSource === "fixture") {
          setGapReport(fixtureGapReport);
          setGapApiPending(true);
        } else {
          setGapReport(null);
          setGapApiPending(true);
        }
      } catch (err) {
        setDataError(getErrorMessage(err));
      } finally {
        setDataLoading(false);
      }
    },
    [],
  );

  const loadGenerationResults = useCallback(
    async (currentGenerationId: string) => {
      setGenerationId(currentGenerationId);
      setActiveVariantGenerationId(currentGenerationId);
      await loadGenerationIntoVariants(currentGenerationId);
    },
    [loadGenerationIntoVariants],
  );

  const handleAnalysisTerminal = useCallback(
    (event: TaskEvent) => {
      if (event.status === "failed" || event.status === "cancelled") {
        setPanel("progress");
        return;
      }
      if (event.status !== "succeeded") return;
      if (lastAction === "analysis" && sampleId) {
        void loadAnalysisResults(sampleId);
        setPanel("analysis");
      }
    },
    [lastAction, loadAnalysisResults, sampleId],
  );

  const handleGenerationTaskTerminal = useCallback(
    (event: TaskEvent) => {
      if (event.status !== "succeeded") {
        setPanel("progress");
        return;
      }
      const match = activeGenerations.find((entry) => entry.taskId === event.taskId);
      if (match) {
        void loadGenerationIntoVariants(match.generationId);
      }
    },
    [activeGenerations, loadGenerationIntoVariants],
  );

  const handleAllGenerationTerminal = useCallback(
    (events: Record<string, TaskEvent>) => {
      const statuses = Object.values(events).map((entry) => entry.status);
      if (statuses.some((status) => status === "failed" || status === "cancelled")) {
        setPanel("progress");
        return;
      }
      if (statuses.every((status) => status === "succeeded")) {
        const primary = activeGenerations[0];
        if (primary) {
          setGenerationId(primary.generationId);
          setActiveVariantGenerationId(primary.generationId);
        }
        setPanel("result");
      }
    },
    [activeGenerations],
  );

  const handleTerminal = useCallback(
    (event: TaskEvent) => {
      if (lastAction === "generation") return;
      handleAnalysisTerminal(event);
    },
    [handleAnalysisTerminal, lastAction],
  );

  const [progressWatchKey, setProgressWatchKey] = useState(0);

  const isGenerationProgress =
    lastAction === "generation" && activeGenerations.length > 0;

  const { event, mode, sseFailureCount, error } = useTaskProgress({
    taskId: isGenerationProgress ? null : taskId,
    enabled: !isGenerationProgress && Boolean(taskId),
    watchKey: progressWatchKey,
    onTerminal: handleTerminal,
  });

  const generationProgressTasks = useMemo(
    () =>
      activeGenerations.map((entry) => ({
        taskId: entry.taskId,
        label: entry.label,
      })),
    [activeGenerations],
  );

  const {
    events: generationEvents,
    modes: generationModes,
    sseFailureCount: generationSseFailureCount,
    error: generationProgressError,
  } = useMultiTaskProgress({
    tasks: generationProgressTasks,
    enabled: isGenerationProgress,
    watchKey: progressWatchKey,
    onTaskTerminal: handleGenerationTaskTerminal,
    onAllTerminal: handleAllGenerationTerminal,
  });

  const handleTaskStarted = useCallback(
    (nextTaskId: string, nextSampleId: string) => {
      setLastAction("analysis");
      setActiveGenerations([]);
      setTaskId(nextTaskId);
      setSampleId(nextSampleId);
      setPanel("progress");
    },
    [],
  );

  const handleStartAnalysis = useCallback(async () => {
    setBusy(true);
    setDataError(null);
    setLastAction("analysis");
    setActiveGenerations([]);
    try {
      const { data: active } = await getActiveSample(projectId);
      setSampleId(active.id);
      const { data } = await startSampleAnalysis(active.id);
      setTaskId(data.taskId);
      setPanel("progress");
    } catch (err) {
      setDataError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [projectId]);

  const handleStartGeneration = useCallback(async () => {
    setBusy(true);
    setDataError(null);
    setLastAction("generation");
    try {
      const brief = briefEditorRef.current?.getBrief() ?? emptyBrief();
      await saveBrief(projectId, brief);
      setSavedBrief(brief);

      const { data: active } = await getActiveSample(projectId);
      if (!active.hasStructure) {
        setDataError(
          "请先对样例视频完成「开始样例分析」，成功后再生成计划。",
        );
        return;
      }
      const { data } = await createGenerationPlan(projectId, {
        brief,
        variants: selectedVariantIds,
      });
      const entries: ActiveGeneration[] = data.generations.map((entry) => ({
        ...entry,
        label: entry.label ?? getVariantLabel(entry.variant),
      }));
      setActiveGenerations(entries);
      setGenerationId(entries[0]?.generationId ?? null);
      setTaskId(null);
      setProgressWatchKey((key) => key + 1);
      setPanel("progress");
    } catch (err) {
      setDataError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [projectId, selectedVariantIds]);

  const loadDemoFixtures = useCallback(() => {
    setStructure(fixtureVideoStructure);
    setGapReport(fixtureGapReport);
    setGenerationPlan(fixtureGenerationPlan);
    setVariantPlans({
      [fixtureGenerationPlan.id]: fixtureGenerationPlan,
      [fixtureGenerationPlanHighClick.id]: fixtureGenerationPlanHighClick,
    });
    setActiveGenerations(
      fixtureMultiVariantGenerations.map((entry) => ({
        generationId: entry.generationId,
        variant: entry.variant,
        taskId: entry.taskId,
        label: entry.label,
      })),
    );
    setActiveVariantGenerationId(fixtureGenerationPlan.id);
    setGenerationId(fixtureGenerationPlan.id);
    setDataSource("fixture");
    setGapApiPending(true);
    setDataError(null);
  }, []);

  const handleRetryFailedTask = useCallback(
    async (retryTaskId?: string) => {
      const activeTaskId =
        retryTaskId ??
        (event?.status === "failed" ? (event.taskId ?? taskId) : (taskId ?? event?.taskId));
      if (!activeTaskId) return;
      setBusy(true);
      setDataError(null);
      try {
        await retryTask(activeTaskId);
        if (lastAction !== "generation") {
          setTaskId(activeTaskId);
        }
        setProgressWatchKey((key) => key + 1);
      } catch (err) {
        setDataError(getErrorMessage(err));
      } finally {
        setBusy(false);
      }
    },
    [event?.status, event?.taskId, lastAction, taskId],
  );

  const variantResultTabs = Object.entries(variantPlans).map(
    ([entryGenerationId, plan]) => {
      const meta =
        activeGenerations.find(
          (entry) => entry.generationId === entryGenerationId,
        ) ??
        fixtureMultiVariantGenerations.find(
          (entry) => entry.generationId === entryGenerationId,
        );
      return {
        generationId: entryGenerationId,
        variant: meta?.variant ?? plan.variant ?? "default",
        label: meta?.label ?? getVariantLabel(plan.variant ?? "default"),
        plan,
      };
    },
  );

  const panels: WorkbenchPanel[] = [
    "input",
    "progress",
    "analysis",
    "structure",
    "gap",
    "timeline",
    "result",
  ];

  return (
    <div className="space-y-6">
      <DataSourceBanner />

      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">项目工作台</h1>
          <p className="font-mono text-sm text-muted-foreground">{projectId}</p>
          {sampleId && (
            <p className="font-mono text-xs text-muted-foreground">
              当前样例：{sampleId}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={loadDemoFixtures}>
            加载演示数据
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={busy || !sampleId}
            onClick={() => void handleStartAnalysis()}
          >
            开始样例分析
          </Button>
          <Button
            type="button"
            disabled={busy}
            onClick={() => void handleStartGeneration()}
          >
            开始生成计划
          </Button>
        </div>
      </div>

      {(dataError || dataLoading) && (
        <p
          className={`text-sm ${dataError ? "text-destructive" : "text-muted-foreground"}`}
          role="status"
        >
          {dataLoading ? "正在加载结果…" : dataError}
        </p>
      )}

      <nav
        className="flex flex-wrap gap-2"
        aria-label="工作台视图"
        data-testid="workbench-nav"
      >
        {panels.map((key) => (
          <Button
            key={key}
            type="button"
            size="sm"
            variant={panel === key ? "default" : "outline"}
            onClick={() => setPanel(key)}
          >
            {PANEL_LABELS[key]}
          </Button>
        ))}
        {taskId && !isGenerationProgress && (
          <Badge variant="ai" className="ml-auto">
            任务 {taskId}
          </Badge>
        )}
        {isGenerationProgress && (
          <Badge variant="ai" className="ml-auto">
            {activeGenerations.length} 个变体任务
          </Badge>
        )}
      </nav>

      <div className="grid gap-4 lg:grid-cols-2 lg:items-stretch">
        {panel === "input" && (
          <>
            <SampleInputPanel
              projectId={projectId}
              samples={projectSamples}
              activeSample={activeSample}
              onTaskStarted={handleTaskStarted}
              onSampleReady={(id) => {
                setSampleId(id);
                setTaskId(null);
                setDataError(null);
              }}
              onSampleChanged={() => void loadProjectInput()}
            />
            <AssetInputPanel
              projectId={projectId}
              assets={projectAssets}
              onAssetsChanged={() => void loadProjectInput()}
            />
            <div className="lg:col-span-2">
              <BriefEditor
                ref={briefEditorRef}
                projectId={projectId}
                initialBrief={savedBrief}
                onSaved={(brief) => setSavedBrief(brief)}
              />
            </div>
            <div className="lg:col-span-2">
              <VariantPicker
                selectedVariantIds={selectedVariantIds}
                onChange={setSelectedVariantIds}
                disabled={busy}
              />
            </div>
          </>
        )}

        {panel === "progress" && (
          <div className="lg:col-span-2">
            {isGenerationProgress ? (
              <MultiTaskProgressPanel
                tasks={activeGenerations.map((entry) => ({
                  taskId: entry.taskId,
                  label: entry.label,
                  event: generationEvents[entry.taskId] ?? null,
                  mode: generationModes[entry.taskId] ?? "idle",
                }))}
                sseFailureCount={generationSseFailureCount}
                error={generationProgressError}
                retryBusy={busy}
                retryLabel="重试生成计划"
                onRetry={(retryTaskId) => void handleRetryFailedTask(retryTaskId)}
              />
            ) : (
              <TaskProgressPanel
                event={event}
                mode={mode}
                sseFailureCount={sseFailureCount}
                error={error}
                retryBusy={busy}
                retryLabel={
                  lastAction === "generation" ? "重试生成计划" : "重试样例分析"
                }
                onRetry={
                  event?.status === "failed" && (taskId || event.taskId) && !busy
                    ? () => void handleRetryFailedTask()
                    : undefined
                }
              />
            )}
          </div>
        )}

        {panel === "analysis" && (
          <div className="lg:col-span-2 space-y-4">
            {structure ? (
              <>
                <StructureEvidencePanel
                  structure={structure}
                  highlightedSlotIds={highlightedSlotIds}
                  onHighlightSlot={(slotId) => setHighlightedSlotIds([slotId])}
                  analysisStage={
                    lastAction === "analysis" ? event?.stage : undefined
                  }
                />
                <SampleAnalysisView structure={structure} />
              </>
            ) : (
              <EmptyPanel message="暂无分析结果，请先完成样例分析或加载演示数据。" />
            )}
          </div>
        )}

        {panel === "structure" && (
          <div className="lg:col-span-2">
            {structure ? (
              <StructureSlotBoard
                structure={structure}
                highlightedSlotIds={highlightedSlotIds}
              />
            ) : (
              <EmptyPanel message="暂无结构槽数据。" />
            )}
          </div>
        )}

        {panel === "gap" && (
          <div className="lg:col-span-2 space-y-2">
            {gapApiPending && dataSource === "fixture" && (
              <p className="text-xs text-muted-foreground">
                演示模式下使用 fixture 缺口数据；连接 API 后将显示真实 GapReport。
              </p>
            )}
            {gapReport ? (
              <GapReportView
                report={gapReport}
                completionActions={generationPlan?.completionActions}
                onUploadAsset={() => setPanel("input")}
                onGenerate={() => setPanel("result")}
              />
            ) : (
              <EmptyPanel message="暂无缺口报告，请先运行生成计划。" />
            )}
          </div>
        )}

        {panel === "timeline" && (
          <div className="lg:col-span-2">
            {generationPlan ? (
              <TimelinePreview timeline={generationPlan.timeline} />
            ) : (
              <EmptyPanel message="暂无时间线数据。" />
            )}
          </div>
        )}

        {panel === "result" && (
          <div className="lg:col-span-2">
            {variantResultTabs.length > 1 ? (
              <VariantTabs
                tabs={variantResultTabs}
                activeGenerationId={
                  activeVariantGenerationId ??
                  variantResultTabs[0]?.generationId ??
                  null
                }
                onActiveChange={(nextId) => {
                  setActiveVariantGenerationId(nextId);
                  const plan = variantPlans[nextId];
                  if (plan) setGenerationPlan(plan);
                }}
              />
            ) : generationPlan ? (
              <GenerationResultView plan={generationPlan} showTimeline />
            ) : (
              <EmptyPanel message="暂无生成结果。" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyPanel({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
      {message}
    </div>
  );
}
