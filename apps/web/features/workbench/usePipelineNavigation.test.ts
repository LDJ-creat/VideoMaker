import { describe, expect, it } from "vitest";

import { fixtureTaskEvent } from "@/fixtures";
import {
  anyGenerationAwaitingReviewFromEvents,
  buildGenerationSettlementKey,
  computeAnalysisCompletionIntent,
  computeGenerationMilestoneIntent,
  computeGenerationSettlementIntent,
} from "@/features/workbench/usePipelineNavigation";

describe("usePipelineNavigation", () => {
  it("routes generation awaiting_review to script review", () => {
    const intent = computeGenerationMilestoneIntent(
      {
        ...fixtureTaskEvent,
        status: "awaiting_review",
        stage: "awaiting_master_review",
      },
      {
        lastAction: "generation",
        panel: "progress",
        autoNavEnabled: true,
      },
    );
    expect(intent).toEqual({
      type: "go_script_review",
      reason: "milestone:awaiting-review",
    });
  });

  it("routes resumed generation back to progress from script review", () => {
    const intent = computeGenerationMilestoneIntent(
      {
        ...fixtureTaskEvent,
        status: "retrying",
        stage: "awaiting_master_review",
      },
      {
        lastAction: "generation",
        panel: "script-review",
        autoNavEnabled: true,
      },
    );
    expect(intent).toEqual({
      type: "go_progress",
      reason: "milestone:resumed-after-review",
    });
  });

  it("ignores stale awaiting_review when override is retrying", () => {
    const events = {
      t1: {
        ...fixtureTaskEvent,
        taskId: "t1",
        status: "awaiting_review" as const,
        stage: "awaiting_master_review",
      },
    };
    expect(
      anyGenerationAwaitingReviewFromEvents(events, ["t1"], {
        t1: "retrying",
      }),
    ).toBe(false);
  });

  it("routes analysis success to analysis panel", () => {
    const intent = computeAnalysisCompletionIntent({
      lastAction: "analysis",
      panel: "progress",
      autoNavEnabled: true,
      sampleId: "sample-1",
      isBatchAnalysis: false,
      eventStatus: "succeeded",
    });
    expect(intent).toEqual({
      type: "go_analysis",
      sampleId: "sample-1",
      reason: "analysis-terminal:succeeded",
    });
  });

  it("includes updatedAt in settlement key", () => {
    const keyA = buildGenerationSettlementKey({
      t1: {
        ...fixtureTaskEvent,
        taskId: "t1",
        status: "succeeded",
        updatedAt: "2026-06-10T12:00:00.000Z",
      },
    });
    const keyB = buildGenerationSettlementKey({
      t1: {
        ...fixtureTaskEvent,
        taskId: "t1",
        status: "succeeded",
        updatedAt: "2026-06-10T12:00:05.000Z",
      },
    });
    expect(keyA).not.toEqual(keyB);
  });

  it("navigates to result when all tasks succeeded despite stale running hydrate", () => {
    const intent = computeGenerationSettlementIntent({
      lastAction: "generation",
      panel: "progress",
      autoNavEnabled: true,
      displayGenerationEvents: {},
      activeGenerationTaskIds: ["t1"],
      allGenerationTasksSucceeded: true,
      anyGenerationTaskFailed: false,
      anyGenerationAwaitingReview: false,
      singleTaskEvent: null,
      sampleId: null,
      isBatchAnalysis: false,
      reloadSucceeded: true,
      hydrateAwaitingReview: false,
      hydrateRunning: true,
      hydrateAllSucceeded: false,
    });
    expect(intent).toEqual({
      type: "go_result",
      reason: "generation-settlement:reloaded",
      reloadFailed: false,
    });
  });

  it("navigates to result when reload fails but all tasks succeeded", () => {
    const intent = computeGenerationSettlementIntent({
      lastAction: "generation",
      panel: "progress",
      autoNavEnabled: true,
      displayGenerationEvents: {},
      activeGenerationTaskIds: ["t1"],
      allGenerationTasksSucceeded: true,
      anyGenerationTaskFailed: false,
      anyGenerationAwaitingReview: false,
      singleTaskEvent: null,
      sampleId: null,
      isBatchAnalysis: false,
      reloadSucceeded: false,
      hydrateAwaitingReview: false,
      hydrateRunning: false,
      hydrateAllSucceeded: false,
    });
    expect(intent).toEqual({
      type: "go_result",
      reason: "generation-settlement:reload-pending",
      reloadFailed: true,
    });
  });
});
