import { act, renderHook, waitFor } from "@testing-library/react";
import type { TaskStage } from "@videomaker/contracts";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fixtureTaskEvent } from "@/fixtures";
import * as cache from "@/lib/generationMigrationCache";

import { useGenerationMigrationArtifacts } from "./useGenerationMigrationArtifacts";

const mockArtifacts = {
  slotMatches: [
    {
      slotId: "slot-1",
      matchScore: 0.7,
      matchReason: "semantic fit",
    },
  ],
  gapReport: null,
  completionActions: [],
};

describe("useGenerationMigrationArtifacts", () => {
  beforeEach(() => {
    vi.spyOn(cache, "fetchMigrationSnapshotCached").mockResolvedValue(mockArtifacts);
    vi.spyOn(cache, "peekMigrationSnapshotCache").mockReturnValue(null);
    vi.spyOn(cache, "invalidateMigrationSnapshotCache").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not refetch on every stage change while polling", async () => {
    const { rerender } = renderHook(
      ({ stage }: { stage: TaskStage }) =>
        useGenerationMigrationArtifacts({
          projectId: "project-1",
          generationId: "gen-1",
          event: {
            ...fixtureTaskEvent,
            stage,
            status: "running",
          },
        }),
      {
        initialProps: { stage: "mapping_slots" as TaskStage },
      },
    );

    await waitFor(() =>
      expect(cache.fetchMigrationSnapshotCached).toHaveBeenCalledTimes(1),
    );

    rerender({ stage: "planning_completion" });
    rerender({ stage: "generating_material" });
    rerender({ stage: "generating_image" });
    rerender({ stage: "generating_video" });

    expect(cache.fetchMigrationSnapshotCached).toHaveBeenCalledTimes(1);
  });

  it("does not poll when task failed", async () => {
    renderHook(() =>
      useGenerationMigrationArtifacts({
        projectId: "project-1",
        generationId: "gen-1",
        event: {
          ...fixtureTaskEvent,
          stage: "mapping_slots",
          status: "failed",
        },
      }),
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(cache.fetchMigrationSnapshotCached).not.toHaveBeenCalled();
  });

  it("polls on interval during active migration stage", async () => {
    vi.useFakeTimers();
    renderHook(() =>
      useGenerationMigrationArtifacts({
        projectId: "project-1",
        generationId: "gen-1",
        event: {
          ...fixtureTaskEvent,
          stage: "mapping_slots",
          status: "running",
        },
      }),
    );

    await act(async () => {
      await Promise.resolve();
    });
    expect(cache.fetchMigrationSnapshotCached).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(4000);
    });
    expect(cache.fetchMigrationSnapshotCached).toHaveBeenCalledTimes(2);

    vi.useRealTimers();
  });
});
