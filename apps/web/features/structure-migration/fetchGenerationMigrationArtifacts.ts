import type { CompletionAction, GapReport, SlotMatch } from "@videomaker/contracts";

import { projectFileMediaUrl } from "@/lib/artifactUrl";

export type GenerationMigrationArtifacts = {
  slotMatches: SlotMatch[];
  gapReport: GapReport | null;
  completionActions: CompletionAction[];
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

export async function fetchGenerationMigrationArtifacts(
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

  const [slotPayload, gapReport, plan] = await Promise.all([
    fetchJsonFile<{ slotMatches?: SlotMatch[] }>(slotMatchesUrl),
    fetchJsonFile<GapReport>(gapReportUrl),
    fetchJsonFile<{ completionActions?: CompletionAction[] }>(planUrl),
  ]);

  return {
    slotMatches: slotPayload?.slotMatches ?? [],
    gapReport,
    completionActions: plan?.completionActions ?? [],
  };
}
