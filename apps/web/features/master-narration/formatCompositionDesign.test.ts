import { describe, expect, it } from "vitest";

import {
  compositionModeLabel,
  formatCompositionBriefMeta,
  hasCompositionDesignContent,
} from "@/features/master-narration/formatCompositionDesign";

describe("formatCompositionDesign", () => {
  it("formats brief metadata labels", () => {
    expect(
      formatCompositionBriefMeta({
        mode: "hf_native",
        authorPrompt: "居中字卡",
        layoutAnchor: "center",
        templatePreference: "benefit-card",
      }),
    ).toEqual(["HF 全屏生成", "主信息居中", "benefit-card 模板"]);
  });

  it("detects design section visibility", () => {
    expect(
      hasCompositionDesignContent({
        brief: { mode: "hf_native", authorPrompt: "居中卖点卡" },
      }),
    ).toBe(true);
    expect(
      hasCompositionDesignContent({
        finishIntent: "强化对比条",
      }),
    ).toBe(true);
    expect(hasCompositionDesignContent({})).toBe(false);
  });

  it("maps unknown mode to raw value", () => {
    expect(compositionModeLabel("custom_mode")).toBe("custom_mode");
  });
});
