export function generationRunStatusLabel(status: string): string {
  if (status === "awaiting_review") return "等待脚本审核";
  if (status === "completed") return "已完成";
  if (status === "partial_failed") return "部分失败";
  if (status === "running") return "进行中";
  if (status === "failed") return "失败";
  return status;
}

export function generationStatusLabel(status: string | undefined): string {
  if (!status) return "未知";
  if (status === "succeeded") return "生成成功";
  if (status === "failed") return "生成失败";
  if (status === "running") return "生成中";
  if (status === "pending") return "等待中";
  if (status === "awaiting_review") return "等待脚本审核";
  return status;
}

export function generationStatusBadgeVariant(
  status: string | undefined,
): "outline" | "secondary" | "destructive" | "success" | "warning" {
  if (status === "succeeded") return "success";
  if (status === "failed") return "destructive";
  if (status === "awaiting_review") return "warning";
  if (status === "running") return "secondary";
  return "outline";
}
