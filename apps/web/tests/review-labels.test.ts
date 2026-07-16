import { describe, expect, it } from "vitest";

import {
  materialReviewVerdictLabel,
  slotStatusDisplay,
} from "@/features/material-review/reviewLabels";

describe("reviewLabels", () => {
  it("maps review_bypass status for UI", () => {
    expect(slotStatusDisplay("review_bypass")).toBe("待人工审片");
    expect(
      materialReviewVerdictLabel(
        {
          approved: false,
          reviewBypass: "no_in_session_marker",
          reviewInputs: { mode: "skipped" },
        },
        { status: "review_bypass", reviewBypass: "no_in_session_marker" },
      ),
    ).toContain("待人工审片");
  });
});
