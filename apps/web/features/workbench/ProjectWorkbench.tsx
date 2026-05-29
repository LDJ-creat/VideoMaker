"use client";

import type {
  GapReport,
  GenerationPlan,
  TaskEvent,
  VideoStructure,
} from "@videomaker/contracts";
import { useCallback, useEffect, useRef, useState } from "react";

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
import { TaskProgressPanel } from "@/features/tasks/TaskProgressPanel";
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
  ProjectAsset,
  UserBriefRequest,
} from "@/lib/apiClient";
import {
  createGenerationPlan,
  getActiveSample,
  getBrief,
  getGeneration,
  getLatestGeneration,
  getSampleStructure,
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

type ProjectWorkbenchProps = {
  projectId: string;
};

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
      const { data, meta } = await getLatestGeneration(projectId);
      setGenerationId(data.id);
      setGenerationPlan(data);
      setDataSource(meta.dataSource);
      if (data.gapReport) {
        setGapReport(data.gapReport);
        setGapApiPending(false);
      } else {
        setGapReport(null);
        setGapApiPending(false);
      }
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

  const loadGenerationResults = useCallback(async (currentGenerationId: string) => {
    setDataLoading(true);
    setDataError(null);
    setGapApiPending(false);
    try {
      const { data, meta } = await getGeneration(currentGenerationId);
      setGenerationPlan(data);
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
  }, []);

  const handleTerminal = useCallback(
    (event: TaskEvent) => {
      if (event.status === "failed" || event.status === "cancelled") {
        setPanel("progress");
        return;
      }
      if (event.status !== "succeeded") return;

      if (lastAction === "analysis" && sampleId) {
        void loadAnalysisResults(sampleId);
        setPanel("analysis");
      } else if (lastAction === "generation" && generationId) {
        void loadGenerationResults(generationId);
        setPanel("result");
      }
    },
    [
      generationId,
      lastAction,
      loadAnalysisResults,
      loadGenerationResults,
      sampleId,
    ],
  );

  const [progressWatchKey, setProgressWatchKey] = useState(0);

  const { event, mode, sseFailureCount, error } = useTaskProgress({
    taskId,
    enabled: Boolean(taskId),
    watchKey: progressWatchKey,
    onTerminal: handleTerminal,
  });

  const handleTaskStarted = useCallback(
    (nextTaskId: string, nextSampleId: string) => {
      setLastAction("analysis");
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
      const primary = data.generations[0];
      if (primary) {
        setGenerationId(primary.generationId);
        if (primary.taskId) {
          setTaskId(primary.taskId);
        }
      }
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
    setActiveVariantGenerationId(fixtureGenerationPlan.id);
    setGenerationId(fixtureGenerationPlan.id);
    setDataSource("fixture");
    setGapApiPending(true);
    setDataError(null);
  }, []);

  const handleRetryFailedTask = useCallback(async () => {
    const activeTaskId =
      event?.status === "failed" ? (event.taskId ?? taskId) : (taskId ?? event?.taskId);
    if (!activeTaskId) return;
    setBusy(true);
    setDataError(null);
    try {
      await retryTask(activeTaskId);
      setTaskId(activeTaskId);
      setProgressWatchKey((key) => key + 1);
    } catch (err) {
      setDataError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [event?.status, event?.taskId, taskId]);

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
        {taskId && (
          <Badge variant="ai" className="ml-auto">
            任务 {taskId}
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
                  ? () => handleRetryFailedTask()
                  : undefined
              }
            />
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
            {Object.keys(variantPlans).length > 1 ? (
              <VariantTabs
                tabs={fixtureMultiVariantGenerations.map((entry) => ({
                  generationId: entry.generationId,
                  variant: entry.variant,
                  label: entry.label,
                  plan: variantPlans[entry.generationId] ?? null,
                }))}
                activeGenerationId={
                  activeVariantGenerationId ?? fixtureGenerationPlan.id
                }
                onActiveChange={setActiveVariantGenerationId}
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
