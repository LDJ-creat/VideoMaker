"use client";

import type {
  EditIntentItem,
  RevisePlan,
  ReviseSession,
  GapReport,
  GenerationPlan,
  TaskEvent,
  TaskStatus,
  VideoStructure,
} from "@videomaker/contracts";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";

import { DataSourceBanner } from "@/components/data-source-banner";
import { WorkbenchToast } from "@/components/workbench/WorkbenchToast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  GENERATION_KNOWLEDGE_ONLY_HINT,
  GENERATION_KNOWLEDGE_ONLY_NO_LIBRARY,
  GENERATION_REQUIRES_BRIEF_OR_SAMPLE,
} from "@/features/knowledge/knowledgeMessages";
import {
  canStartGeneration,
  hasAnalyzedRealSample,
  hasMeaningfulBrief,
} from "@/features/knowledge/knowledgeReadiness";
import {
  KnowledgeLibraryView,
  KnowledgeSelectionPanel,
  type KnowledgeSelectionPanelHandle,
} from "@/features/knowledge/KnowledgeSelectionPanel";
import { GenerationResultView } from "@/features/generation-result/GenerationResultView";
import { CompositionPatternPromotePanel } from "@/features/knowledge/CompositionPatternPromotePanel";
import {
  getDefaultSelectedVariantIds,
} from "@/features/generation-variants/VariantPicker";
import { VariantCompareView } from "@/features/generation-variants/VariantCompareView";
import { VariantTabs } from "@/features/generation-variants/VariantTabs";
import { MasterNarrationPanel } from "@/features/master-narration/MasterNarrationPanel";
import type { MigrationProgressContext } from "@/features/structure-migration/useGenerationMigrationArtifacts";
import { EditIntentList } from "@/features/nl-revise/EditIntentList";
import { ReviseInputBar } from "@/features/nl-revise/ReviseInputBar";
import { RevisePlanCard } from "@/features/nl-revise/RevisePlanCard";
import { ReviseSessionPanel } from "@/features/nl-revise/ReviseSessionPanel";
import { TimelineDiffSummary } from "@/features/nl-revise/TimelineDiffSummary";
import { ScriptReviewPanel } from "@/features/script-review/ScriptReviewPanel";
import { GenerationRunHistoryPanel } from "@/features/generation-runs/GenerationRunHistoryPanel";
import { SampleBatchAnalysisProgress } from "@/features/project-input/SampleBatchAnalysisProgress";
import {
  InputWorkbenchPanel,
  type InputWorkbenchPanelHandle,
} from "@/features/workbench/InputWorkbenchPanel";
import { WorkbenchStepper } from "@/features/workbench/WorkbenchStepper";
import { ProjectTitleEditor } from "@/features/workbench/ProjectTitleEditor";
import { computeWorkbenchPhaseState } from "@/features/workbench/workbenchPhases";
import {
  PANEL_LABELS,
  type WorkbenchPanel,
} from "@/features/workbench/workbenchTypes";
import { SampleAnalysisPanel } from "@/features/sample-analysis/SampleAnalysisPanel";
import { sampleDisplayName } from "@/features/project-input/SampleVideoCard";
import { buildRecentSampleAnalysisTasks } from "@/lib/batchAnalysisProgress";
import { StructureProvenancePanel } from "@/features/structure-provenance/StructureProvenancePanel";
import { MultiTaskProgressPanel } from "@/features/tasks/MultiTaskProgressPanel";
import { TaskProgressPanel } from "@/features/tasks/TaskProgressPanel";
import { useMultiTaskProgress } from "@/features/tasks/useMultiTaskProgress";
import { useTaskProgress } from "@/features/tasks/useTaskProgress";
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
  listGenerationRuns,
  getProject,
  getSampleKeyframes,
  getSampleAnalysis,
  getSampleSelection,
  getSampleStructure,
  getTask,
  getVariantLabel,
  listKnowledgeEntries,
  listProjectAssets,
  listProjectSamples,
  cancelRevisePlan,
  executeRevisePlan,
  getReviseSession,
  planReviseGeneration,
  retryTask,
  saveBrief,
  startSampleAnalysis,
  updateKnowledgeSelection,
  type SampleAnalysisFacts,
  type SampleKeyframeRecord,
} from "@/lib/apiClient";
import {
  buildGenerationStatusByTaskId,
  canRetryGenerationTask,
  hasRetryableFailedGeneration,
  isGenerationRenderIncomplete,
  shouldWatchGenerationTasks,
} from "@/lib/generationTaskHydration";
import { getErrorMessage } from "@/lib/errors";
import { mergeTaskEvents } from "@/lib/taskEventMerge";
import { isTaskWatchActive } from "@/lib/taskStatusLabels";
import {
  loadProjectSession,
  saveProjectSession,
} from "@/lib/project-session";
import { resolveRenderVideoUrl } from "@/lib/resolveRenderVideoUrl";
import {
  applyGenerationRunDetail,
  generationRunPlansAreLoaded,
  reloadGenerationRunPlansWithRetry,
  type ActiveGenerationEntry,
} from "@/lib/reloadGenerationRunResults";


type LastPipelineAction = "analysis" | "generation" | "revise" | null;

function emptyBrief(): UserBriefRequest {
  return { sellingPoints: [], mustMention: [], avoidMention: [] };
}

type ActiveGeneration = {
  generationId: string;
  variant: string;
  taskId: string;
  label: string;
  status?: string;
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
    setRenderVideoByGenerationId: Dispatch<SetStateAction<Record<string, string>>>;
  },
) {
  const plans: Record<string, GenerationPlan> = {};
  const renderVideos: Record<string, string> = {};
  for (const entry of data.generations) {
    if (entry.plan) {
      plans[entry.generationId] = entry.plan;
    }
    const planVideo = (entry.plan as GenerationResponse | undefined)?.renderVideoUrl;
    const videoUrl = entry.renderVideoUrl ?? planVideo;
    if (videoUrl) {
      renderVideos[entry.generationId] = videoUrl;
    }
  }
  setters.setRenderVideoByGenerationId((prev) => ({ ...prev, ...renderVideos }));
  setters.setVariantPlans(plans);
  setters.setActiveGenerations(
    data.generations.map((entry) => ({
      generationId: entry.generationId,
      variant: entry.variant,
      taskId: entry.taskId ?? "",
      label: getVariantLabel(entry.variant),
      status: entry.status,
    })),
  );
  const primary =
    data.generations.find((entry) => entry.plan != null) ?? data.generations[0];
  if (!primary) return;
  setters.setGenerationId(primary.generationId);
  setters.setActiveVariantGenerationId(primary.generationId);
  if (primary.plan) {
    setters.setGenerationPlan(primary.plan);
    if (primary.plan.gapReport) {
      setters.setGapReport(primary.plan.gapReport);
      setters.setGapApiPending(false);
    } else {
      setters.setGapReport(null);
      setters.setGapApiPending(false);
    }
  }
}

