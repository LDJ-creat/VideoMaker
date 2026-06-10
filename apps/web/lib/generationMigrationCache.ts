import {
  fetchGenerationMigrationArtifacts,
  type GenerationMigrationArtifacts,
} from "@/features/structure-migration/fetchGenerationMigrationArtifacts";
import { artifactsSnapshotKey } from "@/features/structure-migration/artifactsSnapshotKey";
import { recordDevProgressMetric } from "@/lib/devProgressMetrics";

const DEFAULT_TTL_MS = 4000;

type CacheEntry = {
  artifacts: GenerationMigrationArtifacts;
  snapshotKey: string;
  fetchedAt: number;
};

const cache = new Map<string, CacheEntry>();
const inFlight = new Map<string, Promise<GenerationMigrationArtifacts>>();

function cacheKey(projectId: string, generationId: string): string {
  return `${projectId}:${generationId}`;
}

export function invalidateMigrationSnapshotCache(generationId: string): void {
  for (const key of cache.keys()) {
    if (key.endsWith(`:${generationId}`)) {
      cache.delete(key);
    }
  }
  for (const key of inFlight.keys()) {
    if (key.endsWith(`:${generationId}`)) {
      inFlight.delete(key);
    }
  }
}

export async function fetchMigrationSnapshotCached(
  projectId: string,
  generationId: string,
  options?: { ttlMs?: number; force?: boolean },
): Promise<GenerationMigrationArtifacts> {
  const key = cacheKey(projectId, generationId);
  const ttlMs = options?.ttlMs ?? DEFAULT_TTL_MS;
  const now = Date.now();

  if (!options?.force) {
    const cached = cache.get(key);
    if (cached && now - cached.fetchedAt < ttlMs) {
      return cached.artifacts;
    }
  }

  const pending = inFlight.get(key);
  if (pending) {
    return pending;
  }

  const request = (async () => {
    recordDevProgressMetric("artifactFetch");
    const artifacts = await fetchGenerationMigrationArtifacts(projectId, generationId);
    cache.set(key, {
      artifacts,
      snapshotKey: artifactsSnapshotKey(artifacts),
      fetchedAt: Date.now(),
    });
    return artifacts;
  })();

  inFlight.set(key, request);
  try {
    return await request;
  } finally {
    inFlight.delete(key);
  }
}

export function peekMigrationSnapshotCache(
  projectId: string,
  generationId: string,
): GenerationMigrationArtifacts | null {
  return cache.get(cacheKey(projectId, generationId))?.artifacts ?? null;
}
