import type { CompletionAction, GapReport, SlotMatch } from "@videomaker/contracts";

import { getGenerationMigrationSnapshot } from "@/lib/apiClient";
import { projectFileMediaUrl } from "@/lib/artifactUrl";

export type GenerationMigrationMaterialState = {
  completedActionIds: string[];
};

export type GenerationMigrationArtifacts = {
  slotMatches: SlotMatch[];
  gapReport: GapReport | null;
  completionActions: CompletionAction[];
  materialState: GenerationMigrationMaterialState | null;
};

async function fetchJsonFile<T>(url: string): Promise<T | null> {
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

async function fetchGenerationMigrationArtifactsFromFiles(
  projectId: string,
  generationId: string,
): Promise<GenerationMigrationArtifacts> {
  const slotMatchesUrl = projectFileMediaUrl(
    projectId,
    `generations/${generationId}/slot-matches.json`,
  );
  const gapReportUrl = projectFileMediaUrl(
    projectId,
    `generations/${generationId}/gap-report.json`,
  );
  const planUrl = projectFileMediaUrl(
    projectId,
    `generations/${generationId}/generation-plan.json`,
  );

  const materialStateUrl = projectFileMediaUrl(
    projectId,
    `generations/${generationId}/material-state.json`,
  );

  const [slotPayload, gapReport, plan, materialState] = await Promise.all([
    fetchJsonFile<{ slotMatches?: SlotMatch[] }>(slotMatchesUrl),
    fetchJsonFile<GapReport>(gapReportUrl),
    fetchJsonFile<{ completionActions?: CompletionAction[] }>(planUrl),
    fetchJsonFile<{ completedActionIds?: string[] }>(materialStateUrl),
  ]);

  return {
    slotMatches: slotPayload?.slotMatches ?? [],
    gapReport,
    completionActions: plan?.completionActions ?? [],
    materialState: materialState?.completedActionIds
      ? { completedActionIds: materialState.completedActionIds }
      : null,
  };
}

export async function fetchGenerationMigrationArtifacts(
  projectId: string,
  generationId: string,
): Promise<GenerationMigrationArtifacts> {
  try {
    const { data } = await getGenerationMigrationSnapshot(generationId);
    return {
      slotMatches: data.slotMatches ?? [],
      gapReport: data.gapReport ?? null,
      completionActions: data.completionActions ?? [],
      materialState: data.materialState ?? null,
    };
  } catch {
    return fetchGenerationMigrationArtifactsFromFiles(projectId, generationId);
  }
}
