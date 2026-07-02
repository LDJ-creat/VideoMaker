import type { GenerationPlan, TaskEvent } from "@videomaker/contracts";

const SCENE_REVISE_REVIEW_STAGES = new Set([
  "awaiting_material_review",
  "awaiting_storyboard_review",
  "awaiting_master_review",
]);

/** Whether the active generation is far enough along to plan structured per-scene revise. */
export function isGenerationReadyForSceneRevise(
  taskEvent: TaskEvent | undefined,
  plan: GenerationPlan | null | undefined,
): boolean {
  if (!plan?.storyboard?.length) {
    return false;
  }
  if (!taskEvent) {
    return true;
  }
  if (taskEvent.status === "succeeded") {
    return true;
  }
  if (taskEvent.status === "awaiting_review") {
    return SCENE_REVISE_REVIEW_STAGES.has(String(taskEvent.stage ?? ""));
  }
  return false;
}
