import { describe, expect, it } from "vitest";

import {
  formatStructureQualityWarnings,
  hasCriticalStructureQualityWarnings,
  parseStructureQualityWarning,
} from "@/lib/structureQualityWarningLabels";

describe("structureQualityWarningLabels", () => {
  it("maps common warnings to Chinese messages", () => {
    expect(parseStructureQualityWarning("narrative_summary_repeats_segments").message).toContain(
      "全片摘要",
    );
    expect(parseStructureQualityWarning("critical: slot_roles_uniform:usage_scene").message).toContain(
      "使用场景",
    );
    expect(parseStructureQualityWarning("critical: slot_roles_uniform:usage_scene").severity).toBe(
      "critical",
    );
  });

  it("hides analysis route info from quality panel", () => {
    const visible = formatStructureQualityWarnings([
      "analysis_route:direct_multimodal",
      "narrative_summary_repeats_segments",
    ]);
    expect(visible).toHaveLength(1);
    expect(visible[0]?.code).toBe("narrative_summary_repeats_segments");
  });

  it("detects critical warnings for promote gate messaging", () => {
    expect(
      hasCriticalStructureQualityWarnings([
        "warn: narrative_summary_repeats_segments",
        "critical: slot_roles_uniform:usage_scene",
      ]),
    ).toBe(true);
  });
});
