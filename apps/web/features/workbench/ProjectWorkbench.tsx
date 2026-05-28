"use client";

import { useCallback, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AssetInputPanel } from "@/features/project-input/AssetInputPanel";
import { BriefEditor } from "@/features/project-input/BriefEditor";
import { SampleInputPanel } from "@/features/project-input/SampleInputPanel";
import { GapReportView } from "@/features/gap-report/GapReportView";
import { GenerationResultView } from "@/features/generation-result/GenerationResultView";
import { SampleAnalysisView } from "@/features/sample-analysis/SampleAnalysisView";
import { StructureSlotBoard } from "@/features/structure-mapping/StructureSlotBoard";
import { TimelinePreview } from "@/features/timeline-preview/TimelinePreview";
import { TaskProgressPanel } from "@/features/tasks/TaskProgressPanel";
import { useTaskProgress } from "@/features/tasks/useTaskProgress";
import {
  createGenerationPlan,
  startSampleAnalysis,
} from "@/lib/apiClient";
import { getApiBaseUrl } from "@/lib/config";
import {
  fixtureGapReport,
  fixtureGenerationPlan,
  fixtureVideoStructure,
} from "@/fixtures";

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

type ProjectWorkbenchProps = {
  projectId: string;
};

export function ProjectWorkbench({ projectId }: ProjectWorkbenchProps) {
  const apiBaseUrl = getApiBaseUrl();
  const [panel, setPanel] = useState<WorkbenchPanel>("input");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [sampleId, setSampleId] = useState<string>("sample-demo-001");
  const [busy, setBusy] = useState(false);

  const structure = useMemo(() => fixtureVideoStructure, []);
  const gapReport = useMemo(() => fixtureGapReport, []);
  const generationPlan = useMemo(() => fixtureGenerationPlan, []);

  const { event, mode, sseFailureCount, error } = useTaskProgress({
    apiBaseUrl,
    taskId,
    enabled: Boolean(taskId),
  });

  const handleTaskStarted = useCallback((nextTaskId: string, nextSampleId: string) => {
    setTaskId(nextTaskId);
    setSampleId(nextSampleId);
    setPanel("progress");
  }, []);

  const handleStartAnalysis = useCallback(async () => {
    setBusy(true);
    try {
      const { taskId: analysisTaskId } = await startSampleAnalysis(
        apiBaseUrl,
        sampleId,
      );
      setTaskId(analysisTaskId);
      setPanel("progress");
    } finally {
      setBusy(false);
    }
  }, [apiBaseUrl, sampleId]);

  const handleStartGeneration = useCallback(async () => {
    setBusy(true);
    try {
      const { taskId: genTaskId } = await createGenerationPlan(
        apiBaseUrl,
        projectId,
      );
      setTaskId(genTaskId ?? null);
      setPanel("progress");
    } finally {
      setBusy(false);
    }
  }, [apiBaseUrl, projectId]);

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
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">项目工作台</h1>
          <p className="font-mono text-sm text-muted-foreground">{projectId}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={busy}
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

      <div className="grid gap-4 lg:grid-cols-2">
        {panel === "input" && (
          <>
            <SampleInputPanel
              apiBaseUrl={apiBaseUrl}
              projectId={projectId}
              onTaskStarted={handleTaskStarted}
            />
            <AssetInputPanel apiBaseUrl={apiBaseUrl} projectId={projectId} />
            <div className="lg:col-span-2">
              <BriefEditor apiBaseUrl={apiBaseUrl} projectId={projectId} />
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
            <SampleAnalysisView structure={structure} />
          </div>
        )}

        {panel === "structure" && (
          <div className="lg:col-span-2">
            <StructureSlotBoard structure={structure} />
          </div>
        )}

        {panel === "gap" && (
          <div className="lg:col-span-2">
            <GapReportView
              report={gapReport}
              onUploadAsset={() => setPanel("input")}
              onGenerate={() => setPanel("result")}
            />
          </div>
        )}

        {panel === "timeline" && (
          <div className="lg:col-span-2">
            <TimelinePreview timeline={generationPlan.timeline} />
          </div>
        )}

        {panel === "result" && (
          <div className="lg:col-span-2">
            <GenerationResultView plan={generationPlan} />
          </div>
        )}
      </div>
    </div>
  );
}
