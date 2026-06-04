"use client";

import { MultiTaskProgressPanel } from "@/features/tasks/MultiTaskProgressPanel";
import { useMultiTaskProgress } from "@/features/tasks/useMultiTaskProgress";

type SampleBatchAnalysisProgressProps = {
  projectId?: string;
  tasks: Array<{ sampleId: string; taskId: string; label?: string }>;
  onAllComplete?: () => void;
};

export function SampleBatchAnalysisProgress({
  projectId,
  tasks,
  onAllComplete,
}: SampleBatchAnalysisProgressProps) {
  const progress = useMultiTaskProgress({
    tasks: tasks.map((task) => ({
      taskId: task.taskId,
      label: task.label ?? task.sampleId.slice(0, 8),
    })),
    enabled: tasks.length > 0,
    onAllTerminal: () => onAllComplete?.(),
  });

  if (tasks.length === 0) return null;

  return (
    <MultiTaskProgressPanel
      projectId={projectId}
      tasks={tasks.map((task) => ({
        taskId: task.taskId,
        label: task.label ?? task.sampleId.slice(0, 8),
        event: progress.byTaskId[task.taskId]?.event ?? null,
        mode: progress.byTaskId[task.taskId]?.mode ?? "idle",
        sseFailureCount: progress.byTaskId[task.taskId]?.sseFailureCount ?? 0,
      }))}
      sseFailureCounts={progress.sseFailureCounts}
      error={progress.error}
    />
  );
}
