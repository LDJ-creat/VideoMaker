"use client";

import type {
  EditIntentItem,
  GapReport,
  GenerationPlan,
  TaskEvent,
  VideoStructure,
} from "@videomaker/contracts";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DataSourceBanner } from "@/components/data-source-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { KnowledgeDraftPanel } from "@/features/knowledge/KnowledgeDraftPanel";
import {
  KnowledgeLibraryView,
  KnowledgeSelectionPanel,
} from "@/features/knowledge/KnowledgeSelectionPanel";
import {
  getDefaultSelectedVariantIds,
  VariantPicker,
} from "@/features/generation-variants/VariantPicker";
import { VariantCompareView } from "@/features/generation-variants/VariantCompareView";
import { VariantTabs } from "@/features/generation-variants/VariantTabs";
import { GenerationResultView } from "@/features/generation-result/GenerationResultView";
import { GapReportView } from "@/features/gap-report/GapReportView";
import { MasterNarrationPanel } from "@/features/master-narration/MasterNarrationPanel";
import { EditIntentList } from "@/features/nl-revise/EditIntentList";
import { ReviseInputBar } from "@/features/nl-revise/ReviseInputBar";
import { TimelineDiffSummary } from "@/features/nl-revise/TimelineDiffSummary";
import { AssetInputPanel } from "@/features/project-input/AssetInputPanel";
import {
  BriefEditor,
  type BriefEditorHandle,
} from "@/features/project-input/BriefEditor";
import {
  DurationTargetPanel,
  type DurationTargetPanelHandle,
} from "@/features/project-input/DurationTargetPanel";
import { ScriptReviewPanel } from "@/features/script-review/ScriptReviewPanel";
import { GenerationRunHistoryPanel } from "@/features/generation-runs/GenerationRunHistoryPanel";
import { SampleBatchAnalysisProgress } from "@/features/project-input/SampleBatchAnalysisProgress";
import { SampleInputPanel } from "@/features/project-input/SampleInputPanel";
import { SampleSelectionPanel } from "@/features/project-input/SampleSelectionPanel";
import { SampleAnalysisPanel } from "@/features/sample-analysis/SampleAnalysisPanel";
import { StructureSlotBoard } from "@/features/structure-mapping/StructureSlotBoard";
import { StructureProvenancePanel } from "@/features/structure-provenance/StructureProvenancePanel";
import { MultiTaskProgressPanel } from "@/features/tasks/MultiTaskProgressPanel";
import { TaskProgressPanel } from "@/features/tasks/TaskProgressPanel";
import { useMultiTaskProgress } from "@/features/tasks/useMultiTaskProgress";
import { useTaskProgress } from "@/features/tasks/useTaskProgress";
import { TimelinePreview } from "@/features/timeline-preview/TimelinePreview";
import { AgentRunsDrawer } from "@/features/observability/AgentRunsDrawer";
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
  GenerationResponse,
  LatestGenerationsResponse,
  ProjectAsset,
  StructureProvenanceSummary,
  UserBriefRequest,
} from "@/lib/apiClient";
import {
  createGenerationPlan,
  getActiveSample,
  getBrief,
  getGeneration,
  getGenerationRun,
  getLatestGenerations,
  getProject,
  getSampleKeyframes,
  getSampleAnalysis,
  getSampleSelection,
  getSampleStructure,
  getTask,
  getVariantLabel,
  listProjectAssets,
  listProjectSamples,
  retryTask,
  reviseGeneration,
  saveBrief,
  startSampleAnalysis,
  updateKnowledgeSelection,
  type SampleAnalysisFacts,
  type SampleKeyframeRecord,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";
import {
  loadProjectSession,
  saveProjectSession,
} from "@/lib/project-session";

export type WorkbenchPanel =
  | "input"
  | "progress"
  | "script-review"
  | "analysis"
  | "structure"
  | "gap"
  | "timeline"
  | "narration"
  | "result"
  | "knowledge";

const PANEL_LABELS: Record<WorkbenchPanel, string> = {
  input: "录入",
  progress: "进度",
  "script-review": "脚本审核",
  analysis: "样例分析",
  structure: "结构槽",
  gap: "缺口",
  timeline: "时间线",
  narration: "全片口播",
  result: "结果",
  knowledge: "知识库",
};

type LastPipelineAction = "analysis" | "generation" | "revise" | null;

function emptyBrief(): UserBriefRequest {
  return { sellingPoints: [], mustMention: [], avoidMention: [] };
}

type ActiveGeneration = {
  generationId: string;
  variant: string;
  taskId: string;
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
    setRenderVideoByGenerationId: (urls: Record<string, string>) => void;
  },
) {
  const plans: Record<string, GenerationPlan> = {};
  const renderVideos: Record<string, string> = {};
  for (const entry of data.generations) {
    plans[entry.generationId] = entry.plan;
    if (entry.renderVideoUrl) {
      renderVideos[entry.generationId] = entry.renderVideoUrl;
    }
  }
  setters.setRenderVideoByGenerationId(renderVideos);
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
  const durationTargetRef = useRef<DurationTargetPanelHandle>(null);
  const [panel, setPanel] = useState<WorkbenchPanel>("input");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [sampleId, setSampleId] = useState<string | null>(null);
  const [analysisSampleId, setAnalysisSampleId] = useState<string | null>(null);
  const [pendingAnalysisSampleId, setPendingAnalysisSampleId] = useState<
    string | null
  >(null);
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
  const [sampleKeyframes, setSampleKeyframes] = useState<SampleKeyframeRecord[]>(
    [],
  );
  const [sampleAnalysisFacts, setSampleAnalysisFacts] =
    useState<SampleAnalysisFacts | null>(null);
  const [gapReport, setGapReport] = useState<GapReport | null>(null);
  const [renderVideoByGenerationId, setRenderVideoByGenerationId] = useState<
    Record<string, string>
  >({});
  const [generationPlan, setGenerationPlan] = useState<GenerationPlan | null>(
    null,
  );
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);
  const [projectName, setProjectName] = useState<string | null>(null);
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
  const [analysisBatchTasks, setAnalysisBatchTasks] = useState<
    Array<{ sampleId: string; taskId: string }>
  >([]);
  const [activeGenerationRunId, setActiveGenerationRunId] = useState<
    string | null
  >(null);
  const [structureProvenance, setStructureProvenance] =
    useState<StructureProvenanceSummary | null>(null);
  const [reviseIntents, setReviseIntents] = useState<EditIntentItem[] | null>(
    null,
  );
  const [preRevisePlan, setPreRevisePlan] = useState<GenerationPlan | null>(
    null,
  );

  const loadAnalysisResults = useCallback(
    async (
      currentSampleId: string,
      options?: { showGlobalLoading?: boolean },
    ) => {
      setPendingAnalysisSampleId(currentSampleId);
      if (options?.showGlobalLoading) {
        setDataLoading(true);
      }
      setDataError(null);
      try {
        const [structureResult, keyframesResult, sampleFactsResult] =
          await Promise.all([
          getSampleStructure(currentSampleId),
          getSampleKeyframes(currentSampleId),
          getSampleAnalysis(currentSampleId),
        ]);
        setStructure(structureResult.data);
        setSampleKeyframes(keyframesResult.data.keyframes ?? []);
        setSampleAnalysisFacts(sampleFactsResult.data);
        setAnalysisSampleId(currentSampleId);
        setDataSource(structureResult.meta.dataSource);
      } catch (err) {
        setDataError(getErrorMessage(err));
      } finally {
        setPendingAnalysisSampleId(null);
        if (options?.showGlobalLoading) {
          setDataLoading(false);
        }
      }
    },
    [],
  );

  const handleSelectAnalysisSample = useCallback(
    (nextSampleId: string) => {
      if (
        nextSampleId === analysisSampleId ||
        nextSampleId === pendingAnalysisSampleId
      ) {
        return;
      }
      void loadAnalysisResults(nextSampleId);
    },
    [analysisSampleId, pendingAnalysisSampleId, loadAnalysisResults],
  );

  const viewAnalysisSampleId = analysisSampleId ?? sampleId;

  const loadGenerationRunProvenance = useCallback(
    async (runId: string) => {
      try {
        const { data } = await getGenerationRun(projectId, runId);
        if (data.provenance) {
          setStructureProvenance(data.provenance);
        }
      } catch {
        /* run may still be running or incomplete */
      }
    },
    [projectId],
  );

  const loadProjectInput = useCallback(async () => {
    const [briefResult, assetsResult, samplesResult, sampleResult, projectResult] =
      await Promise.allSettled([
      getBrief(projectId),
      listProjectAssets(projectId),
      listProjectSamples(projectId),
      getActiveSample(projectId),
      getProject(projectId),
    ]);

    if (projectResult.status === "fulfilled") {
      setProjectName(projectResult.value.data.name);
    } else {
      setProjectName(null);
    }

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
        const allSamples =
          samplesResult.status === "fulfilled"
            ? samplesResult.value.data.samples
            : [];
        const analyzedIds = new Set(
          allSamples
            .filter((item) => item.hasStructure && item.status === "analyzed")
            .map((item) => item.id),
        );
        setAnalysisSampleId((prev) => {
          const next =
            prev && analyzedIds.has(prev) ? prev : sample.id;
          void loadAnalysisResults(next, {
            showGlobalLoading: !(prev && analyzedIds.has(prev)),
          });
          return prev && analyzedIds.has(prev) ? prev : null;
        });
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
        setRenderVideoByGenerationId,
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
    if (saved?.activeGenerations?.length) {
      setActiveGenerations(saved.activeGenerations as ActiveGeneration[]);
    }
    if (saved?.activeVariantGenerationId) {
      setActiveVariantGenerationId(saved.activeVariantGenerationId);
    }
    if (saved?.reviseIntents?.length) {
      setReviseIntents(saved.reviseIntents);
    }
    if (saved?.preReviseGenerationId) {
      void getGeneration(saved.preReviseGenerationId)
        .then(({ data }) => setPreRevisePlan(data))
        .catch(() => {
          /* plan may no longer exist */
        });
    }
    if (saved?.activeGenerationRunId) {
      setActiveGenerationRunId(saved.activeGenerationRunId);
      void getGenerationRun(projectId, saved.activeGenerationRunId)
        .then(({ data }) => {
          if (data.provenance) {
            setStructureProvenance(data.provenance);
          }
        })
        .catch(() => {
          /* run may be incomplete */
        });
    }
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
      activeGenerationRunId,
      lastAction,
      activeGenerations,
      activeVariantGenerationId,
      reviseIntents,
      preReviseGenerationId: preRevisePlan?.id ?? null,
    });
  }, [
    projectId,
    taskId,
    sampleId,
    generationId,
    activeGenerationRunId,
    lastAction,
    activeGenerations,
    activeVariantGenerationId,
    reviseIntents,
    preRevisePlan,
  ]);

  const loadGenerationIntoVariants = useCallback(
    async (currentGenerationId: string) => {
      setDataLoading(true);
      setDataError(null);
      setGapApiPending(false);
      try {
        const { data, meta } = await getGeneration(currentGenerationId);
        setGenerationPlan(data);
        setVariantPlans((prev) => ({ ...prev, [data.id]: data }));
        if (data.renderVideoUrl) {
          setRenderVideoByGenerationId((prev) => ({
            ...prev,
            [data.id]: data.renderVideoUrl!,
          }));
        }
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
      const match = activeGenerations.find((entry) => entry.taskId === event.taskId);
      if (match) {
        void loadGenerationIntoVariants(match.generationId);
      }
      if (event.status === "awaiting_review") {
        setPanel("script-review");
        return;
      }
      if (event.status !== "succeeded") {
        setPanel("progress");
        return;
      }
    },
    [activeGenerations, loadGenerationIntoVariants],
  );

  const handleAllGenerationTerminal = useCallback(
    (events: Record<string, TaskEvent>) => {
      void loadProjectResults();
      if (activeGenerationRunId) {
        void loadGenerationRunProvenance(activeGenerationRunId);
      }
      const statuses = Object.values(events).map((entry) => entry.status);
      if (statuses.some((status) => status === "awaiting_review")) {
        setPanel("script-review");
        return;
      }
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
    [
      activeGenerationRunId,
      activeGenerations,
      loadGenerationRunProvenance,
      loadProjectResults,
    ],
  );

  const handleTerminal = useCallback(
    (event: TaskEvent) => {
      if (lastAction === "generation") return;
      if (lastAction === "revise") {
        if (event.status === "failed" || event.status === "cancelled") {
          setPanel("progress");
          return;
        }
        if (event.status === "succeeded" && generationId) {
          void loadGenerationResults(generationId);
          setPanel("result");
        }
        return;
      }
      handleAnalysisTerminal(event);
    },
    [generationId, handleAnalysisTerminal, lastAction, loadGenerationResults],
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
    sseFailureCounts: generationSseFailureCounts,
    error: generationProgressError,
  } = useMultiTaskProgress({
    tasks: generationProgressTasks,
    enabled: isGenerationProgress,
    watchKey: progressWatchKey,
    onTaskTerminal: handleGenerationTaskTerminal,
    onAllTerminal: handleAllGenerationTerminal,
  });

  useEffect(() => {
    if (!isGenerationProgress || lastAction !== "generation") return;
    const awaiting = Object.values(generationEvents).some(
      (entry) => entry?.status === "awaiting_review",
    );
    if (awaiting) {
      setPanel("script-review");
    }
  }, [generationEvents, isGenerationProgress, lastAction]);

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
      const targetSampleId =
        sampleId ?? (await getActiveSample(projectId)).data.id;
      setSampleId(targetSampleId);
      const { data } = await startSampleAnalysis(targetSampleId);
      setTaskId(data.taskId);
      setAnalysisBatchTasks([]);
      setPanel("progress");
    } catch (err) {
      setDataError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [projectId, sampleId]);

  const handleStartGeneration = useCallback(async () => {
    setBusy(true);
    setDataError(null);
    setLastAction("generation");
    try {
      const brief = briefEditorRef.current?.getBrief() ?? emptyBrief();
      const durationTarget = durationTargetRef.current?.getDurationTarget();
      if (durationTarget) {
        brief.durationTarget = durationTarget;
      }
      await saveBrief(projectId, brief);
      setSavedBrief(brief);

      const { data: selectionData } = await getSampleSelection(projectId);
      const primaryId = selectionData.selection?.primarySampleId;
      if (!primaryId) {
        setDataError("请先上传样例并设置主样例。");
        return;
      }
      const { data: samplesData } = await listProjectSamples(projectId);
      const primarySample = samplesData.samples.find(
        (sample) => sample.id === primaryId,
      );
      if (!primarySample?.hasStructure) {
        setDataError("请先对主样例视频完成分析，成功后再生成计划。");
        return;
      }
      const { data } = await createGenerationPlan(projectId, {
        brief,
        variants: selectedVariantIds,
        sampleSelection: {
          primarySampleId: primaryId,
          referenceSampleIds: selectionData.selection?.referenceSampleIds ?? [],
        },
      });
      if (data.generationRunId) {
        setActiveGenerationRunId(data.generationRunId);
      }
      const entries: ActiveGeneration[] = data.generations.map((entry) => ({
        generationId: entry.generationId,
        variant: entry.variant,
        taskId: entry.taskId,
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

  const activeResultPlan =
    (activeVariantGenerationId
      ? variantPlans[activeVariantGenerationId]
      : null) ?? generationPlan;

  const activeResultGenerationId =
    activeVariantGenerationId ?? generationId;

  const handleRevise = useCallback(
    async (instruction: string) => {
      const targetGenerationId = activeResultGenerationId;
      const sourcePlan = activeResultPlan;
      if (!targetGenerationId || !sourcePlan) {
        setDataError("请先完成生成计划后再改片。");
        return;
      }

      setBusy(true);
      setDataError(null);
      setLastAction("revise");
      setPreRevisePlan(sourcePlan);
      try {
        const { data } = await reviseGeneration(targetGenerationId, instruction);
        setReviseIntents(data.intents);
        setGenerationId(data.generationId);
        setTaskId(data.taskId);
        setActiveGenerations((prev) =>
          prev.length > 0
            ? prev.map((entry) =>
                entry.generationId === targetGenerationId
                  ? {
                      ...entry,
                      generationId: data.generationId,
                      taskId: data.taskId,
                    }
                  : entry,
              )
            : [
                {
                  generationId: data.generationId,
                  variant: sourcePlan.variant,
                  taskId: data.taskId,
                  label: getVariantLabel(sourcePlan.variant),
                },
              ],
        );
        setActiveVariantGenerationId(data.generationId);
        setVariantPlans((prev) => {
          const next = { ...prev };
          delete next[targetGenerationId];
          return next;
        });
        setProgressWatchKey((key) => key + 1);
        setPanel("progress");
      } catch (err) {
        setDataError(getErrorMessage(err));
        setLastAction(null);
        setPreRevisePlan(null);
        setReviseIntents(null);
      } finally {
        setBusy(false);
      }
    },
    [activeResultGenerationId, activeResultPlan],
  );

  const loadDemoFixtures = useCallback(() => {
    setStructure(fixtureVideoStructure);
    setGapReport(fixtureGapReport);
    setGenerationPlan(fixtureGenerationPlan);
    setActiveGenerations(
      fixtureMultiVariantGenerations.map((entry) => ({
        generationId: entry.generationId,
        variant: entry.variant,
        taskId: entry.taskId,
        label: entry.label,
      })),
    );
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

  const handleRetryFailedTask = useCallback(
    async (retryTaskId?: string) => {
      const activeTaskId =
        retryTaskId ??
        (event?.status === "failed" ? (event.taskId ?? taskId) : (taskId ?? event?.taskId));
      if (!activeTaskId) return;
      setBusy(true);
      setDataError(null);
      try {
        const { data: latest } = await getTask(activeTaskId);
        if (
          latest.status !== "failed" &&
          latest.status !== "retrying" &&
          latest.status !== "running"
        ) {
          setDataError(`当前任务状态为「${latest.status}」，无法重试`);
          return;
        }
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
        renderVideoUrl: renderVideoByGenerationId[entryGenerationId],
      };
    },
  );

  const comparePlans = variantResultTabs
    .map((tab) => tab.plan)
    .filter((plan): plan is GenerationPlan => plan != null);

  const activeGapReport = useMemo(() => {
    const activeId = activeVariantGenerationId ?? generationId;
    const plan = activeId ? variantPlans[activeId] : generationPlan;
    const fromPlan =
      plan && "gapReport" in plan
        ? (plan as GenerationResponse).gapReport
        : undefined;
    return fromPlan ?? gapReport;
  }, [
    activeVariantGenerationId,
    generationId,
    variantPlans,
    generationPlan,
    gapReport,
  ]);

  const panels: WorkbenchPanel[] = [
    "input",
    "progress",
    "script-review",
    "analysis",
    "structure",
    "gap",
    "timeline",
    "narration",
    "result",
    "knowledge",
  ];

  return (
    <div className="space-y-6">
      <DataSourceBanner />

      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="font-serif text-2xl font-semibold tracking-tight">
            {projectName ?? "项目工作台"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            可解释结构迁移
            <span className="mx-2 text-border">·</span>
            <span className="font-mono text-xs">{projectId}</span>
          </p>
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
              selectedSampleId={sampleId}
              onTaskStarted={handleTaskStarted}
              onBatchAnalysisStarted={(tasks) => {
                setAnalysisBatchTasks(tasks);
                setLastAction("analysis");
                setPanel("progress");
              }}
              onSampleReady={(id) => {
                setSampleId(id);
                setTaskId(null);
                setDataError(null);
              }}
              onSelectSample={(id) => {
                setSampleId(id);
                void loadAnalysisResults(id);
              }}
              onSampleChanged={() => void loadProjectInput()}
            />
            <AssetInputPanel
              projectId={projectId}
              assets={projectAssets}
              onAssetsChanged={() => void loadProjectInput()}
            />
            <div className="lg:col-span-2">
              <SampleSelectionPanel
                projectId={projectId}
                onSelectionChanged={() => void loadProjectInput()}
              />
            </div>
            <div className="lg:col-span-2">
              <KnowledgeSelectionPanel
                projectId={projectId}
                onApplied={() => void loadProjectInput()}
              />
            </div>
            <div className="lg:col-span-2">
              <DurationTargetPanel
                ref={durationTargetRef}
                projectId={projectId}
                initialTarget={savedBrief?.durationTarget}
              />
            </div>
            <div className="lg:col-span-2">
              <BriefEditor
                ref={briefEditorRef}
                projectId={projectId}
                initialBrief={savedBrief}
                getDurationTarget={() => durationTargetRef.current?.getDurationTarget()}
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
          <div className="lg:col-span-2 space-y-4">
            {analysisBatchTasks.length > 0 && lastAction === "analysis" && (
              <SampleBatchAnalysisProgress
                projectId={projectId}
                tasks={analysisBatchTasks}
                onAllComplete={() => {
                  void loadProjectInput();
                  if (sampleId) {
                    void loadAnalysisResults(sampleId);
                  }
                }}
              />
            )}
            {isGenerationProgress ? (
              <MultiTaskProgressPanel
                projectId={projectId}
                tasks={activeGenerations.map((entry) => ({
                  taskId: entry.taskId,
                  label: entry.label,
                  event: generationEvents[entry.taskId] ?? null,
                  mode: generationModes[entry.taskId] ?? "idle",
                }))}
                sseFailureCounts={generationSseFailureCounts}
                error={generationProgressError}
                retryBusy={busy}
                retryLabel="重试生成计划"
                onRetry={(retryTaskId) => void handleRetryFailedTask(retryTaskId)}
                onGoToScriptReview={() => setPanel("script-review")}
              />
            ) : (
              <TaskProgressPanel
                projectId={projectId}
                event={event}
                mode={mode}
                sseFailureCount={sseFailureCount}
                error={error}
                retryBusy={busy}
                retryLabel={
                  lastAction === "revise"
                    ? "重试改片"
                    : lastAction === "generation"
                      ? "重试生成计划"
                      : "重试样例分析"
                }
                onRetry={
                  event?.status === "failed" && (taskId || event.taskId) && !busy
                    ? () => void handleRetryFailedTask()
                    : undefined
                }
                onGoToScriptReview={() => setPanel("script-review")}
              />
            )}
            {lastAction === "revise" && reviseIntents && reviseIntents.length > 0 && (
              <EditIntentList intents={reviseIntents} />
            )}
          </div>
        )}

        {panel === "script-review" && (
          <div className="lg:col-span-2">
            <ScriptReviewPanel
              projectId={projectId}
              variants={activeGenerations.map((entry) => ({
                generationId: entry.generationId,
                variant: entry.variant,
                label: entry.label,
                taskEvent: generationEvents[entry.taskId] ?? null,
              }))}
              onApproved={() => {
                setProgressWatchKey((key) => key + 1);
                setPanel("progress");
              }}
            />
          </div>
        )}

        {panel === "analysis" && (
          <div className="lg:col-span-2">
            <SampleAnalysisPanel
              projectId={projectId}
              samples={projectSamples}
              displayedSampleId={viewAnalysisSampleId}
              pendingSampleId={pendingAnalysisSampleId}
              onSelectSample={handleSelectAnalysisSample}
              structure={structure}
              sampleAnalysisFacts={sampleAnalysisFacts}
              sampleKeyframes={sampleKeyframes}
              error={dataError}
              highlightedSlotIds={highlightedSlotIds}
              onHighlightSlot={(slotId) => setHighlightedSlotIds([slotId])}
              analysisStage={
                lastAction === "analysis" ? event?.stage : undefined
              }
            />
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
            {activeGapReport ? (
              <GapReportView
                report={activeGapReport}
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

        {panel === "narration" && (
          <div className="lg:col-span-2 space-y-4">
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
                  if (plan) {
                    setGenerationPlan(plan);
                    const response = plan as GenerationResponse;
                    if (response.gapReport) {
                      setGapReport(response.gapReport);
                    }
                  }
                }}
                renderPlan={(plan) => <MasterNarrationPanel plan={plan} />}
              />
            ) : generationPlan ? (
              <MasterNarrationPanel plan={generationPlan} />
            ) : (
              <EmptyPanel message="暂无生成计划，请先运行生成或加载演示数据。" />
            )}
          </div>
        )}

        {panel === "result" && (
          <div className="lg:col-span-2 space-y-4">
            {structureProvenance && (
              <StructureProvenancePanel provenance={structureProvenance} />
            )}
            <GenerationRunHistoryPanel
              projectId={projectId}
              activeRunId={activeGenerationRunId}
              onSelectRun={(runId) => {
                setActiveGenerationRunId(runId);
                void getGenerationRun(projectId, runId)
                  .then(({ data }) => {
                    if (data.provenance) {
                      setStructureProvenance(data.provenance);
                    }
                    const first = data.generations[0];
                    if (first?.plan) {
                      setGenerationPlan(first.plan);
                      setGenerationId(first.generationId);
                      setActiveVariantGenerationId(first.generationId);
                      if (first.plan.gapReport) {
                        setGapReport(first.plan.gapReport);
                      }
                    }
                  })
                  .catch(() => {
                    /* run may be incomplete */
                  });
              }}
            />
            {preRevisePlan &&
              generationPlan &&
              preRevisePlan.id !== generationPlan.id && (
                <TimelineDiffSummary before={preRevisePlan} after={generationPlan} />
              )}

            {variantResultTabs.length > 1 && comparePlans.length > 1 && (
              <VariantCompareView plans={comparePlans} />
            )}

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
                  if (plan) {
                    setGenerationPlan(plan);
                    const response = plan as GenerationResponse;
                    if (response.gapReport) {
                      setGapReport(response.gapReport);
                    }
                  }
                }}
              />
            ) : generationPlan ? (
              <GenerationResultView
                plan={generationPlan}
                showTimeline
                videoHref={
                  generationPlan.id
                    ? renderVideoByGenerationId[generationPlan.id]
                    : undefined
                }
              />
            ) : (
              <EmptyPanel message="暂无生成结果。" />
            )}

            {(generationPlan || activeGenerations.length > 0) && (
              <ReviseInputBar
                onSubmit={handleRevise}
                busy={busy}
                disabled={!activeResultGenerationId}
              />
            )}

            {activeResultGenerationId && (
              <AgentRunsDrawer generationId={activeResultGenerationId} />
            )}
          </div>
        )}

        {panel === "knowledge" && (
          <div className="lg:col-span-2 space-y-4">
            <KnowledgeSelectionPanel
              projectId={projectId}
              onApplied={() => void loadProjectInput()}
            />
            <KnowledgeLibraryView
              onSelect={(entryId) => {
                void updateKnowledgeSelection(projectId, {
                  primaryEntryId: entryId,
                  applyStructure: false,
                }).then(() => void loadProjectInput());
              }}
            />
            {sampleId && (
              <KnowledgeDraftPanel
                projectId={projectId}
                sampleId={sampleId}
              />
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
