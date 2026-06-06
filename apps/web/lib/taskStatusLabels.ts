import type { TaskStatus } from "@videomaker/contracts";

export type TaskStatusBadgeVariant =
  | "default"
  | "secondary"
  | "destructive"
  | "outline";

const STATUS_LABELS: Record<TaskStatus, string> = {
  queued: "排队中",
  running: "进行中",
  succeeded: "已完成",
  failed: "失败",
  cancelled: "已取消",
  retrying: "重试中",
  awaiting_review: "待审核",
};

export function getTaskStatusLabel(status: TaskStatus | string): string {
  if (status in STATUS_LABELS) {
    return STATUS_LABELS[status as TaskStatus];
  }
  return String(status);
}

export function getTaskStatusBadgeVariant(
  status: TaskStatus | string,
): TaskStatusBadgeVariant {
  switch (status) {
    case "succeeded":
      return "default";
    case "failed":
    case "cancelled":
      return "destructive";
    case "awaiting_review":
      return "secondary";
    case "queued":
    case "retrying":
      return "outline";
    default:
      return "secondary";
  }
}

export function isTaskTerminalStatus(status: TaskStatus | string): boolean {
  return status === "succeeded" || status === "failed" || status === "cancelled";
}
