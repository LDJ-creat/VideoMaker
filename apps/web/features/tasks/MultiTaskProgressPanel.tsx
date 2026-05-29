"use client";

import type { TaskEvent } from "@videomaker/contracts";

import { TaskProgressPanel } from "@/features/tasks/TaskProgressPanel";
import type { TaskProgressMode } from "@/features/tasks/useTaskProgress";

export type MultiTaskProgressEntry = {
  taskId: string;
  label?: string;
  event: TaskEvent | null;
  mode: TaskProgressMode;
};

type MultiTaskProgressPanelProps = {
  tasks: MultiTaskProgressEntry[];
  sseFailureCount: number;
  error: string | null;
  onRetry?: (taskId: string) => void;
  retryBusy?: boolean;
  retryLabel?: string;
};

export function MultiTaskProgressPanel({
  tasks,
  sseFailureCount,
  error,
  onRetry,
  retryBusy = false,
  retryLabel = "重试任务",
}: MultiTaskProgressPanelProps) {
  if (tasks.length === 0) {
    return (
      <TaskProgressPanel
        event={null}
        mode="idle"
        sseFailureCount={0}
        error={error}
      />
    );
  }

  if (tasks.length === 1) {
    const single = tasks[0];
    return (
      <TaskProgressPanel
        event={single.event}
        mode={single.mode}
        sseFailureCount={sseFailureCount}
        error={error}
        retryBusy={retryBusy}
        retryLabel={retryLabel}
        onRetry={
          single.event?.status === "failed" && onRetry
            ? () => onRetry(single.taskId)
            : undefined
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      {tasks.map((task) => (
        <div key={task.taskId} className="space-y-1">
          {task.label && (
            <p className="text-sm font-medium text-muted-foreground">{task.label}</p>
          )}
          <TaskProgressPanel
            event={task.event}
            mode={task.mode}
            sseFailureCount={sseFailureCount}
            error={error}
            retryBusy={retryBusy}
            retryLabel={retryLabel}
            onRetry={
              task.event?.status === "failed" && onRetry
                ? () => onRetry(task.taskId)
                : undefined
            }
          />
        </div>
      ))}
    </div>
  );
}
