"use client";

import type { TaskEvent } from "@videomaker/contracts";

import { TaskProgressPanel } from "@/features/tasks/TaskProgressPanel";
import type { TaskProgressMode } from "@/features/tasks/useTaskProgress";

export type MultiTaskProgressEntry = {
  taskId: string;
  label?: string;
  event: TaskEvent | null;
  mode: TaskProgressMode;
  sseFailureCount?: number;
};

type MultiTaskProgressPanelProps = {
  projectId?: string;
  tasks: MultiTaskProgressEntry[];
  sseFailureCounts?: Record<string, number>;
  error: string | null;
  title?: string;
  compact?: boolean;
  onRetry?: (taskId: string) => void;
  retryBusy?: boolean;
  retryLabel?: string;
  onGoToScriptReview?: () => void;
};

export function MultiTaskProgressPanel({
  projectId,
  tasks,
  sseFailureCounts = {},
  error,
  title = "任务进度",
  compact = false,
  onRetry,
  retryBusy = false,
  retryLabel = "重试任务",
  onGoToScriptReview,
}: MultiTaskProgressPanelProps) {
  if (tasks.length === 0) {
    return (
      <TaskProgressPanel
        projectId={projectId}
        event={null}
        mode="idle"
        sseFailureCount={0}
        error={error}
        title={title}
        compact={compact}
      />
    );
  }

  if (tasks.length === 1) {
    const single = tasks[0]!;
    return (
      <TaskProgressPanel
        projectId={projectId}
        event={single.event}
        mode={single.mode}
        sseFailureCount={
          single.sseFailureCount ?? sseFailureCounts[single.taskId] ?? 0
        }
        error={error}
        title={title}
        subtitle={single.label}
        compact={compact}
        retryBusy={retryBusy}
        retryLabel={retryLabel}
        onGoToScriptReview={onGoToScriptReview}
        onRetry={
          single.event?.status === "failed" && onRetry
            ? () => onRetry(single.taskId)
            : undefined
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      {tasks.map((task) => (
        <TaskProgressPanel
          key={task.taskId}
          projectId={projectId}
          event={task.event}
          mode={task.mode}
          sseFailureCount={
            task.sseFailureCount ?? sseFailureCounts[task.taskId] ?? 0
          }
          error={error}
          title={title}
          subtitle={task.label ?? `任务 ${task.taskId.slice(0, 8)}`}
          compact
          retryBusy={retryBusy}
          retryLabel={retryLabel}
          onGoToScriptReview={onGoToScriptReview}
          onRetry={
            task.event?.status === "failed" && onRetry
              ? () => onRetry(task.taskId)
              : undefined
          }
        />
      ))}
    </div>
  );
}
