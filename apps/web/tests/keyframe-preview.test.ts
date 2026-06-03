import { describe, expect, it } from "vitest";

import {
  isDuplicateText,
  pickSegmentKeyframe,
  resolveSegmentKeyframePreview,
} from "@/lib/keyframePreview";

describe("keyframePreview", () => {
  it("detects duplicate primary/secondary text", () => {
    expect(
      isDuplicateText("same line", "  same   line "),
    ).toBe(true);
    expect(isDuplicateText("visual", "script")).toBe(false);
  });

  it("picks keyframe within segment time range", () => {
    const keyframes = [
      {
        timeSec: 1.0,
        score: 0.5,
        relativePath: "keyframes/a.jpg",
        previewUrl: "/a.jpg",
      },
      {
        timeSec: 6.0,
        score: 0.9,
        relativePath: "keyframes/b.jpg",
        previewUrl: "/b.jpg",
      },
    ];
    const picked = pickSegmentKeyframe(keyframes, 5, 25);
    expect(picked?.relativePath).toBe("keyframes/b.jpg");
  });

  it("builds preview url from evidence summary", () => {
    const url = resolveSegmentKeyframePreview(
      "proj-1",
      "sample-1",
      [],
      { startSec: 0, endSec: 5 },
      "keyframes/shot-1.jpg",
    );
    expect(url).toBe(
      "/api/projects/proj-1/media/file/samples/sample-1/analysis/keyframes/shot-1.jpg",
    );
  });
});
