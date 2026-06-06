"use client";

import { useMemo } from "react";

import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { MultiTaskProgressPanel } from "@/features/tasks/MultiTaskProgressPanel";
import { useMultiTaskProgress } from "@/features/tasks/useMultiTaskProgress";
import { sampleDisplayName } from "@/features/project-input/SampleVideoCard";
import type { ActiveSampleSummary } from "@/lib/apiClient";
import {
  batchProgressHeadline,
  buildRecentSampleAnalysisTasks,
  countBatchProgress,
  summarizeBatchProgress,
} from "@/lib/batchAnalysisProgress";

type SampleBatchAnalysisProgressProps = {
  projectId?: string;
  samples?: ActiveSampleSummary[];
  tasks: Array<{ sampleId: string; taskId: string; label?: string }>;
  maxConcurrent?: number;
  onAllComplete?: () => void;
};

export function SampleBatchAnalysisProgress({
  projectId,
  samples = [],
  tasks,
  maxConcurrent,
  onAllComplete,
}: SampleBatchAnalysisProgressProps) {
  const sampleById = useMemo(
    () => new Map(samples.map((sample) => [sample.id, sample])),
    [samples],
  );

  const labeledTasks = useMemo(
    () =>
      tasks.map((task) => {
        const sample = sampleById.get(task.sampleId);
        return {
          taskId: task.taskId,
          label:
            task.label ??
            (sample ? sampleDisplayName(sample) : `样例 ${task.sampleId.slice(0, 8)}`),
        };
      }),
    [sampleById, tasks],
  );

  const progress = useMultiTaskProgress({
    tasks: labeledTasks,
    enabled: tasks.length > 0,
    onAllTerminal: () => onAllComplete?.(),
  });

  const counts = countBatchProgress(tasks, progress.events);
  const summary = summarizeBatchProgress(counts);
  const headline = batchProgressHeadline(counts);

  if (tasks.length === 0) return null;

  return (
    <div className="space-y-4" data-testid="sample-batch-analysis-progress">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>{headline}</CardTitle>
          <CardDescription>{summary}</CardDescription>
          {maxConcurrent != null && maxConcurrent > 0 ? (
            <CardDescription className="text-xs">
              系统最多同时分析 {maxConcurrent} 个样例，其余任务会先进入排队。
            </CardDescription>
          ) : null}
        </CardHeader>
      </Card>

      <MultiTaskProgressPanel
        projectId={projectId}
        title="样例分析"
        compact
        tasks={labeledTasks.map((task) => ({
          taskId: task.taskId,
          label: task.label,
          event: progress.byTaskId[task.taskId]?.event ?? null,
          mode: progress.byTaskId[task.taskId]?.mode ?? "idle",
          sseFailureCount: progress.byTaskId[task.taskId]?.sseFailureCount ?? 0,
        }))}
        sseFailureCounts={progress.sseFailureCounts}
        error={progress.error}
      />
    </div>
  );
}
