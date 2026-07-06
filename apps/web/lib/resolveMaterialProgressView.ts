import type { CompletionAction } from "@videomaker/contracts";

import type { MigrationStageGroup } from "@/features/structure-migration/generationMigrationStages";
import { deriveCompletedSlotIds } from "@/lib/deriveCompletedSlotIds";
import {
  mergeCompletedMaterialSlotIds,
  reconcileMaterialSlotProgress,
  seedRegeneratingMaterialSlots,
  type ParallelMaterialActivity,
} from "@/lib/parallelMaterialActivity";

export function resolveMaterialProgressView(input: {
  materialActivity: ParallelMaterialActivity;
  regeneratingSlotIds?: string[];
  completionActions: CompletionAction[];
  completedActionIds?: string[];
  diskCompletedSlotIds?: string[];
  progressGroup: MigrationStageGroup;
}): {
  resolvedActivity: ParallelMaterialActivity;
  completedSlotIds: Set<string>;
  activeSlotIds: Set<string>;
} {
  const seeded = seedRegeneratingMaterialSlots(
    input.materialActivity,
    input.regeneratingSlotIds,
  );
  const completedFromActions = deriveCompletedSlotIds(
    input.completionActions,
    input.completedActionIds,
  );
  const completedSlotIds = mergeCompletedMaterialSlotIds(
    seeded,
    completedFromActions,
    input.diskCompletedSlotIds,
    { includeDisk: input.progressGroup === "completing" || input.progressGroup === "done" },
  );
  const resolvedActivity = reconcileMaterialSlotProgress(seeded, completedSlotIds);
  return {
    resolvedActivity,
    completedSlotIds,
    activeSlotIds: new Set(resolvedActivity.activeSlots.keys()),
  };
}
