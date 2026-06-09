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

  it("labels generation strategies with unified copy", () => {
    expect(generationStrategyLabel("short_form_direct")).toBe("分镜合成模式");
    expect(generationStrategyLabel("long_form_composed")).toBe("分镜合成模式");
  });

  it("uses unified strategy hint regardless of duration", () => {
    expect(generationStrategyHint(45)).toContain("分镜");
    expect(generationStrategyHint(90)).toContain("分镜");
  });
});
