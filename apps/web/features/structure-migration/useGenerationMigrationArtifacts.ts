"use client";

import { useEffect, useRef, useState } from "react";

import type { TaskEvent } from "@videomaker/contracts";

import { artifactsSnapshotKey } from "@/features/structure-migration/artifactsSnapshotKey";
import type { GenerationMigrationArtifacts } from "@/features/structure-migration/fetchGenerationMigrationArtifacts";
import {
  resolveEffectiveMigrationGroup,
  shouldPollMigrationArtifacts,
} from "@/features/structure-migration/resolveEffectiveMigrationGroup";
import {
  fetchMigrationSnapshotCached,
  invalidateMigrationSnapshotCache,
  peekMigrationSnapshotCache,
} from "@/lib/generationMigrationCache";

export const MIGRATION_ARTIFACT_POLL_INTERVAL_MS = 4000;

type UseGenerationMigrationArtifactsOptions = {
  projectId: string;
  generationId: string | null | undefined;
  event: TaskEvent | null;
  enabled?: boolean;
};

export function useGenerationMigrationArtifacts({
  projectId,
  generationId,
  event,
  enabled = true,
}: UseGenerationMigrationArtifactsOptions): {
  artifacts: GenerationMigrationArtifacts | null;
  progressGroup: ReturnType<typeof resolveEffectiveMigrationGroup>;
} {
  const cached =
    generationId && projectId
      ? peekMigrationSnapshotCache(projectId, generationId)
      : null;
  const [artifacts, setArtifacts] = useState<GenerationMigrationArtifacts | null>(
    cached,
  );
  const snapshotKeyRef = useRef<string | null>(
    cached ? artifactsSnapshotKey(cached) : null,
  );

  const progressGroup = resolveEffectiveMigrationGroup(
    event?.stage,
    event?.message,
    artifacts,
  );
  const shouldPoll = shouldPollMigrationArtifacts({
    enabled,
    generationId,
    event,
    artifacts,
  });

  useEffect(() => {
    if (event?.status === "failed" || event?.status === "cancelled") {
      if (generationId) {
        invalidateMigrationSnapshotCache(generationId);
      }
    }
  }, [event?.status, generationId]);

  useEffect(() => {
    if (!shouldPoll || !generationId) {
      return;
    }

    let cancelled = false;

    const refresh = async (options?: { force?: boolean }) => {
      const next = await fetchMigrationSnapshotCached(projectId, generationId, {
        ttlMs: MIGRATION_ARTIFACT_POLL_INTERVAL_MS,
        force: options?.force,
      });
      if (cancelled) return;
      const nextKey = artifactsSnapshotKey(next);
      if (nextKey !== snapshotKeyRef.current) {
        snapshotKeyRef.current = nextKey;
        setArtifacts(next);
      }
    };

    void refresh({ force: true });
    const timer = window.setInterval(() => {
      void refresh();
    }, MIGRATION_ARTIFACT_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [generationId, projectId, shouldPoll]);

  return {
    artifacts,
    progressGroup,
  };
}

export type MigrationProgressContext = {
  projectId: string;
  generationId: string;
  structure: import("@videomaker/contracts").VideoStructure | null;
  variantLabel?: string;
};
