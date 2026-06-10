import type { GenerationMigrationArtifacts } from "@/features/structure-migration/fetchGenerationMigrationArtifacts";

/** Stable fingerprint for deduping artifact poll results. */
export function artifactsSnapshotKey(
  artifacts: GenerationMigrationArtifacts,
): string {
  return JSON.stringify({
    slotMatches: artifacts.slotMatches,
    gapReport: artifacts.gapReport,
    completionActions: artifacts.completionActions,
    materialState: artifacts.materialState,
  });
}
