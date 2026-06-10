import type { TaskStatus } from "@videomaker/contracts";

import { isTaskWatchActive } from "@/lib/taskStatusLabels";

export type GenerationTaskSnapshot = {
  status?: string;
  taskId?: string | null;
  renderVideoUrl?: string | null;
  plan?: { renderVideoUrl?: string | null } | null;
};

export function isGenerationRenderIncomplete(
  entry: GenerationTaskSnapshot,
): boolean {
  if (entry.status !== "succeeded" || !entry.taskId) {
    return false;
  }
  const videoUrl = entry.renderVideoUrl ?? entry.plan?.renderVideoUrl;
  return !videoUrl?.trim();
}

export function canRetryGenerationTask(entry: GenerationTaskSnapshot): boolean {
  if (!entry.taskId) {
    return false;
  }
  if (entry.status === "failed" || entry.status === "cancelled") {
    return true;
  }
  return isGenerationRenderIncomplete(entry);
}

export function hasRetryableFailedGeneration(
  generations: GenerationTaskSnapshot[],
): boolean {
  return generations.some(canRetryGenerationTask);
}

export function buildGenerationStatusByTaskId(
  generations: GenerationTaskSnapshot[],
): Record<string, TaskStatus> {
  const statusByTaskId: Record<string, TaskStatus> = {};
  for (const entry of generations) {
    if (entry.taskId && entry.status) {
      statusByTaskId[entry.taskId] = entry.status as TaskStatus;
    }
  }
  return statusByTaskId;
}

export function shouldWatchGenerationTasks(
  entries: Array<{ taskId: string; status?: string }>,
  statusByTaskId: Record<string, TaskStatus>,
): boolean {
  return entries.some((entry) => {
    if (!entry.taskId) return false;
    const status = statusByTaskId[entry.taskId] ?? entry.status;
    return isTaskWatchActive(status);
  });
}
