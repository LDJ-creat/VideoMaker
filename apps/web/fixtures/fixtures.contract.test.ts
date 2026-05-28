import type {
  GapReport,
  GenerationPlan,
  RenderTimeline,
  TimelineTrackType,
  VideoStructure,
} from "@videomaker/contracts";
import { describe, expect, it } from "vitest";

import {
  fixtureGapReport,
  fixtureGenerationPlan,
  fixtureVideoStructure,
} from "@/fixtures";

const ALL_TRACK_TYPES: TimelineTrackType[] = [
  "video",
  "image",
  "text",
  "voiceover",
  "bgm",
  "effect",
  "transition",
];

function assertVideoStructure(value: VideoStructure) {
  expect(value.slots.length).toBeGreaterThan(0);
  expect(value.narrative.segments.length).toBeGreaterThan(0);
}

function assertGapReport(value: GapReport) {
  expect(value.slotMatches.length + value.missingSlots.length).toBeGreaterThan(
    0,
  );
}

function assertRenderTimeline(value: RenderTimeline) {
  const types = new Set(value.tracks.map((t) => t.type));
  for (const trackType of ALL_TRACK_TYPES) {
    expect(types.has(trackType)).toBe(true);
  }
}

describe("contract fixtures", () => {
  it("video structure fixture satisfies contract shape", () => {
    assertVideoStructure(fixtureVideoStructure);
  });

  it("gap report fixture satisfies contract shape", () => {
    assertGapReport(fixtureGapReport);
  });

  it("generation plan timeline covers all track types", () => {
    assertRenderTimeline(fixtureGenerationPlan.timeline);
  });
});