function applyReloadedGenerationPlans(
  plans: Record<string, GenerationResponse>,
  entries: ActiveGenerationEntry[],
  setters: {
    setVariantPlans: (plans: Record<string, GenerationPlan>) => void;
    setGenerationId: (id: string | null) => void;
    setGenerationPlan: (plan: GenerationPlan | null) => void;
    setActiveVariantGenerationId: (id: string | null) => void;
    setGapReport: (report: GapReport | null) => void;
    setGapApiPending: (pending: boolean) => void;
    setActiveGenerations: (entries: ActiveGeneration[]) => void;
    setRenderVideoByGenerationId: Dispatch<SetStateAction<Record<string, string>>>;
  },
) {
  const planMap: Record<string, GenerationPlan> = {};
  const renderVideos: Record<string, string> = {};
  for (const [generationId, data] of Object.entries(plans)) {
    planMap[generationId] = data;
    if (data.renderVideoUrl) {
      renderVideos[generationId] = data.renderVideoUrl;
    }
  }
  setters.setVariantPlans(planMap);
  setters.setRenderVideoByGenerationId((prev) => ({ ...prev, ...renderVideos }));
  setters.setActiveGenerations(
    entries.map((entry) => ({
      generationId: entry.generationId,
      variant: entry.variant,
      taskId: entry.taskId,
      label: entry.label,
    })),
  );
  const primary =
    entries.find((entry) => planMap[entry.generationId]) ?? entries[0];
  if (!primary) return;
  const primaryPlan = planMap[primary.generationId];
  if (!primaryPlan) return;
  setters.setGenerationId(primary.generationId);
  setters.setActiveVariantGenerationId(primary.generationId);
  setters.setGenerationPlan(primaryPlan);
  const gap = (primaryPlan as GenerationResponse).gapReport;
  if (gap) {
    setters.setGapReport(gap);
    setters.setGapApiPending(false);
  } else {
    setters.setGapReport(null);
    setters.setGapApiPending(false);
  }
}

function clearGenerationResultCache(setters: {
  setVariantPlans: (plans: Record<string, GenerationPlan>) => void;
  setGenerationPlan: (plan: GenerationPlan | null) => void;
  setGapReport: (report: GapReport | null) => void;
  setRenderVideoByGenerationId: Dispatch<SetStateAction<Record<string, string>>>;
  setActiveVariantGenerationId: (id: string | null) => void;
}) {
  setters.setVariantPlans({});
  setters.setGenerationPlan(null);
  setters.setGapReport(null);
  setters.setRenderVideoByGenerationId({});
  setters.setActiveVariantGenerationId(null);
}

export type { WorkbenchPanel } from "@/features/workbench/workbenchTypes";

const OUTPUT_RESULT_PANELS: WorkbenchPanel[] = [
  "narration",
  "result",
];

function buildGenerationSettlementKey(
  events: Record<string, TaskEvent>,
): string {
  return Object.entries(events)
    .map(([taskId, entry]) => `${taskId}:${entry.status}:${entry.stage ?? ""}`)
    .sort()
    .join("|");
}

