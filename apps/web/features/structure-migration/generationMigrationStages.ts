import type { TaskStage } from "@videomaker/contracts";

/** Stages where slot mapping / gap planning / material completion is active. */
export const GENERATION_MIGRATION_STAGES = new Set<TaskStage>([
  "mapping_slots",
  "planning_completion",
  "drafting_master_script",
  "awaiting_master_review",
  "synthesizing_narration_preview",
  "aligning_narration_timing",
  "drafting_storyboard",
  "awaiting_storyboard_review",
  "producing_media",
  "generating_material",
  "generating_image",
  "generating_video",
  "generating_tts",
  "rendering_material",
  "building_timeline",
  "rendering",
]);

export function isGenerationMigrationStage(stage: TaskStage | undefined): boolean {
  if (!stage) return false;
  return GENERATION_MIGRATION_STAGES.has(stage);
}

export type MigrationStageGroup =
  | "pending"
  | "mapping"
  | "planning"
  | "completing"
  | "done";

export function migrationStageGroup(
  stage: TaskStage | undefined,
): MigrationStageGroup {
  if (!stage) return "pending";
  if (stage === "mapping_slots" || stage === "analyzing_assets") return "mapping";
  if (
    stage === "planning_completion" ||
    stage === "drafting_master_script" ||
    stage === "awaiting_master_review" ||
    stage === "synthesizing_narration_preview" ||
    stage === "aligning_narration_timing" ||
    stage === "drafting_storyboard" ||
    stage === "awaiting_storyboard_review" ||
    stage === "producing_media"
  ) {
    return "planning";
  }
  if (
    stage === "generating_material" ||
    stage === "generating_image" ||
    stage === "generating_video" ||
    stage === "generating_tts" ||
    stage === "rendering_material" ||
    stage === "building_timeline" ||
    stage === "rendering"
  ) {
    return "completing";
  }
  if (stage === "completed") return "done";
  return "pending";
}
