import { describe, expect, it } from "vitest";

import {
  formatDurationSec,
  generationStrategyHint,
  generationStrategyLabel,
} from "@/lib/durationTargetLabels";

describe("durationTargetLabels", () => {
  it("formats seconds and minutes", () => {
    expect(formatDurationSec(45)).toBe("45 秒");
    expect(formatDurationSec(90)).toBe("1 分 30 秒");
  });

  it("labels generation strategies", () => {
    expect(generationStrategyLabel("short_form_direct")).toContain("短视频");
    expect(generationStrategyLabel("long_form_composed")).toContain("长视频");
  });

  it("hints short vs long form by threshold", () => {
    expect(generationStrategyHint(45, 60)).toContain("单次视频生成");
    expect(generationStrategyHint(90, 60)).toContain("分镜");
  });
});
