"use client";

import { useEffect, useState } from "react";

import type { TaskEvent, VideoStructure } from "@videomaker/contracts";

import {
  fetchGenerationMigrationArtifacts,
  type GenerationMigrationArtifacts,
} from "@/features/structure-migration/fetchGenerationMigrationArtifacts";
import {
  isGenerationMigrationStage,
  migrationStageGroup,
} from "@/features/structure-migration/generationMigrationStages";

const POLL_INTERVAL_MS = 2000;

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
  loading: boolean;
} {
  const [artifacts, setArtifacts] = useState<GenerationMigrationArtifacts | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const progressGroup = migrationStageGroup(event?.stage);
  const shouldPoll =
    enabled &&
    Boolean(generationId) &&
    Boolean(event) &&
    event?.status !== "failed" &&
    event?.status !== "cancelled" &&
    isGenerationMigrationStage(event?.stage);

  useEffect(() => {
    if (!shouldPoll || !generationId) {
      return;
    }

    let cancelled = false;

    const refresh = async () => {
      setLoading(true);
      try {
        const next = await fetchGenerationMigrationArtifacts(projectId, generationId);
        if (!cancelled) {
          setArtifacts(next);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void refresh();
    const timer = window.setInterval(() => {
      void refresh();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [generationId, projectId, shouldPoll, event?.stage, event?.status]);

  return { artifacts, progressGroup, loading };
}

export type MigrationProgressContext = {
  projectId: string;
  generationId: string;
  structure: VideoStructure | null;
  variantLabel?: string;
};
