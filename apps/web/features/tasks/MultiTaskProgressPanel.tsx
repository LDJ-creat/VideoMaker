"use client";

import type { TaskEvent } from "@videomaker/contracts";

import { TaskProgressPanel } from "@/features/tasks/TaskProgressPanel";
import type { MigrationProgressContext } from "@/features/structure-migration/useGenerationMigrationArtifacts";
import { getDevProgressMetrics } from "@/lib/devProgressMetrics";

import type { TaskProgressMode } from "@/features/tasks/useTaskProgress";
import { isTaskCancellable } from "@/lib/taskStatusLabels";

export type MultiTaskProgressEntry = {
  taskId: string;
  label?: string;
  event: TaskEvent | null;
  mode: TaskProgressMode;
  sseFailureCount?: number;
  retryable?: boolean;
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
  onCancel?: (taskId: string) => void;
  cancelBusy?: boolean;
  cancelLabel?: string;
  onGoToScriptReview?: () => void;
  getMigrationContext?: (taskId: string) => MigrationProgressContext | null;
  taskWatchKeys?: Record<string, number>;
  materialSlotRegenByTask?: Record<string, string[]>;
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
  onCancel,
  cancelBusy = false,
  cancelLabel = "取消任务",
  onGoToScriptReview,
  getMigrationContext,
  taskWatchKeys = {},
  materialSlotRegenByTask = {},
}: MultiTaskProgressPanelProps) {
  const devMetrics =
    process.env.NODE_ENV === "development" ? getDevProgressMetrics() : null;

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
        migrationContext={getMigrationContext?.(single.taskId) ?? undefined}
        progressResetKey={taskWatchKeys[single.taskId] ?? 0}
        regeneratingSlotIds={materialSlotRegenByTask[single.taskId]}
          onRetry={
            (single.retryable ||
              single.event?.status === "failed" ||
              single.event?.status === "cancelled" ||
              single.event?.status === "retrying") &&
            onRetry
              ? () => onRetry(single.taskId)
              : undefined
          }
        onCancel={
          single.event && isTaskCancellable(single.event.status) && onCancel
            ? () => onCancel(single.taskId)
            : undefined
        }
        cancelBusy={cancelBusy}
        cancelLabel={cancelLabel}
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
          migrationContext={getMigrationContext?.(task.taskId) ?? undefined}
          progressResetKey={taskWatchKeys[task.taskId] ?? 0}
          regeneratingSlotIds={materialSlotRegenByTask[task.taskId]}
            onRetry={
              (task.retryable ||
                task.event?.status === "failed" ||
                task.event?.status === "cancelled" ||
                task.event?.status === "retrying") &&
              onRetry
                ? () => onRetry(task.taskId)
                : undefined
            }
          onCancel={
            task.event && isTaskCancellable(task.event.status) && onCancel
              ? () => onCancel(task.taskId)
              : undefined
          }
          cancelBusy={cancelBusy}
          cancelLabel={cancelLabel}
        />
      ))}
      {devMetrics ? (
        <p
          className="font-mono text-[10px] text-muted-foreground/50"
          data-testid="dev-progress-metrics"
        >
          dev fetch: artifact={devMetrics.artifactFetch} poll={devMetrics.taskPoll}{" "}
          sse={devMetrics.sseReconnect}
        </p>
      ) : null}
    </div>
  );
}