export function ProjectWorkbench({ projectId }: ProjectWorkbenchProps) {
  const inputWorkbenchRef = useRef<InputWorkbenchPanelHandle>(null);
  const inputKnowledgePanelRef = useRef<KnowledgeSelectionPanelHandle>(null);
  const tabKnowledgePanelRef = useRef<KnowledgeSelectionPanelHandle>(null);
  const generationSettlementKeyRef = useRef<string | null>(null);
  const activeRunGenerationsRef = useRef<ActiveGeneration[]>([]);
  /** When false, generation terminal handlers hydrate data but do not auto-switch panels. */
  const generationAutoNavRef = useRef(false);
  const panelRef = useRef<WorkbenchPanel>("input");
  const [panel, setPanelState] = useState<WorkbenchPanel>("input");
  const setPanel = useCallback((next: WorkbenchPanel, reason?: string) => {
    if (process.env.NODE_ENV === "development" && reason) {
      console.info("[Workbench] panel", panelRef.current, "->", next, {
        reason,
        lastAction: lastActionRef.current,
      });
    }
    panelRef.current = next;
    setPanelState(next);
  }, []);
  const lastActionRef = useRef<LastPipelineAction>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [sampleId, setSampleId] = useState<string | null>(null);
  const [analysisSampleId, setAnalysisSampleId] = useState<string | null>(null);
  const [pendingAnalysisSampleId, setPendingAnalysisSampleId] = useState<
    string | null
  >(null);
  const [generationId, setGenerationId] = useState<string | null>(null);
  const [lastAction, setLastActionState] = useState<LastPipelineAction>(null);
  const setLastAction = useCallback((next: LastPipelineAction) => {
    lastActionRef.current = next;
    setLastActionState(next);
  }, []);
  const [generationStatusByTaskId, setGenerationStatusByTaskId] = useState<
    Record<string, TaskStatus>
  >({});
  const [settledGenerationEvents, setSettledGenerationEvents] = useState<
    Record<string, TaskEvent>
  >({});
  const [busy, setBusy] = useState(false);
  const [briefSaving, setBriefSaving] = useState(false);
  const [briefSavedToast, setBriefSavedToast] = useState<string | null>(null);
  const [knowledgeRefreshKey, setKnowledgeRefreshKey] = useState(0);

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

  useEffect(() => {
    if (activeGenerations.length > 0) {
      activeRunGenerationsRef.current = activeGenerations;
    }
  }, [activeGenerations]);
  const [analysisBatch, setAnalysisBatch] = useState<{
    tasks: Array<{ sampleId: string; taskId: string }>;
    maxConcurrent: number;
  } | null>(null);
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
  const [pendingRevisePlan, setPendingRevisePlan] = useState<RevisePlan | null>(
    null,
  );
  const [reviseSession, setReviseSession] = useState<ReviseSession | null>(null);
  const [reviseForceNewSession, setReviseForceNewSession] = useState(false);

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
      const maxAttempts = 5;
      const retryDelayMs = 400;
      let lastError: unknown = null;
      try {
        for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
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
            return;
          } catch (err) {
            lastError = err;
            const message = getErrorMessage(err);
            const retryable =
              message.includes("Structure not available") && attempt < maxAttempts - 1;
            if (!retryable) {
              throw err;
            }
            await new Promise((resolve) => setTimeout(resolve, retryDelayMs));
          }
        }
        if (lastError) {
          throw lastError;
        }
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

  const refreshKnowledgePanels = useCallback(async () => {
    await Promise.all([
      inputKnowledgePanelRef.current?.refresh(),
      tabKnowledgePanelRef.current?.refresh(),
    ]);
  }, []);

  const bumpKnowledgeRefreshKey = useCallback(() => {
    setKnowledgeRefreshKey((key) => key + 1);
  }, []);

  const scheduleKnowledgeRefresh = useCallback(() => {
    bumpKnowledgeRefreshKey();
    void refreshKnowledgePanels();
  }, [bumpKnowledgeRefreshKey, refreshKnowledgePanels]);

  const dismissBriefSavedToast = useCallback(() => {
    setBriefSavedToast(null);
  }, []);

  const persistBrief = useCallback(
    async (brief: UserBriefRequest) => {
      setBriefSaving(true);
      try {
        await saveBrief(projectId, brief);
        setSavedBrief(brief);
        setBriefSavedToast("Brief 已保存");
        scheduleKnowledgeRefresh();
      } finally {
        setBriefSaving(false);
      }
    },
    [projectId, scheduleKnowledgeRefresh],
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
      setGenerationStatusByTaskId(buildGenerationStatusByTaskId(data.generations));

      const hasAwaitingReview = data.generations.some(
        (entry) => entry.status === "awaiting_review",
      );
      const hasRunning = data.generations.some(
        (entry) => entry.status === "running",
      );
      const hasRetryableFailed = hasRetryableFailedGeneration(data.generations);
      const hasRenderIncomplete = data.generations.some(isGenerationRenderIncomplete);
      const hasActiveGeneration = hasAwaitingReview || hasRunning;
      if (hasActiveGeneration || hasRetryableFailed || hasRenderIncomplete) {
        setLastAction("generation");
      }
      if (hasActiveGeneration) {
        generationAutoNavRef.current = true;
        if (hasAwaitingReview) {
          setPanel("script-review", "hydrate:awaiting-review");
        } else if (hasRunning) {
          setPanel("progress", "hydrate:running");
        }
      } else if (hasRenderIncomplete) {
        generationAutoNavRef.current = true;
        setPanel("progress", "hydrate:render-incomplete");
      } else {
        generationAutoNavRef.current = false;
      }
      setDataSource(meta.dataSource);
      return data;
    } catch {
      /* no completed generation yet */
      return null;
    }
  }, [projectId]);

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
      reviseSessionId: reviseSession?.sessionId ?? null,
      preReviseGenerationId: preRevisePlan?.id ?? null,
      analysisBatch,
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
    reviseSession,
    preRevisePlan,
    analysisBatch,
  ]);

  const refreshRenderVideoUrls = useCallback(async (generationIds: string[]) => {
    const uniqueIds = [...new Set(generationIds.filter(Boolean))];
    if (uniqueIds.length === 0) return;

    const resolved = new Set<string>();
    for (let attempt = 0; attempt < 8; attempt += 1) {
      const updates: Record<string, string> = {};
      await Promise.all(
        uniqueIds
          .filter((generationId) => !resolved.has(generationId))
          .map(async (generationId) => {
            try {
              const { data } = await getGeneration(generationId);
              if (data.renderVideoUrl) {
                updates[generationId] = data.renderVideoUrl;
              }
            } catch {
              /* generation may still be persisting */
            }
          }),
      );
      if (Object.keys(updates).length > 0) {
        setRenderVideoByGenerationId((prev) => ({ ...prev, ...updates }));
        for (const generationId of Object.keys(updates)) {
          resolved.add(generationId);
        }
      }
      if (uniqueIds.every((id) => resolved.has(id))) return;
      await new Promise<void>((resolve) => {
        window.setTimeout(resolve, 1500);
      });
    }
  }, []);

  const loadGenerationRunView = useCallback(
    async (runId: string) => {
      setActiveGenerationRunId(runId);
      try {
        const { data } = await getGenerationRun(projectId, runId);
        if (data.provenance) {
          setStructureProvenance(data.provenance);
        }
        applyGenerationRunDetail(data, {
          setVariantPlans,
          setGenerationId,
          setGenerationPlan,
          setActiveVariantGenerationId,
          setGapReport,
          setGapApiPending,
          setActiveGenerations,
          setRenderVideoByGenerationId,
        });
        setGenerationStatusByTaskId((previous) => ({
          ...previous,
          ...buildGenerationStatusByTaskId(data.generations),
        }));
        if (
          hasRetryableFailedGeneration(data.generations) ||
          data.generations.some(isGenerationRenderIncomplete) ||
          data.generations.some((entry) => entry.status === "running")
        ) {
          setLastAction("generation");
        }
        const missingVideo = data.generations
          .filter(
            (entry) =>
              entry.plan &&
              !entry.plan.renderVideoUrl &&
              entry.status === "succeeded",
          )
          .map((entry) => entry.generationId);
        if (missingVideo.length > 0) {
          void refreshRenderVideoUrls(missingVideo);
        }
      } catch (err) {
        setDataError(getErrorMessage(err));
      }
    },
    [projectId, refreshRenderVideoUrls],
  );

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
    if (saved?.generationId) {
      void getReviseSession(saved.generationId)
        .then(({ data }) => {
          if (data.session) setReviseSession(data.session);
          if (data.pendingPlan?.status === "draft") {
            setPendingRevisePlan(data.pendingPlan);
            setReviseIntents(data.pendingPlan.intents);
          }
        })
        .catch(() => {
          /* no revise session yet */
        });
    }
    if (saved?.preReviseGenerationId) {
      void getGeneration(saved.preReviseGenerationId)
        .then(({ data }) => setPreRevisePlan(data))
        .catch(() => {
          /* plan may no longer exist */
        });
    }
    if (saved?.taskId) {
      setTaskId(saved.taskId);
    }
    if (saved?.analysisBatch?.tasks?.length) {
      setAnalysisBatch(saved.analysisBatch);
    }
    if (saved?.taskId || saved?.analysisBatch?.tasks?.length) {
      setPanel("progress");
    }
    void loadProjectInput();
    void (async () => {
      await loadProjectResults();
      if (saved?.activeGenerationRunId) {
        await loadGenerationRunView(saved.activeGenerationRunId);
        return;
      }
      try {
        const { data } = await listGenerationRuns(projectId);
        const latestRunId = data.runs[0]?.id ?? null;
        if (latestRunId) {
          setActiveGenerationRunId(latestRunId);
          void loadGenerationRunProvenance(latestRunId);
        }
      } catch {
        /* no generation runs yet */
      }
    })();
  }, [
    projectId,
    loadProjectInput,
    loadProjectResults,
    loadGenerationRunView,
    loadGenerationRunProvenance,
  ]);

  const reloadActiveGenerationResults = useCallback(
    async (entries: ActiveGenerationEntry[]) => {
      if (entries.length === 0) return false;
      const plans = await reloadGenerationRunPlansWithRetry(
        entries,
        async (generationId) => (await getGeneration(generationId)).data,
      );
      if (!plans) return false;
      applyReloadedGenerationPlans(plans, entries, {
        setVariantPlans,
        setGenerationId,
        setGenerationPlan,
        setActiveVariantGenerationId,
        setGapReport,
        setGapApiPending,
        setActiveGenerations,
        setRenderVideoByGenerationId,
      });
      const missingVideo = entries
        .map((entry) => entry.generationId)
        .filter((generationId) => !plans[generationId]?.renderVideoUrl);
      if (missingVideo.length > 0) {
        void refreshRenderVideoUrls(missingVideo);
      }
      return true;
    },
    [refreshRenderVideoUrls],
  );

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
        } else {
          void refreshRenderVideoUrls([data.id]);
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
    [refreshRenderVideoUrls],
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
        setAnalysisSampleId(sampleId);
        void loadAnalysisResults(sampleId);
        setPanel("analysis");
      }
    },
    [lastAction, loadAnalysisResults, sampleId],
  );

  const handleGenerationTaskTerminal = useCallback(
    (event: TaskEvent) => {
      setSettledGenerationEvents((previous) => ({
        ...previous,
        [event.taskId]: event,
      }));
      const match = activeGenerations.find((entry) => entry.taskId === event.taskId);
      if (
        match &&
        (event.status === "succeeded" || event.status === "awaiting_review")
      ) {
        void loadGenerationIntoVariants(match.generationId);
      }
      if (!generationAutoNavRef.current) return;

      if (event.status === "awaiting_review") {
        if (!OUTPUT_RESULT_PANELS.includes(panelRef.current)) {
          setPanel("script-review", "generation-task-terminal:awaiting-review");
        }
        return;
      }
      if (event.status !== "succeeded") {
        if (!OUTPUT_RESULT_PANELS.includes(panelRef.current)) {
          setPanel("progress", "generation-task-terminal:not-succeeded");
        }
        return;
      }
    },
    [activeGenerations, loadGenerationIntoVariants, setPanel],
  );

  const handleAllGenerationTerminal = useCallback(
    (events: Record<string, TaskEvent>) => {
      const settlementKey = buildGenerationSettlementKey(events);
      if (generationSettlementKeyRef.current === settlementKey) {
        return;
      }
      generationSettlementKeyRef.current = settlementKey;

      const hasFailedTask = Object.values(events).some(
        (entry) => entry.status === "failed" || entry.status === "cancelled",
      );

      const autoNavigate = generationAutoNavRef.current;

      void (async () => {
        const runEntries = activeRunGenerationsRef.current;
        if (
          !hasFailedTask &&
          runEntries.length > 0 &&
          runEntries.every((entry) => {
            const event = events[entry.taskId];
            return event?.status === "succeeded";
          })
        ) {
          const reloaded = await reloadActiveGenerationResults(runEntries);
          if (activeGenerationRunId) {
            void loadGenerationRunProvenance(activeGenerationRunId);
          }
          if (
            autoNavigate &&
            reloaded &&
            !OUTPUT_RESULT_PANELS.includes(panelRef.current)
          ) {
            setPanel("result", "generation-settlement:reloaded");
            generationAutoNavRef.current = false;
            return;
          }
          if (reloaded) {
            generationAutoNavRef.current = false;
            return;
          }
        }

        const latest = await loadProjectResults();
        if (activeGenerationRunId) {
          void loadGenerationRunProvenance(activeGenerationRunId);
        }
        if (!latest) {
          generationAutoNavRef.current = false;
          return;
        }
        const generations = latest.generations;
        if (
          hasFailedTask ||
          generations.some(
            (entry) => entry.status === "failed" || entry.status === "cancelled",
          )
        ) {
          setLastAction("generation");
          if (autoNavigate && !OUTPUT_RESULT_PANELS.includes(panelRef.current)) {
            setPanel("progress", "generation-settlement:failed");
          }
          generationAutoNavRef.current = false;
          return;
        }
        if (
          generations.some(
            (entry) =>
              entry.status === "awaiting_review" ||
              entry.status === "running",
          )
        ) {
          if (autoNavigate && !OUTPUT_RESULT_PANELS.includes(panelRef.current)) {
            if (generations.some((entry) => entry.status === "awaiting_review")) {
              setPanel("script-review", "generation-settlement:awaiting-review");
            } else {
              setPanel("progress", "generation-settlement:running");
            }
          }
          return;
        }
        if (
          generations.length > 0 &&
          generations.every((entry) => entry.status === "succeeded")
        ) {
          if (runEntries.length > 0) {
            await reloadActiveGenerationResults(runEntries);
          }
          if (autoNavigate && !OUTPUT_RESULT_PANELS.includes(panelRef.current)) {
            setPanel("result", "generation-settlement:all-succeeded");
          }
          generationAutoNavRef.current = false;
        }
      })();
    },
    [
      activeGenerationRunId,
      loadGenerationRunProvenance,
      loadProjectResults,
      reloadActiveGenerationResults,
      setPanel,
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

  const [taskWatchKeys, setTaskWatchKeys] = useState<Record<string, number>>({});

  const bumpTaskWatchKey = useCallback((taskId: string) => {
    setTaskWatchKeys((previous) => ({
      ...previous,
      [taskId]: (previous[taskId] ?? 0) + 1,
    }));
  }, []);

  const bumpTaskWatchKeys = useCallback((taskIds: string[]) => {
    if (taskIds.length === 0) return;
    setTaskWatchKeys((previous) => {
      const next = { ...previous };
      for (const taskId of taskIds) {
        next[taskId] = (next[taskId] ?? 0) + 1;
      }
      return next;
    });
  }, []);

  const progressSampleLabel = useMemo(() => {
    if (!sampleId) return undefined;
    const sample = projectSamples.find((entry) => entry.id === sampleId);
    return sample ? sampleDisplayName(sample) : `样例 ${sampleId.slice(0, 8)}`;
  }, [projectSamples, sampleId]);

  const progressAnalysisBatch = useMemo(() => {
    if (lastAction === "generation" || lastAction === "revise") {
      return null;
    }
    if (analysisBatch?.tasks.length) {
      return analysisBatch;
    }
    const recent = buildRecentSampleAnalysisTasks(projectSamples);
    if (recent.length >= 2) {
      return { tasks: recent, maxConcurrent: 2 };
    }
    return null;
  }, [analysisBatch, lastAction, projectSamples]);

  const singleProgressTaskId = useMemo(() => {
    if (lastAction === "generation" || progressAnalysisBatch) {
      return null;
    }
    if (taskId) {
      return taskId;
    }
    const recent = buildRecentSampleAnalysisTasks(projectSamples);
    return recent.length === 1 ? recent[0]!.taskId : null;
  }, [lastAction, progressAnalysisBatch, projectSamples, taskId]);

  const isBatchAnalysisProgress =
    progressAnalysisBatch != null && progressAnalysisBatch.tasks.length > 0;

  const showMultiVariantGenerationProgress =
    lastAction === "generation" && activeGenerations.length > 0;

  const generationProgressTasks = useMemo(
    () =>
      activeGenerations
        .filter((entry) => entry.taskId.length > 0)
        .map((entry) => ({
          taskId: entry.taskId,
          label: entry.label,
        })),
    [activeGenerations],
  );

  const watchGenerationTasks = useMemo(() => {
    if (!showMultiVariantGenerationProgress) return false;
    return shouldWatchGenerationTasks(activeGenerations, generationStatusByTaskId);
  }, [
    activeGenerations,
    generationStatusByTaskId,
    showMultiVariantGenerationProgress,
  ]);

  const { event, mode, sseFailureCount, error } = useTaskProgress({
    taskId:
      showMultiVariantGenerationProgress || isBatchAnalysisProgress
        ? null
        : singleProgressTaskId,
    enabled:
      !showMultiVariantGenerationProgress &&
      !isBatchAnalysisProgress &&
      Boolean(singleProgressTaskId),
    watchKey: singleProgressTaskId
      ? (taskWatchKeys[singleProgressTaskId] ?? 0)
      : 0,
    onTerminal: handleTerminal,
  });

  const {
    events: generationEvents,
    modes: generationModes,
    sseFailureCounts: generationSseFailureCounts,
    error: generationProgressError,
  } = useMultiTaskProgress({
    tasks: generationProgressTasks,
    enabled: showMultiVariantGenerationProgress,
    taskWatchKeys,
    onTaskTerminal: handleGenerationTaskTerminal,
    onAllTerminal: handleAllGenerationTerminal,
  });

  useEffect(() => {
    if (!showMultiVariantGenerationProgress) return;
    const updates: Record<string, TaskStatus> = {};
    for (const [taskId, taskEvent] of Object.entries(generationEvents)) {
      updates[taskId] = taskEvent.status;
    }
    if (Object.keys(updates).length === 0) return;
    setGenerationStatusByTaskId((previous) => ({ ...previous, ...updates }));
  }, [generationEvents, showMultiVariantGenerationProgress]);

  useEffect(() => {
    if (process.env.NODE_ENV !== "development") return;
    console.info("[Workbench] task-watch", {
      watchGenerationTasks,
      showMultiVariantGenerationProgress,
      taskIds: activeGenerations.map((entry) => entry.taskId),
      statuses: generationStatusByTaskId,
    });
  }, [
    activeGenerations,
    generationStatusByTaskId,
    showMultiVariantGenerationProgress,
    watchGenerationTasks,
  ]);

  useEffect(() => {
    if (watchGenerationTasks || !showMultiVariantGenerationProgress) return;
    const taskIds = activeGenerations
      .map((entry) => entry.taskId)
      .filter((taskId) => taskId.length > 0);
    if (taskIds.length === 0) return;
    let cancelled = false;
    void (async () => {
      const results: Record<string, TaskEvent> = {};
      for (const taskId of taskIds) {
        try {
          const { data } = await getTask(taskId);
          results[taskId] = data;
        } catch {
          /* task may have been purged */
        }
      }
      if (!cancelled) {
        setSettledGenerationEvents(results);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    activeGenerations,
    showMultiVariantGenerationProgress,
    watchGenerationTasks,
  ]);

  const generationTaskIdsKey = useMemo(
    () =>
      activeGenerations
        .map((entry) => entry.taskId)
        .filter((taskId) => taskId.length > 0)
        .sort()
        .join("|"),
    [activeGenerations],
  );

  useEffect(() => {
    if (panel !== "progress" || !showMultiVariantGenerationProgress) return;
    const taskIds = generationTaskIdsKey.split("|").filter(Boolean);
    if (taskIds.length === 0) return;
    let cancelled = false;
    void (async () => {
      const updates: Record<string, TaskEvent> = {};
      for (const taskId of taskIds) {
        try {
          const { data } = await getTask(taskId);
          const cached =
            generationEvents[taskId] ?? settledGenerationEvents[taskId] ?? null;
          if (
            !cached ||
            cached.status !== data.status ||
            cached.updatedAt !== data.updatedAt
          ) {
            updates[taskId] = data;
          }
        } catch {
          /* task may have been purged */
        }
      }
      if (!cancelled && Object.keys(updates).length > 0) {
        setSettledGenerationEvents((previous) => ({ ...previous, ...updates }));
        setGenerationStatusByTaskId((previous) => {
          const next = { ...previous };
          for (const [taskId, event] of Object.entries(updates)) {
            next[taskId] = event.status;
          }
          return next;
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    generationEvents,
    generationTaskIdsKey,
    panel,
    settledGenerationEvents,
    showMultiVariantGenerationProgress,
  ]);

  useEffect(() => {
    if (panel !== "progress" || !showMultiVariantGenerationProgress) return;
    const taskIds = activeGenerations
      .map((entry) => entry.taskId)
      .filter((taskId) => taskId.length > 0);
    if (taskIds.length === 0) return;
    const hasActiveTask = taskIds.some((taskId) =>
      isTaskWatchActive(generationStatusByTaskId[taskId]),
    );
    if (!hasActiveTask) return;

    let cancelled = false;
    const pollActiveTasks = async () => {
      const updates: Record<string, TaskEvent> = {};
      for (const taskId of taskIds) {
        if (!isTaskWatchActive(generationStatusByTaskId[taskId])) continue;
        try {
          const { data } = await getTask(taskId);
          const cached =
            generationEvents[taskId] ?? settledGenerationEvents[taskId] ?? null;
          if (
            !cached ||
            cached.status !== data.status ||
            cached.updatedAt !== data.updatedAt ||
            cached.progress !== data.progress
          ) {
            updates[taskId] = data;
          }
        } catch {
          /* task may have been purged */
        }
      }
      if (!cancelled && Object.keys(updates).length > 0) {
        setSettledGenerationEvents((previous) => ({ ...previous, ...updates }));
        setGenerationStatusByTaskId((previous) => {
          const next = { ...previous };
          for (const [taskId, event] of Object.entries(updates)) {
            next[taskId] = event.status;
          }
          return next;
        });
      }
    };

    void pollActiveTasks();
    const timer = window.setInterval(() => {
      void pollActiveTasks();
    }, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [
    activeGenerations,
    generationEvents,
    generationStatusByTaskId,
    panel,
    settledGenerationEvents,
    showMultiVariantGenerationProgress,
  ]);

  const displayGenerationEvents = useMemo(
    () => mergeTaskEvents(settledGenerationEvents, generationEvents),
    [generationEvents, settledGenerationEvents],
  );

  useEffect(() => {
    if (!generationAutoNavRef.current) return;
    if (!watchGenerationTasks || lastAction !== "generation") return;
    if (OUTPUT_RESULT_PANELS.includes(panelRef.current)) return;
    const awaiting = Object.values(generationEvents).some(
      (entry) => entry?.status === "awaiting_review",
    );
    if (awaiting) {
      setPanel("script-review", "generation-events:awaiting-review");
    }
  }, [generationEvents, lastAction, setPanel, watchGenerationTasks]);

  const allGenerationTasksSucceeded = useMemo(() => {
    if (activeGenerations.length === 0) return false;
    return activeGenerations.every((entry) => {
      const taskEvent = displayGenerationEvents[entry.taskId];
      return taskEvent?.status === "succeeded";
    });
  }, [activeGenerations, displayGenerationEvents]);

  useEffect(() => {
    if (lastAction !== "generation" || !OUTPUT_RESULT_PANELS.includes(panel)) return;
    if (!allGenerationTasksSucceeded) return;
    const runEntries = activeRunGenerationsRef.current;
    if (runEntries.length === 0) return;
    if (generationRunPlansAreLoaded(runEntries, variantPlans)) return;
    void reloadActiveGenerationResults(runEntries);
  }, [
    allGenerationTasksSucceeded,
    lastAction,
    panel,
    reloadActiveGenerationResults,
    variantPlans,
  ]);

  const handleTaskStarted = useCallback(
    (nextTaskId: string, nextSampleId: string) => {
      setLastAction("analysis");
      setActiveGenerations([]);
      setAnalysisBatch(null);
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
      setAnalysisBatch(null);
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
      const brief =
        (await inputWorkbenchRef.current?.saveBrief()) ?? emptyBrief();

      const { data: samplesData } = await listProjectSamples(projectId);
      const hasRealSample = hasAnalyzedRealSample(samplesData.samples);

      if (
        !canStartGeneration({
          hasMeaningfulBrief: hasMeaningfulBrief(brief),
          hasAnalyzedRealSample: hasRealSample,
        })
      ) {
        setDataError(GENERATION_REQUIRES_BRIEF_OR_SAMPLE);
        return;
      }

      let sampleSelection:
        | { primarySampleId: string; referenceSampleIds: string[] }
        | undefined;

      if (hasRealSample) {
        const { data: selectionData } = await getSampleSelection(projectId);
        const primaryId = selectionData.selection?.primarySampleId;
        const fallbackSample = samplesData.samples.find(
          (sample) =>
            sample.hasStructure &&
            sample.sourceKind !== "knowledge" &&
            sample.status === "analyzed",
        );
        const resolvedPrimaryId = primaryId ?? fallbackSample?.id;
        if (!resolvedPrimaryId) {
          setDataError("请先上传样例并设置主样例。");
          return;
        }
        const primarySample = samplesData.samples.find(
          (sample) => sample.id === resolvedPrimaryId,
        );
        if (!primarySample?.hasStructure || primarySample.sourceKind === "knowledge") {
          setDataError("请先对主样例视频完成分析，成功后再生成计划。");
          return;
        }
        sampleSelection = {
          primarySampleId: resolvedPrimaryId,
          referenceSampleIds: selectionData.selection?.referenceSampleIds ?? [],
        };
      } else {
        const { data: knowledgeData } = await listKnowledgeEntries();
        if (knowledgeData.entries.length === 0) {
          setDataError(GENERATION_KNOWLEDGE_ONLY_NO_LIBRARY);
          return;
        }
      }

      const { data } = await createGenerationPlan(projectId, {
        brief,
        variants: selectedVariantIds,
        ...(sampleSelection ? { sampleSelection } : {}),
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
      generationSettlementKeyRef.current = null;
      generationAutoNavRef.current = true;
      clearGenerationResultCache({
        setVariantPlans,
        setGenerationPlan,
        setGapReport,
        setRenderVideoByGenerationId,
        setActiveVariantGenerationId,
      });
      activeRunGenerationsRef.current = entries;
      setActiveGenerations(entries);
      setSettledGenerationEvents({});
      const initialStatuses: Record<string, TaskStatus> = {};
      for (const entry of entries) {
        initialStatuses[entry.taskId] = "queued";
      }
      setGenerationStatusByTaskId(initialStatuses);
      setGenerationId(entries[0]?.generationId ?? null);
      setTaskId(null);
      bumpTaskWatchKeys(entries.map((entry) => entry.taskId));
      setPanel("progress", "generation-started");
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
      try {
        const { data } = await planReviseGeneration(
          targetGenerationId,
          instruction,
          { newSession: reviseForceNewSession },
        );
        setReviseForceNewSession(false);
        setPendingRevisePlan(data.plan);
        setReviseIntents(data.plan.intents);
        const sessionResult = await getReviseSession(targetGenerationId);
        setReviseSession(sessionResult.data.session);
        if (sessionResult.data.pendingPlan?.status === "draft") {
          setPendingRevisePlan(sessionResult.data.pendingPlan);
          setReviseIntents(sessionResult.data.pendingPlan.intents);
        }
      } catch (err) {
        setDataError(getErrorMessage(err));
        setPendingRevisePlan(null);
        setReviseIntents(null);
      } finally {
        setBusy(false);
      }
    },
    [activeResultGenerationId, activeResultPlan, reviseForceNewSession],
  );

  const handleConfirmRevisePlan = useCallback(async () => {
    const targetGenerationId = activeResultGenerationId;
    const sourcePlan = activeResultPlan;
    const plan = pendingRevisePlan;
    if (!targetGenerationId || !sourcePlan || !plan) {
      return;
    }

    setBusy(true);
    setDataError(null);
    setLastAction("revise");
    setPreRevisePlan(sourcePlan);
    try {
      const { data } = await executeRevisePlan(targetGenerationId, plan.planId);
      setPendingRevisePlan(null);
      setReviseIntents(data.plan.intents);
      const resultGenerationId = data.generationId;
      setGenerationId(resultGenerationId);
      setTaskId(data.taskId);
      if (data.executionMode === "fork") {
        setActiveGenerations((prev) =>
          prev.length > 0
            ? prev.map((entry) =>
                entry.generationId === targetGenerationId
                  ? {
                      ...entry,
                      generationId: resultGenerationId,
                      taskId: data.taskId,
                    }
                  : entry,
              )
            : [
                {
                  generationId: resultGenerationId,
                  variant: sourcePlan.variant,
                  taskId: data.taskId,
                  label: getVariantLabel(sourcePlan.variant),
                },
              ],
        );
        setVariantPlans((prev) => {
          const next = { ...prev };
          delete next[targetGenerationId];
          return next;
        });
      } else {
        setActiveGenerations((prev) =>
          prev.map((entry) =>
            entry.generationId === targetGenerationId
              ? { ...entry, taskId: data.taskId }
              : entry,
          ),
        );
      }
      setActiveVariantGenerationId(resultGenerationId);
      const sessionResult = await getReviseSession(targetGenerationId);
      setReviseSession(sessionResult.data.session);
      bumpTaskWatchKey(data.taskId);
      setPanel("progress");
    } catch (err) {
      setDataError(getErrorMessage(err));
      setLastAction(null);
      setPreRevisePlan(null);
    } finally {
      setBusy(false);
    }
  }, [
    activeResultGenerationId,
    activeResultPlan,
    pendingRevisePlan,
  ]);

  const handleModifyReviseInstruction = useCallback(async () => {
    const targetGenerationId = activeResultGenerationId;
    const plan = pendingRevisePlan;
    if (!targetGenerationId || !plan) {
      setPendingRevisePlan(null);
      setReviseIntents(null);
      return;
    }
    setBusy(true);
    try {
      await cancelRevisePlan(targetGenerationId, plan.planId);
      setPendingRevisePlan(null);
      setReviseIntents(null);
      const sessionResult = await getReviseSession(targetGenerationId);
      setReviseSession(sessionResult.data.session);
    } catch (err) {
      setDataError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [activeResultGenerationId, pendingRevisePlan]);

  const handleNewReviseSession = useCallback(async () => {
    const targetGenerationId = activeResultGenerationId;
    if (!targetGenerationId) return;
    setBusy(true);
    setDataError(null);
    try {
      if (pendingRevisePlan) {
        await cancelRevisePlan(targetGenerationId, pendingRevisePlan.planId);
      }
      setPendingRevisePlan(null);
      setReviseIntents(null);
      setReviseForceNewSession(true);
      setReviseSession(null);
    } catch (err) {
      setDataError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [activeResultGenerationId, pendingRevisePlan]);

  const handleCancelRevisePlan = useCallback(async () => {
    const targetGenerationId = activeResultGenerationId;
    const plan = pendingRevisePlan;
    if (!targetGenerationId || !plan) {
      setPendingRevisePlan(null);
      setReviseIntents(null);
      return;
    }
    setBusy(true);
    try {
      await cancelRevisePlan(targetGenerationId, plan.planId);
      setPendingRevisePlan(null);
      setReviseIntents(null);
    } catch (err) {
      setDataError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [activeResultGenerationId, pendingRevisePlan]);

  const loadDemoFixtures = useCallback(() => {
    const demoSampleId = fixtureVideoStructure.sourceVideoId ?? "sample-demo-001";
    setStructure(fixtureVideoStructure);
    setSampleId(demoSampleId);
    setAnalysisSampleId(demoSampleId);
    setProjectSamples((current) => {
      if (current.some((sample) => sample.id === demoSampleId)) {
        return current.map((sample) =>
          sample.id === demoSampleId
            ? { ...sample, hasStructure: true, status: "analyzed" as const }
            : sample,
        );
      }
      return [
        ...current,
        {
          id: demoSampleId,
          sourceKind: "local" as const,
          status: "analyzed" as const,
          hasStructure: true,
          fileName: "demo.mp4",
        },
      ];
    });
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
  }, [projectId]);

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
        const activeEntry = activeGenerations.find(
          (entry) => entry.taskId === activeTaskId,
        );
        const renderVideoUrl = activeEntry
          ? renderVideoByGenerationId[activeEntry.generationId]
          : undefined;
        const canRetry =
          latest.status === "failed" ||
          latest.status === "retrying" ||
          latest.status === "running" ||
          canRetryGenerationTask({
            status: latest.status,
            taskId: activeTaskId,
            renderVideoUrl,
            plan: activeEntry
              ? variantPlans[activeEntry.generationId]
              : undefined,
          });
        if (!canRetry) {
          setDataError(`当前任务状态为「${latest.status}」，无法重试`);
          return;
        }
        const isGenerationRetry = Boolean(activeEntry);
        await retryTask(activeTaskId);
        generationSettlementKeyRef.current = null;
        const { data: afterRetry } = await getTask(activeTaskId);
        if (isGenerationRetry) {
          setLastAction("generation");
          setSettledGenerationEvents((previous) => ({
            ...previous,
            [activeTaskId]: afterRetry,
          }));
          setGenerationStatusByTaskId((previous) => ({
            ...previous,
            [activeTaskId]: afterRetry.status,
          }));
        } else {
          setTaskId(activeTaskId);
        }
        bumpTaskWatchKey(activeTaskId);
      } catch (err) {
        setDataError(getErrorMessage(err));
      } finally {
        setBusy(false);
      }
    },
    [activeGenerations, event?.status, event?.taskId, renderVideoByGenerationId, taskId, variantPlans],
  );

  const handleRetryGenerationFromResult = useCallback(
    (retryTaskId: string) => {
      setLastAction("generation");
      setPanel("progress", "result-retry");
      void handleRetryFailedTask(retryTaskId);
    },
    [handleRetryFailedTask, setPanel, setLastAction],
  );

  const variantResultTabs = (
    activeGenerations.length > 0
      ? activeGenerations.map((entry) => entry.generationId)
      : Object.keys(variantPlans)
  ).map((entryGenerationId) => {
    const plan = variantPlans[entryGenerationId];
    const activeMeta = activeGenerations.find(
      (entry) => entry.generationId === entryGenerationId,
    );
    const meta =
      activeMeta ??
      fixtureMultiVariantGenerations.find(
        (entry) => entry.generationId === entryGenerationId,
      );
    return {
      generationId: entryGenerationId,
      variant: meta?.variant ?? plan?.variant ?? "default",
      label: meta?.label ?? getVariantLabel(plan?.variant ?? meta?.variant ?? "default"),
      status: activeMeta?.status,
      taskId: activeMeta?.taskId,
      plan,
      renderVideoUrl: plan
        ? resolveRenderVideoUrl(plan, renderVideoByGenerationId)
        : undefined,
    };
  });

  const comparePlans = variantResultTabs
    .map((tab) => tab.plan)
    .filter((plan): plan is GenerationPlan => plan != null);

  const showVariantResultTabs =
    variantResultTabs.length > 1 ||
    variantResultTabs.some(
      (tab) => tab.status === "failed" || tab.status === "cancelled",
    );

  const resolveGapReportForGeneration = useCallback(
    (targetGenerationId: string) => {
      const plan =
        variantPlans[targetGenerationId] ??
        (generationId === targetGenerationId ? generationPlan : null);
      const fromPlan =
        plan && "gapReport" in plan
          ? (plan as GenerationResponse).gapReport
          : undefined;
      return fromPlan ?? (generationId === targetGenerationId ? gapReport : null);
    },
    [generationId, generationPlan, gapReport, variantPlans],
  );

  const getMigrationContext = useCallback(
    (activeTaskId: string): MigrationProgressContext | null => {
      if (lastAction !== "generation" && lastAction !== "revise") {
        return null;
      }
      const entry = activeGenerations.find((item) => item.taskId === activeTaskId);
      if (!entry) {
        if (lastAction === "revise" && generationId && activeTaskId === taskId) {
          return {
            projectId,
            generationId,
            structure,
          };
        }
        return null;
      }
      return {
        projectId,
        generationId: entry.generationId,
        structure,
        variantLabel: entry.label,
      };
    },
    [activeGenerations, generationId, lastAction, projectId, structure, taskId],
  );

  const hasRealAnalyzedSample = useMemo(
    () => hasAnalyzedRealSample(projectSamples),
    [projectSamples],
  );

  const generationReady = useMemo(
    () =>
      canStartGeneration({
        hasMeaningfulBrief: hasMeaningfulBrief(savedBrief ?? undefined),
        hasAnalyzedRealSample: hasRealAnalyzedSample,
      }),
    [hasRealAnalyzedSample, savedBrief],
  );

  const generationButtonTitle = useMemo(() => {
    if (generationReady && !hasRealAnalyzedSample) {
      return GENERATION_KNOWLEDGE_ONLY_HINT;
    }
    if (!generationReady) {
      return GENERATION_REQUIRES_BRIEF_OR_SAMPLE;
    }
    return undefined;
  }, [generationReady, hasRealAnalyzedSample]);

  const hasActiveTask = Boolean(
    taskId || watchGenerationTasks || isBatchAnalysisProgress,
  );

  const hasLoadedGenerationResults = useMemo(
    () =>
      Boolean(generationPlan) ||
      generationRunPlansAreLoaded(activeGenerations, variantPlans),
    [activeGenerations, generationPlan, variantPlans],
  );

  const phaseState = useMemo(
    () =>
      computeWorkbenchPhaseState({
        hasAnalyzedSample: hasRealAnalyzedSample,
        hasActiveTask,
        hasGenerationPlan: hasLoadedGenerationResults,
        panel,
      }),
    [hasActiveTask, hasRealAnalyzedSample, hasLoadedGenerationResults, panel],
  );

  const taskInProgress =
    busy ||
    (event != null &&
      event.status !== "succeeded" &&
      event.status !== "failed" &&
      event.status !== "cancelled" &&
      event.status !== "awaiting_review");

  const scriptReviewVariants = useMemo(
    () =>
      activeGenerations
        .map((entry) => ({
          generationId: entry.generationId,
          variant: entry.variant,
          label: entry.label,
          taskEvent: displayGenerationEvents[entry.taskId] ?? null,
        }))
        .filter((entry) => {
          const stage = entry.taskEvent?.stage;
          return (
            entry.taskEvent?.status === "awaiting_review" ||
            stage === "awaiting_master_review" ||
            stage === "awaiting_storyboard_review"
          );
        }),
    [activeGenerations, displayGenerationEvents],
  );

  return (
    <div className="space-y-6">
      <DataSourceBanner />

      <div className="flex flex-col gap-4 pt-1 md:flex-row md:items-start md:justify-between">
        <div>
          <ProjectTitleEditor
            projectId={projectId}
            name={projectName}
            onNameChange={setProjectName}
            onError={setDataError}
          />
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
          {taskInProgress ? (
            <Button type="button" onClick={() => setPanel("progress")}>
              查看进度
            </Button>
          ) : (
            <>
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
                disabled={busy || briefSaving || !generationReady}
                title={generationButtonTitle}
                onClick={() => void handleStartGeneration()}
              >
                开始生成视频
              </Button>
            </>
          )}
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

      <WorkbenchStepper
        phaseState={phaseState}
        panel={panel}
        panelLabels={PANEL_LABELS}
        onSelectPanel={setPanel}
        taskBadge={
          <>
            {taskId && !showMultiVariantGenerationProgress && !isBatchAnalysisProgress && (
              <Badge variant="outline" className="ml-auto font-normal">
                单任务进度
              </Badge>
            )}
            {isBatchAnalysisProgress && progressAnalysisBatch ? (
              <Badge variant="ai" className="ml-auto">
                批量分析 {progressAnalysisBatch.tasks.length} 个
              </Badge>
            ) : null}
            {showMultiVariantGenerationProgress && (
              <Badge variant="ai" className="ml-auto">
                {activeGenerations.length} 个变体任务
              </Badge>
            )}
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-2 lg:items-stretch">
        {panel === "input" && (
          <div className="lg:col-span-2">
            <InputWorkbenchPanel
              ref={inputWorkbenchRef}
              projectId={projectId}
              samples={projectSamples}
              assets={projectAssets}
              activeSample={activeSample}
              selectedSampleId={sampleId}
              savedBrief={savedBrief}
              selectedVariantIds={selectedVariantIds}
              busy={busy}
              briefSaving={briefSaving}
              knowledgeRefreshKey={knowledgeRefreshKey}
              knowledgePanelRef={inputKnowledgePanelRef}
              onPersistBrief={persistBrief}
              onVariantChange={setSelectedVariantIds}
              onTaskStarted={handleTaskStarted}
              onBatchAnalysisStarted={(tasks, maxConcurrent) => {
                setAnalysisBatch({ tasks, maxConcurrent });
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
              onSampleChanged={() => {
                void loadProjectInput().then(() => bumpKnowledgeRefreshKey());
              }}
              onAssetsChanged={() => void loadProjectInput()}
              onKnowledgeApplied={() => void loadProjectInput()}
              onSelectionChanged={() => {
                void loadProjectInput().then(() => bumpKnowledgeRefreshKey());
              }}
            />
          </div>
        )}

        {panel === "progress" && (
          <div className="lg:col-span-2 space-y-4">
            {isBatchAnalysisProgress && progressAnalysisBatch ? (
              <SampleBatchAnalysisProgress
                projectId={projectId}
                samples={projectSamples}
                tasks={progressAnalysisBatch.tasks}
                maxConcurrent={progressAnalysisBatch.maxConcurrent}
                onAllComplete={() => {
                  void loadProjectInput();
                  if (sampleId) {
                    void loadAnalysisResults(sampleId);
                  }
                }}
              />
            ) : showMultiVariantGenerationProgress ? (
              <MultiTaskProgressPanel
                projectId={projectId}
                title="生成计划"
                tasks={activeGenerations
                  .filter((entry) => entry.taskId.length > 0)
                  .map((entry) => ({
                    taskId: entry.taskId,
                    label: entry.label,
                    event: displayGenerationEvents[entry.taskId] ?? null,
                    mode: generationModes[entry.taskId] ?? "idle",
                    retryable: canRetryGenerationTask({
                      status:
                        displayGenerationEvents[entry.taskId]?.status ??
                        entry.status,
                      taskId: entry.taskId,
                      renderVideoUrl: renderVideoByGenerationId[entry.generationId],
                      plan: variantPlans[entry.generationId],
                    }),
                  }))}
                sseFailureCounts={generationSseFailureCounts}
                error={generationProgressError}
                retryBusy={busy}
                retryLabel="重试生成 / 重新渲染"
                onRetry={(retryTaskId) => void handleRetryFailedTask(retryTaskId)}
                onGoToScriptReview={() => setPanel("script-review")}
                getMigrationContext={getMigrationContext}
              />
            ) : (
              <TaskProgressPanel
                projectId={projectId}
                event={event}
                mode={mode}
                sseFailureCount={sseFailureCount}
                error={error}
                title={
                  lastAction === "revise"
                    ? "改片任务"
                    : lastAction === "analysis"
                      ? "样例分析"
                      : "任务进度"
                }
                subtitle={lastAction === "analysis" ? progressSampleLabel : undefined}
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
                migrationContext={
                  taskId && getMigrationContext(taskId)
                    ? getMigrationContext(taskId)!
                    : undefined
                }
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
              variants={scriptReviewVariants}
              onApproved={() => {
                bumpTaskWatchKeys(
                  activeGenerations
                    .map((entry) => entry.taskId)
                    .filter((id) => id.length > 0),
                );
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
                renderPlan={(plan) => (
                  <MasterNarrationPanel
                    plan={plan}
                    structure={structure}
                    gapReport={resolveGapReportForGeneration(plan.id) ?? null}
                  />
                )}
              />
            ) : generationPlan ? (
              <MasterNarrationPanel
                plan={generationPlan}
                structure={structure}
                gapReport={resolveGapReportForGeneration(generationPlan.id) ?? null}
              />
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
              retryBusy={busy}
              onRetryTask={handleRetryGenerationFromResult}
              onSelectRun={(runId) => {
                void loadGenerationRunView(runId);
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

            {showVariantResultTabs ? (
              <VariantTabs
                tabs={variantResultTabs}
                activeGenerationId={
                  activeVariantGenerationId ??
                  variantResultTabs[0]?.generationId ??
                  null
                }
                retryBusy={busy}
                onRetryTask={handleRetryGenerationFromResult}
                onGoToNarration={() => setPanel("narration")}
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
                videoHref={resolveRenderVideoUrl(
                  generationPlan,
                  renderVideoByGenerationId,
                )}
                onGoToNarration={() => setPanel("narration")}
                onRetryRender={
                  (() => {
                    const activeMeta = activeGenerations.find(
                      (entry) => entry.generationId === generationPlan.id,
                    );
                    const taskId = activeMeta?.taskId;
                    if (
                      !taskId ||
                      !canRetryGenerationTask({
                        status: activeMeta?.status,
                        taskId,
                        renderVideoUrl: resolveRenderVideoUrl(
                          generationPlan,
                          renderVideoByGenerationId,
                        ),
                        plan: generationPlan,
                      })
                    ) {
                      return undefined;
                    }
                    return () => handleRetryGenerationFromResult(taskId);
                  })()
                }
                retryRenderBusy={busy}
              />
            ) : (
              <EmptyPanel message="暂无生成结果。" />
            )}

            {activeResultPlan && activeResultGenerationId ? (
              <CompositionPatternPromotePanel
                projectId={projectId}
                generationId={activeResultGenerationId}
                videoReady={Boolean(
                  resolveRenderVideoUrl(
                    activeResultPlan,
                    renderVideoByGenerationId,
                  ),
                )}
              />
            ) : null}

            {reviseSession && (
              <div className="space-y-2">
                <ReviseSessionPanel session={reviseSession} />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={busy || !activeResultGenerationId}
                  onClick={() => void handleNewReviseSession()}
                >
                  重新开始改片对话
                </Button>
              </div>
            )}

            {pendingRevisePlan && (
              <RevisePlanCard
                plan={pendingRevisePlan}
                busy={busy}
                onConfirm={handleConfirmRevisePlan}
                onCancel={handleCancelRevisePlan}
                onReviseInstruction={() => void handleModifyReviseInstruction()}
              />
            )}

            {(generationPlan || activeGenerations.length > 0) && !pendingRevisePlan && (
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
              ref={tabKnowledgePanelRef}
              projectId={projectId}
              refreshKey={knowledgeRefreshKey}
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
          </div>
        )}
      </div>

      <WorkbenchToast message={briefSavedToast} onDismiss={dismissBriefSavedToast} />
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
