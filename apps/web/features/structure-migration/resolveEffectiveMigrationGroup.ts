import type { TaskStage } from "@videomaker/contracts";

import type { GenerationMigrationArtifacts } from "@/features/structure-migration/fetchGenerationMigrationArtifacts";
import {
  isGenerationMigrationStage,
  migrationStageGroup,
  type MigrationStageGroup,
} from "@/features/structure-migration/generationMigrationStages";
import { parseTaskMaterialProgress } from "@/lib/parseTaskMaterialProgress";

export function resolveEffectiveMigrationGroup(
  stage: TaskStage | undefined,
  message: string | undefined,
  artifacts: GenerationMigrationArtifacts | null | undefined,
): MigrationStageGroup {
  const fromStage = migrationStageGroup(stage);
  if (fromStage !== "pending") {
    return fromStage;
  }

  const materialHint = parseTaskMaterialProgress(message);
  if (materialHint.actionLabel) {
    return "completing";
  }

  if ((artifacts?.completionActions?.length ?? 0) > 0) {
    return "completing";
  }
  if (artifacts?.gapReport) {
    return "planning";
  }
  if ((artifacts?.slotMatches?.length ?? 0) > 0) {
    return "mapping";
  }

  return "pending";
}

export function shouldPollMigrationArtifacts(input: {
  enabled: boolean;
  generationId: string | null | undefined;
  event: { stage?: TaskStage; status?: string; message?: string } | null;
  artifacts: GenerationMigrationArtifacts | null;
}): boolean {
  const { enabled, generationId, event, artifacts } = input;
  if (!enabled || !generationId || !event) return false;
  if (
    event.status === "failed" ||
    event.status === "cancelled" ||
    event.status === "succeeded"
  ) {
    return false;
  }

  if (event.stage && isGenerationMigrationStage(event.stage)) {
    return true;
  }

  if (parseTaskMaterialProgress(event.message).actionLabel) {
    return true;
  }

  return hasMigrationArtifactData(artifacts);
}

function hasMigrationArtifactData(
  artifacts: GenerationMigrationArtifacts | null,
): boolean {
  if (!artifacts) return false;
  return (
    Boolean(artifacts.gapReport) ||
    artifacts.slotMatches.length > 0 ||
    artifacts.completionActions.length > 0 ||
    (artifacts.materialState?.completedActionIds.length ?? 0) > 0
  );
}
