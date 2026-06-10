import type { UserBrief } from "@videomaker/contracts";

export type SampleReadinessSummary = {
  hasStructure: boolean;
  sourceKind: string;
  status?: string;
};

/** Aligns with API `_brief_text` plus common brief fields users fill before save. */
export function hasMeaningfulBrief(brief: UserBrief | null | undefined): boolean {
  if (!brief) {
    return false;
  }
  const parts = [
    brief.topic,
    brief.subjectName,
    brief.productName,
    brief.creativeGoal,
    brief.targetAudience,
    brief.tone,
    brief.supplementalNotes,
    ...(brief.sellingPoints ?? []),
    ...(brief.keyPoints ?? []),
    ...(brief.mustMention ?? []),
  ];
  return parts.some((part) => typeof part === "string" && part.trim().length > 0);
}

export function hasAnalyzedRealSample(
  samples: SampleReadinessSummary[],
): boolean {
  return samples.some(
    (sample) =>
      sample.hasStructure &&
      sample.sourceKind !== "knowledge" &&
      (sample.status === undefined || sample.status === "analyzed"),
  );
}

/** Brief is enough to score recommendations; sample structure only boosts match. */
export function isKnowledgeRecommendationReady(input: {
  hasMeaningfulBrief: boolean;
  hasPersistedSelection: boolean;
}): boolean {
  return input.hasPersistedSelection || input.hasMeaningfulBrief;
}

/** Generation without user sample analysis uses knowledge library structure. */
export function canStartKnowledgeOnlyGeneration(input: {
  hasMeaningfulBrief: boolean;
  hasAnalyzedRealSample: boolean;
}): boolean {
  return input.hasMeaningfulBrief && !input.hasAnalyzedRealSample;
}

export function canStartGeneration(input: {
  hasMeaningfulBrief: boolean;
  hasAnalyzedRealSample: boolean;
}): boolean {
  return input.hasAnalyzedRealSample || input.hasMeaningfulBrief;
}
