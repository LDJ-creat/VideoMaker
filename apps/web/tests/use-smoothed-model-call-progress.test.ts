import { describe, expect, it } from "vitest";

import { fixtureTaskEvent } from "@/fixtures";
import {
  MODEL_CALL_SMOOTH_CAP,
  nextSmoothedModelCallProgress,
  shouldSmoothModelCallProgress,
} from "@/lib/useSmoothedModelCallProgress";

describe("useSmoothedModelCallProgress helpers", () => {
  it("detects direct multimodal model-call smoothing window", () => {
    expect(
      shouldSmoothModelCallProgress({
        ...fixtureTaskEvent,
        status: "running",
        stage: "extracting_structure_direct",
        progress: 58,
      }),
    ).toBe(true);
    expect(
      shouldSmoothModelCallProgress({
        ...fixtureTaskEvent,
        status: "running",
        stage: "extracting_structure_direct",
        progress: 72,
      }),
    ).toBe(false);
  });

  it("eases toward cap without exceeding real milestones", () => {
    expect(nextSmoothedModelCallProgress(55, 55)).toBeCloseTo(55.08, 5);
    expect(nextSmoothedModelCallProgress(60, 58)).toBeCloseTo(60.08, 5);
    expect(nextSmoothedModelCallProgress(70.95, 58)).toBe(MODEL_CALL_SMOOTH_CAP);
    expect(nextSmoothedModelCallProgress(71, 58)).toBe(MODEL_CALL_SMOOTH_CAP);
  });
});
