import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NarrativeTimeline } from "@/features/structure-evidence/NarrativeTimeline";
import { fixtureVideoStructure } from "@/fixtures";

describe("NarrativeTimeline", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders segment buttons and calls onSelectSegment", async () => {
    const user = userEvent.setup();
    const onSelectSegment = vi.fn();
    const segments = fixtureVideoStructure.narrative.segments;

    render(
      <NarrativeTimeline
        segments={segments}
        durationSec={fixtureVideoStructure.metadata.durationSec}
        selectedSegmentId={segments[0]?.id ?? null}
        onSelectSegment={onSelectSegment}
      />,
    );

    expect(screen.getByTestId("narrative-timeline")).toBeInTheDocument();
    const second = segments[1];
    if (!second) return;
    await user.click(screen.getByTestId(`timeline-segment-${second.id}`));
    expect(onSelectSegment).toHaveBeenCalledWith(second.id);
  });
});
