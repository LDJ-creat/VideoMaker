import type { ReviseGenerationSummary } from "@/lib/apiClient";

export function indexRevisionsBySource(
  revisions: ReviseGenerationSummary[],
): Map<string, ReviseGenerationSummary[]> {
  const bySource = new Map<string, ReviseGenerationSummary[]>();
  for (const entry of revisions) {
    const sourceId = String(entry.sourceGenerationId ?? "").trim();
    if (!sourceId) continue;
    const bucket = bySource.get(sourceId) ?? [];
    bucket.push(entry);
    bySource.set(sourceId, bucket);
  }
  for (const [sourceId, items] of bySource.entries()) {
    bySource.set(
      sourceId,
      [...items].sort((left, right) => {
        const leftTime = Date.parse(String(left.updatedAt ?? ""));
        const rightTime = Date.parse(String(right.updatedAt ?? ""));
        if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) return 0;
        return rightTime - leftTime;
      }),
    );
  }
  return bySource;
}

export function collectKnownGenerationIds(
  runGenerations: Record<string, Array<{ generationId: string }>>,
): Set<string> {
  const ids = new Set<string>();
  for (const entries of Object.values(runGenerations)) {
    for (const entry of entries) {
      ids.add(entry.generationId);
    }
  }
  return ids;
}

export function listOrphanRevisions(
  revisions: ReviseGenerationSummary[],
  knownGenerationIds: Set<string>,
): ReviseGenerationSummary[] {
  return revisions.filter((entry) => {
    const sourceId = String(entry.sourceGenerationId ?? "").trim();
    return !sourceId || !knownGenerationIds.has(sourceId);
  });
}

export function countDirectReviseForks(
  revisions: ReviseGenerationSummary[],
  sourceGenerationId: string,
): number {
  return revisions.filter(
    (entry) => entry.sourceGenerationId === sourceGenerationId,
  ).length;
}
