import { describe, expect, it } from "vitest";

import {
  formatGenerationRunDateTime,
  formatGenerationRunMetaLine,
  formatGenerationRunTitle,
  formatShortRunId,
  summarizeRunVariants,
} from "@/lib/formatGenerationRunDisplay";

describe("formatGenerationRunDisplay", () => {
  it("formats api timestamps for display", () => {
    expect(formatGenerationRunDateTime("2026-06-07T11:52:06.877595Z")).toMatch(
      /2026年6月7日/,
    );
  });

  it("builds readable batch titles", () => {
    expect(
      formatGenerationRunTitle("2026-06-07T11:52:06.877595Z", 0, 2),
    ).toMatch(/最近生成（批次 2）· 2026年6月7日/);
    expect(
      formatGenerationRunTitle("2026-06-06T08:00:00.000Z", 1, 2),
    ).toMatch(/批次 1 · 2026年6月6日/);
  });

  it("summarizes variant outcomes in one line", () => {
    expect(
      summarizeRunVariants([
        { variant: "high_click", status: "failed" },
        { variant: "high_conversion", status: "succeeded" },
      ]),
    ).toBe("高点击版失败、高转化版成功");
  });

  it("builds meta line with relative time and run status", () => {
    const meta = formatGenerationRunMetaLine(
      "2026-06-07T11:52:06.877595Z",
      "partial_failed",
      [
        { variant: "high_click", status: "failed" },
        { variant: "high_conversion", status: "succeeded" },
      ],
    );
    expect(meta).toContain("部分失败");
    expect(meta).toContain("高点击版失败");
    expect(meta).toContain("高转化版成功");
  });

  it("shortens run ids for secondary display", () => {
    expect(formatShortRunId("8832eabe-6ee1-48a6-b956-3b62d9d80f8c")).toBe(
      "…d9d80f8c",
    );
  });
});
