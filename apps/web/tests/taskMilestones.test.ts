import { describe, expect, it } from "vitest";

import type { TaskStatus } from "@videomaker/contracts";

import { fixtureTaskEvent } from "@/fixtures";
import {
  applyTaskStatusOverride,
  isEffectiveReviewMilestone,
  isReviewMilestone,
  isTaskMilestone,
  resolveLiveTaskStatus,
} from "@/lib/taskMilestones";

describe("taskMilestones", () => {
  it("does not treat the first snapshot as a milestone by default", () => {
    const next = {
      ...fixtureTaskEvent,
      status: "awaiting_review" as TaskStatus,
      stage: "awaiting_master_review",
    };
    expect(isTaskMilestone(null, next)).toBe(false);
    expect(isTaskMilestone(null, next, { allowInitial: true })).toBe(true);
  });

  it("detects status and stage changes as milestones", () => {
    const previous = { ...fixtureTaskEvent, status: "running" as TaskStatus, stage: "a" };
    const next = {
      ...fixtureTaskEvent,
      status: "awaiting_review" as TaskStatus,
      stage: "b",
    };
    expect(isTaskMilestone(previous, next)).toBe(true);
    expect(isTaskMilestone(next, next)).toBe(false);
  });

  it("detects review milestones", () => {
    expect(
      isReviewMilestone({
        ...fixtureTaskEvent,
        status: "awaiting_review",
        stage: "awaiting_master_review",
      }),
    ).toBe(true);
    expect(
      isReviewMilestone({
        ...fixtureTaskEvent,
        status: "running",
        stage: "awaiting_storyboard_review",
      }),
    ).toBe(false);
  });

  it("respects optimistic overrides for review milestones", () => {
    const event = {
      ...fixtureTaskEvent,
      status: "awaiting_review" as TaskStatus,
      stage: "awaiting_master_review",
    };
    expect(isEffectiveReviewMilestone(event, "retrying")).toBe(false);
    expect(
      applyTaskStatusOverride(event, "retrying").status,
    ).toBe("retrying");
  });

  it("does not let stale queued override mask awaiting_review", () => {
    const event = {
      ...fixtureTaskEvent,
      status: "awaiting_review" as TaskStatus,
      stage: "awaiting_master_review",
    };
    expect(resolveLiveTaskStatus(event, "queued")).toBe("awaiting_review");
    expect(isEffectiveReviewMilestone(event, "queued")).toBe(true);
  });
});
