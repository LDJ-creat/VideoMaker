import { describe, expect, it } from "vitest";

import { computeSegmentFlexLayout } from "@/features/structure-evidence/narrativeTimelineLayout";
import type { NarrativeSegment } from "@videomaker/contracts";

function segment(
  id: string,
  role: NarrativeSegment["role"],
  startSec: number,
  endSec: number,
): NarrativeSegment {
  return {
    id,
    role,
    startSec,
    endSec,
    scriptSummary: "",
    visualSummary: "",
    intent: id,
  };
}

describe("computeSegmentFlexLayout", () => {
  it("gives short transition segments more relative width than pure duration ratio", () => {
    const segments = [
      segment("a", "hook", 0, 7),
      segment("b", "transition", 7, 9),
      segment("c", "benefit", 9, 80),
    ];
    const layout = computeSegmentFlexLayout(segments, 80);
    const transition = layout.find((item) => item.segment.id === "b")!;
    const benefit = layout.find((item) => item.segment.id === "c")!;

    const pureTransition = 2 / 80;
    const pureBenefit = 71 / 80;
    expect(transition.flexGrow).toBeGreaterThan(pureTransition);
    expect(benefit.flexGrow).toBeLessThan(pureBenefit);
  });

  it("returns one entry per segment with normalized flex weights", () => {
    const segments = [
      segment("a", "hook", 0, 10),
      segment("b", "cta", 10, 20),
    ];
    const layout = computeSegmentFlexLayout(segments, 20);
    expect(layout).toHaveLength(2);
    const sum = layout.reduce((acc, item) => acc + item.flexGrow, 0);
    expect(sum).toBeCloseTo(1, 5);
  });
});
