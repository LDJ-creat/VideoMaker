import type { TaskEvent } from "@videomaker/contracts";

export type BatchProgressCounts = {
  total: number;
  queued: number;
  running: number;
  succeeded: number;
  failed: number;
  other: number;
};

export function countBatchProgress(
  tasks: Array<{ taskId: string }>,
  events: Record<string, TaskEvent>,
): BatchProgressCounts {
  const counts: BatchProgressCounts = {
    total: tasks.length,
    queued: 0,
    running: 0,
    succeeded: 0,
    failed: 0,
    other: 0,
  };

  for (const task of tasks) {
    const event = events[task.taskId];
    if (!event) {
      counts.queued += 1;
      continue;
    }
    const status = event.status;
    if (status === "queued" || status === "retrying") {
      counts.queued += 1;
    } else if (status === "running" || status === "awaiting_review") {
      counts.running += 1;
    } else if (status === "succeeded") {
      counts.succeeded += 1;
    } else if (status === "failed" || status === "cancelled") {
      counts.failed += 1;
    } else {
      counts.other += 1;
    }
  }

  return counts;
}

export function summarizeBatchProgress(counts: BatchProgressCounts): string {
  const parts: string[] = [];
  if (counts.running > 0) {
    parts.push(`${counts.running} 个进行中`);
  }
  if (counts.queued > 0) {
    parts.push(`${counts.queued} 个排队`);
  }
  if (counts.succeeded > 0) {
    parts.push(`${counts.succeeded} 个已完成`);
  }
  if (counts.failed > 0) {
    parts.push(`${counts.failed} 个失败`);
  }
  if (parts.length === 0) {
    return `共 ${counts.total} 个样例，等待任务状态…`;
  }
  return `共 ${counts.total} 个样例 · ${parts.join(" · ")}`;
}

export function batchProgressHeadline(counts: BatchProgressCounts): string {
  if (counts.failed > 0 && counts.running === 0 && counts.queued === 0) {
    return "批量分析已结束（部分失败）";
  }
  if (counts.succeeded === counts.total) {
    return "批量分析全部完成";
  }
  if (counts.running > 0 || counts.queued > 0) {
    return "批量样例分析进行中";
  }
  return "批量样例分析";
}

export function buildRecentSampleAnalysisTasks(
  samples: Array<{ id: string; taskId?: string | null; status: string; sourceKind: string }>,
): Array<{ sampleId: string; taskId: string }> {
  return samples
    .filter(
      (sample) =>
        sample.taskId &&
        sample.sourceKind !== "knowledge" &&
        sample.status !== "uploaded",
    )
    .map((sample) => ({
      sampleId: sample.id,
      taskId: sample.taskId!,
    }));
}
