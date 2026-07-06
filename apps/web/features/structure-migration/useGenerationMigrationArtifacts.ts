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
  /** Bump after cancel/retry to drop stale migration snapshot state. */
  resetKey?: number;
  regeneratingSlotIds?: string[];
};

type ArtifactSnapshot = {
  resetKey: number;
  artifacts: GenerationMigrationArtifacts | null;
};

export function useGenerationMigrationArtifacts({
  projectId,
  generationId,
  event,
  enabled = true,
  resetKey = 0,
  regeneratingSlotIds,
}: UseGenerationMigrationArtifactsOptions): {
  artifacts: GenerationMigrationArtifacts | null;
  progressGroup: ReturnType<typeof resolveEffectiveMigrationGroup>;
} {
  const cached =
    generationId && projectId
      ? peekMigrationSnapshotCache(projectId, generationId)
      : null;
  const [snapshot, setSnapshot] = useState<ArtifactSnapshot>(() => ({
    resetKey,
    artifacts: cached,
  }));
  const snapshotKeyRef = useRef<string | null>(
    cached ? artifactsSnapshotKey(cached) : null,
  );

  const effectiveArtifacts =
    snapshot.resetKey === resetKey ? snapshot.artifacts : null;

  const progressGroup = resolveEffectiveMigrationGroup(
    event?.stage,
    event?.message,
    effectiveArtifacts,
    {
      taskStatus: event?.status,
      regeneratingSlotIds,
    },
  );
  const shouldPoll = shouldPollMigrationArtifacts({
    enabled,
    generationId,
    event,
    artifacts: effectiveArtifacts,
  });

  useEffect(() => {
    if (snapshot.resetKey === resetKey) {
      return;
    }
    snapshotKeyRef.current = null;
    setSnapshot({ resetKey, artifacts: null });
    if (generationId) {
      invalidateMigrationSnapshotCache(generationId);
    }
  }, [generationId, resetKey, snapshot.resetKey]);

  useEffect(() => {
    if (event?.status === "failed" || event?.status === "cancelled") {
      snapshotKeyRef.current = null;
      setSnapshot((previous) =>
        previous.resetKey === resetKey
          ? { resetKey, artifacts: null }
          : previous,
      );
      if (generationId) {
        invalidateMigrationSnapshotCache(generationId);
      }
    }
  }, [event?.status, generationId, resetKey]);

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
        setSnapshot({ resetKey, artifacts: next });
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
  }, [generationId, projectId, resetKey, shouldPoll]);

  return {
    artifacts: effectiveArtifacts,
    progressGroup,
  };
}

export type MigrationProgressContext = {
  projectId: string;
  generationId: string;
  structure: import("@videomaker/contracts").VideoStructure | null;
  variantLabel?: string;
};
