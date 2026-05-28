"use client";

import type {
  GapReport,
  GenerationPlan,
  TaskEvent,
  VideoStructure,
} from "@videomaker/contracts";
import { useCallback, useEffect, useState } from "react";

import { DataSourceBanner } from "@/components/data-source-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GapReportView } from "@/features/gap-report/GapReportView";
import { GenerationResultView } from "@/features/generation-result/GenerationResultView";
import { AssetInputPanel } from "@/features/project-input/AssetInputPanel";
import { BriefEditor } from "@/features/project-input/BriefEditor";
import { SampleInputPanel } from "@/features/project-input/SampleInputPanel";
import { SampleAnalysisView } from "@/features/sample-analysis/SampleAnalysisView";
import { StructureSlotBoard } from "@/features/structure-mapping/StructureSlotBoard";
import { TaskProgressPanel } from "@/features/tasks/TaskProgressPanel";
import { useTaskProgress } from "@/features/tasks/useTaskProgress";
import { TimelinePreview } from "@/features/timeline-preview/TimelinePreview";
import {
  fixtureGapReport,
  fixtureGenerationPlan,
  fixtureVideoStructure,
} from "@/fixtures";
import type { DataSource } from "@/lib/api-types";
import {
  createGenerationPlan,
  getGeneration,
  getSampleStructure,
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

type ProjectWorkbenchProps = {
  projectId: string;
};

export function ProjectWorkbench({ projectId }: ProjectWorkbenchProps) {
  const [panel, setPanel] = useState<WorkbenchPanel>("input");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [sampleId, setSampleId] = useState<string | null>(null);
  const [generationId, setGenerationId] = useState<string | null>(null);
  const [lastAction, setLastAction] = useState<LastPipelineAction>(null);
  const [busy, setBusy] = useState(false);

  const [structure, setStructure] = useState<VideoStructure | null>(null);
  const [gapReport, setGapReport] = useState<GapReport | null>(null);
  const [generationPlan, setGenerationPlan] = useState<GenerationPlan | null>(
    null,
  );
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);
  const [gapApiPending, setGapApiPending] = useState(false);

  useEffect(() => {
    const saved = loadProjectSession(projectId);
    if (!saved) return;
    if (saved.sampleId) setSampleId(saved.sampleId);
    if (saved.generationId) setGenerationId(saved.generationId);
    if (saved.lastAction) setLastAction(saved.lastAction);
    if (saved.taskId) {
      setTaskId(saved.taskId);
      setPanel("progress");
    }
  }, [projectId]);

  useEffect(() => {
    saveProjectSession(projectId, {
      taskId,
      sampleId,
      generationId,
      lastAction,
    });
  }, [projectId, taskId, sampleId, generationId, lastAction]);

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

  const { event, mode, sseFailureCount, error } = useTaskProgress({
    taskId,
    enabled: Boolean(taskId),
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
    if (!sampleId) {
      setDataError("请先上传样例视频");
      return;
    }
    setBusy(true);
    setDataError(null);
    setLastAction("analysis");
    try {
      const { data } = await startSampleAnalysis(sampleId);
      setTaskId(data.taskId);
      setPanel("progress");
    } catch (err) {
      setDataError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [sampleId]);

  const handleStartGeneration = useCallback(async () => {
    setBusy(true);
    setDataError(null);
    setLastAction("generation");
    try {
      const { data } = await createGenerationPlan(projectId);
      setGenerationId(data.generationId);
      if (data.taskId) {
        setTaskId(data.taskId);
      }
      if (data.gapReport) {
        setGapReport(data.gapReport);
      }
      setPanel("progress");
    } catch (err) {
      setDataError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [projectId]);

  const loadDemoFixtures = useCallback(() => {
    setStructure(fixtureVideoStructure);
    setGapReport(fixtureGapReport);
    setGenerationPlan(fixtureGenerationPlan);
    setDataSource("fixture");
    setGapApiPending(true);
    setDataError(null);
  }, []);

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
        {dataSource && (
          <Badge variant="outline">数据源 {dataSource}</Badge>
        )}
      </nav>

      <div className="grid gap-4 lg:grid-cols-2">
        {panel === "input" && (
          <>
            <SampleInputPanel
              projectId={projectId}
              onTaskStarted={handleTaskStarted}
            />
            <AssetInputPanel projectId={projectId} />
            <div className="lg:col-span-2">
              <BriefEditor projectId={projectId} />
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
            />
          </div>
        )}

        {panel === "analysis" && (
          <div className="lg:col-span-2">
            {structure ? (
              <SampleAnalysisView structure={structure} />
            ) : (
              <EmptyPanel message="暂无分析结果，请先完成样例分析或加载演示数据。" />
            )}
          </div>
        )}

        {panel === "structure" && (
          <div className="lg:col-span-2">
            {structure ? (
              <StructureSlotBoard structure={structure} />
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
            {generationPlan ? (
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
