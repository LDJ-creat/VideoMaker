import type { MaterialReviewReport, MaterialReviewSlotEntry } from "@videomaker/contracts";

export function slotStatusDisplay(status: string | undefined): string {
  switch (status) {
    case "review_bypass":
      return "待人工审片";
    case "review_exhausted":
      return "审片额度用尽";
    case "review_unavailable":
      return "审片不可用";
    case "agent_passed":
      return "agent_passed";
    case "agent_failed":
      return "agent_failed";
    default:
      return status ?? "";
  }
}

export function materialReviewVerdictLabel(
  report: MaterialReviewReport | undefined,
  slotEntry: MaterialReviewSlotEntry | undefined,
): string {
  if (!report) {
    return "无审阅报告";
  }
  if (report.reviewUnavailable === true || slotEntry?.status === "review_unavailable") {
    return "Agent 审阅不可用（已豁免，可人工审片通过）";
  }
  if (slotEntry?.status === "review_bypass" || report.reviewBypass) {
    if (report.reviewBypass === "no_in_session_marker") {
      return "待人工审片（未跑 Agent 自动审片，预览可播放）";
    }
    if (report.reviewBypass === "partial_harvest") {
      return "待人工审片（部分交付，预览可播放）";
    }
    return `待人工审片（${report.reviewBypass}）`;
  }
  if (slotEntry?.status === "review_exhausted") {
    return "审片额度已用尽，可人工确认后继续";
  }
  if (report.approved) {
    return "通过";
  }
  return "未通过";
}
