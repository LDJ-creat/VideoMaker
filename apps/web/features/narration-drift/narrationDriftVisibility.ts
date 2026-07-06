import type { TaskEvent } from "@videomaker/contracts";

const FIX_SCRIPT_BLOCKED_STAGES = new Set([
  "generating_material",
  "assembling_final",
  "building_timeline",
  "rendering",
  "awaiting_material_review",
]);

export function canShowNarrationDriftPanel(
  taskEvent: TaskEvent | null | undefined,
  options: { storyboardReview: boolean },
): boolean {
  const { storyboardReview } = options;
  const stage = taskEvent?.stage ?? "";
  if (FIX_SCRIPT_BLOCKED_STAGES.has(stage)) {
    return false;
  }
  // 分镜审核暂停点：定稿口播尚未合成，不展示 drift 面板（避免 404 误报）
  if (storyboardReview) {
    return false;
  }
  return (
    stage === "synthesizing_canonical_narration" ||
    stage === "adapting_narration_density"
  );
}
