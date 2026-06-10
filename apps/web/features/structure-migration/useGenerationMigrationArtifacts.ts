"use client";

import { useEffect, useRef, useState } from "react";

import type { TaskEvent } from "@videomaker/contracts";

import { artifactsSnapshotKey } from "@/features/structure-migration/artifactsSnapshotKey";
import type { GenerationMigrationArtifacts } from "@/features/structure-migration/fetchGenerationMigrationArtifacts";
import {
  isGenerationMigrationStage,
  migrationStageGroup,
} from "@/features/structure-migration/generationMigrationStages";
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
  progressGroup: ReturnType<typeof migrationStageGroup>;
  syncing: boolean;
  /** @deprecated Prefer syncing (non-layout indicator). */
  loading: boolean;
} {
  const cached =
    generationId && projectId
      ? peekMigrationSnapshotCache(projectId, generationId)
      : null;
  const [artifacts, setArtifacts] = useState<GenerationMigrationArtifacts | null>(
    cached,
  );
  const [syncing, setSyncing] = useState(false);
  const snapshotKeyRef = useRef<string | null>(
    cached ? artifactsSnapshotKey(cached) : null,
  );
  const hadInitialCacheRef = useRef(Boolean(cached));

  const progressGroup = migrationStageGroup(event?.stage);
  const shouldPoll =
    enabled &&
    Boolean(generationId) &&
    Boolean(event) &&
    event?.status !== "failed" &&
    event?.status !== "cancelled" &&
    isGenerationMigrationStage(event?.stage);

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
      const showSync = !hadInitialCacheRef.current;
      if (showSync) {
        setSyncing(true);
      }
      try {
        const next = await fetchMigrationSnapshotCached(projectId, generationId, {
          ttlMs: MIGRATION_ARTIFACT_POLL_INTERVAL_MS,
          force: options?.force,
        });
        if (cancelled) return;
        hadInitialCacheRef.current = true;
        const nextKey = artifactsSnapshotKey(next);
        if (nextKey !== snapshotKeyRef.current) {
          snapshotKeyRef.current = nextKey;
          setArtifacts(next);
        }
      } finally {
        if (!cancelled && showSync) {
          setSyncing(false);
        }
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
    syncing,
    loading: syncing && artifacts === null,
  };
}

export type MigrationProgressContext = {
  projectId: string;
  generationId: string;
  structure: import("@videomaker/contracts").VideoStructure | null;
  variantLabel?: string;
};
