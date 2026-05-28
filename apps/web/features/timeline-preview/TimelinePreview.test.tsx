import { render, screen } from "@testing-library/react";
import type { TimelineTrackType } from "@videomaker/contracts";
import { describe, expect, it } from "vitest";

import { TimelinePreview } from "@/features/timeline-preview/TimelinePreview";
import { fixtureGenerationPlan } from "@/fixtures";

const ALL_TRACK_TYPES: TimelineTrackType[] = [
  "video",
  "image",
  "text",
  "voiceover",
  "bgm",
  "effect",
  "transition",
];

describe("TimelinePreview", () => {
  it("renders all TimelineTrackType values without crashing", () => {
    const timeline = fixtureGenerationPlan.timeline;
    const types = new Set(timeline.tracks.map((t) => t.type));
    for (const trackType of ALL_TRACK_TYPES) {
      expect(types.has(trackType)).toBe(true);
    }

    render(<TimelinePreview timeline={timeline} />);

    for (const trackType of ALL_TRACK_TYPES) {
      expect(screen.getByText(trackType)).toBeInTheDocument();
    }
  });
});
